"""
Demo mode for reliable hackathon presentations.
Simulates the full Blitz workflow without making real API calls.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from core.redis_client import save_session
from core.events import emit_event as emit_demo_event
from models import (
    BlitzSession,
    CallRecord,
    CallStatus,
    SessionStatus,
    RouterParams,
    Business,
)

logger = logging.getLogger(__name__)

# Demo businesses with realistic data
DEMO_BUSINESSES = [
    Business(
        id="demo_1",
        name="Pimlico Plumbers",
        phone="+442078331111",
        address="1 Sail Street, London SE11 6NQ",
        rating=4.8,
    ),
    Business(
        id="demo_2",
        name="Mr. Plumber London",
        phone="+442072230987",
        address="15 High Street, London EC1V 9JX",
        rating=4.5,
    ),
    Business(
        id="demo_3",
        name="HomeServe UK",
        phone="+443301238888",
        address="Cable Drive, Walsall WS2 7BN",
        rating=4.2,
    ),
]

# Demo results (realistic responses)
DEMO_RESULTS = [
    "Available tomorrow 2pm, £95 call-out fee + parts",
    "Can come today after 5pm, £85 call-out fee",
    None,  # No answer
]


async def run_demo_workflow(
    user_message: str,
    params: RouterParams,
    session_id: str = None,
) -> BlitzSession:
    """
    Simulate the full Blitz workflow for demo purposes.

    Includes realistic timing to demonstrate the experience.

    Args:
        user_message: Original user message
        params: Parsed router params
        session_id: Existing session ID to use (optional)

    Returns:
        BlitzSession with simulated results
    """
    service = params.service or "plumber"

    # Create session with provided ID or generate new one
    session = BlitzSession(
        id=session_id if session_id else None,
        user_message=user_message,
        parsed_params=params,
        status=SessionStatus.SEARCHING,
    )

    # If session_id was provided, use it
    if session_id:
        session.id = session_id

    # Save initial state
    await save_session(session.id, session.model_dump(mode="json"))

    try:
        # Step 1: Simulate search
        await emit_demo_event(
            session.id,
            "status",
            {
                "status": "searching",
                "message": f"Finding {service}s near you...",
            },
        )

        # Realistic delay for search
        await asyncio.sleep(1.5)

        # Set businesses
        session.businesses = DEMO_BUSINESSES[:3]
        session.calls = [
            CallRecord(business=b, status=CallStatus.PENDING)
            for b in session.businesses
        ]

        # Step 2: Start calls
        session.status = SessionStatus.CALLING
        await emit_demo_event(
            session.id,
            "status",
            {
                "status": "calling",
                "message": f"Calling {len(session.businesses)} businesses...",
                "businesses": [b.model_dump() for b in session.businesses],
            },
        )

        # Step 3: Simulate each call with realistic timing
        for i, (call, result) in enumerate(zip(session.calls, DEMO_RESULTS)):
            # Small delay between call starts
            await asyncio.sleep(0.5)

            # Call starts ringing
            call.status = CallStatus.RINGING
            call.started_at = datetime.utcnow()
            await emit_demo_event(
                session.id,
                "call_started",
                {
                    "business": call.business.name,
                    "phone": call.business.phone,
                    "status": "ringing",
                },
            )

            # Simulate ringing time (varies per call)
            await asyncio.sleep(1.5 + (i * 0.5))

            if result is None:
                # Simulate no answer
                call.status = CallStatus.NO_ANSWER
                call.ended_at = datetime.utcnow()
                await emit_demo_event(
                    session.id,
                    "call_failed",
                    {
                        "business": call.business.name,
                        "error": "No answer",
                    },
                )
            else:
                # Call connected
                call.status = CallStatus.CONNECTED
                await emit_demo_event(
                    session.id,
                    "call_connected",
                    {
                        "business": call.business.name,
                        "status": "connected",
                    },
                )

                # Simulate conversation time
                await asyncio.sleep(2)

                # Call complete with result
                call.status = CallStatus.COMPLETE
                call.result = result
                call.ended_at = datetime.utcnow()
                await emit_demo_event(
                    session.id,
                    "call_result",
                    {
                        "business": call.business.name,
                        "status": "complete",
                        "result": result,
                    },
                )

        # Step 4: Complete session
        session.status = SessionStatus.COMPLETE
        session.completed_at = datetime.utcnow()

        # Generate summary
        successful = [c for c in session.calls if c.status == CallStatus.COMPLETE]
        results_text = "\n".join(
            [f"- {c.business.name}: {c.result}" for c in successful]
        )
        session.summary = f"Found {len(successful)} {service}s available:\n\n{results_text}"

        # Final event
        await asyncio.sleep(0.5)
        await emit_demo_event(
            session.id,
            "session_complete",
            {
                "summary": session.summary,
                "results": [
                    {
                        "business": c.business.name,
                        "status": c.status.value,
                        "result": c.result,
                    }
                    for c in session.calls
                ],
            },
        )

        # Save final state
        await save_session(session.id, session.model_dump(mode="json"))

        return session

    except Exception as e:
        logger.error(f"Demo workflow error: {e}")
        session.status = SessionStatus.ERROR
        await emit_demo_event(session.id, "error", {"message": str(e)})
        raise
