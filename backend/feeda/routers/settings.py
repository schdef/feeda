from fastapi import APIRouter
from ..models import StatsResponse
from ..database import db
from .articles import get_for_you_threshold

router = APIRouter(prefix="/api", tags=["settings"])

@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    total_feeds = (await db.fetch_one("SELECT COUNT(*) as c FROM feeds"))['c']
    total_articles = (await db.fetch_one("SELECT COUNT(*) as c FROM articles"))['c']
    unread_count = (await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE is_read = 0"))['c']
    starred_count = (await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE is_starred = 1"))['c']

    today_row = await db.fetch_one(
        "SELECT COUNT(*) as c FROM articles WHERE is_read = 0 AND (date(published_at) = date('now') OR datetime(published_at) >= datetime('now', '-24 hours'))"
    )
    today_unread_count = today_row['c'] if today_row else 0

    for_you_threshold = await get_for_you_threshold()
    for_you_row = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles a 
        WHERE a.is_read = 0 AND a.interest_score >= ? AND (
            a.cluster_id IS NULL OR a.id = (
                SELECT a2.id FROM articles a2 
                WHERE a2.cluster_id = a.cluster_id 
                ORDER BY datetime(COALESCE(a2.published_at, a2.fetched_at)) ASC, a2.id ASC 
                LIMIT 1
            )
        )
    """, (for_you_threshold,))
    for_you_unread_count = for_you_row['c'] if for_you_row else 0

    return {
        "total_feeds": total_feeds,
        "total_articles": total_articles,
        "unread_count": unread_count,
        "starred_count": starred_count,
        "today_unread_count": today_unread_count,
        "for_you_unread_count": for_you_unread_count
    }
