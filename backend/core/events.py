"""
Shared SSE event emission.
All agents use this to push events to the frontend via Redis.
"""

from datetime import datetime
from typing import Dict, Any

from core.redis_client import push_event


async def emit_event(session_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Emit an SSE event for a session.

    Args:
        session_id: Session ID (used as the Redis queue key)
        event_type: Event type string (e.g. "status", "queue_hold", "call_started")
        data: Event payload
    """
    await push_event(
        session_id,
        {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
