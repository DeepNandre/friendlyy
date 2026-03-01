"""
Base enums and shared model definitions.
"""

from enum import Enum


class AgentType(str, Enum):
    """Available agent types for routing."""

    BLITZ = "blitz"  # Find services, get quotes, check availability
    BOUNCE = "bounce"  # Cancel subscriptions
    QUEUE = "queue"  # Wait on hold for someone
    BID = "bid"  # Negotiate bills lower
    BUILD = "build"  # Build websites, apps, landing pages
    CHAT = "chat"  # General conversation


class CallStatus(str, Enum):
    """Status of an individual phone call."""

    PENDING = "pending"  # Call not yet initiated
    RINGING = "ringing"  # Phone is ringing
    CONNECTED = "connected"  # Call answered
    SPEAKING = "speaking"  # AI is speaking
    RECORDING = "recording"  # Recording response
    COMPLETE = "complete"  # Call finished successfully
    NO_ANSWER = "no_answer"  # No one picked up
    BUSY = "busy"  # Line was busy
    FAILED = "failed"  # Call failed for other reason


class SessionStatus(str, Enum):
    """Status of a Blitz session."""

    SEARCHING = "searching"  # Looking for businesses
    CALLING = "calling"  # Making phone calls
    COMPLETE = "complete"  # All calls finished
    ERROR = "error"  # Something went wrong
