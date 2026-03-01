"""
Call Friend agent - calls a friend/contact on behalf of the user.

Uses ElevenLabs Conversational AI for natural conversation.
The AI introduces itself, explains it's calling on behalf of the user,
asks the user's question, and reports back the friend's response.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from core import settings
from core.redis_client import save_session, get_session, push_event
from core.events import emit_event
from models import CallFriendPhase, CallFriendSession

logger = logging.getLogger(__name__)


async def get_call_friend_session(session_id: str) -> Optional[CallFriendSession]:
    """Get current session state from Redis."""
    data = await get_session(session_id)
    if data:
        return CallFriendSession.from_dict(data)
    return None


async def save_call_friend_session(session: CallFriendSession) -> None:
    """Save session state to Redis."""
    await save_session(session.id, session.to_dict())


async def run_call_friend_workflow(
    session_id: str,
    friend_name: str,
    phone_number: str,
    question: str,
) -> CallFriendSession:
    """
    Run the call friend workflow:
    1. Initiate call to friend via Twilio
    2. Use ElevenLabs Conversational AI to have a natural conversation
    3. Capture the friend's response
    4. Report back to user

    Args:
        session_id: Session ID to use
        friend_name: Name of the friend to call
        phone_number: Phone number to call
        question: What to ask the friend

    Returns:
        CallFriendSession with results
    """
    # Create session
    session = CallFriendSession(
        id=session_id,
        friend_name=friend_name,
        phone_number=phone_number,
        question=question,
    )

    await save_call_friend_session(session)

    try:
        # Emit initial status
        await emit_event(
            session.id,
            "status",
            {
                "phase": "initiating",
                "message": f"Calling {friend_name}...",
                "friend_name": friend_name,
            },
        )

        # Initiate the call
        call_sid = await _initiate_call(session)

        if not call_sid:
            session.phase = CallFriendPhase.FAILED
            session.error = "Failed to initiate call"
            await emit_event(
                session.id,
                "error",
                {"message": "Failed to initiate call. Please check the phone number."},
            )
            await save_call_friend_session(session)
            return session

        session.call_sid = call_sid
        session.phase = CallFriendPhase.RINGING
        await save_call_friend_session(session)

        await emit_event(
            session.id,
            "call_started",
            {
                "phase": "ringing",
                "message": f"Ringing {friend_name}...",
                "friend_name": friend_name,
            },
        )

        # Wait for call to complete (with timeout)
        await _wait_for_call_completion(session, timeout=180)  # 3 minute max

        # Generate summary if we got a response
        if session.transcript:
            session.summary = await _generate_call_summary(session)

        # Emit completion
        await emit_event(
            session.id,
            "session_complete",
            {
                "phase": session.phase.value,
                "summary": session.summary,
                "response": session.response,
                "transcript": session.transcript,
                "friend_name": friend_name,
            },
        )

        await save_call_friend_session(session)
        return session

    except Exception as e:
        logger.error(f"Call friend workflow error: {e}")
        session.phase = CallFriendPhase.FAILED
        session.error = str(e)
        await emit_event(session.id, "error", {"message": str(e)})
        await save_call_friend_session(session)
        raise


async def _initiate_call(session: CallFriendSession) -> Optional[str]:
    """
    Initiate the phone call via Twilio.

    Returns:
        Call SID if successful, None otherwise
    """
    from services.twilio_caller import get_twilio_client

    client = get_twilio_client()
    if not client:
        logger.error("Twilio not configured")
        return None

    try:
        call = client.calls.create(
            to=session.phone_number,
            from_=settings.twilio_phone_number,
            url=f"{settings.backend_url}/api/call_friend/twiml/{session.id}",
            status_callback=f"{settings.backend_url}/api/call_friend/webhook?session_id={session.id}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            timeout=45,
            record=True,
            recording_status_callback=f"{settings.backend_url}/api/call_friend/recording?session_id={session.id}",
            machine_detection="Enable",
            async_amd=True,
            async_amd_status_callback=f"{settings.backend_url}/api/call_friend/amd?session_id={session.id}",
            async_amd_status_callback_method="POST",
        )

        logger.info(f"Call initiated to {session.friend_name}: {call.sid}")
        return call.sid

    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        return None


async def _wait_for_call_completion(session: CallFriendSession, timeout: int = 180) -> None:
    """
    Wait for the call to complete by polling Redis.

    Args:
        session: The call friend session
        timeout: Maximum seconds to wait
    """
    start = datetime.utcnow()

    while True:
        # Refresh from Redis
        current = await get_call_friend_session(session.id)
        if current:
            session.phase = current.phase
            session.transcript = current.transcript
            session.response = current.response
            session.recording_url = current.recording_url

        # Check if call is done
        if session.phase in [
            CallFriendPhase.COMPLETE,
            CallFriendPhase.FAILED,
            CallFriendPhase.NO_ANSWER,
        ]:
            break

        # Check timeout
        elapsed = (datetime.utcnow() - start).total_seconds()
        if elapsed > timeout:
            logger.warning(f"Call friend session {session.id} timed out")
            session.phase = CallFriendPhase.FAILED
            session.error = "Call timed out"
            break

        await asyncio.sleep(2)


async def _generate_call_summary(session: CallFriendSession) -> str:
    """
    Generate a friendly summary of the call for the user.

    Args:
        session: The completed call session

    Returns:
        Human-friendly summary string
    """
    from services.chat import generate_chat_response

    # Build transcript text
    transcript_text = "\n".join(
        f"{t.get('role', 'unknown')}: {t.get('text', '')}"
        for t in session.transcript
    )

    prompt = f"""I just called {session.friend_name} on behalf of a user to ask: "{session.question}"

