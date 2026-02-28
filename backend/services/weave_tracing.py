"""
W&B Weave tracing integration for Friendly.

Provides safe, non-blocking tracing decorators and structured outcome logging.
All tracing is fire-and-forget — if W&B is down, the app works normally.
"""

import contextvars
import json
import time
import logging
import functools
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core import settings

logger = logging.getLogger(__name__)

# Track whether Weave is available
_weave_available = False
_weave = None

# Trace context: allows decorated functions to pass path-dependent state
# (e.g., used_fallback, cache_hit) to their log_fn callback.
_trace_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "trace_ctx", default=None
)


def _init_weave():
    """Lazy-initialize Weave module reference."""
    global _weave_available, _weave
    if _weave is not None:
        return
    if settings.wandb_api_key:
        try:
            import weave
            _weave = weave
            _weave_available = True
        except ImportError:
            logger.warning("weave package not installed")
            _weave_available = False
    else:
        _weave_available = False


def get_trace_ctx() -> Dict[str, Any]:
    """
    Get the current trace context dict.

    Use inside a @traced function to pass path-dependent state to log_fn:
        get_trace_ctx()["used_fallback"] = True
    """
    ctx = _trace_ctx.get()
    if ctx is None:
        ctx = {}
        _trace_ctx.set(ctx)
    return ctx


def traced(name: str = None, log_fn: Callable = None):
    """
    Safe decorator that adds Weave tracing and structured logging to async functions.

    Handles timing, success/error detection, and calls log_fn automatically.

    Args:
        name: Operation name for traces. Defaults to function name.
        log_fn: Optional callback called after execution with signature:
            log_fn(*, result, duration, error, args, kwargs, ctx)
            If not provided, a generic trace is auto-logged.

    Usage:
        def _log_classify(*, result, duration, error, args, kwargs, ctx):
            log_router_classification(
                user_message=args[0],
                classified_agent=result.agent.value,
                ...
            )

        @traced("classify_intent", log_fn=_log_classify)
        async def classify_intent(user_message: str) -> RouterResult:
            # No timing or logging boilerplate needed
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            _init_weave()

            op_name = name or func.__name__
            start_time = time.time()
            error_str = None
            result = None

            # Set up trace context for this call
            ctx: Dict[str, Any] = {}
            token = _trace_ctx.set(ctx)

            try:
                # If Weave is available, try to use @weave.op()
                if _weave_available and _weave:
                    try:
                        traced_fn = _weave.op()(func)
                        traced_fn.name = op_name
                        result = await traced_fn(*args, **kwargs)
                    except Exception as trace_err:
                        logger.debug(f"Weave tracing failed for {op_name}: {trace_err}")
                        result = await func(*args, **kwargs)
                else:
                    result = await func(*args, **kwargs)

                return result

            except Exception as e:
                error_str = str(e)
                raise
            finally:
                duration = time.time() - start_time
                _trace_ctx.reset(token)

                # Call log_fn or auto-log
                try:
                    if log_fn:
                        log_fn(
                            result=result, duration=duration, error=error_str,
                            args=args, kwargs=kwargs, ctx=ctx,
                        )
                    else:
                        log_trace(
                            op_name,
                            success=error_str is None,
                            duration_seconds=duration,
                            error=error_str,
                        )
                except Exception:
                    pass  # Never crash from logging

        return wrapper
    return decorator


# ==================== STRUCTURED OUTCOME STORAGE ====================

# In-memory trace store (hydrated from Redis on startup)
_trace_store: List[Dict[str, Any]] = []
MAX_TRACES = 500

# Invalidate-on-write cache for get_performance_summary()
_summary_cache: Optional[Dict[str, Any]] = None


def log_trace(
    operation: str,
    *,
    success: bool,
    duration_seconds: float = 0.0,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """
    Log a structured trace for any operation.

    Args:
        operation: Name of the operation (e.g., "blitz_call", "classify_intent")
        success: Whether the operation succeeded
        duration_seconds: How long it took
        input_data: Input parameters
        output_data: Output/result data
        metadata: Additional structured metadata
        error: Error message if failed
    """
    global _summary_cache
    _summary_cache = None  # Invalidate cache

    trace = {
        "operation": operation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "duration_seconds": round(duration_seconds, 3),
        "input": input_data or {},
        "output": output_data or {},
        "metadata": metadata or {},
        "error": error,
    }

    _trace_store.append(trace)

    # Trim to max size
    if len(_trace_store) > MAX_TRACES:
        _trace_store[:] = _trace_store[-MAX_TRACES:]

    # Also log to Weave if available
    _init_weave()
    if _weave_available and _weave:
        try:
            _weave.publish(trace, name=f"trace/{operation}")
        except Exception:
            pass  # Fire and forget

    # Persist to Redis asynchronously
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_persist_trace_to_redis(trace))
    except Exception:
        pass  # Non-critical


async def _persist_trace_to_redis(trace: Dict[str, Any]) -> None:
    """Persist a trace to Redis for cross-session access."""
    try:
        from core.redis_client import get_redis_client
        r = await get_redis_client()
        if r:
            await r.lpush("friendly:traces", json.dumps(trace))
            await r.ltrim("friendly:traces", 0, 999)
    except Exception as e:
        logger.debug(f"Failed to persist trace to Redis: {e}")


async def load_traces_from_redis() -> None:
    """
    Hydrate in-memory trace store from Redis on startup.
    Called from the application lifespan handler.
    """
    try:
        from core.redis_client import get_redis_client
        r = await get_redis_client()
        if not r:
            return

        raw_traces = await r.lrange("friendly:traces", 0, MAX_TRACES - 1)
        if not raw_traces:
            return

        loaded = []
        for raw in reversed(raw_traces):  # Redis lpush = newest first, reverse for chronological
            try:
                loaded.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                continue

        _trace_store.clear()
        _trace_store.extend(loaded)
        logger.info(f"Loaded {len(loaded)} traces from Redis")

    except Exception as e:
        logger.warning(f"Failed to load traces from Redis: {e}")


# ==================== DOMAIN-SPECIFIC LOG HELPERS ====================
# These are called by log_fn callbacks or directly from service code.


def log_blitz_call(
    *,
    business_name: str,
    business_phone: str,
    call_success: bool,
    call_duration: float = 0.0,
    ivr_navigated: bool = False,
    quote_received: Optional[float] = None,
    business_responded: bool = False,
    result_text: Optional[str] = None,
    error: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Log structured outcome for a single Blitz call."""
    log_trace(
        "blitz_call",
        success=call_success,
        duration_seconds=call_duration,
        input_data={
            "business_name": business_name,
            "business_phone": business_phone,
            "session_id": session_id,
        },
        output_data={
            "result_text": result_text,
            "quote_received": quote_received,
        },
        metadata={
            "call_success": call_success,
            "call_duration": call_duration,
            "ivr_navigated": ivr_navigated,
            "quote_received": quote_received,
            "business_responded": business_responded,
        },
        error=error,
    )


