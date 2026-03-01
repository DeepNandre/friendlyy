"""
Tests for the inbox agent service.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from services.inbox_agent import (
    run_inbox_workflow,
    _summarize_emails,
    _fallback_summary,
    _get_cached_summary,
    _cache_summary,
    INBOX_CACHE_TTL,
)
from models import RouterParams, InboxSummary, InboxPhase


# ==================== _fallback_summary ====================


class TestFallbackSummary:
    """Test count-based fallback summary."""

    def test_with_emails(self):
        emails = [
            {"from": "alice@example.com", "subject": "Hi", "snippet": "...", "is_unread": True},
            {"from": "bob@example.com", "subject": "Bye", "snippet": "...", "is_unread": False},
            {"from": "carol@example.com", "subject": "Re: Hi", "snippet": "...", "is_unread": True},
        ]
        result = _fallback_summary(emails)

        assert result.important_count == 2  # 2 unread
        assert result.needs_action is True
        assert any("3 emails" in u for u in result.top_updates)
        assert any("alice@example.com" in u for u in result.top_updates)

    def test_with_zero_emails(self):
        result = _fallback_summary([])

        assert result.important_count == 0
        assert result.needs_action is False
        assert any("0 emails" in u for u in result.top_updates)

    def test_all_read(self):
        emails = [
            {"from": "alice@example.com", "subject": "Hi", "snippet": "...", "is_unread": False},
        ]
        result = _fallback_summary(emails)

        assert result.important_count == 0
        assert result.needs_action is False


# ==================== _summarize_emails ====================


class TestSummarizeEmails:
    """Test Mistral-based email summarization."""

    @pytest.mark.asyncio
    async def test_empty_inbox_returns_clear_summary(self):
        """Zero emails returns 'inbox is clear' without calling Mistral."""
        result = await _summarize_emails([])

        assert result.important_count == 0
        assert result.needs_action is False
        assert any("clear" in u.lower() for u in result.top_updates)

    @pytest.mark.asyncio
    async def test_happy_path_mistral_summary(self):
        """Successful Mistral call returns structured InboxSummary."""
        summary_json = {
            "important_count": 3,
            "top_updates": [
                "Meeting at 3pm with product team",
                "AWS bill is due tomorrow",
                "PR #42 approved and ready to merge",
            ],
            "needs_action": True,
            "draft_replies_available": False,
            "sender_highlights": ["Product Team", "AWS Billing"],
        }

        # Patch call_mistral directly to avoid module-level settings singleton issue
        with patch(
            "services.inbox_agent.call_mistral",
            AsyncMock(return_value=summary_json),
        ):
            emails = [
                {"from": "team@company.com", "subject": "Meeting at 3pm", "snippet": "Let's discuss...", "is_unread": True, "labels": []},
                {"from": "billing@aws.com", "subject": "AWS Bill Due", "snippet": "Your bill...", "is_unread": True, "labels": []},
                {"from": "github@github.com", "subject": "PR #42 approved", "snippet": "Ready to merge", "is_unread": True, "labels": []},
            ]

            result = await _summarize_emails(emails)

        assert result.important_count == 3
        assert result.needs_action is True
        assert len(result.top_updates) == 3
        assert "Product Team" in result.sender_highlights

    @pytest.mark.asyncio
    async def test_mistral_failure_uses_fallback(self):
        """When Mistral API fails, falls back to count-based summary."""
        with patch(
            "services.inbox_agent.call_mistral",
            AsyncMock(side_effect=Exception("API error")),
        ):
            emails = [
                {"from": "alice@example.com", "subject": "Hi", "snippet": "...", "is_unread": True, "labels": []},
            ]

            result = await _summarize_emails(emails)

        assert result.important_count == 1  # fallback counts unread
        assert result.needs_action is True

    @pytest.mark.asyncio
    async def test_malformed_json_uses_fallback(self):
        """When Mistral returns non-JSON string, falls back to count-based summary."""
        # When parse_json=True fails, call_mistral returns raw string
        with patch(
            "services.inbox_agent.call_mistral",
            AsyncMock(return_value="Here's your summary:\n- email 1\n- email 2"),
        ):
            emails = [
                {"from": "alice@example.com", "subject": "Hi", "snippet": "...", "is_unread": True, "labels": []},
                {"from": "bob@example.com", "subject": "Bye", "snippet": "...", "is_unread": False, "labels": []},
            ]

            result = await _summarize_emails(emails)

        assert result.important_count == 1  # fallback counts unread
        assert any("2 emails" in u for u in result.top_updates)


# ==================== run_inbox_workflow ====================


class TestRunInboxWorkflow:
    """Test the full inbox check workflow."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_composio_and_mistral(self):
        """When cache has a valid summary, skip all API calls."""
        cached = InboxSummary(
            important_count=2,
            top_updates=["Cached update 1", "Cached update 2"],
            needs_action=True,
        )

        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached.model_dump()))

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
        ):
            result = await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="test-session",
                entity_id="test-entity",
            )

        assert result["status"] == "complete"
        assert result["summary"]["important_count"] == 2

        # Should emit start + complete only, no fetching/summarizing
        event_types = [e["event"] for e in events]
        assert event_types == ["inbox_start", "inbox_complete"]

    @pytest.mark.asyncio
    async def test_auth_required_when_not_connected(self):
        """Gmail not connected → emit auth_required with auth URL."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
            patch(
                "services.inbox_agent._check_gmail_connection",
                AsyncMock(return_value=(False, "https://composio.dev/auth/gmail?entity=test")),
            ),
        ):
            result = await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="test-session",
                entity_id="test-entity",
            )

        assert result["status"] == "auth_required"
        assert "composio.dev" in result["auth_url"]

        event_types = [e["event"] for e in events]
        assert "inbox_auth_required" in event_types
        # No fetching or summarizing events
        assert "inbox_fetching" not in event_types
        assert "inbox_summarizing" not in event_types

    @pytest.mark.asyncio
    async def test_happy_path_connected(self):
        """Full flow: connected Gmail → fetch → summarize → cache → complete."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        emails = [
            {"from": "alice@co.com", "subject": "Hi", "snippet": "Hello", "is_unread": True, "labels": []},
        ]

        summary = InboxSummary(
            important_count=1,
            top_updates=["Alice sent you a message"],
            needs_action=True,
            sender_highlights=["Alice"],
        )

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
            patch(
                "services.inbox_agent._check_gmail_connection",
                AsyncMock(return_value=(True, None)),
            ),
            patch("services.inbox_agent._fetch_emails", AsyncMock(return_value=emails)),
            patch("services.inbox_agent._summarize_emails", AsyncMock(return_value=summary)),
        ):
            result = await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="test-session",
                entity_id="test-entity",
            )

        assert result["status"] == "complete"
        assert result["summary"]["important_count"] == 1

        # Full event sequence
        event_types = [e["event"] for e in events]
        assert event_types == [
            "inbox_start",
            "inbox_fetching",
            "inbox_summarizing",
            "inbox_complete",
        ]

        # Verify cache was written
        mock_redis.setex.assert_called_once()
        cache_args = mock_redis.setex.call_args
        assert cache_args[0][0] == "inbox_cache:test-entity"
        assert cache_args[0][1] == INBOX_CACHE_TTL

    @pytest.mark.asyncio
    async def test_zero_emails_graceful(self):
        """Connected but empty inbox → graceful 'inbox is clear' summary."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        clear_summary = InboxSummary(
            important_count=0,
            top_updates=["Your inbox is clear — nothing important in the last 24 hours!"],
            needs_action=False,
        )

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
            patch("services.inbox_agent._check_gmail_connection", AsyncMock(return_value=(True, None))),
            patch("services.inbox_agent._fetch_emails", AsyncMock(return_value=[])),
            patch("services.inbox_agent._summarize_emails", AsyncMock(return_value=clear_summary)),
        ):
            result = await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="test-session",
                entity_id="test-entity",
            )

        assert result["status"] == "complete"
        assert result["summary"]["important_count"] == 0
        assert result["summary"]["needs_action"] is False

    @pytest.mark.asyncio
    async def test_composio_error_emits_inbox_error(self):
        """Composio SDK error → inbox_error event, no crash."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
            patch(
                "services.inbox_agent._check_gmail_connection",
                AsyncMock(side_effect=ValueError("COMPOSIO_API_KEY not configured")),
            ),
        ):
            result = await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="test-session",
                entity_id="test-entity",
            )

        assert result["status"] == "error"
        assert "COMPOSIO_API_KEY" in result["error"]

        event_types = [e["event"] for e in events]
        assert "inbox_error" in event_types

    @pytest.mark.asyncio
    async def test_fetch_error_emits_inbox_error(self):
        """Email fetch failure → inbox_error event."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
            patch("services.inbox_agent._check_gmail_connection", AsyncMock(return_value=(True, None))),
            patch("services.inbox_agent._fetch_emails", AsyncMock(side_effect=RuntimeError("Gmail API timeout"))),
        ):
            result = await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="test-session",
                entity_id="test-entity",
            )

        assert result["status"] == "error"
        assert "Gmail API timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_session_id_passed_through(self):
        """Session ID is used consistently in events."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"session_id": session_id, "event": event_type})

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with (
            patch("services.inbox_agent.emit_event", side_effect=mock_emit),
            patch("services.inbox_agent.save_session", AsyncMock()),
            patch("services.inbox_agent.get_redis_client", return_value=mock_redis),
            patch("services.inbox_agent._check_gmail_connection", AsyncMock(return_value=(True, None))),
            patch("services.inbox_agent._fetch_emails", AsyncMock(return_value=[])),
            patch("services.inbox_agent._summarize_emails", AsyncMock(return_value=InboxSummary())),
        ):
            await run_inbox_workflow(
                user_message="check my email",
                params=RouterParams(),
                session_id="my-unique-session-42",
                entity_id="test-entity",
            )

        for event in events:
            assert event["session_id"] == "my-unique-session-42"
