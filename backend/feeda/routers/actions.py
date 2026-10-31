from fastapi import APIRouter, HTTPException
from ..models import InteractionCreate, VoteRequest, MarkAllReadRequest
from ..database import db
from ..services.ranker import update_term_weights, rescore_articles
import asyncio
import datetime

router = APIRouter(prefix="/api/articles", tags=["actions"])

@router.post("/{article_id}/read")
async def mark_read(article_id: int):
    now = datetime.datetime.utcnow().isoformat()
    article = await db.fetch_one("SELECT cluster_id FROM articles WHERE id = ?", (article_id,))
    if article and article.get('cluster_id'):
        await db.execute("UPDATE articles SET is_read = 1, read_at = ? WHERE cluster_id = ?", (now, article['cluster_id']))
    else:
        await db.execute("UPDATE articles SET is_read = 1, read_at = ? WHERE id = ?", (now, article_id))
    await db.execute("INSERT INTO interactions (article_id, action) VALUES (?, 'open_article')", (article_id,))
    await update_term_weights(article_id, 'open_article', db)
    asyncio.create_task(rescore_articles(db))
    return {"status": "ok"}

@router.post("/{article_id}/unread")
async def mark_unread(article_id: int):
    await db.execute("UPDATE articles SET is_read = 0, read_at = NULL WHERE id = ?", (article_id,))
    return {"status": "ok"}

@router.post("/{article_id}/star")
async def toggle_star(article_id: int):
    article = await db.fetch_one("SELECT is_starred FROM articles WHERE id = ?", (article_id,))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    new_val = 0 if article['is_starred'] else 1
    await db.execute("UPDATE articles SET is_starred = ? WHERE id = ?", (new_val, article_id))
    action = 'star' if new_val else 'unstar'
    await update_term_weights(article_id, action, db)
    asyncio.create_task(rescore_articles(db))
    return {"status": "ok", "is_starred": bool(new_val)}

@router.post("/{article_id}/vote")
async def vote_article(article_id: int, req: VoteRequest):
    article = await db.fetch_one("SELECT id FROM articles WHERE id = ?", (article_id,))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    await db.execute("UPDATE articles SET user_vote = ? WHERE id = ?", (req.direction, article_id))
    action = 'vote_up' if req.direction == 1 else 'vote_down'
    if req.direction == 0:
        action = 'vote_neutral'
    await update_term_weights(article_id, action, db)
    asyncio.create_task(rescore_articles(db))
    return {"status": "ok"}

@router.post("/{article_id}/open")
async def open_article(article_id: int):
    article = await db.fetch_one("SELECT id, feed_id, cluster_id FROM articles WHERE id = ?", (article_id,))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    now = datetime.datetime.utcnow().isoformat()
    if article.get('cluster_id'):
        await db.execute("UPDATE articles SET is_read = 1, read_at = ? WHERE cluster_id = ?", (now, article['cluster_id']))
    else:
        await db.execute("UPDATE articles SET is_read = 1, read_at = ? WHERE id = ?", (now, article_id))

    await db.execute("INSERT INTO interactions (article_id, action) VALUES (?, 'open_website')", (article_id,))
    await update_term_weights(article_id, 'open_website', db)
    asyncio.create_task(rescore_articles(db))
    return {"status": "ok", "article_id": article_id}

@router.post("/{article_id}/interact")
async def log_interaction(article_id: int, req: InteractionCreate):
    article = await db.fetch_one("SELECT id FROM articles WHERE id = ?", (article_id,))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    await db.execute("INSERT INTO interactions (article_id, action, dwell_time_seconds) VALUES (?, ?, ?)", 
                     (article_id, req.action, req.dwell_time))
    await update_term_weights(article_id, req.action, db)
    asyncio.create_task(rescore_articles(db))
    return {"status": "ok"}

@router.post("/mark-all-read")
async def mark_all_read(req: MarkAllReadRequest):
    now = datetime.datetime.utcnow().isoformat()
    where = ["is_read = 0"]
    params = [now]

    if req.feed_id:
        where.append("feed_id = ?")
        params.append(req.feed_id)
    elif req.folder_id:
        where.append("feed_id IN (SELECT id FROM feeds WHERE folder_id = ?)")
        params.append(req.folder_id)

    cutoff_days = None
    if req.older_than == '1d' or req.days == 1:
        cutoff_days = 1
    elif req.older_than == '1w' or req.days == 7:
        cutoff_days = 7
    elif req.days and req.days > 0:
        cutoff_days = req.days

    if cutoff_days:
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=cutoff_days)).isoformat()
        where.append("(published_at < ? OR (published_at IS NULL AND fetched_at < ?))")
        params.append(cutoff)
        params.append(cutoff)

    where_sql = f"WHERE {' AND '.join(where)}"
    await db.execute(f"UPDATE articles SET is_read = 1, read_at = ? {where_sql}", tuple(params))
    return {"status": "ok"}