Here's the conversation transcript:
{transcript_text}

Please write a brief, friendly summary (2-3 sentences) telling the user what {session.friend_name} said.
Be warm and conversational. Start with something like "{session.friend_name} said..." or "Great news!" or "I spoke with {session.friend_name}..."
"""

    try:
        summary = await generate_chat_response(prompt)
        return summary
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        # Fallback summary
        if session.response:
            return f"I spoke with {session.friend_name}. They said: {session.response}"
        return f"I called {session.friend_name} but couldn't get a clear response. You might want to try calling them directly."


def generate_call_friend_twiml(session: CallFriendSession) -> str:
    """
    Generate TwiML for the call friend conversation.

    Uses Media Streams + ElevenLabs Conversational AI for natural dialogue.

    Args:
        session: The call friend session

    Returns:
        TwiML XML string
    """
    response = VoiceResponse()

    # Build WebSocket URL for Media Streams
    ws_url = settings.backend_url.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/api/call_friend/media-stream/{session.id}"

    # Start bidirectional media stream
    start = response.start()
    start.stream(
        url=stream_url,
        track="both_tracks",
    )

    # Keep the call alive while streaming (max 3 minutes)
    response.pause(length=180)

    return str(response)


def generate_call_friend_prompt(session: CallFriendSession) -> tuple[str, str]:
    """
    Generate the system prompt and first message for ElevenLabs Conversational AI.

    Args:
        session: The call friend session

    Returns:
        (system_prompt, first_message)
    """
    system_prompt = f"""You are a friendly AI assistant making a phone call on behalf of someone.
You are calling {session.friend_name}. Your goal is to deliver a message and get a response.

The person who asked you to call wants to know: {session.question}

Guidelines:
- Introduce yourself naturally: "Hi! I'm calling on behalf of your friend"
- Explain you're an AI assistant making this call for them
- Ask the question clearly and conversationally
- Listen to their response and acknowledge it
- Thank them for their time
- Keep the call brief and friendly (under 2 minutes)
- If they seem confused, briefly explain that their friend asked you to call
- If it's a voicemail, leave a brief message asking them to call their friend back

Important: Be warm, natural, and conversational. You're helping connect friends!"""

    first_message = f"""Hi there! Is this {session.friend_name}?
I'm calling on behalf of your friend. They asked me to reach out to you with a quick question - {session.question}"""

    return system_prompt, first_message
