"""
Queue agent - waits on hold for the user.

Flow:
1. Initiate outbound call via Twilio
2. Navigate IVR menus using Mistral for decision-making
3. Detect hold state (music, silence, "your call is important" loops)
4. Wait on hold, streaming elapsed time to the user
5. Detect when a human picks up
6. Alert the user to call back or (stretch) bridge them in
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

from core import settings
from core.redis_client import save_session, get_session
from core.events import emit_event as emit_queue_event
from models import QueuePhase, QueueSession

logger = logging.getLogger(__name__)


# Phase ordering — higher index = more advanced. Used to prevent race conditions
# where a background writer overwrites a more-advanced phase.
_PHASE_ORDER = {
    QueuePhase.INITIATING: 0,
    QueuePhase.RINGING: 1,
    QueuePhase.IVR: 2,
    QueuePhase.HOLD: 3,
    QueuePhase.HUMAN_DETECTED: 4,
    QueuePhase.COMPLETED: 5,
    QueuePhase.FAILED: 5,
    QueuePhase.CANCELLED: 5,
}


async def save_queue_session(session: QueueSession, expected_phase: QueuePhase = None) -> bool:
    """
    Save queue session state to Redis.

    Args:
        session: Session to save.
        expected_phase: If set, re-reads the session first and refuses to write
            if the current phase has advanced beyond expected_phase. This prevents
            race conditions where a slow writer overwrites a more advanced state
            (e.g., hold loop overwriting HUMAN_DETECTED back to HOLD).

    Returns:
        True if saved, False if skipped due to phase guard.
    """
    if expected_phase is not None:
        current = await get_queue_session(session.id)
        if current and _PHASE_ORDER.get(current.phase, 0) > _PHASE_ORDER.get(expected_phase, 0):
            logger.info(
                f"Phase guard: skipping write for {session.id} "
                f"(current={current.phase.value}, expected={expected_phase.value})"
            )
            return False
    await save_session(f"queue:{session.id}", session.to_dict(), ttl_seconds=7200)
    return True


async def get_queue_session(session_id: str) -> Optional[QueueSession]:
    """Load queue session state from Redis."""
    data = await get_session(f"queue:{session_id}")
    if data:
        return QueueSession.from_dict(data)
    return None


# ==================== TWILIO CALL INITIATION ====================


def _get_twilio_client() -> Optional[Client]:
    """Get Twilio client (reuse from twilio_caller if possible)."""
    from services.twilio_caller import get_twilio_client
    return get_twilio_client()


async def initiate_queue_call(session: QueueSession) -> Optional[str]:
    """
    Start a Twilio call for the queue workflow.

    Unlike Blitz calls, queue calls use <Gather> to listen for IVR prompts
    and stay on the line indefinitely.

    Returns:
        Twilio Call SID, or None on failure.
    """
    client = _get_twilio_client()
    if not client:
        return None

    try:
        call = client.calls.create(
            to=session.phone_number,
            from_=settings.twilio_phone_number,
            url=f"{settings.backend_url}/api/queue/twiml/{session.id}",
            status_callback=f"{settings.backend_url}/api/queue/status-callback?session_id={session.id}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            timeout=60,
            # No recording for queue calls — we just need to listen
        )
        logger.info(f"Queue call initiated: {call.sid} to {session.phone_number}")
        return call.sid
    except Exception as e:
        logger.error(f"Queue call failed: {e}")
        return None


# ==================== TWIML GENERATION ====================


def generate_queue_twiml_initial(session_id: str) -> str:
    """
    Generate initial TwiML for queue call.

    Uses <Gather> with speech recognition to listen for IVR prompts.
    The call will listen, and we'll process what we hear to decide
    which buttons to press.
    """
    response = VoiceResponse()

    # Listen for IVR prompts — gather speech + DTMF input options
    # We use a long timeout so we can hear the full menu
    gather = Gather(
        input="speech",
        action=f"{settings.backend_url}/api/queue/ivr-handler/{session_id}",
        method="POST",
        timeout=15,
        speech_timeout="auto",
        language="en-GB",
    )
    # Don't say anything — just listen to the IVR
    response.append(gather)

    # If gather times out with no input, redirect to hold mode
    response.redirect(
        f"{settings.backend_url}/api/queue/hold-loop/{session_id}",
        method="POST",
    )

    return str(response)


def generate_dtmf_and_listen_twiml(session_id: str, digits: str) -> str:
    """
    Generate TwiML that sends DTMF tones then listens again.
    Used after Mistral decides which button to press.
    """
    response = VoiceResponse()

    # Send the DTMF digits
    response.play(digits=digits)

    # Brief pause then listen again for next IVR level
    response.pause(length=2)

    # Gather again for next menu level
    gather = Gather(
        input="speech",
        action=f"{settings.backend_url}/api/queue/ivr-handler/{session_id}",
        method="POST",
        timeout=15,
        speech_timeout="auto",
        language="en-GB",
    )
    response.append(gather)

    # If no more IVR, fall through to hold loop
    response.redirect(
        f"{settings.backend_url}/api/queue/hold-loop/{session_id}",
        method="POST",
    )

    return str(response)


def generate_hold_loop_twiml(session_id: str) -> str:
    """
    Generate TwiML for the hold-waiting phase.

    Periodically checks for human speech by using short <Gather> windows.
    If speech is detected, routes to human-detection handler.
    If silence/music continues, loops back.
    """
    response = VoiceResponse()

    # Listen for 20 seconds — if someone speaks, it triggers the action
    gather = Gather(
        input="speech",
        action=f"{settings.backend_url}/api/queue/human-check/{session_id}",
        method="POST",
        timeout=20,
        speech_timeout="auto",
        language="en-GB",
    )
    response.append(gather)

    # If gather times out (still on hold), loop back
    response.redirect(
        f"{settings.backend_url}/api/queue/hold-loop/{session_id}",
        method="POST",
    )

    return str(response)


# ==================== IVR NAVIGATION ====================


IVR_SYSTEM_PROMPT = """You are navigating an automated phone menu (IVR) on behalf of a user.

