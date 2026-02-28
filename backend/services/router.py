"""
Intent classification using NVIDIA NIM (Mistral Large).
Routes user messages to appropriate agents.
"""

import json
import logging
from typing import Optional

from core import get_http_client, settings
from models import AgentType, RouterParams, RouterResult

logger = logging.getLogger(__name__)

# NVIDIA NIM endpoint for Mistral Large
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

ROUTER_SYSTEM_PROMPT = """You are a router for Friendly, an AI assistant that makes phone calls on behalf of users.

Classify the user's intent and output ONLY valid JSON:
{"agent": "blitz|bounce|queue|bid|chat", "params": {...}, "confidence": 0.0-1.0}

Agents:
- blitz: Find services, get quotes, check availability (plumber, electrician, restaurant, etc.)
- bounce: Cancel subscriptions (Netflix, gym, etc.)
- queue: Wait on hold for someone (HMRC, bank, etc.)
- bid: Negotiate bills lower (Sky, broadband, etc.)
- chat: General conversation, greetings, help, questions about the service

Params for blitz:
- service: the type of service needed (plumber, electrician, locksmith, etc.)
- timeframe: when they need it (today, tomorrow, this week, urgent, ASAP)
- location: where they need it (city, area, postcode)
- action: what they want (quote, book, find, availability)
- notes: any extra details mentioned

Examples:
User: "find me a plumber who can come tomorrow"
{"agent": "blitz", "params": {"service": "plumber", "timeframe": "tomorrow"}, "confidence": 0.95}

User: "I need an electrician in Manchester urgently"
{"agent": "blitz", "params": {"service": "electrician", "location": "Manchester", "timeframe": "urgent"}, "confidence": 0.95}

User: "cancel my Netflix subscription"
{"agent": "bounce", "params": {"service": "Netflix", "action": "cancel"}, "confidence": 0.98}

User: "call HMRC and wait on hold for me"
{"agent": "queue", "params": {"service": "HMRC", "action": "wait"}, "confidence": 0.95}

User: "negotiate my Sky bill down"
{"agent": "bid", "params": {"service": "Sky", "action": "negotiate"}, "confidence": 0.95}

User: "hello"
{"agent": "chat", "params": {"type": "greeting"}, "confidence": 1.0}

User: "what can you do?"
{"agent": "chat", "params": {"type": "help"}, "confidence": 1.0}

Output ONLY the JSON, no explanation or markdown."""


async def classify_intent(user_message: str) -> RouterResult:
    """
    Classify user intent using Mistral Large via NVIDIA NIM.

    Falls back to 'chat' agent if:
    - API call fails
    - Response can't be parsed
    - No API key configured

    Args:
        user_message: The user's input message

    Returns:
        RouterResult with agent type, params, and confidence
    """
    # Check for API key
    if not settings.nvidia_api_key:
        logger.warning("NVIDIA_API_KEY not set, falling back to chat")
        return RouterResult(
            agent=AgentType.CHAT,
            params=RouterParams(),
            confidence=0.5,
        )

    try:
        client = await get_http_client()
        response = await client.post(
            NVIDIA_API_URL,
            headers={
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistralai/mistral-large-2-instruct",
                "messages": [
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,  # Low temperature for consistency
                "max_tokens": 200,
            },
        )

        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()

        # Parse JSON response
        parsed = _parse_router_response(content)
        logger.info(
            f"Router classified '{user_message[:50]}...' as {parsed.agent.value}"
        )
        return parsed

    except Exception as e:
        logger.error(f"Router classification failed: {e}")
        return RouterResult(
            agent=AgentType.CHAT,
            params=RouterParams(),
            confidence=0.5,
        )


def _parse_router_response(content: str) -> RouterResult:
    """
    Parse the router's JSON response.

    Handles potential markdown code blocks and malformed JSON.
    """
    # Remove markdown code blocks if present
    if "```" in content:
        # Extract content between code blocks
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

    # Try to parse JSON
    try:
        parsed = json.loads(content)
        agent_str = parsed.get("agent", "chat").lower()

        # Validate agent type
        try:
            agent = AgentType(agent_str)
        except ValueError:
            agent = AgentType.CHAT

        # Parse params
        params_dict = parsed.get("params", {})
        params = RouterParams(**params_dict)

        # Get confidence
        confidence = float(parsed.get("confidence", 1.0))
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

        return RouterResult(
            agent=agent,
            params=params,
            confidence=confidence,
        )

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to parse router response: {e}")
        return RouterResult(
            agent=AgentType.CHAT,
            params=RouterParams(),
            confidence=0.5,
        )
