"""
Tests for failure mode handling.
Ensures graceful degradation when external services fail.
"""

import pytest
import respx
from httpx import Response

from models import AgentType, CallStatus
from services.router import classify_intent
from services.places import search_businesses
from services.elevenlabs_voice import generate_tts_audio


class TestNVIDIAFailures:
    """Test handling of NVIDIA API failures."""

    @pytest.mark.asyncio
    async def test_fallback_on_500_error(self, mock_settings, mock_nvidia_api):
        """Test fallback to chat on 500 error."""
        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(return_value=Response(500, json={"error": "Internal error"}))

        result = await classify_intent("find me a plumber")

        assert result.agent == AgentType.CHAT
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, mock_settings, mock_nvidia_api):
        """Test fallback on request timeout."""
        import httpx

        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(side_effect=httpx.TimeoutException("Timeout"))

        result = await classify_intent("find me a plumber")

        assert result.agent == AgentType.CHAT
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_fallback_on_malformed_response(self, mock_settings, mock_nvidia_api):
        """Test fallback on malformed JSON response."""
        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(
            return_value=Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "This is not JSON at all"}}
                    ]
                },
            )
        )

        result = await classify_intent("find me a plumber")

        assert result.agent == AgentType.CHAT


class TestGooglePlacesFailures:
    """Test handling of Google Places API failures."""

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self, mock_settings, mock_places_api):
        """Test fallback to hardcoded businesses on API error."""
        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
        ).mock(return_value=Response(500, json={"error": "Server error"}))

        businesses = await search_businesses("plumber", "London")

        # Should return fallback businesses
        assert len(businesses) >= 1
        assert all(b.phone is not None for b in businesses)

    @pytest.mark.asyncio
    async def test_fallback_on_empty_results(self, mock_settings, mock_places_api):
        """Test fallback when no results found."""
        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
        ).mock(return_value=Response(200, json={"results": []}))

        businesses = await search_businesses("plumber", "London")

        # Should return fallback businesses
        assert len(businesses) >= 1

    @pytest.mark.asyncio
    async def test_fallback_on_no_phone_numbers(self, mock_settings, mock_places_api):
        """Test fallback when places have no phone numbers."""
        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
        ).mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {"place_id": "place1", "name": "No Phone Business"}
                    ]
                },
            )
        )

        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/details/json"
        ).mock(
            return_value=Response(
                200,
                json={
                    "result": {
                        "name": "No Phone Business",
                        # No phone number
                        "formatted_address": "123 Test St",
                    }
                },
            )
        )

        businesses = await search_businesses("plumber", "London")

        # Should return fallback businesses since none have phones
        assert len(businesses) >= 1
        assert all(b.phone is not None for b in businesses)


class TestElevenLabsFailures:
    """Test handling of ElevenLabs API failures."""

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self, mock_settings, mock_elevenlabs_api):
        """Test returns None on API error (allows Twilio TTS fallback)."""
        mock_elevenlabs_api.post(
            "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        ).mock(return_value=Response(500, json={"error": "Server error"}))

        audio = await generate_tts_audio("Test message")

        # Should return None, allowing caller to fall back to Twilio TTS
        assert audio is None

    @pytest.mark.asyncio
    async def test_returns_none_on_rate_limit(self, mock_settings, mock_elevenlabs_api):
        """Test returns None on rate limit."""
        mock_elevenlabs_api.post(
            "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        ).mock(
            return_value=Response(
                429, json={"detail": "Rate limit exceeded"}
            )
        )

        audio = await generate_tts_audio("Test message")

        assert audio is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_api_key(self, monkeypatch):
        """Test returns None when no API key configured."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "")
        from core.config import get_settings
        get_settings.cache_clear()

        audio = await generate_tts_audio("Test message")

        assert audio is None


class TestAllCallsFailure:
    """Test handling when all calls fail."""

    def test_summary_indicates_all_failed(self):
        """Test summary message when all calls fail."""
        from services.blitz import _generate_summary
        from models import BlitzSession, CallRecord, Business

        session = BlitzSession(
            user_message="find me a plumber",
            parsed_params={"service": "plumber"},
        )

        # Add failed calls
        for i in range(3):
            business = Business(id=f"b{i}", name=f"Business {i}", phone="+44123")
            call = CallRecord(business=business, status=CallStatus.FAILED)
            session.calls.append(call)

        summary = _generate_summary(session)

        assert "couldn't get through" in summary.lower() or "try different" in summary.lower()
