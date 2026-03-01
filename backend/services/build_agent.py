"""
Build agent - generates websites from natural language descriptions.

Uses Mistral (via NVIDIA NIM) to generate HTML/CSS, then serves
a preview. Streams progress events via Redis SSE queue.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from core import get_http_client, settings
from core.redis_client import save_session, get_redis_client
from core.sse import emit_event

logger = logging.getLogger(__name__)

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

BUILD_SYSTEM_PROMPT = """You are a world-class web developer. Generate a complete, beautiful, single-page HTML website based on the user's description.

Rules:
- Output ONLY the raw HTML. No markdown, no code blocks, no explanation.
- Include all CSS inline in a <style> tag in the <head>.
- Use modern CSS (flexbox, grid, gradients, shadows, smooth transitions).
- Make it fully responsive and mobile-friendly.
- Use a polished, professional color palette appropriate for the business type.
- Include realistic placeholder content (text, sections, calls-to-action).
- Add subtle animations (fade-in, hover effects) using CSS only.
- Use Google Fonts via CDN link for beautiful typography.
- Include a hero section, features/services section, and a footer at minimum.
- Use emoji or unicode icons where appropriate instead of external icon libraries.
- Make the page look like a real, production-quality website.
- The HTML should be complete and self-contained (no external JS dependencies).
- Do NOT use any JavaScript.

Output the complete HTML document starting with <!DOCTYPE html>."""

CLARIFICATION_KEYWORDS = [
    "build something",
    "make something",
    "create something",
    "build me something",
    "something cool",
    "anything",
    "whatever",
    "surprise me",
    "idk",
    "i don't know",
]


def _needs_clarification(message: str) -> bool:
    """Check if the user's request is too vague to build anything useful."""
    msg_lower = message.lower().strip()
    if len(msg_lower.split()) <= 3 and not any(
        kw in msg_lower
        for kw in ["landing", "portfolio", "website", "page", "menu", "store", "blog", "app"]
    ):
        return True
    return any(kw in msg_lower for kw in CLARIFICATION_KEYWORDS)


