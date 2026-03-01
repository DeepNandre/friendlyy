"""
Pydantic models for Queue agent - wait on hold for the user.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueuePhase(str, Enum):
    """Current phase of the queue workflow."""

    INITIATING = "initiating"  # Starting the call
    RINGING = "ringing"  # Phone is ringing
    IVR = "ivr"  # Navigating phone menu
    HOLD = "hold"  # Waiting on hold
    HUMAN_DETECTED = "human_detected"  # A human picked up
    COMPLETED = "completed"  # Workflow finished
    FAILED = "failed"  # Something went wrong
    CANCELLED = "cancelled"  # User cancelled


class QueueSession(BaseModel):
    """A complete queue hold-waiting session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_message: str = ""
    phone_number: str = ""
    business_name: str = ""
    reason: Optional[str] = None

    phase: QueuePhase = QueuePhase.INITIATING
    call_sid: Optional[str] = None

    # IVR tracking
    ivr_steps_taken: List[Dict[str, str]] = Field(default_factory=list)

    # Hold tracking
    hold_started_at: Optional[datetime] = None
    hold_elapsed_seconds: int = 0
    last_update_at: Optional[datetime] = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Result
    human_detected: bool = False
    callback_number: Optional[str] = None
    error: Optional[str] = None

    # Config
    max_hold_minutes: int = 30

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueSession":
        """Create from dictionary (from Redis)."""
        return cls.model_validate(data)
