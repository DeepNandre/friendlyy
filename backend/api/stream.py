"""
Server-Sent Events (SSE) endpoint for real-time call updates.
"""

import logging

from fastapi import APIRouter, Request

from core.sse import create_sse_stream, format_sse
from services.blitz import get_session_state

logger = logging.getLogger(__name__)

router = APIRouter()

BLITZ_TERMINAL_EVENTS = ["session_complete", "error"]


@router.get("/stream/{session_id}")
async def stream_session_updates(session_id: str, request: Request):
    """
    SSE endpoint for real-time call status updates.

    Events emitted:
    - session_start: Initial session state
    - status: Session status change (searching, calling)
    - call_started: A call has been initiated
    - call_connected: Call was answered
    - call_result: Call completed with result
    - call_failed: Call failed
    - session_complete: All calls done, final summary
    - error: Something went wrong
    - keepalive: Sent every 30s to keep connection alive
    """
    # Build initial session_start event if session exists
    initial_data = None
    session = await get_session_state(session_id)
    if session:
        initial_data = format_sse(
            "session_start",
            {
                "session_id": session_id,
                "status": session.status.value,
                "businesses": [b.model_dump() for b in session.businesses],
            },
        )

    return create_sse_stream(
        session_id=session_id,
        request=request,
        terminal_events=BLITZ_TERMINAL_EVENTS,
        error_event="error",
        initial_data=initial_data,
    )
