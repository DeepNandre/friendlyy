"""
Chat service using Mistral via NVIDIA NIM.
Handles general conversation when not routing to specific agents.
"""

import logging
from typing import Optional

from core import get_http_client, settings
from services.weave_tracing import traced, log_chat_response

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
- Be warm, engaging, and conversational — like chatting with a knowledgeable friend
- Give thoughtful, substantive answers. Expand when it helps; keep it tight when a quick reply fits
- Remember context from the conversation and build on it. Reference what the user said earlier when relevant
- Ask clarifying questions when their request is ambiguous
- Use natural language. Avoid jargon unless the user does
- Proactively offer helpful next steps or follow-ups when useful

When users ask for services, quotes, or availability — guide them to Blitz (e.g. "find me a plumber", "get quotes from electricians").
When users want to build something — guide them to VibeCoder.

Do NOT make up information. If you don't know something, say so. Stay helpful and iterative throughout the conversation."""


def _log_chat(*, result, duration, error, args, kwargs, ctx):
    """Log callback for generate_chat_response."""
    user_message = args[0] if args else kwargs.get("user_message", "")
    log_chat_response(
        user_message=user_message,
        response_text=result or "",
        duration=duration,
        success=error is None,
        error=error,
    )


# Map frontend model IDs to NVIDIA NIM model names
# See https://build.nvidia.com/nim for available models
MODEL_MAP = {
    "mistral-nemo": "mistralai/mixtral-8x7b-instruct-v0.1",
    "mixtral-8x7b": "mistralai/mixtral-8x7b-instruct-v0.1",
    "mistral-small": "mistralai/mixtral-8x7b-instruct-v0.1",
    "devstral-small": "mistralai/mixtral-8x7b-instruct-v0.1",
}


@traced("generate_chat_response", log_fn=_log_chat)
async def generate_chat_response(
    user_message: str,
    conversation_history: Optional[list] = None,
    model_id: Optional[str] = None,
) -> str:
    """
    Generate a conversational response using Mistral.

    Args:
        user_message: The user's message
        conversation_history: Optional previous messages for context
        model_id: Frontend model ID (mistral-nemo, mixtral-8x7b, etc.)

    Returns:
        The AI's response text
    """
    # Check for API key
    if not settings.nvidia_api_key:
        logger.warning("NVIDIA_API_KEY not set, using fallback response")
        return _fallback_response(user_message)

    # Resolve model - use Mistral API if available for some models, else NVIDIA NIM
    api_url = NVIDIA_API_URL
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    nim_model = MODEL_MAP.get(model_id or "mixtral-8x7b", "mistralai/mixtral-8x7b-instruct-v0.1")

    try:
        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history - last 12 messages (6 exchanges) for richer context
        if conversation_history:
            for msg in conversation_history[-12:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content.strip():
                    messages.append({"role": role, "content": content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        client = await get_http_client()
        response = await client.post(
            api_url,
            headers=headers,
            json={
                "model": nim_model,
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 1024,
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
