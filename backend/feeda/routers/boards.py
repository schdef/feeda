from fastapi import APIRouter, HTTPException, Query
from fastapi.routing import APIRoute
from typing import List, Optional, Any
import asyncio
from ..models import (
    BoardCreate,
    BoardUpdate,
    BoardResponse,
    BoardListResponse,
    SaveToBoardRequest,
    UpdateBoardNoteRequest,
    ArticleBoardsResponse,
    ArticleListResponse,
)
from ..database import db
from ..services.ranker import update_term_weights, rescore_articles
from ..services.feed_parser import decode_html_text
from .articles import compute_likelihood_tier, get_likelihood_thresholds, format_article_dict

router = APIRouter(prefix="/api/boards", tags=["boards"])

@router.get("", response_model=BoardListResponse)
async def list_boards():
    rows = await db.fetch_all("""
        SELECT b.*, 
               (SELECT COUNT(*) FROM board_articles ba WHERE ba.board_id = b.id) as article_count
        FROM boards b
        ORDER BY b.position ASC, b.created_at ASC
    """)
    for row in rows:
        row['article_count'] = int(row.get('article_count') or 0)
    return {"boards": rows}

@router.post("", response_model=BoardResponse)
async def create_board(board: BoardCreate):
    try:
        board_id = await db.execute(
            "INSERT INTO boards (name, description) VALUES (?, ?)",
            (board.name.strip(), board.description)
        )
        row = await db.fetch_one("SELECT * FROM boards WHERE id = ?", (board_id,))
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create board")
        row = dict(row)
        row['article_count'] = 0
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{board_id}", response_model=BoardResponse)
async def get_board(board_id: int):
    row = await db.fetch_one("""
        SELECT b.*, 
               (SELECT COUNT(*) FROM board_articles ba WHERE ba.board_id = b.id) as article_count
        FROM boards b
        WHERE b.id = ?
    """, (board_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Board not found")
    row = dict(row)
    row['article_count'] = int(row.get('article_count') or 0)
    return row

@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(board_id: int, board: BoardUpdate):
    existing = await db.fetch_one("SELECT id FROM boards WHERE id = ?", (board_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Board not found")

    updates = []
    params = []
    if board.name is not None:
        updates.append("name = ?")
        params.append(board.name.strip())
    if board.description is not None:
        updates.append("description = ?")
        params.append(board.description)
    if board.position is not None:
        updates.append("position = ?")
        params.append(board.position)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        query = f"UPDATE boards SET {', '.join(updates)} WHERE id = ?"
        params.append(board_id)
        await db.execute(query, tuple(params))

    row = await db.fetch_one("""
        SELECT b.*, 
               (SELECT COUNT(*) FROM board_articles ba WHERE ba.board_id = b.id) as article_count
        FROM boards b
        WHERE b.id = ?
    """, (board_id,))
    row = dict(row)
    row['article_count'] = int(row.get('article_count') or 0)
    return row

@router.delete("/{board_id}")
async def delete_board(board_id: int):
    existing = await db.fetch_one("SELECT id FROM boards WHERE id = ?", (board_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Board not found")

    await db.execute("DELETE FROM board_articles WHERE board_id = ?", (board_id,))
    await db.execute("DELETE FROM boards WHERE id = ?", (board_id,))
    return {"status": "ok"}

@router.get("/{board_id}/articles", response_model=ArticleListResponse)
async def get_board_articles(
    board_id: int,
    sort: str = Query("date_added", pattern="^(date_added|date)$"),
    page: int = 1,
    limit: int = 50,
):
    board = await db.fetch_one("SELECT id FROM boards WHERE id = ?", (board_id,))
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    likely_threshold, high_threshold, _, _ = await get_likelihood_thresholds()

    if sort == "date":
        order_clause = "ORDER BY a.published_at DESC"
    else:
        order_clause = "ORDER BY ba.added_at DESC"

    offset = (page - 1) * limit

    query = f"""
        SELECT a.*, 
               f.title as feed_title,
               f.favicon_url as feed_favicon_url,
               (SELECT COUNT(*) FROM articles ac WHERE ac.cluster_id = a.cluster_id) as cluster_count,
               ba.note as board_note,
               ba.added_at as board_added_at
        FROM board_articles ba
        JOIN articles a ON ba.article_id = a.id
        LEFT JOIN feeds f ON a.feed_id = f.id
        WHERE ba.board_id = ?
        {order_clause}
        LIMIT ? OFFSET ?
    """
    items = await db.fetch_all(query, (board_id, limit, offset))
    for item in items:
        board_note = item.get('board_note')
        board_added_at = str(item.get('board_added_at')) if item.get('board_added_at') else None
        format_article_dict(item, likely_threshold, high_threshold)
        item['board_note'] = board_note
        item['board_added_at'] = board_added_at

    count_row = await db.fetch_one("SELECT COUNT(*) as total FROM board_articles WHERE board_id = ?", (board_id,))
    total = count_row['total'] if count_row else 0

    return {
        "articles": items,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (page * limit) < total
    }

@router.post("/{board_id}/articles")
async def save_to_board(board_id: int, req: SaveToBoardRequest):
    board = await db.fetch_one("SELECT id FROM boards WHERE id = ?", (board_id,))
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    article = await db.fetch_one("SELECT id FROM articles WHERE id = ?", (req.article_id,))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    await db.execute("""
        INSERT INTO board_articles (board_id, article_id, note)
        VALUES (?, ?, ?)
        ON CONFLICT(board_id, article_id) DO UPDATE SET note = excluded.note
    """, (board_id, req.article_id, req.note))

    await db.execute("INSERT INTO interactions (article_id, action) VALUES (?, 'save_to_board')", (req.article_id,))
    await update_term_weights(req.article_id, 'save_to_board', db)
    asyncio.create_task(rescore_articles(db))

    return {"status": "ok", "board_id": board_id, "article_id": req.article_id}

@router.delete("/{board_id}/articles/{article_id}")
async def remove_from_board(board_id: int, article_id: int):
    await db.execute("DELETE FROM board_articles WHERE board_id = ? AND article_id = ?", (board_id, article_id))
    return {"status": "ok"}

@router.put("/{board_id}/articles/{article_id}/note")
async def update_board_article_note(board_id: int, article_id: int, req: UpdateBoardNoteRequest):
    existing = await db.fetch_one(
        "SELECT 1 FROM board_articles WHERE board_id = ? AND article_id = ?",
        (board_id, article_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Article not found in board")

    await db.execute(
        "UPDATE board_articles SET note = ? WHERE board_id = ? AND article_id = ?",
        (req.note, board_id, article_id)
    )
    return {"status": "ok", "board_id": board_id, "article_id": article_id, "note": req.note}

async def get_article_boards(article_id: int) -> dict:
    rows = await db.fetch_all("""
        SELECT ba.board_id, b.name as board_name, ba.note, ba.added_at
        FROM board_articles ba
        JOIN boards b ON ba.board_id = b.id
        WHERE ba.article_id = ?
        ORDER BY ba.added_at DESC
    """, (article_id,))
    for row in rows:
        if row.get('added_at'):
            row['added_at'] = str(row['added_at'])
    return {
        "article_id": article_id,
        "boards": rows
    }

@router.get("/by-article/{article_id}", response_model=ArticleBoardsResponse)
async def get_boards_by_article(article_id: int):
    return await get_article_boards(article_id)

# Direct route registration so it is reachable under /api/articles/{article_id}/boards
router.routes.append(
    APIRoute(
        path="/api/articles/{article_id}/boards",
        endpoint=get_article_boards,
        methods=["GET"],
        response_model=ArticleBoardsResponse,
        tags=["boards"]
    )
)