The user wants to: {reason}
They are calling: {business_name}

You just heard this from the phone menu:
"{transcript}"

Based on what you heard, decide what to do:

1. If you heard menu options (e.g., "press 1 for X, press 2 for Y"), respond with the digit(s) to press.
2. If you're being asked to hold or wait, respond with "HOLD" — we'll wait on hold.
3. If a human seems to be talking (not a recording), respond with "HUMAN".
4. If you can't understand or it's unclear, respond with "HOLD" to wait.

Respond with ONLY one of:
- A digit or digits to press (e.g., "1", "2", "31")
- "HOLD"
- "HUMAN"

No explanation, just the action."""


async def decide_ivr_action(
    transcript: str,
    business_name: str,
    reason: str,
) -> str:
    """
    Use Mistral via NVIDIA NIM to decide which IVR button to press.

    Returns: digit string (e.g. "1"), "HOLD", or "HUMAN"
    """
    if not settings.nvidia_api_key:
        logger.warning("No NVIDIA API key — defaulting to HOLD")
        return "HOLD"

    prompt = IVR_SYSTEM_PROMPT.format(
        reason=reason or "general enquiry",
        business_name=business_name,
        transcript=transcript,
    )

    try:
        from core import get_http_client

        client = await get_http_client()
        response = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistralai/mixtral-8x7b-instruct-v0.1",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Menu audio: {transcript}"},
                ],
                "temperature": 0.1,
                "max_tokens": 10,
            },
        )
        response.raise_for_status()
        result = response.json()
        action = result["choices"][0]["message"]["content"].strip().upper()

        # Validate: should be digits, "HOLD", or "HUMAN"
        if action in ("HOLD", "HUMAN"):
            return action
        # Check if it's valid digits
        cleaned = action.replace(" ", "")
        if cleaned.isdigit():
            return cleaned

        logger.warning(f"Unexpected IVR action from Mistral: {action}, defaulting to HOLD")
        return "HOLD"

    except Exception as e:
        logger.error(f"IVR decision failed: {e}")
        return "HOLD"


# ==================== HUMAN DETECTION ====================


HOLD_PHRASES = [
    "your call is important",
    "please hold",
    "please wait",
    "all of our",
    "agents are busy",
    "advisors are busy",
    "currently experiencing",
    "high call volume",
    "you are number",
    "position in the queue",
    "estimated wait time",
    "thank you for holding",
    "thank you for waiting",
    "we appreciate your patience",
    "please continue to hold",
    "call may be recorded",
    "calls may be monitored",
    "for training purposes",
    "for quality purposes",
]


def is_likely_human_speech(transcript: str) -> bool:
    """
    Simple heuristic: if the speech doesn't contain common hold phrases,
    and is conversational in nature, it's likely a real human.

    This is intentionally simple for a hackathon demo.
    False positives are OK — better to alert the user and be wrong
    than miss when a human actually picks up.
    """
    if not transcript or len(transcript.strip()) < 5:
        return False

    lower = transcript.lower()

    # If it contains any hold/IVR phrase, it's not a human
    for phrase in HOLD_PHRASES:
        if phrase in lower:
            return False

    # If it's a short generic phrase, probably not a human yet
    generic_short = ["hello", "hi", "welcome", "good morning", "good afternoon"]
    # These could be either IVR or human — only flag as human if there's more
    stripped = lower.strip().rstrip(".")
    if stripped in generic_short:
        return False

    # If we get here, it's speech that doesn't match hold patterns
    # Likely a real human asking something like "How can I help you?"
    return True


# ==================== MAIN WORKFLOW ====================


async def run_queue_workflow(
    phone_number: str,
    business_name: str,
    reason: Optional[str] = None,
    session_id: Optional[str] = None,
) -> QueueSession:
    """
    Start the queue hold-waiting workflow.

    1. Create session
    2. Initiate call
    3. The rest happens via Twilio webhooks (IVR nav, hold loop, human detection)

    Returns:
        QueueSession with initial state
    """
    session = QueueSession(
        phone_number=phone_number,
        business_name=business_name,
        reason=reason,
        phase=QueuePhase.INITIATING,
    )
    if session_id:
        session.id = session_id

    await save_queue_session(session)

    # Emit: starting
    await emit_queue_event(
        session.id,
        "queue_started",
        {
            "message": f"Calling {business_name}...",
            "phone": phone_number,
            "business": business_name,
        },
    )

    # Initiate the call
    call_sid = await initiate_queue_call(session)

    if not call_sid:
        session.phase = QueuePhase.FAILED
        session.error = "Failed to initiate call — Twilio not configured or call failed"
        await save_queue_session(session)
        await emit_queue_event(
            session.id,
            "queue_failed",
            {
                "message": "Couldn't connect the call. Want me to try again?",
                "error": session.error,
            },
        )
        return session

    session.call_sid = call_sid
    session.phase = QueuePhase.RINGING
    await save_queue_session(session)

    # Start background task to send hold updates
    asyncio.create_task(_hold_update_loop(session.id))

    return session


async def _hold_update_loop(session_id: str) -> None:
    """
    Background task that sends periodic hold updates to the frontend.
    Runs every 30 seconds while the session is in HOLD phase.

    Wrapped in try/except to prevent silent death — if this loop crashes,
    the user gets a queue_failed event instead of silence.
    """
    try:
        while True:
            await asyncio.sleep(30)

            session = await get_queue_session(session_id)
            if not session:
                break

            # Stop if we're no longer in a waiting state
            if session.phase not in (QueuePhase.HOLD, QueuePhase.IVR, QueuePhase.RINGING):
                break

            # Check max hold time
            if session.hold_started_at:
                elapsed = (datetime.utcnow() - session.hold_started_at).total_seconds()
                session.hold_elapsed_seconds = int(elapsed)

                if elapsed > session.max_hold_minutes * 60:
                    session.phase = QueuePhase.FAILED
                    session.error = f"Hold time exceeded {session.max_hold_minutes} minutes"
                    await save_queue_session(session, expected_phase=QueuePhase.HOLD)
                    await emit_queue_event(
                        session_id,
                        "queue_failed",
                        {
                            "message": f"Been on hold for over {session.max_hold_minutes} minutes. Want me to keep trying or give up?",
                            "elapsed": session.hold_elapsed_seconds,
                        },
                    )
                    await _hangup_call(session)
                    break

                await save_queue_session(session, expected_phase=QueuePhase.HOLD)
                await emit_queue_event(
                    session_id,
                    "queue_hold_update",
                    {
                        "message": "Still on hold...",
                        "elapsed": session.hold_elapsed_seconds,
                    },
                )
            else:
                # Not on hold yet (still in IVR or ringing), just send a status ping
                await emit_queue_event(
                    session_id,
                    "queue_hold_update",
                    {
                        "message": f"Still connecting to {session.business_name}...",
                        "elapsed": 0,
                    },
                )
    except asyncio.CancelledError:
        logger.info(f"Hold update loop cancelled for session {session_id}")
    except Exception as e:
        logger.error(f"Hold update loop crashed for session {session_id}: {e}")
        try:
            await emit_queue_event(
                session_id,
                "queue_failed",
                {
                    "message": "Something went wrong while waiting on hold. Want me to try again?",
                    "error": str(e),
                },
            )
        except Exception:
            pass  # Best-effort error notification


async def handle_ivr_speech(session_id: str, transcript: str) -> str:
    """
    Called when Twilio's <Gather> captures speech during IVR phase.
    Uses Mistral to decide what to do, returns TwiML.
    """
    session = await get_queue_session(session_id)
    if not session:
        # Session gone — just hang up
        response = VoiceResponse()
        response.hangup()
        return str(response)

    session.phase = QueuePhase.IVR
    await save_queue_session(session)

    await emit_queue_event(
        session_id,
        "queue_ivr",
        {
            "message": "Navigating phone menu...",
            "heard": transcript[:100],
        },
    )

    # Ask Mistral what to do
    action = await decide_ivr_action(
        transcript=transcript,
        business_name=session.business_name,
        reason=session.reason,
    )

    if action == "HUMAN":
        # Human detected during IVR!
        return await _handle_human_detected(session)

    if action == "HOLD":
        # Transition to hold phase
        session.phase = QueuePhase.HOLD
        session.hold_started_at = datetime.utcnow()
        await save_queue_session(session)
        await emit_queue_event(
            session_id,
            "queue_hold",
            {
                "message": "On hold... waiting for a human",
                "elapsed": 0,
            },
        )
        return generate_hold_loop_twiml(session_id)

    # It's a digit — press it and listen for next menu
    session.ivr_steps_taken.append({
        "heard": transcript[:200],
        "pressed": action,
        "at": datetime.utcnow().isoformat(),
    })
    await save_queue_session(session)

    await emit_queue_event(
        session_id,
        "queue_ivr",
        {
            "message": f"Pressing {action}...",
            "step": len(session.ivr_steps_taken),
        },
    )

    return generate_dtmf_and_listen_twiml(session_id, action)


async def handle_human_check(session_id: str, transcript: str) -> str:
    """
    Called when <Gather> captures speech during hold phase.
    Determines if it's a human or just hold music/automated message.
    """
    session = await get_queue_session(session_id)
    if not session:
        response = VoiceResponse()
        response.hangup()
        return str(response)

    if is_likely_human_speech(transcript):
        return await _handle_human_detected(session)

    # Not a human — keep waiting
    # Update elapsed time
    if session.hold_started_at:
        session.hold_elapsed_seconds = int(
            (datetime.utcnow() - session.hold_started_at).total_seconds()
        )
        await save_queue_session(session, expected_phase=QueuePhase.HOLD)

    return generate_hold_loop_twiml(session_id)


async def _handle_human_detected(session: QueueSession) -> str:
    """Handle the moment a human picks up."""
    session.phase = QueuePhase.HUMAN_DETECTED
    session.human_detected = True
    session.completed_at = datetime.utcnow()
    session.callback_number = session.phone_number

    if session.hold_started_at:
        session.hold_elapsed_seconds = int(
            (datetime.utcnow() - session.hold_started_at).total_seconds()
        )

    await save_queue_session(session)

    await emit_queue_event(
        session.id,
        "queue_human_detected",
        {
            "message": f"A human picked up at {session.business_name}! Call now: {session.phone_number}",
            "phone": session.phone_number,
            "business": session.business_name,
            "hold_time": session.hold_elapsed_seconds,
        },
    )

    # Keep the call alive for a moment so the human doesn't hang up
    # Play a brief message to buy the user time to call back
    response = VoiceResponse()
    response.say(
        "Hello, please hold for just a moment. The person you're calling for will be right with you.",
        voice="Polly.Amy",
        language="en-GB",
    )
    response.pause(length=30)
    response.say(
        "Thank you for waiting. Goodbye.",
        voice="Polly.Amy",
        language="en-GB",
    )
    response.hangup()

    return str(response)


async def cancel_queue(session_id: str) -> bool:
    """Cancel a queue wait — user wants to stop."""
    session = await get_queue_session(session_id)
    if not session:
        return False

    session.phase = QueuePhase.CANCELLED
    session.completed_at = datetime.utcnow()
    await save_queue_session(session)

    await emit_queue_event(
        session_id,
        "queue_failed",
        {
            "message": "Queue cancelled. I've hung up the call.",
            "cancelled": True,
        },
    )

    # Hang up the Twilio call
    await _hangup_call(session)

    return True


async def _hangup_call(session: QueueSession) -> None:
    """Hang up an active Twilio call."""
    if not session.call_sid:
        return

    client = _get_twilio_client()
    if not client:
        return

    try:
        client.calls(session.call_sid).update(status="completed")
        logger.info(f"Hung up queue call: {session.call_sid}")
    except Exception as e:
        logger.error(f"Failed to hang up call {session.call_sid}: {e}")


async def handle_call_status(session_id: str, call_status: str) -> None:
    """Handle Twilio status webhook for queue calls."""
    session = await get_queue_session(session_id)
    if not session:
        return

    logger.info(f"Queue call status: {session_id} -> {call_status}")

    if call_status in ("completed", "busy", "no-answer", "failed", "canceled"):
        # Call ended — if we haven't detected a human, it failed
        if session.phase not in (QueuePhase.HUMAN_DETECTED, QueuePhase.COMPLETED, QueuePhase.CANCELLED):
            session.phase = QueuePhase.FAILED
            error_map = {
                "completed": "Call ended without reaching a human",
                "busy": "Line was busy",
                "no-answer": "No answer",
                "failed": "Call failed to connect",
                "canceled": "Call was cancelled",
            }
            session.error = error_map.get(call_status, "Call ended")
            await save_queue_session(session)
            await emit_queue_event(
                session_id,
                "queue_failed",
                {
                    "message": f"{session.error}. Want me to try again?",
                    "error": session.error,
                },
            )
    elif call_status in ("in-progress", "answered"):
        # Call connected — transition to IVR listening
        if session.phase == QueuePhase.RINGING:
            session.phase = QueuePhase.IVR
            await save_queue_session(session)
            await emit_queue_event(
                session_id,
                "queue_ivr",
                {
                    "message": "Connected! Listening to the phone menu...",
                },
            )
