"""
Main chat endpoint - routes user messages to appropriate agents.
"""

import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException

from core import settings
from models import ChatRequest, ChatResponse, AgentType
import re
from services.router import classify_intent
from services.blitz import run_blitz_workflow
from services.demo_mode import run_demo_workflow
from services.build_agent import run_build_workflow
from services.chat import generate_chat_response
from services.inbox_agent import run_inbox_workflow
from services.call_friend_agent import run_call_friend_workflow

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
        f"=== ROUTER DECISION === Agent: {result.agent.value}, Confidence: {result.confidence}"
    )
    logger.info(
        f"=== ROUTER PARAMS === service: '{result.params.service}', action: '{result.params.action}', notes: '{result.params.notes}'"
    )
    logger.info(
        f"Router params: service='{result.params.service}', location='{result.params.location}', timeframe='{result.params.timeframe}'"
    )

    # Check for phone number follow-up (user providing number after we asked for call_friend)
    if request.conversation_history:
        # Check if user's message is primarily a phone number
        phone_match = re.search(r'[\+]?[\d\s\-\(\)]{10,}', request.message)
        if phone_match:
            # Look for recent call_friend context in conversation
            for msg in reversed(request.conversation_history):
                if msg.role == "assistant":
                    # Check for various phrases that indicate we asked for a phone number
                    call_friend_indicators = [
                        "phone number",
                        "their number",
                        "what's their",
                        "provide me with",
                        "call your friend",
                        "call them",
                        "connect with your friend",
                    ]
                    if any(indicator in msg.content.lower() for indicator in call_friend_indicators):
                        return await _continue_call_friend(request, phone_match.group(), background_tasks)
                    break  # Only check the most recent assistant message
                elif msg.role == "user":
                    # Check if user previously asked to call someone
                    user_call_patterns = [
                        r"call (?:my )?(?:friend|mate|pal|mom|dad|brother|sister)",
                        r"ring (?:my )?(?:friend|mate|pal|mom|dad|brother|sister)",
                        r"call \w+ and ask",
                    ]
                    if any(re.search(p, msg.content, re.IGNORECASE) for p in user_call_patterns):
                        return await _continue_call_friend(request, phone_match.group(), background_tasks)
                    break  # Only check the most recent user message before this one

    # Route based on agent type
    if result.agent == AgentType.BLITZ:
        logger.info("=== ROUTING TO: BLITZ ===")
        return await _handle_blitz(request, result, background_tasks)
    elif result.agent == AgentType.BUILD:
        logger.info("=== ROUTING TO: BUILD ===")
        return await _handle_build(request, result, background_tasks)
    elif result.agent == AgentType.BOUNCE:
        logger.info("=== ROUTING TO: BOUNCE ===")
        return _handle_not_implemented("bounce", result)
    elif result.agent == AgentType.QUEUE:
        logger.info("=== ROUTING TO: QUEUE ===")
        return await _handle_queue(request, result, background_tasks)
    elif result.agent == AgentType.INBOX:
        logger.info("=== ROUTING TO: INBOX ===")
        return await _handle_inbox(request, result, background_tasks)
    elif result.agent == AgentType.CALL_FRIEND:
        logger.info("=== ROUTING TO: CALL_FRIEND ===")
        return await _handle_call_friend(request, result, background_tasks)
    elif result.agent == AgentType.BID:
        logger.info("=== ROUTING TO: BID ===")
        return _handle_not_implemented("bid", result)
    else:
        logger.info(f"=== ROUTING TO: CHAT (fallback, agent was {result.agent}) ===")
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
    try:
        await save_session(session.id, session.model_dump(mode="json"))
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        return ChatResponse(
            session_id=session.id,
            agent=AgentType.BLITZ,
            status="error",
            message="Sorry, I couldn't start the search. Please try again.",
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
    from core.redis_client import push_event
    from datetime import datetime

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
        # Emit error event so frontend doesn't hang
        await push_event(
            session.id,
            {
                "event": "error",
                "data": {"message": str(e)},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


async def _handle_build(
    request: ChatRequest,
    result,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Handle Build agent requests."""
    import uuid

    session_id = str(uuid.uuid4())
    site_type = result.params.service or "website"

    background_tasks.add_task(
        run_build_workflow,
        user_message=request.message,
        params=result.params,
        session_id=session_id,
    )

    return ChatResponse(
        session_id=session_id,
        agent=AgentType.BUILD,
        status="building",
        message=f"On it! Let me build a {site_type} for you...",
        stream_url=f"/api/build/stream/{session_id}",
    )


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


async def _handle_inbox(
    request: ChatRequest,
    result,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Handle Inbox agent requests — check Gmail."""
    import uuid

    session_id = str(uuid.uuid4())
    entity_id = request.entity_id or "default"

    background_tasks.add_task(
        run_inbox_workflow,
        user_message=request.message,
        params=result.params,
        session_id=session_id,
        entity_id=entity_id,
    )

    return ChatResponse(
        session_id=session_id,
        agent=AgentType.INBOX,
        status="checking",
        message="Let me check your inbox...",
        stream_url=f"/api/inbox/stream/{session_id}",
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


async def _handle_call_friend(
    request: ChatRequest,
    result,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Handle Call Friend agent requests — call a friend with a custom question."""
    import uuid

    session_id = str(uuid.uuid4())

    # Extract friend name and question from params
    friend_name = result.params.service or "your friend"
    question = result.params.action or request.message
    phone_number = result.params.notes  # Phone number might be in notes

    # Also check message for phone number
    if not phone_number:
        phone_match = re.search(r'[\+]?[\d\s\-\(\)]{10,}', request.message)
        if phone_match:
            phone_number = re.sub(r'[^\d+]', '', phone_match.group())

    # If no phone number, ask for it
    if not phone_number:
        # Store the friend name and question for follow-up
        return ChatResponse(
            session_id=session_id,
            agent=AgentType.CALL_FRIEND,
            status="awaiting_phone",
            message=f"I'll call {friend_name} for you! What's their phone number?",
        )

    # Clean up phone number
    phone_number = re.sub(r'[^\d+]', '', phone_number)

    # Start call friend workflow
    background_tasks.add_task(
        run_call_friend_workflow,
        session_id=session_id,
        friend_name=friend_name,
        phone_number=phone_number,
        question=question,
    )

    return ChatResponse(
        session_id=session_id,
        agent=AgentType.CALL_FRIEND,
        status="calling",
        message=f"Calling {friend_name} now! I'll ask: \"{question}\"",
        stream_url=f"/api/call_friend/stream/{session_id}",
    )


async def _continue_call_friend(
    request: ChatRequest,
    phone_number: str,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Continue a call friend request after user provides phone number."""
    import uuid

    session_id = str(uuid.uuid4())

    # Try to extract friend name and question from conversation history
    friend_name = "your friend"
    question = "checking in"

    if request.conversation_history:
        # Look for the original call_friend message in history
        for msg in reversed(request.conversation_history):
            if msg.role == "user" and ("call" in msg.content.lower() or "ring" in msg.content.lower()):
                # This is likely the original request
                question = msg.content
                # Try to extract name
                name_patterns = [
                    r"call (?:my )?(?:friend |mate |pal )?(\w+)",
                    r"ring (?:my )?(?:friend |mate |pal )?(\w+)",
                    r"call (?:my )?(\w+)",
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, msg.content, re.IGNORECASE)
                    if match:
                        friend_name = match.group(1)
                        break
                break

    # Clean up phone number
    phone_number = re.sub(r'[^\d+]', '', phone_number)

    # Start call friend workflow
    background_tasks.add_task(
        run_call_friend_workflow,
        session_id=session_id,
        friend_name=friend_name,
        phone_number=phone_number,
        question=question,
    )

    return ChatResponse(
        session_id=session_id,
        agent=AgentType.CALL_FRIEND,
        status="calling",
        message=f"Calling {friend_name} now!",
        stream_url=f"/api/call_friend/stream/{session_id}",
    )


async def _handle_chat(request: ChatRequest, result) -> ChatResponse:
    """Handle general chat requests using Mistral."""
    import uuid

    # Convert conversation history to format expected by chat service
    history = None
    if request.conversation_history:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

    # Generate response using Mistral with conversation context
    response = await generate_chat_response(
        request.message,
        conversation_history=history,
        model_id=request.model,
    )

    return ChatResponse(
        session_id=str(uuid.uuid4()),
        agent=AgentType.CHAT,
        status="complete",
        message=response,
    )
