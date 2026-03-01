"""
Inbox agent API routes — SSE streaming and Gmail auth callback.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from core.sse import create_sse_stream

logger = logging.getLogger(__name__)

router = APIRouter()

INBOX_TERMINAL_EVENTS = ["inbox_complete", "inbox_error", "inbox_auth_required"]


@router.get("/stream/{session_id}")
async def stream_inbox_updates(session_id: str, request: Request):
    """
    SSE endpoint for real-time inbox check updates.

    Events:
    - inbox_start: Checking Gmail connection
    - inbox_auth_required: Need authorization (includes auth URL) — terminal
    - inbox_fetching: Fetching emails
    - inbox_summarizing: Processing with Mistral
    - inbox_complete: Final summary — terminal
    - inbox_error: Something went wrong — terminal
    """
    return create_sse_stream(
        session_id=session_id,
        request=request,
        terminal_events=INBOX_TERMINAL_EVENTS,
        error_event="inbox_error",
    )


@router.get("/auth-callback")
async def gmail_auth_callback(request: Request):
    """
    OAuth callback from Composio after user authorizes Gmail.

    Composio handles the token exchange automatically.
    This endpoint redirects the user back to the chat.
    """
    return HTMLResponse(
        content="""
        <html>
        <head><title>Gmail Connected</title></head>
        <body style="font-family: Inter, system-ui, sans-serif; display: flex;
                      justify-content: center; align-items: center;
                      height: 100vh; margin: 0; background: #fafaf5;">
            <div style="text-align: center;">
                <h2 style="margin-bottom: 8px;">Gmail Connected!</h2>
                <p style="color: #666;">You can close this window and ask Friendly to check your inbox again.</p>
                <script>
                    if (window.opener) {
                        window.opener.postMessage({ type: 'gmail_connected' }, '*');
                        setTimeout(function() { window.close(); }, 2000);
                    }
                </script>
            </div>
        </body>
        </html>
        """,
        status_code=200,
    )
