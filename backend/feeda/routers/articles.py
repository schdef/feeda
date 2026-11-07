from fastapi import APIRouter, Query
from typing import List, Optional, Union
import asyncio
from ..models import ArticleResponse, ArticleListResponse, SearchResponse, ArticleBoardsResponse
from ..database import db
from ..services.llm_dedup import deduplicate_articles_sync, cluster_unclustered_articles_background
from ..services.feed_parser import decode_html_text

router = APIRouter(prefix="/api/articles", tags=["articles"])

async def get_likelihood_thresholds():
    stats = await db.fetch_one("""
        SELECT AVG(interest_score) as avg_score, MIN(interest_score) as min_score, MAX(interest_score) as max_score 
        FROM articles 
        WHERE is_read = 0 AND (published_at IS NULL OR datetime(published_at) >= datetime('now', '-6 months'))
    """)
    if not stats or stats.get('avg_score') is None:
        stats = await db.fetch_one("""
            SELECT AVG(interest_score) as avg_score, MIN(interest_score) as min_score, MAX(interest_score) as max_score 
            FROM articles 
            WHERE published_at IS NULL OR datetime(published_at) >= datetime('now', '-6 months')
        """)
    avg_score = float(stats['avg_score']) if stats and stats.get('avg_score') is not None else 0.0
    min_score = float(stats['min_score']) if stats and stats.get('min_score') is not None else 0.0
    max_score = float(stats['max_score']) if stats and stats.get('max_score') is not None else 0.0

    likely_threshold = avg_score

    rows = await db.fetch_all("""
        SELECT interest_score FROM articles 
        WHERE is_read = 0 AND (published_at IS NULL OR datetime(published_at) >= datetime('now', '-6 months'))
        ORDER BY interest_score DESC
    """)
    scores = [float(r['interest_score']) for r in rows if r.get('interest_score') is not None]
    if not scores:
        rows = await db.fetch_all("""
            SELECT interest_score FROM articles 
            WHERE published_at IS NULL OR datetime(published_at) >= datetime('now', '-6 months')
            ORDER BY interest_score DESC
        """)
        scores = [float(r['interest_score']) for r in rows if r.get('interest_score') is not None]

    if not scores or len(scores) < 10:
        high_threshold = max(likely_threshold + 1.0, max_score)
    else:
        top_20_idx = max(1, int(len(scores) * 0.20))
        spread_above = max_score - likely_threshold
        min_high = likely_threshold + max(1.0, spread_above * 0.25 if spread_above > 0 else 1.0)
        high_threshold = max(scores[top_20_idx], min_high)

    if high_threshold <= likely_threshold:
        high_threshold = likely_threshold + 1.0

    return likely_threshold, high_threshold, min_score, max_score

async def get_for_you_threshold() -> float:
    _, high_threshold, _, _ = await get_likelihood_thresholds()
    return high_threshold

def compute_likelihood_tier(score: float, likely_threshold: float, high_threshold: float) -> str:
    if score < likely_threshold:
        return "low"
    elif score >= high_threshold:
        return "high"
    else:
        return "medium"

