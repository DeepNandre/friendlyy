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
        return _handle_not_implemented("queue", result)
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
    import uuid
    from models import SessionStatus, BlitzSession
    from core.redis_client import save_session

    session_id = str(uuid.uuid4())

    session = BlitzSession(
        id=session_id,
        user_message=request.message,
        parsed_params=result.params,
        status=SessionStatus.SEARCHING,
    )

    # Save initial session to Redis — if this fails, still return a response
    try:
        await save_session(session.id, session.model_dump(mode="json"))
    except Exception as e:
        logger.error(f"Failed to save initial session to Redis: {e}")
        # Return a graceful error instead of crashing the endpoint
        return ChatResponse(
            session_id=session.id,
            agent=AgentType.BLITZ,
            status="error",
            message="Sorry, the service is temporarily unavailable. Please try again in a moment.",
        )

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
        logger.error(f"Background workflow error: {e}", exc_info=True)
        # Emit error event so the SSE stream terminates instead of hanging
        try:
            from services.blitz import emit_event
            await emit_event(session.id, "error", {"message": f"Workflow failed: {e}"})
        except Exception:
            logger.error(f"Failed to emit error event for session {session.id}")


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
