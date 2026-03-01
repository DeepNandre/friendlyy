"""
Friendly API - Blitz Phone Calling Agent

Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from core import settings
from core.http_client import http_client_lifespan, close_http_client
from core.redis_client import close_redis_client
from api import chat_router, blitz_router, build_router, stream_router, webhooks_router, queue_router, traces_router, inbox_router
from services.weave_tracing import load_traces_from_redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Handles startup and shutdown.
    """
    # Startup
    logger.info("Starting Friendly API...")
    logger.info(f"Demo mode: {settings.demo_mode}")
    logger.info(f"BACKEND_URL: {settings.backend_url}")
    logger.info(f"CORS origins: {settings.cors_origins_list}")
    logger.info(f"Twilio configured: {bool(settings.twilio_account_sid)}")
    logger.info(f"ElevenLabs configured: {bool(settings.elevenlabs_api_key)}")
    logger.info(f"Google Places configured: {bool(settings.google_places_api_key)}")
    logger.info(f"Composio configured: {bool(settings.composio_api_key)}")

    # Initialize W&B Weave if configured
    if settings.wandb_api_key:
        try:
            import weave
            weave.init(settings.weave_project)
            logger.info(f"W&B Weave initialized: {settings.weave_project}")
            logger.info("Weave tracing active on all agent services")
        except Exception as e:
            logger.warning(f"Failed to initialize Weave: {e}")
    else:
        logger.info("W&B Weave not configured (WANDB_API_KEY not set)")
        logger.info("Traces will be stored locally and in Redis")

    # Hydrate in-memory trace store from Redis
    await load_traces_from_redis()

    yield

    # Shutdown
    logger.info("Shutting down Friendly API...")
    await close_http_client()
    await close_redis_client()


# Create FastAPI app
app = FastAPI(
    title="Friendly API",
    description="AI Phone Calling Agent - Makes real calls to get quotes and information",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limiting is applied via decorators on individual endpoints
# See api/chat.py for @limiter.limit() usage


# Include routers
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(blitz_router, prefix="/api/blitz", tags=["blitz"])
app.include_router(stream_router, prefix="/api/blitz", tags=["stream"])
app.include_router(webhooks_router, prefix="/api/blitz", tags=["webhooks"])
app.include_router(build_router, prefix="/api/build", tags=["build"])
app.include_router(queue_router, prefix="/api/queue", tags=["queue"])
app.include_router(inbox_router, prefix="/api/inbox", tags=["inbox"])
app.include_router(traces_router, prefix="/api", tags=["traces"])


@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": "Friendly API",
        "description": "AI Phone Calling Agent",
        "version": "1.0.0",
        "demo_mode": settings.demo_mode,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/debug/config")
async def debug_config():
    """Debug endpoint - show current configuration (no secrets)."""
    return {
        "demo_mode": settings.demo_mode,
        "backend_url": settings.backend_url,
        "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "twilio_phone": settings.twilio_phone_number[:6] + "***" if settings.twilio_phone_number else None,
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        "elevenlabs_key_prefix": settings.elevenlabs_api_key[:8] + "..." if settings.elevenlabs_api_key else None,
        "google_places_configured": bool(settings.google_places_api_key),
        "redis_url": settings.redis_url.split("@")[-1] if "@" in settings.redis_url else "localhost",
    }


@app.get("/debug/places")
async def debug_places(query: str, location: str):
    """Debug endpoint - test places search directly."""
    from services.places import search_businesses
    businesses = await search_businesses(query=query, location=location, max_results=3)
    return {
        "query": query,
        "location": location,
        "results": [b.model_dump() for b in businesses],
    }


@app.get("/debug/call")
async def debug_call(phone: str):
    """Debug endpoint - make a test call to verify Twilio works."""
    from twilio.rest import Client
    from twilio.twiml.voice_response import VoiceResponse

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return {"error": "Twilio not configured"}

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    # Create simple TwiML that just says hello
    twiml_url = f"{settings.backend_url}/debug/twiml"

    try:
        call = client.calls.create(
            to=phone,
            from_=settings.twilio_phone_number,
            url=twiml_url,
            status_callback=f"{settings.backend_url}/debug/call-status",
            timeout=30,
        )
        return {
            "success": True,
            "call_sid": call.sid,
            "to": phone,
            "from": settings.twilio_phone_number,
            "twiml_url": twiml_url,
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/debug/twiml")
@app.get("/debug/twiml")
async def debug_twiml():
    """Simple TwiML for test calls - uses ElevenLabs."""
    from twilio.twiml.voice_response import VoiceResponse
    from fastapi.responses import Response

    response = VoiceResponse()
    # Use ElevenLabs audio instead of robotic Twilio TTS
    response.play(f"{settings.backend_url}/debug/tts")
    response.hangup()

    return Response(content=str(response), media_type="application/xml")


@app.get("/debug/tts")
async def debug_tts():
    """Generate ElevenLabs audio for test call - with full error details."""
    from fastapi.responses import Response, JSONResponse
    from core import get_http_client

    text = "Hello! This is a test call from Friendly."

    # Call ElevenLabs API directly to get full error
    try:
        client = await get_http_client()

        voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "output_format": "mp3_22050_32",
        }

        logger.info(f"[DEBUG TTS] Calling ElevenLabs: {url}")
        response = await client.post(url, headers=headers, json=payload, timeout=30.0)

        if response.status_code != 200:
            error_detail = response.text[:1000]
            logger.error(f"[DEBUG TTS] ElevenLabs error {response.status_code}: {error_detail}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "ElevenLabs API error",
                    "status_code": response.status_code,
                    "detail": error_detail,
                    "api_key_prefix": settings.elevenlabs_api_key[:10] + "..." if settings.elevenlabs_api_key else None,
                },
            )

        audio_data = response.content
        logger.info(f"[DEBUG TTS] Success! {len(audio_data)} bytes")

        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Content-Length": str(len(audio_data))},
        )

    except Exception as e:
        logger.error(f"[DEBUG TTS] Exception: {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": type(e).__name__,
            },
        )


@app.post("/debug/call-status")
async def debug_call_status(request: Request):
    """Log call status for debugging."""
    form = await request.form()
    logger.info(f"[DEBUG CALL STATUS] {dict(form)}")
    return {"status": "ok"}


@app.get("/api")
async def api_root():
    """API root - list available endpoints."""
    return {
        "endpoints": {
            "POST /api/chat": "Send a message to the agent",
            "GET /api/blitz/stream/{session_id}": "Stream real-time call updates",
            "GET /api/blitz/session/{session_id}": "Get session status",
            "GET /api/build/stream/{session_id}": "Stream real-time build updates",
            "GET /api/build/preview/{preview_id}": "View generated website preview",
            "GET /api/inbox/stream/{session_id}": "Stream real-time inbox check updates",
            "GET /api/queue/session/{session_id}": "Get queue session status",
            "POST /api/queue/cancel/{session_id}": "Cancel a queue hold wait",
            "GET /api/traces": "Traces dashboard (performance, improvement, recent)",
            "GET /api/traces/performance": "Aggregate performance metrics",
            "GET /api/traces/improvement": "Self-improvement data over time",
            "GET /api/traces/recent": "Recent traces (filterable by operation)",
            "GET /api/traces/blitz": "Blitz-specific traces and insights",
        },
        "documentation": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
