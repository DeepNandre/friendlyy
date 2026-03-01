"""
Tests for the queue agent service.
Covers: human detection, IVR decision-making, TwiML generation, phone extraction.
"""

import pytest
import respx
from httpx import Response

from services.queue_agent import (
    is_likely_human_speech,
    decide_ivr_action,
    generate_queue_twiml_initial,
    generate_dtmf_and_listen_twiml,
    generate_hold_loop_twiml,
)
from models import QueuePhase


# ==================== is_likely_human_speech ====================


class TestIsLikelyHumanSpeech:
    """Test the core human detection heuristic."""

    def test_empty_input_returns_false(self):
        assert is_likely_human_speech("") is False
        assert is_likely_human_speech(None) is False

    def test_very_short_input_returns_false(self):
        """Fewer than 5 chars after strip should be rejected."""
        assert is_likely_human_speech("hi") is False
        assert is_likely_human_speech("   ") is False
        assert is_likely_human_speech("ok") is False

    def test_hold_phrases_return_false(self):
        """Common hold messages should not be flagged as human."""
        hold_messages = [
            "Your call is important to us, please hold.",
            "Please hold while we connect you.",
            "All of our agents are busy at the moment.",
            "You are number 5 in the queue.",
            "Thank you for holding. Your estimated wait time is 10 minutes.",
            "This call may be recorded for training purposes.",
            "We appreciate your patience. Please continue to hold.",
            "We are currently experiencing high call volume.",
        ]
        for msg in hold_messages:
            assert is_likely_human_speech(msg) is False, f"Should reject: {msg}"

    def test_generic_short_greetings_return_false(self):
        """Single-word greetings could be IVR or human — reject to avoid false positives."""
        assert is_likely_human_speech("Hello") is False
        assert is_likely_human_speech("hello.") is False
        assert is_likely_human_speech("Welcome") is False
        assert is_likely_human_speech("Good morning") is False
        assert is_likely_human_speech("Good afternoon") is False

    def test_conversational_speech_returns_true(self):
        """Actual human speech patterns should be detected."""
        human_messages = [
            "How can I help you today?",
            "Good morning, HMRC self-assessment, how can I help?",
            "Thanks for calling, what can I do for you?",
            "Hello, you're through to customer service, my name is Sarah.",
            "Hi there, what's your account number please?",
        ]
        for msg in human_messages:
            assert is_likely_human_speech(msg) is True, f"Should accept: {msg}"

    def test_hold_phrase_embedded_in_longer_text(self):
        """If a hold phrase appears anywhere in the text, reject it."""
        assert is_likely_human_speech(
            "Thanks for calling. Your call is important to us."
        ) is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert is_likely_human_speech("PLEASE HOLD WHILE WE CONNECT YOU") is False
        assert is_likely_human_speech("HOW CAN I HELP YOU TODAY?") is True

    def test_whitespace_handling(self):
        """Leading/trailing whitespace should be handled."""
        assert is_likely_human_speech("   How can I help?   ") is True
        assert is_likely_human_speech("   ") is False


# ==================== decide_ivr_action ====================


class TestDecideIvrAction:
    """Test IVR menu decision-making via Mistral."""

    @pytest.mark.asyncio
    async def test_returns_hold_when_no_api_key(self, monkeypatch):
        """Without an API key, should default to HOLD."""
        monkeypatch.setenv("NVIDIA_API_KEY", "")
        from core.config import get_settings
        get_settings.cache_clear()

        result = await decide_ivr_action(
            transcript="Press 1 for sales",
            business_name="HMRC",
            reason="tax enquiry",
        )
        assert result == "HOLD"

    @pytest.mark.asyncio
    async def test_returns_digit_from_mistral(self, monkeypatch, mock_nvidia_api):
        """When Mistral returns a digit, it should be passed through."""
        from core import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")

        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [{"message": {"content": "2"}}]
                },
            )
        )

        result = await decide_ivr_action(
            transcript="Press 1 for sales, press 2 for support",
            business_name="Sky",
            reason="cancel subscription",
        )
        assert result == "2"

    @pytest.mark.asyncio
    async def test_returns_hold_from_mistral(self, monkeypatch, mock_nvidia_api):
        """When Mistral returns HOLD, it should be passed through."""
        from core import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")

        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [{"message": {"content": "HOLD"}}]
                },
            )
        )

        result = await decide_ivr_action(
            transcript="Please wait while we connect you",
            business_name="HMRC",
            reason="tax enquiry",
        )
        assert result == "HOLD"

    @pytest.mark.asyncio
    async def test_returns_human_from_mistral(self, monkeypatch, mock_nvidia_api):
        """When Mistral returns HUMAN, it should be passed through."""
        from core import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")

        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [{"message": {"content": "HUMAN"}}]
                },
            )
        )

        result = await decide_ivr_action(
            transcript="Hello, how can I help?",
            business_name="HMRC",
            reason="tax enquiry",
        )
        assert result == "HUMAN"

    @pytest.mark.asyncio
    async def test_garbage_response_defaults_to_hold(self, monkeypatch, mock_nvidia_api):
        """When Mistral returns unexpected text, default to HOLD."""
        from core import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")

        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [{"message": {"content": "I think you should press option number two"}}]
                },
            )
        )

        result = await decide_ivr_action(
            transcript="Press 1 for sales",
            business_name="Sky",
            reason="cancel",
        )
        assert result == "HOLD"

    @pytest.mark.asyncio
    async def test_api_error_defaults_to_hold(self, monkeypatch, mock_nvidia_api):
        """When the API returns an error, default to HOLD."""
        from core import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")

        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "server error"})
        )

        result = await decide_ivr_action(
            transcript="Press 1 for sales",
            business_name="Sky",
            reason="cancel",
        )
        assert result == "HOLD"

    @pytest.mark.asyncio
    async def test_multi_digit_response(self, monkeypatch, mock_nvidia_api):
        """Mistral returning multi-digit codes (e.g. '31') should work."""
        from core import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")

        mock_nvidia_api.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "choices": [{"message": {"content": "31"}}]
                },
            )
        )

        result = await decide_ivr_action(
            transcript="Enter your extension number",
            business_name="Office",
            reason="reach someone",
        )
        assert result == "31"


