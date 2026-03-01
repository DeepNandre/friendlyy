"""
Shared HTTP client singleton.
Provides connection pooling and consistent configuration across all services.
"""

import httpx
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

# Singleton client instance
_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """
    Get the shared httpx AsyncClient.
    Creates a new client if one doesn't exist.
    """
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
        )
    return _client


async def close_http_client() -> None:
    """Close the shared HTTP client."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


@asynccontextmanager
async def http_client_lifespan() -> AsyncGenerator[None, None]:
    """
    Context manager for HTTP client lifecycle.
    Use with FastAPI lifespan.
    """
    yield
    await close_http_client()
