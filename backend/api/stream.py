"""
Server-Sent Events (SSE) endpoint for real-time call updates.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.redis_client import pop_event, get_session
from services.blitz import get_session_state

logger = logging.getLogger(__name__)

router = APIRouter()


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

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from Redis queue."""

        # Send initial session state
        session = await get_session_state(session_id)
        if session:
            yield _format_sse(
                "session_start",
                {
                    "session_id": session_id,
                    "status": session.status.value,
                    "businesses": [b.model_dump() for b in session.businesses],
                },
            )

        # Stream events from Redis
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                logger.info(f"Client disconnected from stream: {session_id}")
                break

            try:
                # Pop event from Redis queue (blocking with timeout)
                event = await pop_event(session_id, timeout=30)

                if event:
                    event_type = event.get("event", "message")
                    event_data = event.get("data", {})

                    yield _format_sse(event_type, event_data)

                    # Check for terminal events
                    if event_type in ["session_complete", "error"]:
                        logger.info(
                            f"Stream ended for session {session_id}: {event_type}"
                        )
                        break
                else:
                    # No event received, send keepalive
                    yield ": keepalive\n\n"

            except asyncio.CancelledError:
                logger.info(f"Stream cancelled for session {session_id}")
                break
            except Exception as e:
                logger.error(f"Stream error for session {session_id}: {e}")
                yield _format_sse("error", {"message": str(e)})
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",
        },
    )


def _format_sse(event_type: str, data: dict) -> str:
    """Format data as SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
