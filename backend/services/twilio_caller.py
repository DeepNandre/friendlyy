"""
Twilio phone call integration.
Makes real phone calls with AI voice.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from core import settings
from core.redis_client import save_session
from models import BlitzSession, CallRecord, CallScript, CallStatus

logger = logging.getLogger(__name__)

# Twilio client (lazy initialized)
_twilio_client: Optional[Client] = None

# Single source of truth for mapping Twilio status strings to internal CallStatus.
# Used by webhook handlers. Add new Twilio statuses here.
TWILIO_STATUS_MAP = {
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


def get_twilio_client() -> Optional[Client]:
    """Get or create Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        if settings.twilio_account_sid and settings.twilio_auth_token:
            _twilio_client = Client(
                settings.twilio_account_sid,
                settings.twilio_auth_token,
            )
    return _twilio_client


async def initiate_parallel_calls(
    session: BlitzSession,
    script: CallScript,
    emit_callback: callable,
) -> None:
    """
    Initiate calls to all businesses in parallel.

    Args:
        session: The Blitz session with businesses
        script: Call script with what to ask
        emit_callback: Async function to emit SSE events
    """
    # Generate script text once for all calls
    from services.elevenlabs_voice import generate_call_script_text

    script_text = generate_call_script_text(
        service_type=script.service_type,
        timeframe=script.timeframe,
        question=script.question,
    )

    # Create call tasks
    tasks = []
    for call_record in session.calls:
        tasks.append(
            _make_single_call(
                session_id=session.id,
                call_record=call_record,
                script_text=script_text,
                emit_callback=emit_callback,
            )
        )

    # Execute all calls in parallel
    await asyncio.gather(*tasks, return_exceptions=True)

    # Save once after all calls are created (or failed).
    # All coroutines share the same session object, so call_sid values
    # and failure statuses are already set in-memory by this point.
    await save_session(session.id, session.model_dump(mode="json"))


async def _make_single_call(
    session_id: str,
    call_record: CallRecord,
    script_text: str,
    emit_callback: callable,
) -> None:
    """
    Make a single phone call to a business.

    Updates call_record in-place. Does NOT save to Redis — the caller
    (initiate_parallel_calls) saves once after all calls complete to
    avoid race conditions between parallel coroutines.

    Args:
        session_id: Parent session ID
        call_record: Call record to update (mutated in-place)
        script_text: Script for the AI to speak
        emit_callback: Async function to emit SSE events
    """
    client = get_twilio_client()
    if not client:
        call_record.status = CallStatus.FAILED
        call_record.error = "Twilio not configured"
        await emit_callback(
            session_id,
            "call_failed",
            {
                "business": call_record.business.name,
                "error": "Twilio not configured",
            },
        )
        return

    try:
        # Update status to ringing
        call_record.status = CallStatus.RINGING
        call_record.started_at = datetime.utcnow()

        await emit_callback(
            session_id,
            "call_started",
            {
                "business": call_record.business.name,
                "phone": call_record.business.phone,
                "status": "ringing",
            },
        )

        # Create the call via Twilio
        call = client.calls.create(
            to=call_record.business.phone,
            from_=settings.twilio_phone_number,
            url=f"{settings.backend_url}/api/blitz/twiml/{session_id}/{call_record.id}",
            status_callback=f"{settings.backend_url}/api/blitz/webhook?session_id={session_id}&call_id={call_record.id}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            timeout=45,
            record=True,
            recording_status_callback=f"{settings.backend_url}/api/blitz/recording?session_id={session_id}&call_id={call_record.id}",
            machine_detection="Enable",
            async_amd=True,
            async_amd_status_callback=f"{settings.backend_url}/api/blitz/amd?session_id={session_id}&call_id={call_record.id}",
            async_amd_status_callback_method="POST",
        )

        call_record.call_sid = call.sid
        logger.info(f"Call initiated: {call.sid} to {call_record.business.name}")

    except Exception as e:
        logger.error(f"Call failed to {call_record.business.name}: {e}")
        call_record.status = CallStatus.FAILED
        call_record.error = str(e)

        await emit_callback(
            session_id,
            "call_failed",
            {
                "business": call_record.business.name,
                "error": str(e),
            },
        )


def generate_twiml(
    script_text: str,
    session_id: str,
    call_id: str,
    use_elevenlabs: bool = True,
) -> str:
    """
    Generate TwiML for a call.

    Single function per approved plan - handles both ElevenLabs and Twilio TTS.

    Args:
        script_text: What the AI should say
        session_id: Session ID for callbacks
        call_id: Call ID for callbacks
        use_elevenlabs: If True, use ElevenLabs TTS; else use Twilio's built-in

    Returns:
        TwiML XML string
    """
    response = VoiceResponse()

    if use_elevenlabs:
        # Play pre-generated ElevenLabs audio
        tts_url = f"{settings.backend_url}/api/blitz/tts-audio/{session_id}/{call_id}"
        response.play(tts_url)
    else:
        # Use Twilio's built-in TTS (fallback)
        response.say(script_text, voice="Polly.Amy", language="en-GB")

    # Pause before recording
    response.pause(length=1)

    # Record the response (max 30 seconds, 5 second silence timeout)
    response.record(
        max_length=30,
        timeout=5,  # 5 second silence detection per approved plan
        action=f"{settings.backend_url}/api/blitz/recording-complete?session_id={session_id}&call_id={call_id}",
        play_beep=True,
        trim="trim-silence",
    )

    # Thank them
    response.say("Thank you for your time. Goodbye!", voice="Polly.Amy", language="en-GB")

    return str(response)


