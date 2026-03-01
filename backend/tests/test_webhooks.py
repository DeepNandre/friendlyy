"""
Tests for Twilio webhook handlers.

Uses FastAPI TestClient with mocked Redis and event emission
to verify webhook behavior without real Twilio or Redis.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from models import (
    BlitzSession,
    CallRecord,
    CallStatus,
    SessionStatus,
    RouterParams,
    Business,
)
from services.twilio_caller import TWILIO_STATUS_MAP


# ==================== FIXTURES ====================


def _make_session(call_sid="CA_test_sid_123", call_id="test-call-id") -> BlitzSession:
    """Create a test session with one call record."""
    business = Business(
        id="biz1",
        name="Test Plumber",
        phone="+441234567890",
    )
    session = BlitzSession(
        id="test-session-id",
        user_message="find me a plumber",
        parsed_params=RouterParams(service="plumber"),
        status=SessionStatus.CALLING,
    )
    session.businesses = [business]
    session.calls = [
        CallRecord(
            id=call_id,
            call_sid=call_sid,
            business=business,
            status=CallStatus.RINGING,
        )
    ]
    return session


@pytest.fixture
def test_session():
    return _make_session()


@pytest.fixture
def mock_deps():
    """Mock Redis and event emission dependencies."""
    with patch("api.webhooks.get_session_state") as mock_get, \
         patch("api.webhooks.save_session") as mock_save, \
         patch("api.webhooks.emit_event") as mock_emit:
        mock_get.return_value = None
        mock_save.return_value = None
        mock_emit.return_value = None
        # Make them async
        mock_get.side_effect = None
        mock_save.side_effect = None
        mock_emit.side_effect = None
        yield {
            "get_session_state": mock_get,
            "save_session": mock_save,
            "emit_event": mock_emit,
        }


@pytest.fixture
def client():
    """Create FastAPI test client with webhook routes."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.webhooks import router

    app = FastAPI()
    app.include_router(router, prefix="/api/blitz")
    return TestClient(app)


# ==================== STATUS WEBHOOK TESTS ====================


