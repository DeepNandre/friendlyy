"""
Pydantic models for Call Friend agent functionality.
Handles calling friends/contacts with custom messages on behalf of the user.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CallFriendPhase(str, Enum):
    """Phases of a call friend session."""

    INITIATING = "initiating"  # About to start the call
    RINGING = "ringing"  # Phone is ringing
    CONNECTED = "connected"  # Call answered, AI is speaking
    COMPLETE = "complete"  # Call finished
    FAILED = "failed"  # Call failed
    NO_ANSWER = "no_answer"  # Friend didn't pick up


class CallFriendSession(BaseModel):
    """A Call Friend session for calling someone on behalf of the user."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    friend_name: str
    phone_number: str
    question: str  # What the user wants to ask their friend
    user_context: Optional[str] = None  # Additional context about the request

    phase: CallFriendPhase = CallFriendPhase.INITIATING
    call_sid: Optional[str] = None

    # Transcript of the conversation
    transcript: List[Dict[str, str]] = Field(default_factory=list)

    # The friend's response/answer
    response: Optional[str] = None

    # Summary of the call for the user
    summary: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    recording_url: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallFriendSession":
        """Create from dictionary (from Redis)."""
        return cls.model_validate(data)
