"""
Main chat endpoint - routes user messages to appropriate agents.
"""

import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException

from core import settings
from models import ChatRequest, ChatResponse, AgentType
from services.router import classify_intent
from services.blitz import run_blitz_workflow
from services.demo_mode import run_demo_workflow

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """
    Process a user message and route to appropriate agent.

    Returns immediately with session info.
    Actual work is done in background.
    """
    logger.info(f"Chat request: {request.message[:50]}...")

    # Classify intent
    result = await classify_intent(request.message)
    logger.info(
        f"Classified as: {result.agent.value} (confidence: {result.confidence})"
    )

    # Route based on agent type
    if result.agent == AgentType.BLITZ:
        return await _handle_blitz(request, result, background_tasks)
    elif result.agent == AgentType.BOUNCE:
        return _handle_not_implemented("bounce", result)
    elif result.agent == AgentType.QUEUE:
        return _handle_not_implemented("queue", result)
    elif result.agent == AgentType.BID:
        return _handle_not_implemented("bid", result)
    else:
        return _handle_chat(request, result)


async def _handle_blitz(
    request: ChatRequest,
    result,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Handle Blitz agent requests."""
    # Choose workflow based on demo mode
    if settings.demo_mode:
        workflow = run_demo_workflow
    else:
        workflow = run_blitz_workflow

    # Start workflow in background
    from services.blitz import BlitzSession
    from models import RouterParams

    # Create a session immediately to get ID
    import uuid
    session_id = str(uuid.uuid4())

    # Run workflow in background
    async def _run_workflow():
        try:
            if settings.demo_mode:
                await run_demo_workflow(
                    user_message=request.message,
                    params=result.params,
                )
            else:
                await run_blitz_workflow(
                    user_message=request.message,
                    params=result.params,
                    location=request.location,
                )
        except Exception as e:
            logger.error(f"Workflow error: {e}")

    # Actually we need to create session first, then run
    # Let's do it slightly differently - create session in workflow
    from models import SessionStatus, BlitzSession

    session = BlitzSession(
        id=session_id,
        user_message=request.message,
        parsed_params=result.params,
        status=SessionStatus.SEARCHING,
    )

    from core.redis_client import save_session
    await save_session(session.id, session.model_dump(mode="json"))

    # Start background task
    background_tasks.add_task(_run_background_workflow, session, settings.demo_mode)

    service = result.params.service or "services"
    return ChatResponse(
        session_id=session.id,
        agent=AgentType.BLITZ,
        status="searching",
        message=f"On it! Let me find some {service} for you...",
        stream_url=f"/api/blitz/stream/{session.id}",
    )


async def _run_background_workflow(session, demo_mode: bool):
    """Run the Blitz workflow in background."""
    try:
        if demo_mode:
            await run_demo_workflow(
                user_message=session.user_message,
                params=session.parsed_params,
            )
        else:
            await run_blitz_workflow(
                user_message=session.user_message,
                params=session.parsed_params,
            )
    except Exception as e:
        logger.error(f"Background workflow error: {e}")


def _handle_not_implemented(agent_name: str, result) -> ChatResponse:
    """Handle agents that aren't implemented yet."""
    import uuid
    return ChatResponse(
        session_id=str(uuid.uuid4()),
        agent=AgentType(agent_name),
        status="pending",
        message=f"The {agent_name.title()} agent is coming soon! For now, I can help you find services with Blitz.",
    )


def _handle_chat(request: ChatRequest, result) -> ChatResponse:
    """Handle general chat requests."""
    import uuid

    # Generate a simple response
    message = request.message.lower()

    if any(word in message for word in ["hello", "hi", "hey"]):
        response = "Hey! I'm Friendly. I can help you find services and get quotes by making phone calls on your behalf. Try saying 'find me a plumber' or 'get quotes for an electrician'."
    elif any(word in message for word in ["help", "what can you do", "how"]):
        response = """I'm Friendly, your AI assistant that makes real phone calls!

I can help you with:
- **Blitz**: Find services and get quotes (plumbers, electricians, etc.)
- **Bounce**: Cancel subscriptions (coming soon)
- **Queue**: Wait on hold for you (coming soon)
- **Bid**: Negotiate your bills (coming soon)

Try: "Find me a plumber who can come tomorrow" """
    else:
        response = "I'm not sure what you need. Try asking me to find a service, like 'find me a plumber in London'."

    return ChatResponse(
        session_id=str(uuid.uuid4()),
        agent=AgentType.CHAT,
        status="complete",
        message=response,
    )
