"""
Shared SSE (Server-Sent Events) utilities.

Provides a reusable event emitter and stream generator so each agent
doesn't duplicate the Redis queue -> SSE plumbing.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

from core.redis_client import pop_event, push_event

logger = logging.getLogger(__name__)


async def emit_event(session_id: str, event_type: str, data: dict) -> None:
    """Push an SSE event to a session's Redis queue."""
    await push_event(
        session_id,
        {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def format_sse(event_type: str, data: dict) -> str:
    """Format data as an SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


def create_sse_stream(
    session_id: str,
    request: Request,
    terminal_events: List[str],
    error_event: str = "error",
    initial_data: Optional[str] = None,
) -> StreamingResponse:
    """
    Create a StreamingResponse that consumes events from a Redis queue.

    Args:
        session_id: Redis queue key suffix (events:{session_id})
        request: FastAPI request (for disconnect detection)
        terminal_events: Event types that end the stream
        error_event: Event type name to emit on unexpected errors
        initial_data: Optional SSE string to yield before the queue loop
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        if initial_data:
            yield initial_data

        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected from stream: {session_id}")
                break

            try:
                event = await pop_event(session_id, timeout=30)

                if event:
                    event_type = event.get("event", "message")
                    event_data = event.get("data", {})
                    yield format_sse(event_type, event_data)

                    if event_type in terminal_events:
                        logger.info(
                            f"Stream ended for {session_id}: {event_type}"
                        )
                        break
                else:
                    yield ": keepalive\n\n"

            except asyncio.CancelledError:
                logger.info(f"Stream cancelled for {session_id}")
                break
            except Exception as e:
                logger.error(f"Stream error for {session_id}: {e}")
                yield format_sse(error_event, {"message": str(e)})
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
