"""
Pydantic models for Blitz agent functionality.
Includes validation constraints per approved plan.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator

from .base import AgentType, CallStatus, SessionStatus


# ==================== ROUTER MODELS ====================


class RouterParams(BaseModel):
    """Parameters extracted from user message by router."""

    service: Optional[str] = None
    timeframe: Optional[str] = None
    location: Optional[str] = None
    action: Optional[str] = None
    notes: Optional[str] = None


class RouterResult(BaseModel):
    """Result of intent classification."""

    agent: AgentType
    params: RouterParams = Field(default_factory=RouterParams)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ==================== BUSINESS MODELS ====================


class Business(BaseModel):
    """A business found via Google Places or fallback."""

    id: str
    name: str
    phone: str
    address: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    place_id: Optional[str] = None
    website: Optional[str] = None


# ==================== CALL MODELS ====================


class CallScript(BaseModel):
    """Script for the AI to follow during a call."""

    service_type: str
    timeframe: Optional[str] = None
    question: str = "availability and pricing"
    user_notes: Optional[str] = None


class CallRecord(BaseModel):
    """Record of an individual phone call."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    call_sid: Optional[str] = None
    business: Business
    status: CallStatus = CallStatus.PENDING
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: List[Dict[str, str]] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    recording_url: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# ==================== SESSION MODELS ====================


class BlitzSession(BaseModel):
    """A complete Blitz workflow session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_message: str
    parsed_params: RouterParams = Field(default_factory=RouterParams)
    status: SessionStatus = SessionStatus.SEARCHING
    businesses: List[Business] = Field(default_factory=list)
    calls: List[CallRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    summary: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlitzSession":
        """Create from dictionary (from Redis)."""
        return cls.model_validate(data)


# ==================== API MODELS ====================


class ChatMessage(BaseModel):
    """A single message in conversation history."""
    role: Literal["user", "assistant"] = "user"
    content: str


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User message to process",
    )
    session_id: Optional[str] = None
    location: Optional[Dict[str, float]] = Field(
        default=None,
        description="User location as {lat: float, lng: float}",
    )
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Previous messages for context",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        """Strip whitespace from message."""
        return v.strip()


class ChatResponse(BaseModel):
    """Response body for POST /api/chat."""

    session_id: str
    agent: AgentType
    status: str
    message: str
    stream_url: Optional[str] = None
    call_statuses: Optional[List[Dict[str, Any]]] = None


# ==================== SSE EVENT MODELS ====================


class SSEEvent(BaseModel):
    """Server-Sent Event structure."""

    event: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def format(self) -> str:
        """Format as SSE text."""
        import json

        return f"event: {self.event}\ndata: {json.dumps(self.data, default=str)}\n\n"
