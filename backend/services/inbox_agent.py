"""
Inbox agent — checks Gmail via Composio and summarizes with Mistral.

Flow:
1. Check Redis cache for recent summary (5-min TTL)
2. Check if Gmail is connected via Composio entity
3. If not connected, emit auth URL for the user to authorize
4. If connected, fetch emails (newer_than:1d, important/unread/primary)
5. Summarize with Mistral via call_mistral()
6. Cache result and emit structured InboxSummary via SSE
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.config import get_settings
from core.mistral import call_mistral, MistralError
from core.redis_client import save_session, get_session, get_redis_client
from core.sse import emit_event
from models.inbox import InboxPhase, InboxSession, InboxSummary

logger = logging.getLogger(__name__)

# Cache TTL for inbox summaries (5 minutes)
INBOX_CACHE_TTL = 300

INBOX_SUMMARY_PROMPT = """You are Friendly's inbox assistant. The user asked you to check their email.

You will receive raw email data. Produce a JSON summary with these fields:
{
  "important_count": <number of important/actionable emails>,
  "top_updates": [<list of 3-7 short bullet strings summarizing the most important emails>],
  "needs_action": <true if any email requires a response or action>,
  "draft_replies_available": false,
  "sender_highlights": [<list of notable senders, e.g. "Your manager Alex", "Amazon shipping">]
}

Rules:
- Each bullet in top_updates should be one concise sentence (under 80 chars)
- Focus on what matters: urgent, from people (not spam), requires action
- Ignore newsletters, promotions, and automated notifications unless they seem important
- Be warm and conversational in the bullet text
- Output ONLY valid JSON, no markdown or explanation"""


async def _get_cached_summary(entity_id: str) -> Optional[InboxSummary]:
    """Check Redis for a cached inbox summary (5-min TTL)."""
    try:
        client = await get_redis_client()
        data = await client.get(f"inbox_cache:{entity_id}")
        if data:
            return InboxSummary.model_validate(json.loads(data))
    except Exception as e:
        logger.debug(f"Cache miss for inbox:{entity_id}: {e}")
    return None


async def _cache_summary(entity_id: str, summary: InboxSummary) -> None:
    """Store inbox summary in Redis with 5-min TTL."""
    try:
        client = await get_redis_client()
        await client.setex(
            f"inbox_cache:{entity_id}",
            INBOX_CACHE_TTL,
            json.dumps(summary.model_dump()),
        )
    except Exception as e:
        logger.warning(f"Failed to cache inbox summary: {e}")


def _get_composio_toolset():
    """Initialize Composio toolset with API key from settings."""
    from composio import ComposioToolSet

    settings = get_settings()
    if not settings.composio_api_key:
        raise ValueError("COMPOSIO_API_KEY not configured")

    return ComposioToolSet(api_key=settings.composio_api_key)


async def _check_gmail_connection(entity_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if Gmail is connected for the given Composio entity.

    Returns (is_connected, auth_url_if_not_connected).
    Composio SDK is synchronous, so we run it in a thread.
    """
    def _sync_check():
        toolset = _get_composio_toolset()
        entity = toolset.get_entity(id=entity_id)

        try:
            connection = entity.get_connection(app="gmail")
            if connection and connection.status == "ACTIVE":
                return True, None
        except Exception:
            pass

        settings = get_settings()
        auth_response = entity.initiate_connection(
            app_name="gmail",
            redirect_url=f"{settings.backend_url}/api/inbox/auth-callback",
        )
        return False, auth_response.redirectUrl

    return await asyncio.to_thread(_sync_check)


async def _fetch_emails(entity_id: str) -> List[Dict[str, Any]]:
    """
    Fetch recent important/unread emails via Composio Gmail tools.

    Uses GMAIL_FETCH_EMAILS with query:
    newer_than:1d (is:important OR is:unread OR category:primary)
    """
    def _sync_fetch():
        toolset = _get_composio_toolset()
        entity = toolset.get_entity(id=entity_id)

        result = entity.execute_action(
            action="GMAIL_FETCH_EMAILS",
            params={
                "query": "newer_than:1d (is:important OR is:unread OR category:primary)",
                "max_results": 20,
            },
        )

        emails = result.get("data", {}).get("messages", [])

        # Normalize — Composio response shapes can vary
        normalized = []
        for email in emails:
            normalized.append({
                "subject": email.get("subject", email.get("Subject", "(no subject)")),
                "from": email.get("sender", email.get("from", email.get("From", "Unknown"))),
                "snippet": email.get("snippet", email.get("body_preview", ""))[:200],
                "date": email.get("date", email.get("internalDate", "")),
                "is_unread": email.get("is_unread", True),
                "labels": email.get("labels", []),
            })

        return normalized

    return await asyncio.to_thread(_sync_fetch)


