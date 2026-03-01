"""
Build agent - generates websites using Devstral agentic approach.

Uses Mistral's Devstral model with tool calling for agentic code generation.
Supports iterative building and multi-turn conversations.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from core import get_http_client, settings
from core.redis_client import save_session, get_redis_client
from core.sse import emit_event

logger = logging.getLogger(__name__)

# API endpoints
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Devstral model for agentic coding
DEVSTRAL_MODEL = "devstral-small-latest"

# System prompt for agentic web development
DEVSTRAL_SYSTEM_PROMPT = """You are an expert web developer AI agent. Your task is to build beautiful, production-quality websites based on user descriptions.

You have access to these tools:
- create_file: Create a new file with the given content
- update_file: Update/replace the content of an existing file
- finish_build: Complete the build and show the preview

WORKFLOW:
1. Analyze the user's request carefully
2. Plan your approach (what pages/components needed)
3. Use create_file to create the HTML file with embedded CSS
4. If changes are needed, use update_file
5. When done, call finish_build with a summary

RULES:
- Create a single index.html file with all CSS inline in a <style> tag
- Use modern CSS (flexbox, grid, gradients, shadows, smooth transitions)
- Make it fully responsive and mobile-friendly
- Use a polished, professional color palette appropriate for the business type
- Include realistic placeholder content (text, sections, calls-to-action)
- Add subtle CSS animations (fade-in, hover effects)
- Use Google Fonts via CDN for beautiful typography
- Include hero section, features/services section, and footer at minimum
- Use emoji or unicode icons instead of external icon libraries
- The HTML should be complete and self-contained (no external JS dependencies)
- Do NOT use any JavaScript

