"""
Build agent API routes - SSE streaming and preview serving.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from core.redis_client import get_redis_client
from core.sse import create_sse_stream

logger = logging.getLogger(__name__)

router = APIRouter()

BUILD_TERMINAL_EVENTS = ["build_complete", "build_error", "build_clarification"]


@router.get("/stream/{session_id}")
async def stream_build_updates(session_id: str, request: Request):
    """
    SSE endpoint for real-time build progress updates.

    Events emitted:
    - build_started: Build has begun, includes step list
    - build_progress: A step completed / next step started
    - build_complete: Build finished with preview URL
    - build_error: Something went wrong
    - build_clarification: Need more info from user
    """
    return create_sse_stream(
        session_id=session_id,
        request=request,
        terminal_events=BUILD_TERMINAL_EVENTS,
        error_event="build_error",
    )


@router.get("/preview/{preview_id}")
async def serve_preview(preview_id: str):
    """Serve a generated website preview from Redis."""
    redis = await get_redis_client()
    html = await redis.get(f"build:preview:{preview_id}")

    if not html:
        return HTMLResponse(
            content="<html><body><h1>Preview expired</h1><p>This preview is no longer available. Please generate a new one.</p></body></html>",
            status_code=404,
        )

    return HTMLResponse(
        content=html,
        headers={
            "Content-Security-Policy": "script-src 'none'; object-src 'none'",
        },
    )