@router.get("", response_model=ArticleListResponse)
async def list_articles(
    feed_id: Optional[int] = None,
    folder_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    is_starred: Optional[bool] = None,
    today: Optional[bool] = None,
    likelihood: Optional[str] = Query(None, pattern="^(likely|not_likely|all)$"),
    sort: str = Query("date", pattern="^(date|score)$"),
    page: int = 1,
    limit: int = 50,
    dedup: bool = Query(True)
):
    where = []
    params = []
    
    if feed_id:
        where.append("a.feed_id = ?")
        params.append(feed_id)
    if folder_id:
        where.append("f.folder_id = ?")
        params.append(folder_id)
    if is_read is not None:
        where.append("a.is_read = ?")
        params.append(1 if is_read else 0)
    if is_starred is not None:
        where.append("a.is_starred = ?")
        params.append(1 if is_starred else 0)
    if today:
        where.append("(date(a.published_at) = date('now') OR datetime(a.published_at) >= datetime('now', '-24 hours'))")

    likely_threshold, high_threshold, min_score, max_score = await get_likelihood_thresholds()
    score_spread = max_score - min_score

    if likelihood is not None:
        effective_likelihood = likelihood
    elif today or feed_id or folder_id:
        effective_likelihood = "all"
    else:
        effective_likelihood = "likely"

    if effective_likelihood == "likely":
        if score_spread > 0.05:
            where.append("a.interest_score >= ?")
            params.append(likely_threshold)
    elif effective_likelihood == "not_likely":
        where.append("a.interest_score < ?")
        params.append(likely_threshold)

    if effective_likelihood == "likely" or sort == "score":
        where.append("(a.published_at IS NULL OR datetime(a.published_at) >= datetime('now', '-6 months'))")

    if sort == "date":
        order_clause = "ORDER BY a.published_at DESC, a.id DESC"
    else:
        order_clause = "ORDER BY a.interest_score ASC, a.published_at DESC, a.id DESC" if effective_likelihood == "not_likely" else "ORDER BY a.interest_score DESC, a.published_at DESC, a.id DESC"

    if dedup:
        subquery_where = ["a2.cluster_id = a.cluster_id"]
        subquery_joins = ""

        if feed_id:
            subquery_where.append("a2.feed_id = a.feed_id")
        elif folder_id:
            subquery_joins = "JOIN feeds f2 ON a2.feed_id = f2.id"
            subquery_where.append("f2.folder_id = f.folder_id")

        if is_read is not None:
            subquery_where.append(f"a2.is_read = {1 if is_read else 0}")

        subquery_where_str = " AND ".join(subquery_where)
        where.append(f"""(a.cluster_id IS NULL OR a.id = (
            SELECT a2.id FROM articles a2 
            {subquery_joins}
            WHERE {subquery_where_str}
            ORDER BY datetime(COALESCE(a2.published_at, a2.fetched_at)) ASC, a2.id ASC 
            LIMIT 1
        ))""")

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    offset = (page - 1) * limit
    
    query = f"""
        SELECT a.*, 
               f.title as feed_title,
               f.favicon_url as feed_favicon_url,
               (SELECT COUNT(*) FROM articles ac WHERE ac.cluster_id = a.cluster_id) as cluster_count,
               (SELECT GROUP_CONCAT(DISTINCT f2.title) 
                FROM articles ac2 
                JOIN feeds f2 ON ac2.feed_id = f2.id 
                WHERE ac2.cluster_id = a.cluster_id AND ac2.id != a.id) as other_cluster_sources
        FROM articles a
        LEFT JOIN feeds f ON a.feed_id = f.id
        {where_clause}
        {order_clause}
        LIMIT ? OFFSET ?
    """
    
    count_query = f"SELECT COUNT(*) as total FROM articles a LEFT JOIN feeds f ON a.feed_id = f.id {where_clause}"
    
    if dedup:
        fetch_limit = max(page * limit * 3, page * limit + 100)
        items = await db.fetch_all(query, tuple(params + [fetch_limit, 0]))
    else:
        items = await db.fetch_all(query, tuple(params + [limit, offset]))

    for item in items:
        item['is_read'] = bool(item['is_read'])
        item['is_starred'] = bool(item['is_starred'])
        item['feed_title'] = decode_html_text(item.get('feed_title')) or 'Feed'
        item['title'] = decode_html_text(item.get('title'))
        item['summary'] = decode_html_text(item.get('summary'))
        raw_sources = item.get('other_cluster_sources')
        if raw_sources:
            item['cluster_sources'] = [decode_html_text(s.strip()) for s in raw_sources.split(',') if s.strip()]
        else:
            item['cluster_sources'] = []
        item['cluster_count'] = item.get('cluster_count') or 1
        item['interest_score'] = float(item.get('interest_score') or 0.0)
        item['likelihood_tier'] = compute_likelihood_tier(item['interest_score'], likely_threshold, high_threshold)
        
    if dedup:
        items = deduplicate_articles_sync(items)
        if not feed_id and not folder_id:
            if any(not a.get("cluster_id") for a in items):
                asyncio.create_task(cluster_unclustered_articles_background(db))
        items = items[offset : offset + limit]
    
    total_row = await db.fetch_one(count_query, tuple(params))
    
    total = total_row['total'] if total_row else 0
    return {
        "articles": items,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (page * limit) < total
    }

