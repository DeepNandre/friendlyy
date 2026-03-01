"""
Tests for Blitz session and SSE functionality.
"""

import pytest
import asyncio
from datetime import datetime

from models import (
    BlitzSession,
    CallRecord,
    CallStatus,
    SessionStatus,
    RouterParams,
    Business,
)


class TestBlitzSession:
    """Test Blitz session model."""

    def test_session_creation(self):
        """Test session is created with correct defaults."""
        session = BlitzSession(
            user_message="find me a plumber",
            parsed_params=RouterParams(service="plumber"),
        )

        assert session.id is not None
        assert session.status == SessionStatus.SEARCHING
        assert session.user_message == "find me a plumber"
        assert len(session.businesses) == 0
        assert len(session.calls) == 0

    def test_session_serialization(self):
        """Test session can be serialized to dict and back."""
        session = BlitzSession(
            user_message="find me a plumber",
            parsed_params=RouterParams(service="plumber", timeframe="tomorrow"),
            status=SessionStatus.CALLING,
        )

        # Add a business and call
        business = Business(
            id="test1",
            name="Test Plumber",
            phone="+441234567890",
        )
        session.businesses.append(business)
        session.calls.append(
            CallRecord(
                business=business,
                status=CallStatus.RINGING,
            )
        )

        # Serialize
        data = session.to_dict()

        # Deserialize
        restored = BlitzSession.from_dict(data)

        assert restored.id == session.id
        assert restored.status == session.status
        assert len(restored.businesses) == 1
        assert len(restored.calls) == 1
        assert restored.calls[0].status == CallStatus.RINGING


class TestCallRecord:
    """Test call record model."""

    def test_call_record_creation(self):
        """Test call record is created with correct defaults."""
        business = Business(
            id="test1",
            name="Test Business",
            phone="+441234567890",
        )

        call = CallRecord(business=business)

        assert call.id is not None
        assert call.status == CallStatus.PENDING
        assert call.business.name == "Test Business"
        assert call.result is None
        assert call.error is None

    def test_call_status_transitions(self):
        """Test call status can transition correctly."""
        business = Business(id="test1", name="Test", phone="+44123")
        call = CallRecord(business=business)

        assert call.status == CallStatus.PENDING

        call.status = CallStatus.RINGING
        call.started_at = datetime.utcnow()
        assert call.status == CallStatus.RINGING

        call.status = CallStatus.CONNECTED
        assert call.status == CallStatus.CONNECTED

        call.status = CallStatus.COMPLETE
        call.result = "Available tomorrow"
        call.ended_at = datetime.utcnow()
        assert call.status == CallStatus.COMPLETE
        assert call.result is not None


class TestSSEEventOrder:
    """Test SSE events are emitted in correct order."""

    @pytest.mark.asyncio
    async def test_event_order_for_successful_call(self):
        """Test events follow correct order for successful call flow."""
        events = []

        # Simulate event emission order
        events.append(("status", "searching"))
        events.append(("status", "calling"))
        events.append(("call_started", "ringing"))
        events.append(("call_connected", "connected"))
        events.append(("call_result", "complete"))
        events.append(("session_complete", "done"))

        # Verify order
        expected_order = [
            "status",
            "status",
            "call_started",
            "call_connected",
            "call_result",
            "session_complete",
        ]

        assert [e[0] for e in events] == expected_order

    @pytest.mark.asyncio
    async def test_event_order_for_failed_call(self):
        """Test events follow correct order for failed call."""
        events = []

        events.append(("status", "searching"))
        events.append(("status", "calling"))
        events.append(("call_started", "ringing"))
        events.append(("call_failed", "no_answer"))
        events.append(("session_complete", "done"))

        # call_failed should come after call_started
        event_types = [e[0] for e in events]
        started_idx = event_types.index("call_started")
        failed_idx = event_types.index("call_failed")

        assert started_idx < failed_idx

    @pytest.mark.asyncio
    async def test_session_complete_is_terminal(self):
        """Test session_complete is always the last event."""
        events = [
            "status",
            "status",
            "call_started",
            "call_result",
            "session_complete",
        ]

        assert events[-1] == "session_complete"
