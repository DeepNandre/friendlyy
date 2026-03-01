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
from api import chat_router, blitz_router, build_router, stream_router, webhooks_router, queue_router, traces_router
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
    logger.info(f"CORS origins: {settings.cors_origins_list}")

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