@router.get("/for-you", response_model=ArticleListResponse)
async def for_you(
    page: int = 1,
    limit: int = 50,
    is_read: Optional[Union[bool, str]] = Query(False),
    dedup: bool = Query(True),
    sort: str = Query("date", pattern="^(date|score)$")
):
    if hasattr(is_read, "default"):
        is_read = is_read.default
    if hasattr(dedup, "default"):
        dedup = dedup.default

    actual_is_read: Optional[bool]
    if isinstance(is_read, str):
        if is_read.lower() in ("all", "none", "null", ""):
            actual_is_read = None
        elif is_read.lower() in ("true", "1"):
            actual_is_read = True
        elif is_read.lower() in ("false", "0"):
            actual_is_read = False
        else:
            actual_is_read = False
    elif is_read is None:
        actual_is_read = None
    else:
        actual_is_read = bool(is_read)

    threshold = await get_for_you_threshold()
    offset = (page - 1) * limit

    where = ["a.interest_score >= ?"]
    params = [threshold]

    where.append("(a.published_at IS NULL OR datetime(a.published_at) >= datetime('now', '-6 months'))")

    if actual_is_read is not None:
        where.append("a.is_read = ?")
        params.append(1 if actual_is_read else 0)

    if dedup:
        subquery_where = ["a2.cluster_id = a.cluster_id"]
        if actual_is_read is not None:
            subquery_where.append(f"a2.is_read = {1 if actual_is_read else 0}")

        subquery_where_str = " AND ".join(subquery_where)
        where.append(f"""(a.cluster_id IS NULL OR a.id = (
            SELECT a2.id FROM articles a2 
            WHERE {subquery_where_str}
            ORDER BY datetime(COALESCE(a2.published_at, a2.fetched_at)) ASC, a2.id ASC 
            LIMIT 1
        ))""")

    where_clause = f"WHERE {' AND '.join(where)}"
    order_clause = "ORDER BY a.published_at DESC, a.id DESC" if sort == "date" else "ORDER BY a.interest_score DESC, a.published_at DESC, a.id DESC"

    query = f"""
        SELECT a.*, 
               f.title as feed_title,
               f.favicon_url as feed_favicon_url,
               (SELECT COUNT(*) FROM articles ac WHERE ac.cluster_id = a.cluster_id) as cluster_count,
               (SELECT GROUP_CONCAT(DISTINCT f2.title) 
                FROM articles ac2 
                JOIN feeds f2 ON ac2.feed_id = f2.id 
                WHERE ac2.cluster_id = a.cluster_id AND ac2.id != a.id) as other_cluster_sources
        FROM articles a
        LEFT JOIN feeds f ON a.feed_id = f.id
        {where_clause}
        {order_clause}
        LIMIT ? OFFSET ?
    """
    if dedup:
        fetch_limit = max(page * limit * 3, page * limit + 100)
        items = await db.fetch_all(query, tuple(params + [fetch_limit, 0]))
    else:
        items = await db.fetch_all(query, tuple(params + [limit, offset]))

    for item in items:
        item['is_read'] = bool(item['is_read'])
        item['is_starred'] = bool(item['is_starred'])
        item['feed_title'] = decode_html_text(item.get('feed_title')) or 'Feed'
        item['title'] = decode_html_text(item.get('title'))
        item['summary'] = decode_html_text(item.get('summary'))
        raw_sources = item.get('other_cluster_sources')
        if raw_sources:
            item['cluster_sources'] = [decode_html_text(s.strip()) for s in raw_sources.split(',') if s.strip()]
        else:
            item['cluster_sources'] = []
        item['cluster_count'] = item.get('cluster_count') or 1
        item['interest_score'] = float(item.get('interest_score') or 0.0)
        item['likelihood_tier'] = 'high'

    if dedup:
        items = deduplicate_articles_sync(items)
        items = items[offset : offset + limit]

    count_row = await db.fetch_one(
        f"SELECT COUNT(*) as total FROM articles a LEFT JOIN feeds f ON a.feed_id = f.id {where_clause}",
        tuple(params)
    )
    total = count_row['total'] if count_row else 0

    return {
        "articles": items,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (page * limit) < total
    }