def log_blitz_session(
    *,
    session_id: str,
    total_calls: int,
    successful_calls: int,
    total_duration: float,
    service_type: str,
    location: Optional[str] = None,
    best_quote: Optional[str] = None,
) -> None:
    """Log structured outcome for a complete Blitz session."""
    success_rate = successful_calls / total_calls if total_calls > 0 else 0.0

    log_trace(
        "blitz_session",
        success=successful_calls > 0,
        duration_seconds=total_duration,
        input_data={
            "session_id": session_id,
            "service_type": service_type,
            "location": location,
        },
        output_data={
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "success_rate": round(success_rate, 3),
            "best_quote": best_quote,
        },
        metadata={
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "success_rate": round(success_rate, 3),
        },
    )


def log_router_classification(
    *,
    user_message: str,
    classified_agent: str,
    confidence: float,
    duration: float,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """Log structured outcome for intent classification."""
    log_trace(
        "classify_intent",
        success=True,
        duration_seconds=duration,
        input_data={"user_message": user_message[:200]},
        output_data={
            "classified_agent": classified_agent,
            "confidence": confidence,
            "params": params or {},
        },
    )


def log_chat_response(
    *,
    user_message: str,
    response_text: str,
    duration: float,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Log structured outcome for chat responses."""
    log_trace(
        "chat_response",
        success=success,
        duration_seconds=duration,
        input_data={"user_message": user_message[:200]},
        output_data={"response_preview": response_text[:200]},
        error=error,
    )


def log_business_search(
    *,
    query: str,
    location: Optional[str],
    results_count: int,
    duration: float,
    used_fallback: bool = False,
) -> None:
    """Log structured outcome for business search."""
    log_trace(
        "business_search",
        success=results_count > 0,
        duration_seconds=duration,
        input_data={"query": query, "location": location},
        output_data={"results_count": results_count, "used_fallback": used_fallback},
    )


def log_tts_generation(
    *,
    text_length: int,
    duration: float,
    cache_hit: bool,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """Log structured outcome for TTS generation."""
    log_trace(
        "tts_generation",
        success=success,
        duration_seconds=duration,
        input_data={"text_length": text_length},
        output_data={"cache_hit": cache_hit},
        error=error,
    )


# ==================== SELF-IMPROVING FEEDBACK ====================


def get_performance_summary() -> Dict[str, Any]:
    """
    Get aggregate performance metrics from stored traces.
    Uses invalidate-on-write caching for efficiency.
    """
    global _summary_cache
    if _summary_cache is not None:
        return _summary_cache

    if not _trace_store:
        result = {"total_traces": 0, "message": "No traces yet"}
        _summary_cache = result
        return result

    # Group by operation
    ops: Dict[str, List[Dict]] = {}
    for trace in _trace_store:
        op = trace["operation"]
        if op not in ops:
            ops[op] = []
        ops[op].append(trace)

    summary: Dict[str, Any] = {
        "total_traces": len(_trace_store),
        "operations": {},
    }

    for op_name, traces in ops.items():
        total = len(traces)
        successes = sum(1 for t in traces if t["success"])
        durations = [t["duration_seconds"] for t in traces if t["duration_seconds"] > 0]

        op_summary = {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": round(successes / total, 3) if total > 0 else 0,
        }

        if durations:
            op_summary["avg_duration"] = round(sum(durations) / len(durations), 3)
            op_summary["min_duration"] = round(min(durations), 3)
            op_summary["max_duration"] = round(max(durations), 3)

        summary["operations"][op_name] = op_summary

    # Add Blitz-specific insights
    blitz_calls = ops.get("blitz_call", [])
    if blitz_calls:
        answered = [t for t in blitz_calls if t["metadata"].get("business_responded")]
        quotes = [t for t in blitz_calls if t["metadata"].get("quote_received") is not None]

        summary["blitz_insights"] = {
            "total_calls": len(blitz_calls),
            "businesses_responded": len(answered),
            "quotes_received": len(quotes),
            "response_rate": round(len(answered) / len(blitz_calls), 3),
            "quote_rate": round(len(quotes) / len(blitz_calls), 3),
        }

        # Analyze by duration brackets
        fast_calls = [t for t in blitz_calls if t["duration_seconds"] <= 10]
        slow_calls = [t for t in blitz_calls if t["duration_seconds"] > 10]

        if fast_calls:
            fast_success = sum(1 for t in fast_calls if t["success"])
            summary["blitz_insights"]["fast_answer_success_rate"] = round(
                fast_success / len(fast_calls), 3
            )

        if slow_calls:
            slow_success = sum(1 for t in slow_calls if t["success"])
            summary["blitz_insights"]["slow_answer_success_rate"] = round(
                slow_success / len(slow_calls), 3
            )

    _summary_cache = summary
    return summary


def get_recent_traces(
    operation: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get recent traces, optionally filtered by operation."""
    traces = _trace_store
    if operation:
        traces = [t for t in traces if t["operation"] == operation]
    return traces[-limit:]


def get_improvement_data() -> Dict[str, Any]:
    """
    Get data showing improvement over time.
    Groups traces into time buckets and shows success rate progression.
    """
    if len(_trace_store) < 2:
        return {"message": "Not enough data for improvement analysis"}

    # Group blitz sessions by order
    sessions = [t for t in _trace_store if t["operation"] == "blitz_session"]
    if len(sessions) < 2:
        return {"message": "Not enough blitz sessions for improvement analysis"}

    # Split into buckets (first half vs second half)
    mid = len(sessions) // 2
    first_half = sessions[:mid]
    second_half = sessions[mid:]

    def bucket_stats(bucket):
        total = len(bucket)
        successes = sum(1 for t in bucket if t["success"])
        durations = [t["duration_seconds"] for t in bucket if t["duration_seconds"] > 0]
        success_rates = [
            t["output"].get("success_rate", 0) for t in bucket
        ]
        return {
            "sessions": total,
            "successes": successes,
            "avg_session_success_rate": round(
                sum(success_rates) / len(success_rates), 3
            ) if success_rates else 0,
            "avg_duration": round(
                sum(durations) / len(durations), 3
            ) if durations else 0,
        }

    early = bucket_stats(first_half)
    recent = bucket_stats(second_half)

    # Calculate improvement
    rate_change = recent["avg_session_success_rate"] - early["avg_session_success_rate"]
    duration_change = early["avg_duration"] - recent["avg_duration"]

    return {
        "early_sessions": early,
        "recent_sessions": recent,
        "improvement": {
            "success_rate_change": round(rate_change, 3),
            "duration_reduction_seconds": round(duration_change, 3),
            "improving": rate_change > 0 or duration_change > 0,
        },
        "total_sessions_analyzed": len(sessions),
    }
