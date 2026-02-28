"""
Blitz agent orchestration.
Coordinates the find businesses → call → collect results workflow.
"""

import asyncio
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from core.redis_client import (
    save_session,
    get_session,
    delete_session,
    push_event,
    clear_events,
)
from models import (
    BlitzSession,
    CallRecord,
    CallScript,
    CallStatus,
    SessionStatus,
    RouterParams,
    Business,
)
from services.places import search_businesses
from services.twilio_caller import initiate_parallel_calls
from services.weave_tracing import (
    traced,
    log_blitz_call,
    log_blitz_session,
    get_performance_summary,
    get_trace_ctx,
)

logger = logging.getLogger(__name__)


async def emit_event(session_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Emit an SSE event for a session.

    Args:
        session_id: Session ID
        event_type: Event type (status, call_started, etc.)
        data: Event data
    """
    await push_event(
        session_id,
        {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def get_session_state(session_id: str) -> Optional[BlitzSession]:
    """
    Get current session state from Redis.

    Args:
        session_id: Session ID

    Returns:
        BlitzSession or None if not found
    """
    data = await get_session(session_id)
    if data:
        return BlitzSession.from_dict(data)
    return None


async def save_session_state(session: BlitzSession) -> None:
    """Save session state to Redis."""
    await save_session(session.id, session.to_dict())


def _log_blitz_workflow(*, result, duration, error, args, kwargs, ctx):
    """Log callback for run_blitz_workflow — handles session-level trace."""
    session = result
    service_type = ctx.get("service_type", "service")
    location = ctx.get("location", "London")
    session_id = ctx.get("session_id", "unknown")

    if error or not session:
        log_blitz_session(
            session_id=session_id,
            total_calls=0,
            successful_calls=0,
            total_duration=duration,
            service_type=service_type,
            location=location,
        )
        return

    successful = [
        c for c in session.calls if c.status == CallStatus.COMPLETE and c.result
    ]
    log_blitz_session(
        session_id=session.id,
        total_calls=len(session.calls),
        successful_calls=len(successful),
        total_duration=duration,
        service_type=service_type,
        location=location,
        best_quote=successful[0].result if successful else None,
    )


@traced("run_blitz_workflow", log_fn=_log_blitz_workflow)
async def run_blitz_workflow(
    user_message: str,
    params: RouterParams,
    location: Optional[Dict[str, float]] = None,
    session_id: str = None,
) -> BlitzSession:
    """
    Complete Blitz workflow:
    1. Search for businesses
    2. Initiate parallel calls
    3. Collect results
    4. Generate summary

    Args:
        user_message: Original user message
        params: Parsed router params
        location: Optional user location
        session_id: Existing session ID to use (optional)

    Returns:
        BlitzSession with results
    """
    # Store context for log_fn callback
    ctx = get_trace_ctx()
    ctx["service_type"] = params.service or "service"
    ctx["location"] = params.location or "London"

    # Self-improving: check past performance before starting
    try:
        perf = get_performance_summary()
        if perf.get("blitz_insights"):
            insights = perf["blitz_insights"]
            logger.info(
                f"[Self-Improve] Past performance: "
                f"{insights.get('total_calls', 0)} calls, "
                f"{insights.get('response_rate', 0)*100:.0f}% response rate, "
                f"{insights.get('quote_rate', 0)*100:.0f}% quote rate"
            )
    except Exception:
        pass

    # Create session with provided ID or generate new one
    session = BlitzSession(
        user_message=user_message,
        parsed_params=params,
        status=SessionStatus.SEARCHING,
    )

    # If session_id was provided, use it
    if session_id:
        session.id = session_id

    ctx["session_id"] = session.id
    await save_session_state(session)

    try:
        # Step 1: Search for businesses
        await emit_event(
            session.id,
            "status",
            {
                "status": "searching",
                "message": f"Finding {params.service or 'services'} near you...",
            },
        )

        location_str = params.location or "London"  # Default to London
        businesses = await search_businesses(
            query=params.service or "service",
            location=location_str,
            lat_lng=location,
            max_results=3,
        )

        # Filter to businesses with phone numbers
        businesses = [b for b in businesses if b.phone][:3]
        session.businesses = businesses

        if not businesses:
            session.status = SessionStatus.COMPLETE
            session.summary = f"Sorry, I couldn't find any {params.service or 'services'} with phone numbers in that area."
            await emit_event(
                session.id,
                "session_complete",
                {
                    "summary": session.summary,
                    "results": [],
                },
            )
            await save_session_state(session)
            return session

        # Step 2: Create call script
        script = CallScript(
            service_type=params.service or "service",
            timeframe=params.timeframe,
            question="availability and call-out fee",
            user_notes=params.notes,
        )

        # Step 3: Update status to calling
        session.status = SessionStatus.CALLING
        await emit_event(
            session.id,
            "status",
            {
                "status": "calling",
                "message": f"Calling {len(businesses)} businesses...",
                "businesses": [b.model_dump() for b in businesses],
            },
        )

        # Create call records
        session.calls = [
            CallRecord(business=b, status=CallStatus.PENDING)
            for b in businesses
        ]
        await save_session_state(session)

        # Step 4: Start calls in parallel
        await initiate_parallel_calls(session, script, emit_event)

        # Step 5: Wait for all calls to complete
        await _wait_for_calls_completion(session, timeout=120)

        # Step 6: Generate summary
        session.status = SessionStatus.COMPLETE
        session.completed_at = datetime.utcnow()
        session.summary = _generate_summary(session)

        await emit_event(
            session.id,
            "session_complete",
            {
                "summary": session.summary,
                "results": [
                    {
                        "business": c.business.name,
                        "status": c.status.value,
                        "result": c.result,
                    }
                    for c in session.calls
                ],
            },
        )

        await save_session_state(session)

        # Log each call outcome (per-call logging stays here — multiple traces per session)
        for call in session.calls:
            call_duration = 0.0
            if call.started_at and call.ended_at:
                call_duration = (call.ended_at - call.started_at).total_seconds()

            log_blitz_call(
                business_name=call.business.name,
                business_phone=call.business.phone,
                call_success=call.status == CallStatus.COMPLETE and call.result is not None,
                call_duration=call_duration,
                ivr_navigated=False,
                quote_received=_extract_quote(call.result) if call.result else None,
                business_responded=call.status == CallStatus.COMPLETE,
                result_text=call.result,
                error=call.error,
                session_id=session.id,
            )

        # Session-level log is handled by _log_blitz_workflow callback
        return session

    except Exception as e:
        logger.error(f"Blitz workflow error: {e}")
        session.status = SessionStatus.ERROR
        await emit_event(session.id, "error", {"message": str(e)})
        await save_session_state(session)
        # Session-level error log is handled by _log_blitz_workflow callback
        raise


def _extract_quote(result_text: str) -> Optional[float]:
    """Try to extract a numeric quote from result text.

    Requires a currency symbol (£ or $) to avoid false positives
    like matching plain numbers in "call 3 businesses".
    """
    if not result_text:
        return None
    match = re.search(r'[£$]\s*(\d+(?:\.\d{1,2})?)', result_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


async def _wait_for_calls_completion(
    session: BlitzSession, timeout: int = 120
) -> None:
    """
    Wait for all calls to complete with timeout.

    Polls session state from Redis every second.
    """
    start = datetime.utcnow()

    while True:
        # Refresh session from Redis
        current = await get_session_state(session.id)
        if current:
            session.calls = current.calls

        # Check if all calls are done
        all_done = all(
            c.status
            in [
                CallStatus.COMPLETE,
                CallStatus.NO_ANSWER,
                CallStatus.BUSY,
                CallStatus.FAILED,
            ]
            for c in session.calls
        )

        if all_done:
            break

        # Check timeout
        elapsed = (datetime.utcnow() - start).total_seconds()
        if elapsed > timeout:
            logger.warning(f"Session {session.id} timed out after {timeout}s")
            # Mark remaining calls as failed
            for call in session.calls:
                if call.status not in [
                    CallStatus.COMPLETE,
                    CallStatus.NO_ANSWER,
                    CallStatus.BUSY,
                    CallStatus.FAILED,
                ]:
                    call.status = CallStatus.FAILED
                    call.error = "Timeout"
            break

        await asyncio.sleep(1)


def _generate_summary(session: BlitzSession) -> str:
    """Generate human-readable summary of call results."""
    successful = [
        c for c in session.calls if c.status == CallStatus.COMPLETE and c.result
    ]

    if not successful:
        failed_count = len(session.calls)
        return f"I called {failed_count} {session.parsed_params.service or 'businesses'} but couldn't get through to any of them. Would you like me to try different ones?"

    results_text = "\n".join(
        [f"- {c.business.name}: {c.result}" for c in successful]
    )

    return f"Found {len(successful)} options for you:\n\n{results_text}"


async def cleanup_session(session_id: str) -> None:
    """
    Clean up session data from Redis.
    Called after session_complete or error.
    """
    await delete_session(session_id)
    await clear_events(session_id)
