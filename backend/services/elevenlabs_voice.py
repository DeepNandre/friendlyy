"""
ElevenLabs TTS integration with Redis caching.
Generates AI voice for phone calls.
"""

import logging
import hashlib
from typing import Optional

from core import get_http_client, settings
from core.redis_client import get_cached_audio, cache_audio
from services.weave_tracing import traced, log_tts_generation, get_trace_ctx

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

# Voice IDs - Rachel is a professional female voice
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel

VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}


def _log_tts(*, result, duration, error, args, kwargs, ctx):
    """Log callback for generate_tts_audio."""
    text = args[0] if args else kwargs.get("text", "")
    log_tts_generation(
        text_length=len(text),
        duration=duration,
        cache_hit=ctx.get("cache_hit", False),
        success=result is not None,
        error=error,
    )


@traced("generate_tts_audio", log_fn=_log_tts)
async def generate_tts_audio(
    text: str,
    voice_id: Optional[str] = None,
    use_cache: bool = True,
) -> Optional[bytes]:
    """
    Generate speech audio from text using ElevenLabs.

    Uses Redis caching to save API credits.
    Falls back to None if API fails (caller should use Twilio TTS).

    Args:
        text: Text to convert to speech
        voice_id: ElevenLabs voice ID (default: Rachel)
        use_cache: Whether to use Redis cache

    Returns:
        Audio bytes (MP3) or None if failed
    """
    voice_id = voice_id or DEFAULT_VOICE_ID

    # Check cache first
    if use_cache:
        cached = await get_cached_audio(text)
        if cached:
            logger.info(f"TTS cache hit for text: {text[:30]}...")
            get_trace_ctx()["cache_hit"] = True
            return cached

    # Check for API key
    if not settings.elevenlabs_api_key:
        logger.warning("ELEVENLABS_API_KEY not set")
        return None

    try:
        client = await get_http_client()
        response = await client.post(
            f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": VOICE_SETTINGS,
            },
        )

        response.raise_for_status()
        audio_data = response.content

        # Cache the audio
        if use_cache:
            await cache_audio(text, audio_data)
            logger.info(f"TTS cached for text: {text[:30]}...")

        return audio_data

    except Exception as e:
        logger.error(f"ElevenLabs TTS failed: {e}")
        return None


def generate_call_script_text(
    service_type: str,
    timeframe: Optional[str] = None,
    question: str = "availability and call-out fee",
) -> str:
    """
    Generate the text the AI will speak on a call.

    Args:
        service_type: Type of service (plumber, electrician, etc.)
        timeframe: When service is needed (today, tomorrow, etc.)
        question: What to ask about

    Returns:
        Script text for TTS
    """
    timeframe_text = timeframe or "soon"

    script = f"""Hello! I'm an AI assistant calling on behalf of a customer.
They're looking for a {service_type} and would like to know about your {question}.
They need someone who can come {timeframe_text}.
Could you let me know your availability and pricing?
Please speak clearly after the beep."""

    return script


def get_character_count(text: str) -> int:
    """Get character count for credit estimation."""
    return len(text)


def estimate_credits_used(texts: list) -> int:
    """Estimate total ElevenLabs credits that would be used."""
    return sum(get_character_count(t) for t in texts)