async def _generate_site_html(description: str) -> str:
    """Generate website HTML using Mistral via NVIDIA NIM."""
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
                {"role": "system", "content": BUILD_SYSTEM_PROMPT},
                {"role": "user", "content": description},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    result = response.json()
    html = result["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if html.startswith("```"):
        lines = html.split("\n")
        # Remove first line (```html or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        html = "\n".join(lines)

    return html


BUILD_TIMEOUT_SECONDS = 90


async def run_build_workflow(
    user_message: str,
    params: "RouterParams",
    session_id: Optional[str] = None,
) -> dict:
    """
    Run the full build workflow with an overall timeout.

    1. Validate the request (ask for clarification if too vague)
    2. Stream progress events
    3. Generate website HTML via Mistral
    4. Store the result and emit completion event

    Args:
        user_message: Original user message
        params: Parsed router params (service, notes)
        session_id: Pre-created session ID

    Returns:
        Dict with build results
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    site_type = params.service or "website"
    notes = params.notes or user_message

    # Clarification check runs outside the timeout (it's instant)
    if _needs_clarification(user_message):
        await emit_event(
            session_id,
            "build_clarification",
            {
                "message": "I'd love to build something for you! Could you tell me more about what you need? For example:\n\n- What type of site? (landing page, portfolio, menu, etc.)\n- What's it for? (business name, purpose)\n- Any style preferences? (modern, minimal, colorful)",
            },
        )
        return {"session_id": session_id, "status": "clarification_needed"}

    # Build a rich description for the LLM
    description = f"Create a {site_type}"
    if notes:
        description += f": {notes}"
    description += f". Original request: \"{user_message}\""

    try:
        return await asyncio.wait_for(
            _execute_build(session_id, site_type, description, user_message),
            timeout=BUILD_TIMEOUT_SECONDS,
        )

    except asyncio.TimeoutError:
        logger.error(f"Build timed out after {BUILD_TIMEOUT_SECONDS}s for session {session_id}")
        await emit_event(
            session_id,
            "build_error",
            {"message": "Build timed out. Please try again with a simpler request."},
        )
        return {"session_id": session_id, "status": "error"}

    except Exception as e:
        logger.error(f"Build workflow error for session {session_id}: {e}")
        await emit_event(
            session_id,
            "build_error",
            {"message": "Something went wrong while building. Please try again."},
        )
        return {"session_id": session_id, "status": "error"}


async def _execute_build(
    session_id: str,
    site_type: str,
    description: str,
    user_message: str,
) -> dict:
    """Core build logic wrapped by wait_for timeout."""
    # Step 1: Build started
    await emit_event(
        session_id,
        "build_started",
        {
            "message": f"Building your {site_type}...",
            "steps": [
                {"id": "analyze", "label": "Analyzing requirements", "status": "in_progress"},
                {"id": "design", "label": "Designing layout", "status": "pending"},
                {"id": "generate", "label": "Generating code", "status": "pending"},
                {"id": "polish", "label": "Final polish", "status": "pending"},
            ],
        },
    )

    await asyncio.sleep(1.0)

    # Step 2: Designing
    await emit_event(
        session_id,
        "build_progress",
        {
            "step": "design",
            "message": "Designing your layout and color scheme...",
            "completed_step": "analyze",
        },
    )

    await asyncio.sleep(0.8)

    # Step 3: Generating code
    await emit_event(
        session_id,
        "build_progress",
        {
            "step": "generate",
            "message": "Generating HTML & CSS...",
            "completed_step": "design",
        },
    )

    # Actually generate the site
    if settings.nvidia_api_key:
        html = await _generate_site_html(description)
    else:
        html = _get_demo_html(site_type, description)

    # Store the generated HTML in Redis
    redis = await get_redis_client()
    preview_id = str(uuid.uuid4())[:8]
    await redis.setex(
        f"build:preview:{preview_id}",
        3600,  # 1 hour TTL
        html,
    )

    # Step 4: Polish
    await emit_event(
        session_id,
        "build_progress",
        {
            "step": "polish",
            "message": "Adding final touches...",
            "completed_step": "generate",
        },
    )

    await asyncio.sleep(0.5)

    # Build the preview URL
    preview_url = f"{settings.backend_url}/api/build/preview/{preview_id}"

    # Step 5: Complete
    await emit_event(
        session_id,
        "build_complete",
        {
            "message": f"Your {site_type} is ready!",
            "preview_url": preview_url,
            "preview_id": preview_id,
            "completed_step": "polish",
        },
    )

    # Save session state
    await save_session(
        session_id,
        {
            "id": session_id,
            "type": "build",
            "status": "complete",
            "user_message": user_message,
            "site_type": site_type,
            "preview_url": preview_url,
            "preview_id": preview_id,
            "created_at": datetime.utcnow().isoformat(),
        },
    )

    return {
        "session_id": session_id,
        "status": "complete",
        "preview_url": preview_url,
        "preview_id": preview_id,
    }


def _get_demo_html(site_type: str, notes: str) -> str:
    """Fallback HTML for demo mode when no API key is available."""
    title = notes.split(",")[0].title() if notes else site_type.title()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', sans-serif; color: #1a1a2e; background: #fafafa; }}
.hero {{
  min-height: 80vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white; padding: 2rem;
}}
.hero h1 {{ font-size: 3.5rem; font-weight: 700; margin-bottom: 1rem; animation: fadeIn 1s ease; }}
.hero p {{ font-size: 1.25rem; opacity: 0.9; max-width: 600px; line-height: 1.6; animation: fadeIn 1.5s ease; }}
.cta {{
  margin-top: 2rem; padding: 1rem 2.5rem; background: white; color: #667eea;
  border: none; border-radius: 50px; font-size: 1.1rem; font-weight: 600;
  cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
  animation: fadeIn 2s ease;
}}
.cta:hover {{ transform: translateY(-2px); box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
.features {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem; padding: 5rem 2rem; max-width: 1100px; margin: 0 auto;
}}
.feature {{
  background: white; padding: 2rem; border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.06); transition: transform 0.2s;
}}
.feature:hover {{ transform: translateY(-4px); }}
.feature .icon {{ font-size: 2.5rem; margin-bottom: 1rem; }}
.feature h3 {{ font-size: 1.25rem; margin-bottom: 0.5rem; }}
.feature p {{ color: #666; line-height: 1.6; }}
footer {{
  text-align: center; padding: 3rem 2rem; background: #1a1a2e; color: rgba(255,255,255,0.7);
  font-size: 0.9rem;
}}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
</style>
</head>
<body>
<section class="hero">
  <h1>{title}</h1>
  <p>Welcome to our site. We're building something amazing. Stay tuned for updates.</p>
  <button class="cta">Get Started</button>
</section>
<section class="features">
  <div class="feature">
    <div class="icon">&#x2728;</div>
    <h3>Quality Service</h3>
    <p>We deliver exceptional quality in everything we do, ensuring your complete satisfaction.</p>
  </div>
  <div class="feature">
    <div class="icon">&#x1F680;</div>
    <h3>Fast & Reliable</h3>
    <p>Quick turnaround times without compromising on quality. Your time matters to us.</p>
  </div>
  <div class="feature">
    <div class="icon">&#x1F4AC;</div>
    <h3>24/7 Support</h3>
    <p>Our dedicated team is always here to help. Reach out anytime, day or night.</p>
  </div>
</section>
<footer>
  <p>&copy; 2026 {title}. Built with Friendly AI.</p>
</footer>
</body>
</html>"""
