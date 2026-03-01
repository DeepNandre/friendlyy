"""
Shared Mistral LLM utility via NVIDIA NIM.

Single place for all Mistral API calls — used by router, chat, inbox,
and any future agent that needs LLM completions. Eliminates duplication
of HTTP plumbing, auth, response parsing, and error handling.
"""

import json
import logging
from typing import Optional, Union

from core.config import settings
from core.http_client import get_http_client

logger = logging.getLogger(__name__)

# NVIDIA NIM endpoint for Mistral models
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

DEFAULT_MODEL = "mistralai/mixtral-8x7b-instruct-v0.1"


def _strip_markdown_fences(content: str) -> str:
    """Remove markdown code fences (```json ... ```) from LLM output."""
    if "```" not in content:
        return content
    parts = content.split("```")
    if len(parts) >= 2:
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        return inner.strip()
    return content.strip()


async def call_mistral(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 800,
    timeout: float = 30.0,
    parse_json: bool = False,
) -> Union[str, dict]:
    """
    Call Mistral via NVIDIA NIM and return the response content.

    Args:
        messages: Chat messages (system + user + optional history)
        model: NVIDIA NIM model identifier
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum response tokens
        timeout: HTTP request timeout in seconds
        parse_json: If True, parse response as JSON and return dict.
                    Returns raw string on parse failure.

    Returns:
        Response content as str, or parsed dict if parse_json=True.

    Raises:
        MistralError: If the API call fails or returns an unexpected response.
    """
    if not settings.nvidia_api_key:
        raise MistralError("NVIDIA_API_KEY not configured")

    client = await get_http_client()
    response = await client.post(
        NVIDIA_API_URL,
        headers={
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    response.raise_for_status()

    result = response.json()
    content = result["choices"][0]["message"]["content"].strip()
    content = _strip_markdown_fences(content)

    if parse_json:
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Mistral JSON response: {e}")
            return content

    return content


class MistralError(Exception):
    """Raised when a Mistral API call fails."""
