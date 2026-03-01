"""
Call Friend API endpoints.

Handles TwiML, webhooks, media streams, and SSE for the call friend feature.
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Form, Query, Request, Response, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.config import settings
from core.redis_client import get_session, save_session, push_event
from core.sse import create_sse_stream, format_sse
from core.events import emit_event
from models import CallFriendPhase, CallFriendSession
from services.call_friend_agent import (
    get_call_friend_session,
    save_call_friend_session,
    generate_call_friend_twiml,
    generate_call_friend_prompt,
)
from services.elevenlabs_conversation import (
    create_conversation_session,
    close_conversation_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()

CALL_FRIEND_TERMINAL_EVENTS = ["session_complete", "error"]


# ==================== SSE Stream ====================


@router.get("/stream/{session_id}")
async def stream_call_friend_updates(session_id: str, request: Request):
    """
    SSE endpoint for real-time call friend updates.

    Events emitted:
    - status: Call status change (initiating, ringing, connected)
    - call_started: Call has been initiated
    - call_connected: Friend answered
    - transcript: Live conversation transcript
    - session_complete: Call finished with summary
    - error: Something went wrong
    """
    # Build initial event if session exists
    initial_data = None
    session = await get_call_friend_session(session_id)
    if session:
        initial_data = format_sse(
            "session_start",
            {
                "session_id": session_id,
                "phase": session.phase.value,
                "friend_name": session.friend_name,
                "question": session.question,
            },
        )

    return create_sse_stream(
        session_id=session_id,
        request=request,
        terminal_events=CALL_FRIEND_TERMINAL_EVENTS,
        error_event="error",
        initial_data=initial_data,
    )


# ==================== TwiML ====================


@router.post("/twiml/{session_id}")
@router.get("/twiml/{session_id}")
async def get_twiml(session_id: str):
    """
    Serve TwiML for the call friend conversation.
    Called by Twilio when the call connects.
    """
    session = await get_call_friend_session(session_id)
    if not session:
        logger.error(f"Session not found: {session_id}")
        # Return a fallback TwiML that apologizes and hangs up
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say("Sorry, something went wrong. Please try again.", voice="Polly.Amy")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    twiml = generate_call_friend_twiml(session)
    logger.info(f"TwiML generated for call friend session {session_id}")

    return Response(content=twiml, media_type="application/xml")


# ==================== Media Stream WebSocket ====================


@router.websocket("/media-stream/{session_id}")
async def call_friend_media_stream(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for Twilio Media Streams.
    Bridges audio to ElevenLabs Conversational AI for real-time conversation.
    """
    await websocket.accept()
    logger.info(f"[Call Friend Media Stream] WebSocket connected: {session_id}")

    # Get session to build prompts
    session = await get_call_friend_session(session_id)
    if not session:
        logger.error(f"[Call Friend Media Stream] Session not found: {session_id}")
        await websocket.close()
        return

    # Generate conversation prompts
    system_prompt, first_message = generate_call_friend_prompt(session)

    # Get ElevenLabs agent ID
    agent_id = settings.elevenlabs_agent_id if hasattr(settings, 'elevenlabs_agent_id') else None

    if not agent_id:
        logger.warning("[Call Friend Media Stream] ELEVENLABS_AGENT_ID not configured")
        await push_event(
            session_id,
            {
                "event": "transcript",
                "data": {
                    "speaker": "system",
                    "text": "Live conversation mode not configured. Please set ELEVENLABS_AGENT_ID.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        await websocket.close()
        return

    # Create ElevenLabs conversation session
    conversation = await create_conversation_session(
        session_id=session_id,
        call_id=session_id,  # Use session_id as call_id for simplicity
        agent_id=agent_id,
        system_prompt=system_prompt,
        first_message=first_message,
    )

    if not conversation:
        logger.error("[Call Friend Media Stream] Failed to create conversation session")
        await websocket.close()
        return

    stream_sid = None

    async def send_audio_to_twilio(audio_data: bytes):
        """Send audio from ElevenLabs back to Twilio."""
        if websocket.client_state != WebSocketState.CONNECTED:
            return

        if not stream_sid:
            return

        media_message = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(audio_data).decode("utf-8"),
            },
        }

        try:
            await websocket.send_json(media_message)
        except Exception as e:
            logger.warning(f"[Call Friend Media Stream] Failed to send audio: {e}")

    # Start listening to ElevenLabs in background
    elevenlabs_task = asyncio.create_task(
        conversation.listen_to_elevenlabs(send_audio_to_twilio)
    )

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")

            if event == "start":
                stream_sid = message.get("start", {}).get("streamSid")
                logger.info(f"[Call Friend Media Stream] Stream started: {stream_sid}")

                # Update session phase
                session.phase = CallFriendPhase.CONNECTED
                await save_call_friend_session(session)

                await push_event(
                    session_id,
                    {
                        "event": "call_connected",
                        "data": {
                            "phase": "connected",
                            "message": f"{session.friend_name} answered! AI is now speaking...",
                            "friend_name": session.friend_name,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

                await push_event(
                    session_id,
                    {
                        "event": "transcript",
                        "data": {
                            "speaker": "system",
                            "text": f"Connected to {session.friend_name}. AI is introducing itself...",
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif event == "media":
                # Forward audio to ElevenLabs
                await conversation.handle_twilio_message(message)

            elif event == "stop":
                logger.info(f"[Call Friend Media Stream] Stream stopped: {stream_sid}")
                break

    except WebSocketDisconnect:
        logger.info(f"[Call Friend Media Stream] WebSocket disconnected: {session_id}")

    except Exception as e:
        logger.error(f"[Call Friend Media Stream] Error: {e}")

    finally:
        # Cleanup
        elevenlabs_task.cancel()
        try:
            await elevenlabs_task
        except asyncio.CancelledError:
            pass

        await close_conversation_session(session_id, session_id)

        # Update session with transcripts from conversation
        if conversation.transcripts:
            session = await get_call_friend_session(session_id)
            if session:
                session.transcript = conversation.transcripts
                session.phase = CallFriendPhase.COMPLETE
                session.completed_at = datetime.utcnow()

                # Extract friend's response from transcripts
                friend_responses = [
                    t.get("text", "") for t in conversation.transcripts
                    if t.get("role") == "human"
                ]
                if friend_responses:
                    session.response = " ".join(friend_responses)

                await save_call_friend_session(session)

        await push_event(
            session_id,
            {
                "event": "transcript",
                "data": {
                    "speaker": "system",
                    "text": "Call ended.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"[Call Friend Media Stream] Session cleanup complete: {session_id}")


# ==================== Webhooks ====================


@router.post("/webhook")
async def call_friend_status_callback(
    request: Request,
    CallSid: str = Form(...),
    call_status_value: str = Form(..., alias="CallStatus"),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
):
    """
    Handle Twilio call status webhooks for call friend.
    """
    logger.info(f"[Call Friend] Webhook: {CallSid} -> {call_status_value}")

    params = dict(request.query_params)
    session_id = params.get("session_id")

    if not session_id:
        logger.warning(f"No session_id in webhook for call {CallSid}")
        return {"status": "ok"}

    session = await get_call_friend_session(session_id)
    if not session:
        logger.warning(f"Session not found: {session_id}")
        return {"status": "ok"}

    status_lower = call_status_value.lower()

    # Map status to phase
    if status_lower == "ringing":
        session.phase = CallFriendPhase.RINGING
        await emit_event(
            session_id,
            "status",
            {
                "phase": "ringing",
                "message": f"Ringing {session.friend_name}...",
                "friend_name": session.friend_name,
            },
        )

    elif status_lower in ("in-progress", "answered"):
        session.phase = CallFriendPhase.CONNECTED
        await emit_event(
            session_id,
            "call_connected",
            {
                "phase": "connected",
                "message": f"{session.friend_name} answered!",
                "friend_name": session.friend_name,
            },
        )

    elif status_lower == "completed":
        if session.phase != CallFriendPhase.COMPLETE:
            session.phase = CallFriendPhase.COMPLETE
            session.completed_at = datetime.utcnow()

    elif status_lower in ("busy", "no-answer"):
        session.phase = CallFriendPhase.NO_ANSWER
        session.error = "No answer" if status_lower == "no-answer" else "Line busy"
        await emit_event(
            session_id,
            "error",
            {
                "phase": "no_answer",
                "message": f"{session.friend_name} didn't answer. They might be busy - try again later!",
                "friend_name": session.friend_name,
            },
        )

    elif status_lower in ("failed", "canceled"):
        session.phase = CallFriendPhase.FAILED
        session.error = "Call failed"
        await emit_event(
            session_id,
            "error",
            {
                "phase": "failed",
                "message": f"Couldn't connect to {session.friend_name}. Please check the number and try again.",
                "friend_name": session.friend_name,
            },
        )

    session.call_sid = CallSid
    await save_call_friend_session(session)

    return {"status": "ok"}


@router.post("/amd")
async def call_friend_amd_callback(
    request: Request,
    CallSid: str = Form(None),
    AnsweredBy: str = Form(None),
):
    """
    Handle Answering Machine Detection for call friend.
    If voicemail is detected, leave a message instead of hanging up.
    """
    params = dict(request.query_params)
    session_id = params.get("session_id")

    logger.info(f"[Call Friend] AMD callback: {CallSid} -> AnsweredBy={AnsweredBy}")

    if AnsweredBy and AnsweredBy in ("machine_start", "machine_end_beep", "machine_end_silence", "machine_end_other"):
        logger.info(f"Voicemail detected for call friend {CallSid}")

        # For call friend, we let the voicemail play out
        # The AI will leave a message naturally through the conversation
        if session_id:
            session = await get_call_friend_session(session_id)
            if session:
                await emit_event(
                    session_id,
                    "transcript",
                    {
                        "speaker": "system",
                        "text": f"Reached {session.friend_name}'s voicemail. Leaving a message...",
                    },
                )

    return {"status": "ok"}


@router.post("/recording")
async def call_friend_recording_callback(
    request: Request,
    RecordingSid: str = Form(None),
    RecordingUrl: str = Form(None),
    RecordingStatus: str = Form(None),
    CallSid: str = Form(None),
):
    """
    Handle recording status callback for call friend.
    """
    logger.info(f"[Call Friend] Recording callback: {RecordingSid} -> {RecordingStatus}")

    params = dict(request.query_params)
    session_id = params.get("session_id")

    if not session_id or not RecordingUrl:
        return {"status": "ok"}

    session = await get_call_friend_session(session_id)
    if not session:
        return {"status": "ok"}

    session.recording_url = RecordingUrl
    await save_call_friend_session(session)

    return {"status": "ok"}


# ==================== Session Info ====================


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get current call friend session state."""
    session = await get_call_friend_session(session_id)
    if not session:
        return {"error": "Session not found"}

    return {
        "session_id": session.id,
        "friend_name": session.friend_name,
        "phone_number": session.phone_number,
        "question": session.question,
        "phase": session.phase.value,
        "transcript": session.transcript,
        "response": session.response,
        "summary": session.summary,
        "error": session.error,
    }
