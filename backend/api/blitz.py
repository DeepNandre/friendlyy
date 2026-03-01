"""
Blitz-specific API endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Response

from core import settings
from services.blitz import get_session_state
from services.twilio_caller import generate_twiml
from services.elevenlabs_voice import generate_tts_audio, generate_call_script_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get current session state."""
    session = await get_session_state(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.id,
        "status": session.status.value,
        "businesses": [b.model_dump() for b in session.businesses],
        "calls": [
            {
                "business": c.business.name,
                "status": c.status.value,
                "result": c.result,
            }
            for c in session.calls
        ],
        "summary": session.summary,
    }


@router.post("/twiml/{session_id}/{call_id}")
async def get_twiml(session_id: str, call_id: str):
    """
    Serve TwiML for a specific call.
    Called by Twilio when the call connects.
    """
    session = await get_session_state(session_id)
    if not session:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    # Find the call
    call = None
    for c in session.calls:
        if c.id == call_id:
            call = c
            break

    if not call:
        logger.error(f"Call not found: {call_id}")
        raise HTTPException(status_code=404, detail="Call not found")

    # Generate script text
    script_text = generate_call_script_text(
        service_type=session.parsed_params.service or "service",
        timeframe=session.parsed_params.timeframe,
        question="availability and call-out fee",
    )

    # Check if ElevenLabs audio exists
    use_elevenlabs = bool(settings.elevenlabs_api_key)

    # Generate TwiML
    twiml = generate_twiml(
        script_text=script_text,
        session_id=session_id,
        call_id=call_id,
        use_elevenlabs=use_elevenlabs,
    )

    return Response(content=twiml, media_type="application/xml")


@router.get("/tts-audio/{session_id}/{call_id}")
async def get_tts_audio(session_id: str, call_id: str):
    """
    Serve pre-generated TTS audio for a call.
    Called by Twilio <Play> verb.
    """
    session = await get_session_state(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Generate script text
    script_text = generate_call_script_text(
        service_type=session.parsed_params.service or "service",
        timeframe=session.parsed_params.timeframe,
        question="availability and call-out fee",
    )

    # Generate or get cached audio
    audio = await generate_tts_audio(script_text)

    if not audio:
        raise HTTPException(
            status_code=500,
            detail="TTS generation failed",
        )

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "public, max-age=3600",
        },
    )
