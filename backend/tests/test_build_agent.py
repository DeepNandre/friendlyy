"""
Tests for the build agent service.
"""

import pytest
import respx
from httpx import Response
from unittest.mock import AsyncMock, patch, MagicMock

from services.build_agent import (
    _needs_clarification,
    _generate_site_html,
    _get_demo_html,
    run_build_workflow,
)
from models import RouterParams


# ==================== _needs_clarification ====================


class TestNeedsClarification:
    """Test vague input detection."""

    @pytest.mark.parametrize(
        "message",
        [
            "build something cool",
            "make something",
            "create something",
            "build me something",
            "whatever",
            "surprise me",
            "idk",
            "i don't know",
            "anything",
        ],
    )
    def test_vague_inputs_need_clarification(self, message):
        assert _needs_clarification(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "build me a landing page for my dog walking business",
            "create a portfolio website for photography",
            "make a restaurant menu page",
            "build a blog about cooking",
            "create a store for my handmade jewelry",
            "make me an app landing page",
        ],
    )
    def test_specific_inputs_dont_need_clarification(self, message):
        assert _needs_clarification(message) is False

    def test_case_insensitive(self):
        assert _needs_clarification("BUILD SOMETHING COOL") is True
        assert _needs_clarification("Build Me A Landing Page") is False

    def test_short_vague_input(self):
        """Short messages without site keywords need clarification."""
        assert _needs_clarification("hi") is True
        assert _needs_clarification("yo") is True
        assert _needs_clarification("build") is True

    def test_short_specific_input(self):
        """Short messages WITH site keywords don't need clarification."""
        assert _needs_clarification("landing page") is False
        assert _needs_clarification("portfolio website") is False

    def test_whitespace_handling(self):
        assert _needs_clarification("  build something cool  ") is True
        assert _needs_clarification("  landing page  ") is False


# ==================== _generate_site_html ====================


class TestGenerateSiteHtml:
    """Test LLM response parsing and code fence stripping."""

    @pytest.mark.asyncio
    async def test_raw_html_returned_as_is(self, mock_settings, mock_nvidia_api):
        """HTML without code fences is returned unchanged."""
        html = "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>"
        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(
            return_value=Response(
                200,
                json={"choices": [{"message": {"content": html}}]},
            )
        )

        result = await _generate_site_html("test description")
        assert result == html

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(self, mock_settings, mock_nvidia_api):
        """Code fences (```html ... ```) are stripped."""
        html = "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>"
        wrapped = f"```html\n{html}\n```"
        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(
            return_value=Response(
                200,
                json={"choices": [{"message": {"content": wrapped}}]},
            )
        )

        result = await _generate_site_html("test description")
        assert result == html

    @pytest.mark.asyncio
    async def test_strips_plain_code_fences(self, mock_settings, mock_nvidia_api):
        """Code fences without language tag (``` ... ```) are stripped."""
        html = "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>"
        wrapped = f"```\n{html}\n```"
        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(
            return_value=Response(
                200,
                json={"choices": [{"message": {"content": wrapped}}]},
            )
        )

        result = await _generate_site_html("test description")
        assert result == html

    @pytest.mark.asyncio
    async def test_api_error_raises(self, mock_settings, mock_nvidia_api):
        """API errors propagate as exceptions."""
        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(return_value=Response(500, json={"error": "Server error"}))

        with pytest.raises(Exception):
            await _generate_site_html("test description")


# ==================== _get_demo_html ====================


class TestGetDemoHtml:
    """Test fallback demo HTML generation."""

    def test_includes_title(self):
        html = _get_demo_html("landing page", "Dog Walking Co")
        assert "Dog Walking Co" in html

    def test_uses_site_type_as_fallback_title(self):
        html = _get_demo_html("portfolio", "")
        assert "Portfolio" in html

    def test_includes_required_sections(self):
        html = _get_demo_html("website", "Test")
        assert "<section class=\"hero\">" in html
        assert "<section class=\"features\">" in html
        assert "<footer>" in html

    def test_valid_html_structure(self):
        html = _get_demo_html("landing page", "My Biz")
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_handles_notes_with_commas(self):
        """Should use first part before comma as title."""
        html = _get_demo_html("website", "My Business, in London, UK")
        assert "My Business" in html


# ==================== run_build_workflow ====================


