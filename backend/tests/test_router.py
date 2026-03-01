"""
Tests for the router service.
"""

import pytest
import respx
from httpx import Response

from models import AgentType
from services.router import classify_intent, _parse_router_response


class TestRouterClassification:
    """Test intent classification."""

    @pytest.mark.asyncio
    async def test_classify_blitz_intent(self, mock_settings, mock_nvidia_api):
        """Test classification of blitz intent (find services)."""
        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"agent": "blitz", "params": {"service": "plumber", "timeframe": "tomorrow"}, "confidence": 0.95}'
                            }
                        }
                    ]
                },
            )
        )

        result = await classify_intent("find me a plumber who can come tomorrow")

        assert result.agent == AgentType.BLITZ
        assert result.params.service == "plumber"
        assert result.params.timeframe == "tomorrow"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_classify_bounce_intent(self, mock_settings, mock_nvidia_api):
        """Test classification of bounce intent (cancel subscriptions)."""
        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"agent": "bounce", "params": {"service": "Netflix", "action": "cancel"}, "confidence": 0.98}'
                            }
                        }
                    ]
                },
            )
        )

        result = await classify_intent("cancel my Netflix subscription")

        assert result.agent == AgentType.BOUNCE
        assert result.params.service == "Netflix"
        assert result.confidence == 0.98

    @pytest.mark.asyncio
    async def test_classify_chat_greeting(self, mock_settings, mock_nvidia_api):
        """Test classification of general chat/greeting."""
        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"agent": "chat", "params": {"type": "greeting"}, "confidence": 1.0}'
                            }
                        }
                    ]
                },
            )
        )

        result = await classify_intent("hello")

        assert result.agent == AgentType.CHAT
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self, mock_settings, mock_nvidia_api):
        """Test fallback to chat on API error."""
        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "Internal error"})
        )

        result = await classify_intent("find me a plumber")

        assert result.agent == AgentType.CHAT
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_fallback_on_no_api_key(self, monkeypatch):
        """Test fallback to chat when no API key."""
        monkeypatch.setenv("NVIDIA_API_KEY", "")
        from core.config import get_settings
        get_settings.cache_clear()

        result = await classify_intent("find me a plumber")

        assert result.agent == AgentType.CHAT
        assert result.confidence == 0.5


class TestRouterResponseParsing:
    """Test JSON response parsing."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        content = '{"agent": "blitz", "params": {"service": "electrician"}, "confidence": 0.9}'
        result = _parse_router_response(content)

        assert result.agent == AgentType.BLITZ
        assert result.params.service == "electrician"
        assert result.confidence == 0.9

    def test_parse_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        content = '```json\n{"agent": "blitz", "params": {"service": "plumber"}, "confidence": 0.95}\n```'
        result = _parse_router_response(content)

        assert result.agent == AgentType.BLITZ
        assert result.params.service == "plumber"

    def test_parse_invalid_json_fallback(self):
        """Test fallback on invalid JSON."""
        content = "This is not valid JSON"
        result = _parse_router_response(content)

        assert result.agent == AgentType.CHAT
        assert result.confidence == 0.5

    def test_parse_invalid_agent_fallback(self):
        """Test fallback on invalid agent type."""
        content = '{"agent": "invalid_agent", "params": {}, "confidence": 0.9}'
        result = _parse_router_response(content)

        assert result.agent == AgentType.CHAT

    def test_confidence_clamping(self):
        """Test confidence is clamped to [0, 1]."""
        content = '{"agent": "blitz", "params": {}, "confidence": 1.5}'
        result = _parse_router_response(content)

        assert result.confidence == 1.0

        content = '{"agent": "blitz", "params": {}, "confidence": -0.5}'
        result = _parse_router_response(content)

        assert result.confidence == 0.0