# ==================== TwiML Generation ====================


class TestTwimlGeneration:
    """Test TwiML XML generation for different phases."""

    def test_initial_twiml_contains_gather(self):
        """Initial TwiML should have a Gather element for speech recognition."""
        twiml = generate_queue_twiml_initial("test-session-123")
        assert "<Gather" in twiml
        assert "speech" in twiml
        assert "ivr-handler/test-session-123" in twiml

    def test_initial_twiml_has_fallback_redirect(self):
        """If Gather times out, should redirect to hold loop."""
        twiml = generate_queue_twiml_initial("test-session-123")
        assert "hold-loop/test-session-123" in twiml
        assert "<Redirect" in twiml

    def test_dtmf_twiml_sends_digits(self):
        """DTMF TwiML should play the specified digits."""
        twiml = generate_dtmf_and_listen_twiml("test-session-123", "2")
        assert 'digits="2"' in twiml
        assert "<Gather" in twiml
        assert "ivr-handler/test-session-123" in twiml

    def test_dtmf_twiml_falls_through_to_hold(self):
        """After pressing digits and listening, should fall through to hold loop."""
        twiml = generate_dtmf_and_listen_twiml("test-session-123", "1")
        assert "hold-loop/test-session-123" in twiml

    def test_hold_loop_twiml_gathers_speech(self):
        """Hold loop should listen for speech to detect humans."""
        twiml = generate_hold_loop_twiml("test-session-123")
        assert "<Gather" in twiml
        assert "human-check/test-session-123" in twiml

    def test_hold_loop_twiml_loops_on_timeout(self):
        """If no speech detected during hold, loop back."""
        twiml = generate_hold_loop_twiml("test-session-123")
        assert "hold-loop/test-session-123" in twiml
        assert "<Redirect" in twiml

    def test_twiml_is_valid_xml(self):
        """All generated TwiML should be parseable XML."""
        import xml.etree.ElementTree as ET

        for twiml in [
            generate_queue_twiml_initial("s1"),
            generate_dtmf_and_listen_twiml("s1", "5"),
            generate_hold_loop_twiml("s1"),
        ]:
            # Should not raise
            ET.fromstring(twiml)


# ==================== Phone Number Extraction ====================


class TestPhoneNumberExtraction:
    """Test the phone number extraction logic in _handle_queue."""

    def test_has_digits_check(self):
        """The router check for phone numbers uses `any(c.isdigit() for c in notes)`."""
        # Valid phone numbers
        assert any(c.isdigit() for c in "0800 595 9000")
        assert any(c.isdigit() for c in "+44 800 595 9000")
        assert any(c.isdigit() for c in "08005959000")

        # Not phone numbers
        assert not any(c.isdigit() for c in "")
        assert not any(c.isdigit() for c in "no number here")
        assert not any(c.isdigit() for c in "call them please")


# ==================== Phase Progression Guard ====================


class TestPhaseProgression:
    """Test the phase ordering used by the progression guard."""

    def test_phase_ordering_is_monotonic(self):
        """Terminal phases should have the highest order values."""
        from services.queue_agent import _PHASE_ORDER

        assert _PHASE_ORDER[QueuePhase.INITIATING] < _PHASE_ORDER[QueuePhase.RINGING]
        assert _PHASE_ORDER[QueuePhase.RINGING] < _PHASE_ORDER[QueuePhase.IVR]
        assert _PHASE_ORDER[QueuePhase.IVR] < _PHASE_ORDER[QueuePhase.HOLD]
        assert _PHASE_ORDER[QueuePhase.HOLD] < _PHASE_ORDER[QueuePhase.HUMAN_DETECTED]

    def test_terminal_phases_cannot_be_overwritten_by_hold(self):
        """All terminal phases should have higher order than HOLD, preventing overwrites."""
        from services.queue_agent import _PHASE_ORDER

        hold_order = _PHASE_ORDER[QueuePhase.HOLD]
        for phase in (QueuePhase.HUMAN_DETECTED, QueuePhase.COMPLETED, QueuePhase.FAILED, QueuePhase.CANCELLED):
            assert _PHASE_ORDER[phase] > hold_order, f"{phase.value} should be > HOLD"