@router.get("/search", response_model=SearchResponse)
async def search_articles(q: str, limit: int = 50):
    likely_threshold, high_threshold, _, _ = await get_likelihood_thresholds()

    query = """
        SELECT a.*, 
               f.title as feed_title,
               f.favicon_url as feed_favicon_url
        FROM articles_fts fts
        JOIN articles a ON fts.rowid = a.id
        LEFT JOIN feeds f ON a.feed_id = f.id
        WHERE articles_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    items = await db.fetch_all(query, (q, limit))
    for item in items:
        item['is_read'] = bool(item['is_read'])
        item['is_starred'] = bool(item['is_starred'])
        item['feed_title'] = decode_html_text(item.get('feed_title')) or 'Feed'
        item['title'] = decode_html_text(item.get('title'))
        item['summary'] = decode_html_text(item.get('summary'))
        item['cluster_count'] = 1
        item['cluster_sources'] = []
        item['interest_score'] = float(item.get('interest_score') or 0.0)
        item['likelihood_tier'] = compute_likelihood_tier(item['interest_score'], likely_threshold, high_threshold)
    
    return {"articles": items, "total": len(items)}

@router.get("/dedup-status")
async def dedup_status():
    """Returns some basic stats about clustering in the database."""
    clusters_count = await db.fetch_one("SELECT COUNT(*) as total FROM clusters")
    clustered_articles = await db.fetch_one("SELECT COUNT(*) as total FROM articles WHERE cluster_id IS NOT NULL")
    
    return {
        "total_clusters": clusters_count["total"] if clusters_count else 0,
        "clustered_articles": clustered_articles["total"] if clustered_articles else 0,
        "llm_dedup_enabled": True
    }

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int):
    likely_threshold, high_threshold, _, _ = await get_likelihood_thresholds()

    item = await db.fetch_one("""
        SELECT a.*, 
               f.title as feed_title,
               f.favicon_url as feed_favicon_url,
               (SELECT COUNT(*) FROM articles ac WHERE ac.cluster_id = a.cluster_id) as cluster_count,
               (SELECT GROUP_CONCAT(DISTINCT f2.title) 
                FROM articles ac2 
                JOIN feeds f2 ON ac2.feed_id = f2.id 
                WHERE ac2.cluster_id = a.cluster_id AND ac2.id != a.id) as other_cluster_sources
        FROM articles a
        LEFT JOIN feeds f ON a.feed_id = f.id
        WHERE a.id = ?
    """, (article_id,))
    if item:
        item['is_read'] = bool(item['is_read'])
        item['is_starred'] = bool(item['is_starred'])
        item['feed_title'] = decode_html_text(item.get('feed_title')) or 'Feed'
        item['title'] = decode_html_text(item.get('title'))
        item['summary'] = decode_html_text(item.get('summary'))
        item['author'] = decode_html_text(item.get('author'))
        if item.get('content'):
            item['content'] = decode_html_text(item['content'])
        raw_sources = item.get('other_cluster_sources')
        if raw_sources:
            item['cluster_sources'] = [decode_html_text(s.strip()) for s in raw_sources.split(',') if s.strip()]
        else:
            item['cluster_sources'] = []
        item['cluster_count'] = item.get('cluster_count') or 1
        item['interest_score'] = float(item.get('interest_score') or 0.0)
        item['likelihood_tier'] = compute_likelihood_tier(item['interest_score'], likely_threshold, high_threshold)
    return item

@router.get("/{article_id}/boards", response_model=ArticleBoardsResponse)
async def get_article_boards_endpoint(article_id: int):
    from .boards import get_article_boards
    return await get_article_boards(article_id)

