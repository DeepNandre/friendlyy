"""
Traces dashboard API - Shows W&B Weave tracing data and self-improvement metrics.
For hackathon judges to see the self-improving workflow in action.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query

from services.weave_tracing import (
    get_performance_summary,
    get_recent_traces,
    get_improvement_data,
)
from core import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/traces")
async def get_traces_dashboard():
    """
    Get the full traces dashboard data.

    Returns aggregate metrics, improvement data, and recent traces.
    This is the main endpoint for demonstrating the self-improving workflow.
    """
    return {
        "project": settings.weave_project,
        "weave_enabled": bool(settings.wandb_api_key),
        "performance": get_performance_summary(),
        "improvement": get_improvement_data(),
        "recent_traces": get_recent_traces(limit=10),
    }


@router.get("/traces/performance")
async def get_performance():
    """Get aggregate performance metrics across all operations."""
    return get_performance_summary()


@router.get("/traces/improvement")
async def get_improvement():
    """
    Get improvement data showing success rate progression over time.
    This is the key data for the Self-Improving Workflow prize.
    """
    return get_improvement_data()


@router.get("/traces/recent")
async def get_recent(
    operation: Optional[str] = Query(None, description="Filter by operation type"),
    limit: int = Query(20, ge=1, le=100, description="Number of traces to return"),
):
    """Get recent traces, optionally filtered by operation type."""
    return get_recent_traces(operation=operation, limit=limit)


@router.get("/traces/blitz")
async def get_blitz_traces():
    """Get Blitz-specific traces and insights."""
    blitz_calls = get_recent_traces(operation="blitz_call", limit=50)
    blitz_sessions = get_recent_traces(operation="blitz_session", limit=20)
    performance = get_performance_summary()

    return {
        "blitz_insights": performance.get("blitz_insights", {}),
        "recent_calls": blitz_calls[-10:],
        "recent_sessions": blitz_sessions[-5:],
        "total_calls": len(blitz_calls),
        "total_sessions": len(blitz_sessions),
    }
