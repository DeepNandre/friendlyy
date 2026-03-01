"""
ElevenLabs Conversational AI integration for real-time phone conversations.

Bridges Twilio Media Streams to ElevenLabs Conversational AI via WebSocket.
Provides live transcription of both AI and human speech.

Flow:
1. Twilio call connects → Media Stream WebSocket to our server
2. We connect to ElevenLabs Conversational AI WebSocket
3. Audio flows: Twilio → Us → ElevenLabs → Us → Twilio
4. Transcripts emitted via SSE to frontend
"""

import asyncio
import base64
import json
import logging
from typing import Optional, Callable, Awaitable
from datetime import datetime

import websockets

from core.config import settings
from core.redis_client import push_event

logger = logging.getLogger(__name__)

# ElevenLabs Conversational AI WebSocket endpoint
ELEVENLABS_CONV_WS_URL = "wss://api.elevenlabs.io/v1/convai/conversation"


class ConversationSession:
    """
    Manages a single phone conversation between Twilio and ElevenLabs.

    Handles:
    - WebSocket connection to ElevenLabs
    - Audio streaming (Twilio mulaw → ElevenLabs PCM → Twilio mulaw)
    - Transcript capture and SSE emission
    """

    def __init__(
        self,
        session_id: str,
        call_id: str,
        agent_id: str,
        system_prompt: str,
        first_message: str,
    ):
        self.session_id = session_id
        self.call_id = call_id
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.first_message = first_message

        self.elevenlabs_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.twilio_ws = None
        self.stream_sid: Optional[str] = None
        self.is_connected = False
        self.transcripts: list = []

    async def connect_to_elevenlabs(self) -> bool:
        """Establish WebSocket connection to ElevenLabs Conversational AI."""
        try:
            url = f"{ELEVENLABS_CONV_WS_URL}?agent_id={self.agent_id}"

            headers = {
                "xi-api-key": settings.elevenlabs_api_key,
            }

            self.elevenlabs_ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10,
            )

            # Send initialization with system prompt and first message
            init_message = {
                "type": "conversation_initiation_client_data",
                "conversation_config_override": {
                    "agent": {
                        "prompt": {
                            "prompt": self.system_prompt,
                        },
                        "first_message": self.first_message,
                    },
                    "tts": {
                        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel
                    },
                },
            }

            await self.elevenlabs_ws.send(json.dumps(init_message))
            self.is_connected = True

            logger.info(f"[ElevenLabs Conv] Connected for session {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"[ElevenLabs Conv] Connection failed: {e}")
            return False

    async def handle_twilio_message(self, message: dict) -> Optional[bytes]:
        """
        Process incoming Twilio Media Stream message.

        Returns audio bytes to send back to Twilio, if any.
        """
        event = message.get("event")

        if event == "start":
            self.stream_sid = message.get("start", {}).get("streamSid")
            logger.info(f"[Twilio Stream] Started: {self.stream_sid}")

            # Emit transcript event
            await self._emit_transcript("system", "Call connected, AI is speaking...")

        elif event == "media":
            # Forward audio to ElevenLabs
            if self.elevenlabs_ws and self.is_connected:
                payload = message.get("media", {}).get("payload", "")
                audio_data = base64.b64decode(payload)

                # Send as user audio chunk
                audio_message = {
                    "type": "user_audio_chunk",
                    "audio_chunk": base64.b64encode(audio_data).decode("utf-8"),
                }

                try:
                    await self.elevenlabs_ws.send(json.dumps(audio_message))
                except Exception as e:
                    logger.warning(f"[ElevenLabs Conv] Failed to send audio: {e}")

        elif event == "stop":
            logger.info(f"[Twilio Stream] Stopped: {self.stream_sid}")
            await self.close()

        return None

    async def handle_elevenlabs_message(self, message: dict) -> Optional[bytes]:
        """
        Process incoming ElevenLabs Conversational AI message.

        Returns audio bytes to send to Twilio, if any.
        """
        msg_type = message.get("type")

        if msg_type == "audio":
            # Audio from AI - forward to Twilio
            audio_b64 = message.get("audio", "")
            return base64.b64decode(audio_b64)

        elif msg_type == "user_transcript":
            # Human (business) speaking
            transcript = message.get("transcript", "")
            is_final = message.get("is_final", False)

            if is_final and transcript.strip():
                await self._emit_transcript("human", transcript)
                self.transcripts.append({
                    "role": "human",
                    "text": transcript,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        elif msg_type == "agent_response":
            # AI speaking
            response = message.get("response", "")

            if response.strip():
                await self._emit_transcript("ai", response)
                self.transcripts.append({
                    "role": "ai",
                    "text": response,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        elif msg_type == "conversation_end":
            logger.info(f"[ElevenLabs Conv] Conversation ended for {self.session_id}")
            await self._emit_transcript("system", "Conversation ended")

        elif msg_type == "error":
            error = message.get("message", "Unknown error")
            logger.error(f"[ElevenLabs Conv] Error: {error}")
            await self._emit_transcript("error", error)

        return None

    async def _emit_transcript(self, speaker: str, text: str):
        """Emit transcript event to SSE stream."""
        await push_event(
            self.session_id,
            {
                "event": "transcript",
                "data": {
                    "call_id": self.call_id,
                    "speaker": speaker,  # "ai", "human", "system", "error"
                    "text": text,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def listen_to_elevenlabs(self, send_to_twilio: Callable[[bytes], Awaitable[None]]):
        """
        Listen for messages from ElevenLabs and forward audio to Twilio.

        Args:
            send_to_twilio: Callback to send audio data to Twilio WebSocket
        """
        if not self.elevenlabs_ws:
            return

        try:
            async for message in self.elevenlabs_ws:
                try:
                    data = json.loads(message)
                    audio = await self.handle_elevenlabs_message(data)

                    if audio:
                        await send_to_twilio(audio)

                except json.JSONDecodeError:
                    logger.warning("[ElevenLabs Conv] Invalid JSON received")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[ElevenLabs Conv] Connection closed for {self.session_id}")
        except Exception as e:
            logger.error(f"[ElevenLabs Conv] Listen error: {e}")

    async def close(self):
        """Close all connections."""
        self.is_connected = False

        if self.elevenlabs_ws:
            try:
                await self.elevenlabs_ws.close()
            except:
                pass
            self.elevenlabs_ws = None

        logger.info(f"[ElevenLabs Conv] Session closed: {self.session_id}")


# Store active conversation sessions
_active_sessions: dict[str, ConversationSession] = {}


def get_conversation_session(session_id: str) -> Optional[ConversationSession]:
    """Get an active conversation session."""
    return _active_sessions.get(session_id)


async def create_conversation_session(
    session_id: str,
    call_id: str,
    agent_id: str,
    system_prompt: str,
    first_message: str,
) -> Optional[ConversationSession]:
    """
    Create a new conversation session for a phone call.

    Args:
        session_id: Blitz session ID
        call_id: Individual call ID
        agent_id: ElevenLabs agent ID
        system_prompt: System prompt for the AI
        first_message: First message AI should say

    Returns:
        ConversationSession if successful, None otherwise
    """
    session = ConversationSession(
        session_id=session_id,
        call_id=call_id,
        agent_id=agent_id,
        system_prompt=system_prompt,
        first_message=first_message,
    )

    if await session.connect_to_elevenlabs():
        _active_sessions[f"{session_id}:{call_id}"] = session
        return session

    return None


async def close_conversation_session(session_id: str, call_id: str):
    """Close and remove a conversation session."""
    key = f"{session_id}:{call_id}"
    session = _active_sessions.pop(key, None)

    if session:
        await session.close()


def generate_conversation_prompt(
    service_type: str,
    timeframe: Optional[str] = None,
    question: str = "availability and pricing",
) -> tuple[str, str]:
    """
    Generate system prompt and first message for the AI conversation.

    Returns:
        (system_prompt, first_message)
    """
    timeframe_text = timeframe or "as soon as possible"

    system_prompt = f"""You are a friendly AI assistant calling on behalf of a customer.
You are speaking to a {service_type} business.
Your goal is to inquire about their {question} for a customer who needs service {timeframe_text}.

Guidelines:
- Be polite and professional
- Ask about availability and pricing
- If they ask for contact details, say the customer will call back
- Keep the conversation brief (under 2 minutes)
- Thank them at the end
- If it's a voicemail or answering machine, leave a brief message and hang up

Important: You are on a phone call. Speak naturally and conversationally."""

    first_message = f"""Hello! I'm calling on behalf of a customer who's looking for a {service_type}.
They'd like to know about your availability and pricing.
Do you have a moment to help?"""

    return system_prompt, first_message