class TestTwilioStatusCallback:
    """Tests for POST /api/blitz/webhook."""

    def test_missing_session_id_returns_ok(self, client, mock_deps):
        """Webhook without session_id should return 200 without crashing."""
        response = client.post(
            "/api/blitz/webhook",
            data={"CallSid": "CA_test", "CallStatus": "ringing"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        # Should NOT try to load session
        mock_deps["get_session_state"].assert_not_called()

    def test_session_not_found_returns_ok(self, client, mock_deps):
        """Webhook with unknown session should return 200 gracefully."""
        mock_deps["get_session_state"].return_value = None

        response = client.post(
            "/api/blitz/webhook?session_id=unknown&call_id=c1",
            data={"CallSid": "CA_test", "CallStatus": "ringing"},
        )
        assert response.status_code == 200
        mock_deps["save_session"].assert_not_called()

    def test_call_record_not_found_returns_ok(self, client, mock_deps, test_session):
        """Webhook with mismatched CallSid/call_id should return 200."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=wrong-id",
            data={"CallSid": "CA_wrong_sid", "CallStatus": "ringing"},
        )
        assert response.status_code == 200
        # Should not save since no record was found
        mock_deps["save_session"].assert_not_called()

    def test_ringing_status_emits_call_started(self, client, mock_deps, test_session):
        """Ringing status should emit call_started event."""
        test_session.calls[0].status = CallStatus.PENDING
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=test-call-id",
            data={"CallSid": "CA_test_sid_123", "CallStatus": "ringing"},
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.RINGING
        mock_deps["emit_event"].assert_called_once()
        call_args = mock_deps["emit_event"].call_args
        assert call_args[0][1] == "call_started"

    def test_in_progress_status_emits_call_connected(self, client, mock_deps, test_session):
        """In-progress status should emit call_connected event."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=test-call-id",
            data={"CallSid": "CA_test_sid_123", "CallStatus": "in-progress"},
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.CONNECTED
        mock_deps["emit_event"].assert_called_once()
        call_args = mock_deps["emit_event"].call_args
        assert call_args[0][1] == "call_connected"

    def test_busy_status_emits_call_failed(self, client, mock_deps, test_session):
        """Busy status should emit call_failed with 'Line busy' message."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=test-call-id",
            data={"CallSid": "CA_test_sid_123", "CallStatus": "busy"},
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.BUSY
        mock_deps["emit_event"].assert_called_once()
        call_args = mock_deps["emit_event"].call_args
        assert call_args[0][1] == "call_failed"
        assert call_args[0][2]["error"] == "Line busy"

    def test_no_answer_emits_call_failed(self, client, mock_deps, test_session):
        """No-answer status should emit call_failed."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=test-call-id",
            data={"CallSid": "CA_test_sid_123", "CallStatus": "no-answer"},
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.NO_ANSWER

    def test_completed_status_saves_session(self, client, mock_deps, test_session):
        """Completed status should update record and save to Redis."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=test-call-id",
            data={"CallSid": "CA_test_sid_123", "CallStatus": "completed"},
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.COMPLETE
        mock_deps["save_session"].assert_called_once()

    def test_unknown_status_defaults_to_failed(self, client, mock_deps, test_session):
        """Unknown Twilio status should default to FAILED."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=test-call-id",
            data={"CallSid": "CA_test_sid_123", "CallStatus": "some-unknown-status"},
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.FAILED

    def test_call_matched_by_call_id_when_sid_differs(self, client, mock_deps):
        """Should find call record by call_id even if CallSid doesn't match."""
        session = _make_session(call_sid=None, call_id="my-call-id")
        mock_deps["get_session_state"].return_value = session

        response = client.post(
            "/api/blitz/webhook?session_id=test-session-id&call_id=my-call-id",
            data={"CallSid": "CA_different_sid", "CallStatus": "in-progress"},
        )

        assert response.status_code == 200
        assert session.calls[0].status == CallStatus.CONNECTED


# ==================== STATUS MAP TESTS ====================


class TestTwilioStatusMap:
    """Verify the shared TWILIO_STATUS_MAP constant covers all known statuses."""

    def test_all_twilio_statuses_mapped(self):
        """Every known Twilio call status should have a mapping."""
        known_statuses = [
            "initiated", "ringing", "in-progress", "answered",
            "completed", "busy", "no-answer", "failed", "canceled",
        ]
        for status in known_statuses:
            assert status in TWILIO_STATUS_MAP, f"Missing mapping for '{status}'"

    def test_map_values_are_call_status_enums(self):
        """Every mapped value should be a valid CallStatus enum member."""
        for twilio_status, internal_status in TWILIO_STATUS_MAP.items():
            assert isinstance(internal_status, CallStatus), (
                f"TWILIO_STATUS_MAP['{twilio_status}'] = {internal_status} is not a CallStatus"
            )

    def test_terminal_statuses_are_terminal(self):
        """Terminal Twilio statuses should map to terminal internal statuses."""
        terminal_twilio = ["completed", "busy", "no-answer", "failed", "canceled"]
        terminal_internal = {CallStatus.COMPLETE, CallStatus.BUSY, CallStatus.NO_ANSWER, CallStatus.FAILED}

        for status in terminal_twilio:
            assert TWILIO_STATUS_MAP[status] in terminal_internal, (
                f"'{status}' mapped to {TWILIO_STATUS_MAP[status]} which is not terminal"
            )


# ==================== AMD TESTS ====================


class TestAnsweringMachineDetection:
    """Tests for POST /api/blitz/amd."""

    def test_human_detected_does_nothing(self, client, mock_deps):
        """Human answer should not hang up the call."""
        response = client.post(
            "/api/blitz/amd?session_id=s1&call_id=c1",
            data={"CallSid": "CA_test", "AnsweredBy": "human"},
        )
        assert response.status_code == 200
        mock_deps["get_session_state"].assert_not_called()

    def test_machine_detected_updates_session(self, client, mock_deps, test_session):
        """Machine detection should mark call as failed with voicemail error."""
        mock_deps["get_session_state"].return_value = test_session

        with patch("services.twilio_caller.get_twilio_client") as mock_twilio:
            mock_client = MagicMock()
            mock_twilio.return_value = mock_client

            response = client.post(
                "/api/blitz/amd?session_id=test-session-id&call_id=test-call-id",
                data={"CallSid": "CA_test_sid_123", "AnsweredBy": "machine_start"},
            )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.FAILED
        assert test_session.calls[0].error == "Voicemail detected"
        mock_deps["emit_event"].assert_called_once()

    @pytest.mark.parametrize("answered_by", [
        "machine_start", "machine_end_beep", "machine_end_silence",
        "machine_end_other", "fax",
    ])
    def test_all_machine_types_trigger_hangup(self, client, mock_deps, answered_by):
        """All machine AnsweredBy values should trigger the hangup flow."""
        session = _make_session()
        mock_deps["get_session_state"].return_value = session

        with patch("services.twilio_caller.get_twilio_client") as mock_twilio:
            mock_twilio.return_value = MagicMock()

            response = client.post(
                "/api/blitz/amd?session_id=test-session-id&call_id=test-call-id",
                data={"CallSid": "CA_test_sid_123", "AnsweredBy": answered_by},
            )

        assert response.status_code == 200
        assert session.calls[0].status == CallStatus.FAILED

    def test_amd_without_session_id_still_hangs_up(self, client, mock_deps):
        """AMD should attempt hangup even without session_id."""
        with patch("services.twilio_caller.get_twilio_client") as mock_twilio:
            mock_client = MagicMock()
            mock_twilio.return_value = mock_client

            response = client.post(
                "/api/blitz/amd",
                data={"CallSid": "CA_test", "AnsweredBy": "machine_start"},
            )

        assert response.status_code == 200
        # Should still try to hang up the call
        mock_client.calls.assert_called_once_with("CA_test")


# ==================== RECORDING TESTS ====================


class TestRecordingComplete:
    """Tests for POST /api/blitz/recording-complete."""

    def test_recording_complete_marks_call_done(self, client, mock_deps, test_session):
        """Recording completion should mark call as COMPLETE with result."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/recording-complete?session_id=test-session-id&call_id=test-call-id",
            data={
                "RecordingUrl": "https://api.twilio.com/recordings/RE123",
                "RecordingDuration": "15",
            },
        )

        assert response.status_code == 200
        assert test_session.calls[0].status == CallStatus.COMPLETE
        assert test_session.calls[0].recording_url == "https://api.twilio.com/recordings/RE123"
        assert test_session.calls[0].result is not None
        mock_deps["emit_event"].assert_called_once()
        call_args = mock_deps["emit_event"].call_args
        assert call_args[0][1] == "call_result"

    def test_recording_complete_missing_params_returns_ok(self, client, mock_deps):
        """Missing session_id or call_id should return 200 gracefully."""
        response = client.post(
            "/api/blitz/recording-complete",
            data={"RecordingUrl": "https://example.com/rec"},
        )
        assert response.status_code == 200
        mock_deps["get_session_state"].assert_not_called()

    def test_recording_complete_unknown_call_returns_ok(self, client, mock_deps, test_session):
        """Unknown call_id should return 200 without emitting events."""
        mock_deps["get_session_state"].return_value = test_session

        response = client.post(
            "/api/blitz/recording-complete?session_id=test-session-id&call_id=wrong-id",
            data={"RecordingUrl": "https://example.com/rec"},
        )

        assert response.status_code == 200
        mock_deps["emit_event"].assert_not_called()
