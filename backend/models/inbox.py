"""
Pydantic models for the Inbox agent — check Gmail via Composio.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class InboxPhase(str, Enum):
    """Current phase of the inbox check workflow."""

    CHECKING_CONNECTION = "checking_connection"
    AUTH_REQUIRED = "auth_required"
    FETCHING = "fetching"
    SUMMARIZING = "summarizing"
    COMPLETE = "complete"
    ERROR = "error"


class InboxSummary(BaseModel):
    """Structured summary returned to the frontend."""

    important_count: int = 0
    top_updates: List[str] = Field(default_factory=list)
    needs_action: bool = False
    draft_replies_available: bool = False
    sender_highlights: List[str] = Field(default_factory=list)
    time_range: str = "last 24 hours"


class InboxSession(BaseModel):
    """State for a single inbox-check workflow run."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_message: str = ""
    entity_id: str = "default"
    phase: InboxPhase = InboxPhase.CHECKING_CONNECTION

    # Auth
    auth_url: Optional[str] = None

    # Results
    email_count: int = 0
    summary: Optional[InboxSummary] = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InboxSession":
        return cls.model_validate(data)