class TestRunBuildWorkflow:
    """Test the full build workflow."""

    @pytest.mark.asyncio
    async def test_clarification_for_vague_input(self):
        """Vague input triggers clarification event, not a build."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        with patch("services.build_agent.emit_event", side_effect=mock_emit):
            result = await run_build_workflow(
                user_message="build something cool",
                params=RouterParams(),
                session_id="test-session",
            )

        assert result["status"] == "clarification_needed"
        assert len(events) == 1
        assert events[0]["event"] == "build_clarification"

    @pytest.mark.asyncio
    async def test_happy_path_with_demo_fallback(self):
        """Full workflow with no API key falls back to demo HTML."""
        events = []
        saved_sessions = {}

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        async def mock_save(session_id, data, ttl_seconds=3600):
            saved_sessions[session_id] = data

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        with (
            patch("services.build_agent.emit_event", side_effect=mock_emit),
            patch("services.build_agent.save_session", side_effect=mock_save),
            patch("services.build_agent.settings", MagicMock(nvidia_api_key="", backend_url="http://localhost:8000")),
            patch("services.build_agent.get_redis_client", return_value=mock_redis),
        ):
            result = await run_build_workflow(
                user_message="make me a landing page for my dog walking business",
                params=RouterParams(service="landing page", notes="dog walking business"),
                session_id="test-session",
            )

        assert result["status"] == "complete"
        assert "preview_url" in result
        assert "preview_id" in result

        # Verify event sequence
        event_types = [e["event"] for e in events]
        assert event_types == [
            "build_started",
            "build_progress",
            "build_progress",
            "build_progress",
            "build_complete",
        ]

        # Verify build_started has steps
        started_data = events[0]["data"]
        assert len(started_data["steps"]) == 4

        # Verify build_complete has preview_url
        complete_data = events[-1]["data"]
        assert "preview_url" in complete_data

        # Verify HTML was stored in Redis
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("build:preview:")
        assert "<!DOCTYPE html>" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_happy_path_with_api(self, mock_settings, mock_nvidia_api):
        """Full workflow with API key calls the LLM."""
        events = []
        html_output = "<!DOCTYPE html><html><body><h1>Generated</h1></body></html>"

        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(
            return_value=Response(
                200,
                json={"choices": [{"message": {"content": html_output}}]},
            )
        )

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        with (
            patch("services.build_agent.emit_event", side_effect=mock_emit),
            patch("services.build_agent.save_session", AsyncMock()),
            patch("services.build_agent.get_redis_client", return_value=mock_redis),
            patch("services.build_agent.settings", MagicMock(nvidia_api_key="test-key", backend_url="http://localhost:8000")),
        ):
            result = await run_build_workflow(
                user_message="make me a portfolio",
                params=RouterParams(service="portfolio", notes="photographer"),
                session_id="test-session",
            )

        assert result["status"] == "complete"

        # Verify HTML stored is the LLM output
        stored_html = mock_redis.setex.call_args[0][2]
        assert stored_html == html_output

    @pytest.mark.asyncio
    async def test_api_error_emits_build_error(self, mock_settings, mock_nvidia_api):
        """API failure emits build_error event."""
        events = []

        mock_nvidia_api.post(
            "https://integrate.api.nvidia.com/v1/chat/completions"
        ).mock(return_value=Response(500, json={"error": "fail"}))

        async def mock_emit(session_id, event_type, data):
            events.append({"event": event_type, "data": data})

        with (
            patch("services.build_agent.emit_event", side_effect=mock_emit),
            patch("services.build_agent.save_session", AsyncMock()),
        ):
            result = await run_build_workflow(
                user_message="build a website",
                params=RouterParams(service="website"),
                session_id="test-session",
            )

        assert result["status"] == "error"
        error_events = [e for e in events if e["event"] == "build_error"]
        assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_generates_session_id_if_not_provided(self):
        """Workflow generates a session ID when none is given."""
        events = []

        async def mock_emit(session_id, event_type, data):
            events.append({"session_id": session_id, "event": event_type})

        with (
            patch("services.build_agent.emit_event", side_effect=mock_emit),
        ):
            result = await run_build_workflow(
                user_message="build something cool",
                params=RouterParams(),
            )

        assert result["session_id"] is not None
        assert len(result["session_id"]) == 36  # UUID format


# ==================== Preview endpoint ====================


class TestPreviewEndpoint:
    """Test the preview serving endpoint."""

    @pytest.mark.asyncio
    async def test_serves_stored_html(self):
        """Returns HTML from Redis with CSP headers."""
        from api.build import serve_preview

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="<html><body>Hello</body></html>")

        with patch("api.build.get_redis_client", return_value=mock_redis):
            response = await serve_preview("abc12345")

        assert response.status_code == 200
        assert "script-src 'none'" in response.headers.get(
            "content-security-policy", ""
        )

    @pytest.mark.asyncio
    async def test_returns_404_for_expired_preview(self):
        """Returns 404 when preview not found in Redis."""
        from api.build import serve_preview

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("api.build.get_redis_client", return_value=mock_redis):
            response = await serve_preview("nonexistent")

        assert response.status_code == 404
