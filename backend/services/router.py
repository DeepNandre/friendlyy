"""
Intent classification using NVIDIA NIM (Mixtral 8x7B).
Routes user messages to appropriate agents.
"""

import json
import logging
from typing import Optional

from core import get_http_client, settings
from models import AgentType, RouterParams, RouterResult
from services.weave_tracing import traced, log_router_classification

logger = logging.getLogger(__name__)

# NVIDIA NIM endpoint for Mixtral 8x7B
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

ROUTER_SYSTEM_PROMPT = """You are a router for Friendly, an AI assistant that makes phone calls on behalf of users.

Classify the user's intent and output ONLY valid JSON:
{"agent": "blitz|build|bounce|queue|bid|chat", "params": {...}, "confidence": 0.0-1.0}

Agents:
- blitz: Find services, get quotes, check availability. ANY request to find, locate, search for, or get quotes from a service provider is blitz. This includes plumbers, electricians, cleaners, locksmiths, restaurants, dentists, mechanics, movers, tutors, painters, gardeners, and ANY other service.
- build: Build, create, or make websites, landing pages, portfolios, apps, web pages
- bounce: Cancel subscriptions (Netflix, gym, etc.)
- queue: Wait on hold for someone (HMRC, bank, etc.)
- bid: Negotiate bills lower (Sky, broadband, etc.)
- chat: ONLY for greetings, help questions, or messages that don't involve finding/calling any service

IMPORTANT: If the user mentions ANY service they want to find, get quotes from, or check availability for, classify as blitz. When in doubt between blitz and chat, choose blitz.

Params for blitz:
- service: the type of service needed (plumber, electrician, locksmith, etc.)
- timeframe: when they need it (today, tomorrow, this week, urgent, ASAP)
- location: where they need it (city, area, postcode)
- action: what they want (quote, book, find, availability)
- notes: any extra details mentioned

Params for build:
- service: type of site (landing page, portfolio, restaurant menu, coming soon, etc.)
- notes: description of what to build, business name, style preferences, content details

Examples:
User: "find me a plumber who can come tomorrow"
{"agent": "blitz", "params": {"service": "plumber", "timeframe": "tomorrow"}, "confidence": 0.95}

User: "I need an electrician in Manchester urgently"
{"agent": "blitz", "params": {"service": "electrician", "location": "Manchester", "timeframe": "urgent"}, "confidence": 0.95}

User: "find cleaners near me"
{"agent": "blitz", "params": {"service": "cleaners", "action": "find"}, "confidence": 0.95}

User: "was planning to find cleaners near me"
{"agent": "blitz", "params": {"service": "cleaners", "action": "find"}, "confidence": 0.90}

User: "get quotes for bathroom cleaning in Wembley"
{"agent": "blitz", "params": {"service": "bathroom cleaning", "location": "Wembley", "action": "quote"}, "confidence": 0.95}

User: "I need to get my carpets cleaned, can you find a reliable service?"
{"agent": "blitz", "params": {"service": "carpet cleaning", "action": "find"}, "confidence": 0.95}

User: "find carpet cleaners in 12345"
{"agent": "blitz", "params": {"service": "carpet cleaning", "location": "12345", "action": "find"}, "confidence": 0.95}

User: "looking for a locksmith in London"
{"agent": "blitz", "params": {"service": "locksmith", "location": "London", "action": "find"}, "confidence": 0.95}

User: "can you find me a good dentist?"
{"agent": "blitz", "params": {"service": "dentist", "action": "find"}, "confidence": 0.90}

User: "I want to get my car fixed"
{"agent": "blitz", "params": {"service": "mechanic", "action": "find"}, "confidence": 0.85}

User: "make me a landing page for my dog walking business"
{"agent": "build", "params": {"service": "landing page", "notes": "dog walking business"}, "confidence": 0.95}

User: "build me a portfolio website, I'm a photographer"
{"agent": "build", "params": {"service": "portfolio", "notes": "photographer portfolio"}, "confidence": 0.95}

User: "create a coming soon page for my app called Friendly"
{"agent": "build", "params": {"service": "coming soon page", "notes": "app called Friendly"}, "confidence": 0.95}

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


def _log_classify(*, result, duration, error, args, kwargs, ctx):
    """Log callback for classify_intent — extracts domain data from result."""
    user_message = args[0] if args else kwargs.get("user_message", "")
    if result:
        log_router_classification(
            user_message=user_message,
            classified_agent=result.agent.value,
            confidence=result.confidence,
            duration=duration,
            params=result.params.model_dump() if result.params else None,
        )
    else:
        log_router_classification(
            user_message=user_message,
            classified_agent="chat",
            confidence=0.5,
            duration=duration,
        )


@traced("classify_intent", log_fn=_log_classify)
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
                "model": "mistralai/mixtral-8x7b-instruct-v0.1",
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