Always think step-by-step before creating files."""

# Tool definitions for Devstral
DEVSTRAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with the specified content. Use this to create the initial HTML/CSS for the website.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to create (e.g., 'index.html')"
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete content of the file"
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what this file does"
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_file",
            "description": "Update an existing file with new content. Use this to make changes to previously created files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to update"
                    },
                    "content": {
                        "type": "string",
                        "description": "The new complete content of the file"
                    },
                    "changes": {
                        "type": "string",
                        "description": "Brief description of what was changed"
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish_build",
            "description": "Complete the build process and show the preview. Call this when the website is ready.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what was built"
                    },
                    "features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of key features in the website"
                    }
                },
                "required": ["summary"]
            }
        }
    }
]

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


class AgenticBuilder:
    """Agentic website builder using Devstral with tool calling."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.files: Dict[str, str] = {}  # filename -> content
        self.messages: List[Dict[str, Any]] = []
        self.is_complete = False
        self.summary = ""
        self.features: List[str] = []

    async def _call_devstral(self) -> Dict[str, Any]:
        """Make a call to Devstral API with tool support."""
        client = await get_http_client()

        # Use Mistral API if key is available, otherwise fall back to NVIDIA NIM
        if settings.mistral_api_key:
            api_url = MISTRAL_API_URL
            headers = {
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
            }
            model = DEVSTRAL_MODEL
        elif settings.nvidia_api_key:
            # Fallback to NVIDIA NIM (without tool calling)
            api_url = NVIDIA_API_URL
            headers = {
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
            }
            model = "mistralai/mixtral-8x7b-instruct-v0.1"
        else:
            raise ValueError("No API key configured for Mistral or NVIDIA")

        payload = {
            "model": model,
            "messages": self.messages,
            "temperature": 0.7,
            "max_tokens": 8192,
        }

        # Only add tools if using Mistral API (NVIDIA NIM doesn't support tools well)
        if settings.mistral_api_key:
            payload["tools"] = DEVSTRAL_TOOLS
            payload["tool_choice"] = "auto"

        logger.info(f"[BUILD] Calling {model} with {len(self.messages)} messages")

        response = await client.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=90.0,
        )

        if response.status_code != 200:
            error_text = response.text[:500]
            logger.error(f"[BUILD] API error {response.status_code}: {error_text}")
            raise Exception(f"API error: {response.status_code}")

        return response.json()

    async def _handle_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """Execute a tool call and return the result."""
        func_name = tool_call["function"]["name"]
        args_str = tool_call["function"].get("arguments", "{}")

        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments: {args_str[:100]}"

        logger.info(f"[BUILD] Tool call: {func_name}({list(args.keys())})")

        if func_name == "create_file":
            filename = args.get("filename", "index.html")
            content = args.get("content", "")
            description = args.get("description", "")

            self.files[filename] = content

            await emit_event(
                self.session_id,
                "build_progress",
                {
                    "step": "generate",
                    "message": f"Created {filename}" + (f": {description}" if description else ""),
                    "file": filename,
                },
            )

            return f"Successfully created {filename} ({len(content)} bytes)"

        elif func_name == "update_file":
            filename = args.get("filename", "index.html")
            content = args.get("content", "")
            changes = args.get("changes", "")

            if filename not in self.files:
                return f"Error: File {filename} does not exist. Use create_file first."

            self.files[filename] = content

            await emit_event(
                self.session_id,
                "build_progress",
                {
                    "step": "generate",
                    "message": f"Updated {filename}" + (f": {changes}" if changes else ""),
                    "file": filename,
                },
            )

            return f"Successfully updated {filename}"

        elif func_name == "finish_build":
            self.summary = args.get("summary", "Website built successfully")
            self.features = args.get("features", [])
            self.is_complete = True

            return "Build marked as complete. Generating preview..."

        else:
            return f"Unknown tool: {func_name}"

    async def build(self, user_message: str, site_type: str = "website") -> Dict[str, Any]:
        """Run the agentic build workflow."""
        # Initialize conversation
        self.messages = [
            {"role": "system", "content": DEVSTRAL_SYSTEM_PROMPT},
            {"role": "user", "content": f"Build a {site_type}: {user_message}"},
        ]

        # Emit build started event
        await emit_event(
            self.session_id,
            "build_started",
            {
                "message": f"Building your {site_type} with AI...",
                "steps": [
                    {"id": "analyze", "label": "Analyzing requirements", "status": "in_progress"},
                    {"id": "plan", "label": "Planning structure", "status": "pending"},
                    {"id": "generate", "label": "Generating code", "status": "pending"},
                    {"id": "polish", "label": "Final polish", "status": "pending"},
                ],
            },
        )

        await asyncio.sleep(0.5)

        # Emit analyzing progress
        await emit_event(
            self.session_id,
            "build_progress",
            {
                "step": "plan",
                "message": "Planning your website structure...",
                "completed_step": "analyze",
            },
        )

        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while not self.is_complete and iteration < max_iterations:
            iteration += 1
            logger.info(f"[BUILD] Iteration {iteration}")

            try:
                result = await self._call_devstral()
            except Exception as e:
                logger.error(f"[BUILD] API call failed: {e}")
                # If Mistral fails, try simple generation fallback
                return await self._fallback_build(user_message, site_type)

            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason")

            # Check for tool calls
            tool_calls = message.get("tool_calls", [])

            if tool_calls:
                # Add assistant message with tool calls to history
                self.messages.append(message)

                # Process each tool call
                for tool_call in tool_calls:
                    tool_result = await self._handle_tool_call(tool_call)

                    # Add tool result to conversation
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": tool_result,
                    })

            elif message.get("content"):
                # Model responded with text (no tools) - might be done
                self.messages.append(message)

                # If no files created yet but model finished, fall back to extracting HTML
                if not self.files and finish_reason == "stop":
                    content = message.get("content", "")
                    if "<!DOCTYPE" in content or "<html" in content:
                        # Model generated HTML directly
                        self.files["index.html"] = content
                        self.is_complete = True
                    else:
                        # Prompt model to create the file
                        self.messages.append({
                            "role": "user",
                            "content": "Please create the HTML file using the create_file tool, then call finish_build."
                        })
                else:
                    # Model is done with tool calls
                    if self.files:
                        self.is_complete = True
            else:
                # Empty response, try to continue
                break

        # If no files were created, use fallback
        if not self.files:
            return await self._fallback_build(user_message, site_type)

        # Store the HTML in Redis
        html = self.files.get("index.html", list(self.files.values())[0])
        redis = await get_redis_client()
        preview_id = str(uuid.uuid4())[:8]
        await redis.setex(f"build:preview:{preview_id}", 3600, html)

        preview_url = f"{settings.backend_url}/api/build/preview/{preview_id}"

        # Emit completion
        await emit_event(
            self.session_id,
            "build_progress",
            {
                "step": "polish",
                "message": "Adding final touches...",
                "completed_step": "generate",
            },
        )

        await asyncio.sleep(0.3)

        await emit_event(
            self.session_id,
            "build_complete",
            {
                "message": self.summary or f"Your {site_type} is ready!",
                "preview_url": preview_url,
                "preview_id": preview_id,
                "features": self.features,
                "completed_step": "polish",
            },
        )

        # Save session state
        await save_session(
            self.session_id,
            {
                "id": self.session_id,
                "type": "build",
                "status": "complete",
                "user_message": user_message,
                "site_type": site_type,
                "preview_url": preview_url,
                "preview_id": preview_id,
                "files": list(self.files.keys()),
                "summary": self.summary,
                "features": self.features,
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        return {
            "session_id": self.session_id,
            "status": "complete",
            "preview_url": preview_url,
            "preview_id": preview_id,
        }

    async def _fallback_build(self, user_message: str, site_type: str) -> Dict[str, Any]:
        """Fallback to simple generation if agentic approach fails."""
        logger.info("[BUILD] Using fallback generation")

        await emit_event(
            self.session_id,
            "build_progress",
            {
                "step": "generate",
                "message": "Generating code...",
                "completed_step": "plan",
            },
        )

        # Use simple generation
        if settings.nvidia_api_key or settings.mistral_api_key:
            html = await _generate_site_html_simple(f"Create a {site_type}: {user_message}")
        else:
            html = _get_demo_html(site_type, user_message)

        self.files["index.html"] = html

        # Store and complete
        redis = await get_redis_client()
        preview_id = str(uuid.uuid4())[:8]
        await redis.setex(f"build:preview:{preview_id}", 3600, html)

        preview_url = f"{settings.backend_url}/api/build/preview/{preview_id}"

        await emit_event(
            self.session_id,
            "build_progress",
            {
                "step": "polish",
                "message": "Adding final touches...",
                "completed_step": "generate",
            },
        )

        await asyncio.sleep(0.3)

        await emit_event(
            self.session_id,
            "build_complete",
            {
                "message": f"Your {site_type} is ready!",
                "preview_url": preview_url,
                "preview_id": preview_id,
                "completed_step": "polish",
            },
        )

        await save_session(
            self.session_id,
            {
                "id": self.session_id,
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
            "session_id": self.session_id,
            "status": "complete",
            "preview_url": preview_url,
            "preview_id": preview_id,
        }


async def _generate_site_html_simple(description: str) -> str:
    """Simple HTML generation without tool calling (fallback)."""
    client = await get_http_client()

    simple_prompt = """You are a world-class web developer. Generate a complete, beautiful, single-page HTML website.

Rules:
- Output ONLY raw HTML. No markdown, no code blocks, no explanation.
- Include all CSS inline in a <style> tag.
- Use modern CSS (flexbox, grid, gradients, shadows).
- Make it fully responsive.
- Use Google Fonts via CDN.
- Include hero, features, and footer sections.
- Do NOT use JavaScript.

Output the complete HTML starting with <!DOCTYPE html>."""

    # Try Mistral first, then NVIDIA
    if settings.mistral_api_key:
        api_url = MISTRAL_API_URL
        headers = {
            "Authorization": f"Bearer {settings.mistral_api_key}",
            "Content-Type": "application/json",
        }
        model = "mistral-small-latest"
    else:
        api_url = NVIDIA_API_URL
        headers = {
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Content-Type": "application/json",
        }
        model = "mistralai/mixtral-8x7b-instruct-v0.1"

    response = await client.post(
        api_url,
        headers=headers,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": simple_prompt},
                {"role": "user", "content": description},
            ],
            "temperature": 0.7,
            "max_tokens": 8192,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    result = response.json()
    html = result["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if html.startswith("```"):
        lines = html.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        html = "\n".join(lines)

    return html


BUILD_TIMEOUT_SECONDS = 120  # Increased for agentic workflow


async def run_build_workflow(
    user_message: str,
    params: "RouterParams",
    session_id: Optional[str] = None,
) -> dict:
    """
    Run the agentic build workflow.

    Uses Devstral with tool calling for iterative, agentic website building.
    Falls back to simple generation if needed.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    site_type = params.service or "website"
    notes = params.notes or user_message

    # Clarification check
    if _needs_clarification(user_message):
        await emit_event(
            session_id,
            "build_clarification",
            {
                "message": "I'd love to build something for you! Could you tell me more about what you need? For example:\n\n- What type of site? (landing page, portfolio, menu, etc.)\n- What's it for? (business name, purpose)\n- Any style preferences? (modern, minimal, colorful)",
            },
        )
        return {"session_id": session_id, "status": "clarification_needed"}

    # Build description
    description = notes if notes != user_message else f"{site_type}: {user_message}"

    try:
        builder = AgenticBuilder(session_id)
        return await asyncio.wait_for(
            builder.build(description, site_type),
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
