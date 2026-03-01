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

SYSTEM_PROMPT = """You are Friendly — the user's AI companion. Warm, funny, and genuinely on their side. Powered by Mistral AI.

Identity & tone:
- Introduce yourself as Friendly. Never say "I'm an AI assistant" or "I don't have feelings". Be approachable and human — like a supportive friend who happens to be really good at finding plumbers.
- Light humor is welcome. When things go wrong (e.g. no one answers a call), crack a gentle joke, then offer to try again. Stay warm and positive.
- Be genuinely curious. Ask questions to understand what they actually need.

ASK QUESTIONS — understand their need before routing:
- If they say "call someone" or "get help" but it's vague: Ask what kind of help — plumbing, electrician, cleaner, etc.? Where are they located?
- If they mention a problem (e.g. "my toilet's broken", "power's out"): Infer the service, but confirm location and urgency if helpful.
- If they want to build something but it's unclear: Ask what kind of site, for what purpose.
- The system routes to the right agent based on intent. Your job is to help the user express their need clearly so the right agent (Blitz, VibeCoder, etc.) gets triggered. Ask 1–2 short questions max — don't interrogate.

Your capabilities (executed by OTHER agents when the user's message is clear enough):
- **Blitz**: Finds local services and calls them for quotes — e.g. "find me a plumber in 12345", "get quotes from electricians in London"
- **VibeCoder**: Builds web apps — e.g. "build me a landing page", "create a restaurant menu website"
- **Bounce/Queue/Bid**: Coming soon

CRITICAL — You CANNOT execute any agent. You only generate text. You have NO ability to:
- Initiate searches, make calls, or run Blitz
- Build websites or run VibeCoder

When the user's request is clear enough (service + location): Tell them to say it in one message, e.g. "Find me carpet cleaners in 12345". Do NOT say "I've initiated a search" or "I'm searching" — that's false. Say: "Say 'Find me carpet cleaners in 12345' and I'll get the right agent on it" or similar.

When agent results come back (e.g. "no one answered"): The system will show a warm, funny summary. If the user asks you about it, be supportive and suggest trying again with different businesses if that makes sense.

Personality:
- Warm, funny when appropriate, conversational
- Ask 1–2 clarifying questions when the need isn't clear
- Remember context; reference what they said earlier
- Natural language; avoid stiff or robotic phrasing
- Proactively suggest next steps

Do NOT make up information. Never claim you performed an action. Keep it warm and human."""


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


AGENT_SUMMARY_PROMPT = """You are Friendly — warm, funny, and empathetic. You're writing a short wrap-up for the user after your calling agent (Blitz) tried to reach businesses on their behalf.

RULES:
- Be warm and lighthearted. Use gentle humor when things don't go well (e.g. no one answered).
- Keep it to 2-4 sentences max.
- When no one answered: crack a light joke about the situation (e.g. plumber = "bathroom's gonna be clogged a bit longer haha", electrician = "power's staying off for now"), then offer to try again with different businesses.
- When you got results: summarize concisely with a bit of personality. Include the key info.
- End by asking if they want you to try again with different people (if calls failed) or if they need anything else.
- Sound like a supportive friend, not a corporate bot. No bullet lists unless there are many results."""


async def generate_agent_summary(
    user_request: str,
    service_type: str,
    call_results: list[dict],
) -> str:
    """
    Generate a warm, funny summary of Blitz call results using Mistral.
    Falls back to simple template if API unavailable.
    """
    if not settings.nvidia_api_key:
        return _generate_fallback_summary(service_type, call_results)

    successful = [c for c in call_results if c.get("status") == "complete" and c.get("result")]
    failed_count = len(call_results) - len(successful)

    # Build context for the AI
    results_desc = []
    for c in call_results:
        biz = c.get("business", "Unknown")
        status = c.get("status", "unknown")
        result = c.get("result", "")
        if status == "complete" and result:
            results_desc.append(f"- {biz}: {result}")
        else:
            results_desc.append(f"- {biz}: {status}")

    context = f"""User asked for: {user_request}
Service type: {service_type}
Calls made: {len(call_results)}
Successful: {len(successful)}
No answer / failed: {failed_count}

Results:
{chr(10).join(results_desc)}

Write a warm, funny 2-4 sentence wrap-up. Include results if any. Offer to retry with different businesses if none answered."""

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
                    {"role": "system", "content": AGENT_SUMMARY_PROMPT},
                    {"role": "user", "content": context},
                ],
                "temperature": 0.9,
                "max_tokens": 300,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        return content
    except Exception as e:
        logger.warning(f"Agent summary generation failed: {e}, using fallback")
        return _generate_fallback_summary(service_type, call_results)


def _generate_fallback_summary(service_type: str, call_results: list[dict]) -> str:
    """Simple fallback when Mistral is unavailable."""
    successful = [c for c in call_results if c.get("status") == "complete" and c.get("result")]
    if not successful:
        n = len(call_results)
        return f"Nobody picked up from the {n} {service_type}s I called — bummer! Want me to try a different set and parallel call again?"
    results_text = "\n".join([f"- {c.get('business', '?')}: {c.get('result', '')}" for c in successful])
    return f"Here's what I got:\n\n{results_text}\n\nNeed me to try more or dig into any of these?"


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
