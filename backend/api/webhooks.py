"""
Twilio webhook handlers for call status updates.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Form, Query, Request

from core.redis_client import get_session, save_session
from models import CallStatus, SessionStatus
from services.blitz import emit_event, get_session_state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def twilio_status_callback(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
):
    """
    Handle Twilio call status webhooks.

    Twilio sends updates as the call progresses:
    - initiated
    - ringing
    - in-progress (answered)
    - completed
    - busy
    - no-answer
    - failed
    """
    logger.info(f"Twilio webhook: {CallSid} -> {CallStatus}")

    # Extract session_id from query params if present
    # (We include it in the callback URL)
    params = dict(request.query_params)
    session_id = params.get("session_id")
    call_id = params.get("call_id")

    if not session_id:
        logger.warning(f"No session_id in webhook for call {CallSid}")
        return {"status": "ok"}

    # Get session
    session = await get_session_state(session_id)
    if not session:
        logger.warning(f"Session not found: {session_id}")
        return {"status": "ok"}

    # Find and update call record
    call_record = None
    for call in session.calls:
        if call.call_sid == CallSid or call.id == call_id:
            call_record = call
            break

    if not call_record:
        logger.warning(f"Call record not found for SID: {CallSid}")
        return {"status": "ok"}

    # Map Twilio status to our status
    status_map = {
        "initiated": CallStatus.PENDING,
        "ringing": CallStatus.RINGING,
        "in-progress": CallStatus.CONNECTED,
        "answered": CallStatus.CONNECTED,
        "completed": CallStatus.COMPLETE,
        "busy": CallStatus.BUSY,
        "no-answer": CallStatus.NO_ANSWER,
        "failed": CallStatus.FAILED,
        "canceled": CallStatus.FAILED,
    }

    twilio_status = CallStatus.lower() if isinstance(CallStatus, str) else CallStatus
    # Note: shadowing the import name, so using the form value directly
    status_str = request._form.get("CallStatus", "").lower()
    new_status = status_map.get(status_str, CallStatus.FAILED)
    call_record.status = new_status

    # Emit appropriate event
    if new_status == CallStatus.RINGING:
        await emit_event(
            session_id,
            "call_started",
            {
                "business": call_record.business.name,
                "phone": call_record.business.phone,
                "status": "ringing",
            },
        )
    elif new_status == CallStatus.CONNECTED:
        await emit_event(
            session_id,
            "call_connected",
            {
                "business": call_record.business.name,
                "status": "connected",
            },
        )
    elif new_status in [CallStatus.BUSY, CallStatus.NO_ANSWER, CallStatus.FAILED]:
        error_messages = {
            CallStatus.BUSY: "Line busy",
            CallStatus.NO_ANSWER: "No answer",
            CallStatus.FAILED: "Call failed",
        }
        await emit_event(
            session_id,
            "call_failed",
            {
                "business": call_record.business.name,
                "error": error_messages.get(new_status, "Failed"),
            },
        )

    # Save updated session
    await save_session(session_id, session.model_dump(mode="json"))

    return {"status": "ok"}


@router.post("/recording")
async def twilio_recording_callback(
    request: Request,
    RecordingSid: str = Form(None),
    RecordingUrl: str = Form(None),
    RecordingStatus: str = Form(None),
    CallSid: str = Form(None),
):
    """
    Handle Twilio recording status callbacks.
    """
    logger.info(f"Recording callback: {RecordingSid} -> {RecordingStatus}")

    params = dict(request.query_params)
    session_id = params.get("session_id")
    call_id = params.get("call_id")

    if not session_id or not RecordingUrl:
        return {"status": "ok"}

    # Get session
    session = await get_session_state(session_id)
    if not session:
        return {"status": "ok"}

    # Find call record
    for call in session.calls:
        if call.call_sid == CallSid or call.id == call_id:
            call.recording_url = RecordingUrl
            break

    # Save updated session
    await save_session(session_id, session.model_dump(mode="json"))

    return {"status": "ok"}


@router.post("/recording-complete")
async def recording_complete(
    request: Request,
    RecordingUrl: str = Form(None),
    RecordingDuration: str = Form(None),
    session_id: str = Query(None),
    call_id: str = Query(None),
):
    """
    Handle recording completion - extract result from recording.
    """
    logger.info(f"Recording complete for session {session_id}, call {call_id}")

    if not session_id or not call_id:
        return {"status": "ok"}

    # Get session
    session = await get_session_state(session_id)
    if not session:
        return {"status": "ok"}

    # Find call record
    call_record = None
    for call in session.calls:
        if call.id == call_id:
            call_record = call
            break

    if not call_record:
        return {"status": "ok"}

    # Save recording URL
    call_record.recording_url = RecordingUrl

    # For now, set a placeholder result
    # In production, you'd transcribe and analyze the recording
    if RecordingUrl:
        call_record.result = "Response recorded - processing..."
        call_record.status = CallStatus.COMPLETE

        await emit_event(
            session_id,
            "call_result",
            {
                "business": call_record.business.name,
                "status": "complete",
                "result": call_record.result,
            },
        )

    # Save updated session
    await save_session(session_id, session.model_dump(mode="json"))

    return {"status": "ok"}
