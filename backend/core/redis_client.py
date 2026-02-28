"""
Redis client for session storage and caching.
Provides connection pooling and consistent configuration.
"""

import json
import hashlib
from typing import Optional, Any
from datetime import timedelta
import redis.asyncio as redis
from .config import settings

# Singleton client instance
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Get the shared Redis client.
    Creates a new client if one doesn't exist.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close the Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# Session storage helpers

async def save_session(session_id: str, data: dict, ttl_seconds: int = 3600) -> None:
    """Save a session to Redis with TTL."""
    client = await get_redis_client()
    await client.setex(
        f"session:{session_id}",
        ttl_seconds,
        json.dumps(data, default=str),
    )


async def get_session(session_id: str) -> Optional[dict]:
    """Get a session from Redis."""
    client = await get_redis_client()
    data = await client.get(f"session:{session_id}")
    if data:
        return json.loads(data)
    return None


async def delete_session(session_id: str) -> None:
    """Delete a session from Redis."""
    client = await get_redis_client()
    await client.delete(f"session:{session_id}")


async def update_session(session_id: str, updates: dict) -> None:
    """Update specific fields in a session."""
    session = await get_session(session_id)
    if session:
        session.update(updates)
        await save_session(session_id, session)


# Cache helpers for TTS audio

def get_cache_key(text: str) -> str:
    """Generate a consistent cache key from text using MD5 hash."""
    return f"tts:{hashlib.md5(text.encode()).hexdigest()}"


async def get_cached_audio(text: str) -> Optional[bytes]:
    """Get cached TTS audio for text."""
    client = await get_redis_client()
    key = get_cache_key(text)
    data = await client.get(key)
    if data:
        # Data is stored as base64 string
        import base64
        return base64.b64decode(data)
    return None


async def cache_audio(text: str, audio: bytes, ttl_seconds: int = 86400) -> None:
    """Cache TTS audio for text (24 hour TTL by default)."""
    client = await get_redis_client()
    key = get_cache_key(text)
    import base64
    await client.setex(key, ttl_seconds, base64.b64encode(audio).decode())


# SSE event queue helpers

async def push_event(session_id: str, event: dict) -> None:
    """Push an event to a session's event queue."""
    client = await get_redis_client()
    await client.rpush(
        f"events:{session_id}",
        json.dumps(event, default=str),
    )
    # Set TTL on the queue
    await client.expire(f"events:{session_id}", 3600)


async def pop_event(session_id: str, timeout: int = 30) -> Optional[dict]:
    """Pop an event from a session's event queue (blocking)."""
    client = await get_redis_client()
    result = await client.blpop(f"events:{session_id}", timeout=timeout)
    if result:
        _, data = result
        return json.loads(data)
    return None


async def clear_events(session_id: str) -> None:
    """Clear all events for a session."""
    client = await get_redis_client()
    await client.delete(f"events:{session_id}")
