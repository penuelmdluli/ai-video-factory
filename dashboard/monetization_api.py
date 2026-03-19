"""
AI Video Factory — Monetization API Router

FastAPI router that exposes monetization data from the SQLite tracker.
Mount this on the main FastAPI app:

    from dashboard.monetization_api import router as monetization_router
    app.include_router(monetization_router)
"""

import sys
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

# Ensure project root is importable
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.monetization_tracker import (
    get_revenue_summary,
    get_revenue_by_niche,
    get_revenue_trend,
    get_conversion_funnel,
    get_top_affiliates,
    get_monthly_recurring_revenue,
    get_subscriber_stats,
)

router = APIRouter(prefix="/api/monetization", tags=["monetization"])


@router.get("/summary")
async def revenue_summary(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
    niche: str = Query(None, description="Optional niche filter"),
):
    """
    Get total revenue and breakdown by source for the last N days.

    Returns:
        JSON with 'total', 'by_source' dict, 'mrr', and 'period_days'.
    """
    try:
        summary = get_revenue_summary(days=days, niche=niche)
        mrr = get_monthly_recurring_revenue()
        return {**summary, "mrr": mrr}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Failed to fetch revenue summary"},
        )


@router.get("/revenue-by-niche")
async def revenue_by_niche(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
):
    """
    Get revenue totals grouped by niche for the last N days.

    Returns:
        JSON dict mapping niche name to total revenue.
    """
    try:
        data = get_revenue_by_niche(days=days)
        return data
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Failed to fetch revenue by niche"},
        )


@router.get("/revenue-trend")
async def revenue_trend(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
):
    """
    Get daily revenue totals for the last N days.

    Returns:
        JSON list of {date, total} objects.
    """
    try:
        data = get_revenue_trend(days=days)
        return data
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Failed to fetch revenue trend"},
        )


@router.get("/conversion-funnel")
async def conversion_funnel(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
    niche: str = Query(None, description="Optional niche filter"),
):
    """
    Get conversion counts by funnel stage for the last N days.

    Returns:
        JSON dict mapping stage name to count, ordered from view to purchase.
    """
    try:
        data = get_conversion_funnel(niche=niche, days=days)
        return data
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Failed to fetch conversion funnel"},
        )


@router.get("/top-affiliates")
async def top_affiliates(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """
    Get top affiliate links ranked by click count.

    Returns:
        JSON list of {link_url, niche, total_clicks} objects.
    """
    try:
        data = get_top_affiliates(days=days, limit=limit)
        return data
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Failed to fetch top affiliates"},
        )


@router.get("/subscriber-stats")
async def subscriber_stats(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
):
    """
    Get subscriber/signup statistics from conversion data.

    Returns:
        JSON with 'total', 'by_niche' dict, and 'trend' list.
    """
    try:
        data = get_subscriber_stats(days=days)
        return data
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Failed to fetch subscriber stats"},
        )
