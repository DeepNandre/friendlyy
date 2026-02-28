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
from services.chat import generate_chat_response

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
        return await _handle_queue(request, result, background_tasks)
    elif result.agent == AgentType.BID:
        return _handle_not_implemented("bid", result)
    else:
        return await _handle_chat(request, result)


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
                session_id=session.id,
            )
        else:
            await run_blitz_workflow(
                user_message=session.user_message,
                params=session.parsed_params,
                session_id=session.id,
            )
    except Exception as e:
        logger.error(f"Background workflow error: {e}")


async def _handle_queue(
    request: ChatRequest,
    result,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Handle Queue agent requests — wait on hold for the user."""
    import uuid
    from services.queue_agent import run_queue_workflow

    session_id = str(uuid.uuid4())

    # Extract phone number and business from params
    phone_number = result.params.notes or ""  # Phone number might be in notes
    business_name = result.params.service or "Unknown"
    reason = result.params.action or "general enquiry"

    # If no phone number found, ask the user
    if not phone_number or not any(c.isdigit() for c in phone_number):
        return ChatResponse(
            session_id=session_id,
            agent=AgentType.QUEUE,
            status="pending",
            message=f"I can wait on hold at {business_name} for you! What's their phone number?",
        )

    # Start queue workflow in background
    async def _run_queue():
        try:
            await run_queue_workflow(
                phone_number=phone_number,
                business_name=business_name,
                reason=reason,
                session_id=session_id,
            )
        except Exception as e:
            logger.error(f"Queue workflow error: {e}")

    background_tasks.add_task(_run_queue)

    return ChatResponse(
        session_id=session_id,
        agent=AgentType.QUEUE,
        status="calling",
        message=f"On it! I'm calling {business_name} and will wait on hold for you. I'll let you know when a human picks up.",
        stream_url=f"/api/blitz/stream/{session_id}",
    )


def _handle_not_implemented(agent_name: str, result) -> ChatResponse:
    """Handle agents that aren't implemented yet."""
    import uuid
    return ChatResponse(
        session_id=str(uuid.uuid4()),
        agent=AgentType(agent_name),
        status="pending",
        message=f"The {agent_name.title()} agent is coming soon! For now, I can help you find services with Blitz.",
    )


async def _handle_chat(request: ChatRequest, result) -> ChatResponse:
    """Handle general chat requests using Mistral."""
    import uuid

    # Generate response using Mistral
    response = await generate_chat_response(request.message)

    return ChatResponse(
        session_id=str(uuid.uuid4()),
        agent=AgentType.CHAT,
        status="complete",
        message=response,
    )
