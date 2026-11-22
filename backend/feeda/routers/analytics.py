from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from ..database import db
from ..models import InterestTrendsResponse, LearningInspectorResponse
from ..services.analytics import (
    get_interest_trends,
    get_learning_inspector_data,
    seed_demo_reading_activity,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/interest-trends", response_model=InterestTrendsResponse)
async def fetch_interest_trends(
    period: str = Query("7d", description="Time period: '7d', '14d', '30d', or 'all'"),
):
    """
    Returns interest trends, primary hotspot, top 5 topics per category,
    and daily timeline data for the interactive time scrubber.
    """
    return await get_interest_trends(db, period=period)


@router.get("/learning-inspector", response_model=LearningInspectorResponse)
async def fetch_learning_inspector(
    limit: int = Query(30, ge=1, le=100, description="Max terms to return"),
):
    """
    Returns ML transparency data: top boosted positive & negative vocabulary terms,
    feed affinity leaderboard, behavioral action weights, and learning events.
    """
    return await get_learning_inspector_data(db, limit=limit)


@router.post("/seed-demo-activity")
async def trigger_seed_demo_activity():
    """
    Seeds sample articles and interactions to demonstrate live Bayesian ML updates,
    term weight adjustments, and feed affinity evolution.
    """
    result = await seed_demo_reading_activity(db)
    return result
