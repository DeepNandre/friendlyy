"""
Intent classification using NVIDIA NIM (Mixtral 8x7B).
Routes user messages to appropriate agents.
"""

import json
import logging
from typing import Optional

from core import settings
from core.mistral import call_mistral, MistralError
from models import AgentType, RouterParams, RouterResult
from services.weave_tracing import traced, log_router_classification

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are a router for Friendly, an AI assistant that makes phone calls on behalf of users.

Classify the user's intent and output ONLY valid JSON:
{"agent": "blitz|build|bounce|queue|bid|inbox|call_friend|chat", "params": {...}, "confidence": 0.0-1.0}

PRIORITY ORDER (check in this order):
1. call_friend: HIGHEST PRIORITY. If user says "call my friend/mate/mom/dad/brother/sister [NAME]" or "ring [NAME]" or "call [NAME] and ask...", this is ALWAYS call_friend, even if the message mentions restaurants, activities, or places. The user wants YOU to call their FRIEND, not search for businesses.
2. blitz: Find services, get quotes, check availability from BUSINESSES (not personal contacts)
3. Other agents as described below

Agents:
- call_friend: Call a specific PERSON (friend, family member, contact by name) with a custom message or question. Keywords: "call my friend", "ring my mate", "call [person's name] and ask", "call my mom/dad/brother/sister". The rest of the message is what to ASK them. Example: "call my friend Alex and ask if they're free for sushi" = call_friend (Alex is the friend, "free for sushi" is the question to ask Alex)
- blitz: Find services, get quotes, check availability from BUSINESSES. This is for finding plumbers, electricians, restaurants, dentists, etc. NOT for calling personal contacts.
- build: Build, create, or make websites, landing pages, portfolios, apps, web pages
- bounce: Cancel subscriptions (Netflix, gym, etc.)
- queue: Wait on hold for someone (HMRC, bank, etc.)
- bid: Negotiate bills lower (Sky, broadband, etc.)
- inbox: Check email, read inbox, email summaries, mail updates
- chat: Greetings, help questions, or general conversation

CRITICAL DISTINCTION:
- "call my friend Alex about sushi" → call_friend (calling a PERSON named Alex)
- "find sushi restaurants" → blitz (searching for BUSINESSES)
- "call Alex and ask if free tomorrow" → call_friend (Alex is a person)
- "find Alex's Plumbing" → blitz (Alex's Plumbing is a business name)

Params for call_friend:
- service: the friend/contact's NAME (e.g., "Alex", "mom", "John")
- action: the question/message to ask them (e.g., "ask if free for sushi tomorrow")
- notes: phone number if provided
- location: where to meet (if mentioned, for context in the message)
- timeframe: when (if mentioned, for context in the message)

Params for blitz:
- service: the type of service/business needed (plumber, restaurant, etc.)
- timeframe: when they need it (today, tomorrow, this week)
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

User: "check my email"
{"agent": "inbox", "params": {"action": "check"}, "confidence": 0.95}

User: "any important emails today?"
{"agent": "inbox", "params": {"action": "check", "timeframe": "today"}, "confidence": 0.95}

User: "what's in my inbox?"
{"agent": "inbox", "params": {"action": "check"}, "confidence": 0.90}

User: "do I have any new mail?"
{"agent": "inbox", "params": {"action": "check"}, "confidence": 0.90}

User: "summarize my emails from this morning"
{"agent": "inbox", "params": {"action": "check", "timeframe": "this morning"}, "confidence": 0.95}

User: "call my friend John and ask if he's free for dinner"
{"agent": "call_friend", "params": {"service": "John", "action": "ask if free for dinner"}, "confidence": 0.98}

User: "call my friend Alex and ask if they're free tomorrow for sushi in Soho"
{"agent": "call_friend", "params": {"service": "Alex", "action": "ask if free tomorrow for sushi in Soho", "location": "Soho", "timeframe": "tomorrow"}, "confidence": 0.98}

User: "ring my mate Sarah, her number is 07123456789, and check if she wants to come to the party"
{"agent": "call_friend", "params": {"service": "Sarah", "notes": "07123456789", "action": "check if wants to come to party"}, "confidence": 0.98}

User: "call my mom and ask about the recipe"
{"agent": "call_friend", "params": {"service": "mom", "action": "ask about the recipe"}, "confidence": 0.98}

User: "can you call Dave for me?"
{"agent": "call_friend", "params": {"service": "Dave"}, "confidence": 0.95}

User: "call my friend Mike and see if he wants to grab pizza in Camden"
{"agent": "call_friend", "params": {"service": "Mike", "action": "see if he wants to grab pizza in Camden", "location": "Camden"}, "confidence": 0.98}

User: "ring my brother and ask when he's arriving"
{"agent": "call_friend", "params": {"service": "brother", "action": "ask when he's arriving"}, "confidence": 0.98}

User: "call Emma and ask if she's free for coffee tomorrow"
{"agent": "call_friend", "params": {"service": "Emma", "action": "ask if free for coffee tomorrow", "timeframe": "tomorrow"}, "confidence": 0.98}

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
    try:
        content = await call_mistral(
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=200,
        )

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
