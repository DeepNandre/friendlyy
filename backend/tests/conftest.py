"""
Pytest configuration and fixtures.
"""

import asyncio
import pytest
import respx
from httpx import Response

from core.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-places-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-elevenlabs-key")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15005550006")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")
    monkeypatch.setenv("DEMO_MODE", "false")

    # Clear cached settings and rebuild with test env vars
    from core.config import get_settings
    get_settings.cache_clear()
    fresh_settings = get_settings()

    # Patch the module-level settings reference in core.mistral
    # (it imports settings at module load time, so env changes alone don't reach it)
    monkeypatch.setattr("core.mistral.settings", fresh_settings)

    yield

    get_settings.cache_clear()


@pytest.fixture
def mock_nvidia_api():
    """Mock NVIDIA NIM API responses."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def mock_places_api():
    """Mock Google Places API responses."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def mock_elevenlabs_api():
    """Mock ElevenLabs API responses."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock


# Sample API responses for mocking

NVIDIA_ROUTER_RESPONSE_BLITZ = {
    "choices": [
        {
            "message": {
                "content": '{"agent": "blitz", "params": {"service": "plumber", "timeframe": "tomorrow"}, "confidence": 0.95}'
            }
        }
    ]
}

NVIDIA_ROUTER_RESPONSE_CHAT = {
    "choices": [
        {
            "message": {
                "content": '{"agent": "chat", "params": {"type": "greeting"}, "confidence": 1.0}'
            }
        }
    ]
}

NVIDIA_ROUTER_RESPONSE_INBOX = {
    "choices": [
        {
            "message": {
                "content": '{"agent": "inbox", "params": {"action": "check"}, "confidence": 0.95}'
            }
        }
    ]
}

NVIDIA_INBOX_SUMMARY_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": '{"important_count": 3, "top_updates": ["Meeting at 3pm", "AWS bill due", "PR approved"], "needs_action": true, "draft_replies_available": false, "sender_highlights": ["Product Team", "AWS"]}'
            }
        }
    ]
}

PLACES_SEARCH_RESPONSE = {
    "results": [
        {"place_id": "place1", "name": "Test Plumber 1"},
        {"place_id": "place2", "name": "Test Plumber 2"},
    ]
}

PLACES_DETAILS_RESPONSE = {
    "result": {
        "name": "Test Plumber 1",
        "international_phone_number": "+441234567890",
        "formatted_address": "123 Test St, London",
        "rating": 4.5,
    }
}