async def _summarize_emails(emails: List[Dict[str, Any]]) -> InboxSummary:
    """Summarize emails into structured InboxSummary using Mistral."""
    if not emails:
        return InboxSummary(
            important_count=0,
            top_updates=["Your inbox is clear — nothing important in the last 24 hours!"],
            needs_action=False,
        )

    # Build context for Mistral (limit to 15 emails to fit context window)
    email_parts = []
    for i, email in enumerate(emails[:15], 1):
        email_parts.append(
            f"{i}. From: {email['from']}\n"
            f"   Subject: {email['subject']}\n"
            f"   Preview: {email['snippet'][:150]}\n"
            f"   Unread: {email['is_unread']}"
        )

    email_context = "\n\n".join(email_parts)

    try:
        parsed = await call_mistral(
            messages=[
                {"role": "system", "content": INBOX_SUMMARY_PROMPT},
                {"role": "user", "content": f"Here are my recent emails:\n\n{email_context}"},
            ],
            temperature=0.3,
            max_tokens=800,
            parse_json=True,
        )

        if isinstance(parsed, dict):
            return InboxSummary(**parsed)

        # parse_json returned raw string (JSON parsing failed) — use fallback
        logger.warning("Mistral returned non-JSON for inbox summary, using fallback")
        return _fallback_summary(emails)

    except Exception as e:
        logger.error(f"Email summarization failed: {e}")
        return _fallback_summary(emails)


def _fallback_summary(emails: List[Dict[str, Any]]) -> InboxSummary:
    """Simple count-based summary when Mistral is unavailable."""
    unread_count = sum(1 for e in emails if e.get("is_unread"))
    updates = [f"You have {len(emails)} emails in the last 24 hours ({unread_count} unread)"]
    if emails:
        updates.append(f"Latest from: {emails[0]['from']}")

    return InboxSummary(
        important_count=unread_count,
        top_updates=updates,
        needs_action=unread_count > 0,
    )


async def run_inbox_workflow(
    user_message: str,
    params: Any,
    session_id: str,
    entity_id: str = "default",
) -> dict:
    """
    Run the full inbox check workflow.

    1. Check cache → return immediately if hit
    2. Check Composio Gmail connection
    3. If not connected → emit auth_required with auth URL
    4. If connected → fetch emails → summarize → cache → emit complete
    """
    session = InboxSession(
        id=session_id,
        user_message=user_message,
        entity_id=entity_id,
        phase=InboxPhase.CHECKING_CONNECTION,
    )
    await save_session(f"inbox:{session_id}", session.to_dict())

    # Step 0: Check cache
    cached = await _get_cached_summary(entity_id)
    if cached:
        logger.info(f"Inbox cache hit for entity {entity_id}")
        await emit_event(session_id, "inbox_start", {"message": "Checking your inbox..."})
        session.phase = InboxPhase.COMPLETE
        session.summary = cached
        session.completed_at = datetime.utcnow()
        await save_session(f"inbox:{session_id}", session.to_dict())
        await emit_event(session_id, "inbox_complete", {
            "message": "Here's your inbox summary!",
            "summary": cached.model_dump(),
        })
        return {"session_id": session_id, "status": "complete", "summary": cached.model_dump()}

    # Step 1: Emit start
    await emit_event(session_id, "inbox_start", {"message": "Checking your Gmail connection..."})

    try:
        # Step 2: Check connection
        is_connected, auth_url = await _check_gmail_connection(entity_id)

        if not is_connected:
            session.phase = InboxPhase.AUTH_REQUIRED
            session.auth_url = auth_url
            await save_session(f"inbox:{session_id}", session.to_dict())
            await emit_event(session_id, "inbox_auth_required", {
                "message": "I need to connect to your Gmail first. Click the link below to authorize:",
                "auth_url": auth_url,
            })
            return {"session_id": session_id, "status": "auth_required", "auth_url": auth_url}

        # Step 3: Fetch emails
        session.phase = InboxPhase.FETCHING
        await save_session(f"inbox:{session_id}", session.to_dict())
        await emit_event(session_id, "inbox_fetching", {
            "message": "Connected! Fetching your recent emails...",
        })

        emails = await _fetch_emails(entity_id)
        session.email_count = len(emails)
        await save_session(f"inbox:{session_id}", session.to_dict())

        # Step 4: Summarize
        session.phase = InboxPhase.SUMMARIZING
        await save_session(f"inbox:{session_id}", session.to_dict())
        await emit_event(session_id, "inbox_summarizing", {
            "message": f"Found {len(emails)} emails. Summarizing what's important...",
            "email_count": len(emails),
        })

        summary = await _summarize_emails(emails)

        # Step 5: Complete + cache
        session.phase = InboxPhase.COMPLETE
        session.summary = summary
        session.completed_at = datetime.utcnow()
        await save_session(f"inbox:{session_id}", session.to_dict())
        await _cache_summary(entity_id, summary)

        await emit_event(session_id, "inbox_complete", {
            "message": "Here's your inbox summary!",
            "summary": summary.model_dump(),
        })
        return {"session_id": session_id, "status": "complete", "summary": summary.model_dump()}

    except Exception as e:
        logger.error(f"Inbox workflow error: {e}")
        session.phase = InboxPhase.ERROR
        session.error = str(e)
        await save_session(f"inbox:{session_id}", session.to_dict())
        await emit_event(session_id, "inbox_error", {
            "message": "Something went wrong checking your inbox. Want me to try again?",
            "error": str(e),
        })
        return {"session_id": session_id, "status": "error", "error": str(e)}
