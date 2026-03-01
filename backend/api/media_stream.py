"""
Twilio Media Streams WebSocket endpoint.

Handles real-time audio streaming between Twilio and ElevenLabs Conversational AI.
"""

import asyncio
import base64
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.config import settings
from core.redis_client import push_event
from services.elevenlabs_conversation import (
    create_conversation_session,
    close_conversation_session,
    generate_conversation_prompt,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/media-stream/{session_id}/{call_id}")
async def media_stream_websocket(
    websocket: WebSocket,
    session_id: str,
    call_id: str,
):
    """
    WebSocket endpoint for Twilio Media Streams.

    Twilio connects here when a call starts with <Stream>.
    We bridge audio to ElevenLabs Conversational AI for real-time conversation.
    """
    await websocket.accept()
    logger.info(f"[Media Stream] WebSocket connected: {session_id}/{call_id}")

    # Get call details from query params or session
    service_type = websocket.query_params.get("service", "service provider")
    timeframe = websocket.query_params.get("timeframe", "soon")

    # Generate conversation prompts
    system_prompt, first_message = generate_conversation_prompt(
        service_type=service_type,
        timeframe=timeframe,
    )

    # Create ElevenLabs conversation session
    # Note: You need to create an agent in ElevenLabs dashboard first
    # and set ELEVENLABS_AGENT_ID in environment
    agent_id = settings.elevenlabs_agent_id if hasattr(settings, 'elevenlabs_agent_id') else None

    if not agent_id:
        logger.warning("[Media Stream] ELEVENLABS_AGENT_ID not configured, using demo mode")
        # In demo mode, just acknowledge and close
        await push_event(
            session_id,
            {
                "event": "transcript",
                "data": {
                    "call_id": call_id,
                    "speaker": "system",
                    "text": "Live conversation mode not configured. Please set ELEVENLABS_AGENT_ID.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        await websocket.close()
        return

    conversation = await create_conversation_session(
        session_id=session_id,
        call_id=call_id,
        agent_id=agent_id,
        system_prompt=system_prompt,
        first_message=first_message,
    )

    if not conversation:
        logger.error("[Media Stream] Failed to create conversation session")
        await websocket.close()
        return

    stream_sid = None

    async def send_audio_to_twilio(audio_data: bytes):
        """Send audio from ElevenLabs back to Twilio."""
        if websocket.client_state != WebSocketState.CONNECTED:
            return

        if not stream_sid:
            return

        # Twilio expects mulaw audio in base64
        media_message = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(audio_data).decode("utf-8"),
            },
        }

        try:
            await websocket.send_json(media_message)
        except Exception as e:
            logger.warning(f"[Media Stream] Failed to send audio to Twilio: {e}")

    # Start listening to ElevenLabs in background
    elevenlabs_task = asyncio.create_task(
        conversation.listen_to_elevenlabs(send_audio_to_twilio)
    )

    try:
        while True:
            # Receive message from Twilio
            data = await websocket.receive_text()
            message = json.loads(data)

            event = message.get("event")

            if event == "start":
                stream_sid = message.get("start", {}).get("streamSid")
                logger.info(f"[Media Stream] Stream started: {stream_sid}")

                await push_event(
                    session_id,
                    {
                        "event": "transcript",
                        "data": {
                            "call_id": call_id,
                            "speaker": "system",
                            "text": "Call connected. AI is now speaking...",
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif event == "media":
                # Forward audio to ElevenLabs
                await conversation.handle_twilio_message(message)

            elif event == "stop":
                logger.info(f"[Media Stream] Stream stopped: {stream_sid}")
                break

    except WebSocketDisconnect:
        logger.info(f"[Media Stream] WebSocket disconnected: {session_id}/{call_id}")

    except Exception as e:
        logger.error(f"[Media Stream] Error: {e}")

    finally:
        # Cleanup
        elevenlabs_task.cancel()
        try:
            await elevenlabs_task
        except asyncio.CancelledError:
            pass

        await close_conversation_session(session_id, call_id)

        await push_event(
            session_id,
            {
                "event": "transcript",
                "data": {
                    "call_id": call_id,
                    "speaker": "system",
                    "text": "Call ended.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"[Media Stream] Session cleanup complete: {session_id}/{call_id}")
