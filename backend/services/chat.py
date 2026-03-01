"""
Chat service using Mistral via NVIDIA NIM.
Handles general conversation when not routing to specific agents.
"""

import logging
from typing import Optional

from core import get_http_client, settings

logger = logging.getLogger(__name__)

# NVIDIA NIM endpoint
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

SYSTEM_PROMPT = """You are Friendly, a helpful AI assistant that can make real phone calls on behalf of users.

Your capabilities:
- **Blitz**: Find local services (plumbers, electricians, etc.) and call them in parallel to get quotes and availability
- **VibeCoder**: Help users build web apps and landing pages
- **Bounce**: Cancel subscriptions for users (coming soon)
- **Queue**: Wait on hold for users (coming soon)
- **Bid**: Negotiate bills down (coming soon)

Personality:
- Friendly, casual, and helpful
- Concise responses (2-3 sentences max unless explaining something complex)
- Use simple language, no jargon
- Proactively suggest how you can help

When users ask for services, quotes, or availability - guide them to use Blitz by saying something like "find me a plumber" or "get quotes from electricians".

When users want to build something - guide them to VibeCoder.

Do NOT make up information. If you don't know something, say so."""


async def generate_chat_response(
    user_message: str,
    conversation_history: Optional[list] = None,
) -> str:
    """
    Generate a conversational response using Mistral.

    Args:
        user_message: The user's message
        conversation_history: Optional previous messages for context

    Returns:
        The AI's response text
    """
    # Check for API key
    if not settings.nvidia_api_key:
        logger.warning("NVIDIA_API_KEY not set, using fallback response")
        return _fallback_response(user_message)

    try:
        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # Add current message
        messages.append({"role": "user", "content": user_message})

        client = await get_http_client()
        response = await client.post(
            NVIDIA_API_URL,
            headers={
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistralai/mixtral-8x7b-instruct-v0.1",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=30.0,
        )

        response.raise_for_status()
        result = response.json()

        content = result["choices"][0]["message"]["content"].strip()
        logger.info(f"Generated chat response: {content[:100]}...")

        return content

    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        return _fallback_response(user_message)


def _fallback_response(message: str) -> str:
    """Fallback responses when API is unavailable."""
    message = message.lower()

    if any(word in message for word in ["hello", "hi", "hey", "yo"]):
        return "Hey! I'm Friendly. I can help you find services and get quotes by making phone calls. Try saying 'find me a plumber' or 'get quotes for an electrician'."

    elif any(word in message for word in ["help", "what can you do", "how do you work"]):
        return """I'm Friendly, your AI assistant that makes real phone calls!

I can help you with:
- **Blitz**: Find services and get quotes (plumbers, electricians, etc.)
- **VibeCoder**: Build web apps and landing pages

Try: "Find me a plumber who can come tomorrow" or "Build me a landing page" """

    elif any(word in message for word in ["thank", "thanks", "cheers"]):
        return "You're welcome! Let me know if you need anything else."

    elif any(word in message for word in ["bye", "goodbye", "see you"]):
        return "Bye! Come back when you need help finding services or building something."

    else:
        return "I can help you find services (like plumbers or electricians) or build web apps. What do you need?"
