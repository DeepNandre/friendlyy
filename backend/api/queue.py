"""
Queue agent API routes.

Handles:
- TwiML webhooks for IVR navigation and hold loop
- Twilio status callbacks
- Queue cancellation
- SSE streaming (uses same stream infrastructure as Blitz)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import Response

from services.queue_agent import (
    generate_queue_twiml_initial,
    generate_hold_loop_twiml,
    handle_ivr_speech,
    handle_human_check,
    handle_call_status,
    cancel_queue,
    get_queue_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/twiml/{session_id}")
async def queue_twiml(session_id: str):
    """
    Serve initial TwiML when Twilio connects the queue call.
    Starts listening for IVR menu options.
    """
    logger.info(f"Serving queue TwiML for session: {session_id}")
    twiml = generate_queue_twiml_initial(session_id)
    return Response(content=twiml, media_type="application/xml")


@router.post("/ivr-handler/{session_id}")
async def ivr_handler(
    session_id: str,
    SpeechResult: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
):
    """
    Handle IVR speech recognition results.
    Twilio calls this when <Gather> captures speech during the IVR phase.
    """
    transcript = SpeechResult or ""
    logger.info(f"IVR heard [{session_id}]: {transcript[:100]}")

    twiml = await handle_ivr_speech(session_id, transcript)
    return Response(content=twiml, media_type="application/xml")


@router.post("/hold-loop/{session_id}")
async def hold_loop(session_id: str):
    """
    Hold loop entry point.
    Called when the call enters hold phase (no IVR detected).
    """
    logger.info(f"Hold loop for session: {session_id}")
    twiml = generate_hold_loop_twiml(session_id)
    return Response(content=twiml, media_type="application/xml")


@router.post("/human-check/{session_id}")
async def human_check(
    session_id: str,
    SpeechResult: Optional[str] = Form(None),
):
    """
    Human detection check.
    Called when <Gather> captures speech during hold phase.
    Determines if it's a real human or just automated hold messages.
    """
    transcript = SpeechResult or ""
    logger.info(f"Human check [{session_id}]: {transcript[:100]}")

    twiml = await handle_human_check(session_id, transcript)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status-callback")
async def status_callback(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    session_id: str = Query(None),
):
    """
    Twilio call status webhook for queue calls.
    """
    logger.info(f"Queue status callback: {CallSid} -> {CallStatus}")

    if not session_id:
        params = dict(request.query_params)
        session_id = params.get("session_id")

    if session_id:
        status_str = CallStatus.lower() if isinstance(CallStatus, str) else str(CallStatus)
        await handle_call_status(session_id, status_str)

    return {"status": "ok"}


@router.post("/cancel/{session_id}")
async def cancel(session_id: str):
    """
    Cancel a queue wait.
    User wants to stop waiting on hold.
    """
    logger.info(f"Cancelling queue: {session_id}")
    success = await cancel_queue(session_id)
    if success:
        return {"status": "cancelled", "message": "Queue cancelled. Call has been hung up."}
    return {"status": "not_found", "message": "Queue session not found."}


@router.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """Get current queue session status."""
    session = await get_queue_session(session_id)
    if not session:
        return {"status": "not_found"}

    return {
        "session_id": session.id,
        "phase": session.phase.value,
        "business": session.business_name,
        "phone": session.phone_number,
        "hold_elapsed": session.hold_elapsed_seconds,
        "human_detected": session.human_detected,
        "error": session.error,
    }
