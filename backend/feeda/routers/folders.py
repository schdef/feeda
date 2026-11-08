import asyncio
from fastapi import APIRouter, HTTPException
from typing import List
from ..models import FolderCreate, FolderUpdate, FolderResponse
from ..database import db
from ..services.feed_poller import poll_single_feed

router = APIRouter(prefix="/api/folders", tags=["folders"])

@router.get("", response_model=List[FolderResponse])
async def list_folders():
    rows = await db.fetch_all("""
        SELECT f.*, COUNT(fd.id) as feed_count,
               (SELECT COUNT(*) FROM articles a 
                JOIN feeds fd ON a.feed_id = fd.id 
                WHERE fd.folder_id = f.id AND a.is_read = 0
                  AND (a.cluster_id IS NULL OR a.id = (
                      SELECT a2.id FROM articles a2 
                      JOIN feeds fd2 ON a2.feed_id = fd2.id 
                      WHERE a2.cluster_id = a.cluster_id 
                        AND fd2.folder_id = f.id 
                        AND a2.is_read = 0 
                      ORDER BY datetime(COALESCE(a2.published_at, a2.fetched_at)) ASC, a2.id ASC 
                      LIMIT 1
                  ))) as unread_count
        FROM folders f 
        LEFT JOIN feeds fd ON f.id = fd.folder_id 
        GROUP BY f.id ORDER BY f.position
    """)
    return rows

@router.post("", response_model=FolderResponse)
async def create_folder(folder: FolderCreate):
    try:
        clean_name = folder.name.strip()
        existing = await db.fetch_one("SELECT * FROM folders WHERE name = ?", (clean_name,))
        if existing:
            unread = await db.fetch_one("""
                SELECT COUNT(*) as unread_count 
                FROM articles a 
                JOIN feeds fd ON a.feed_id = fd.id 
                WHERE fd.folder_id = ? AND a.is_read = 0
                  AND (a.cluster_id IS NULL OR a.id = (
                      SELECT a2.id FROM articles a2 
                      JOIN feeds fd2 ON a2.feed_id = fd2.id 
                      WHERE a2.cluster_id = a.cluster_id 
                        AND fd2.folder_id = ? 
                        AND a2.is_read = 0 
                      ORDER BY datetime(COALESCE(a2.published_at, a2.fetched_at)) ASC, a2.id ASC 
                      LIMIT 1
                  ))
            """, (existing["id"], existing["id"]))
            feed_count = await db.fetch_one("SELECT COUNT(*) as cnt FROM feeds WHERE folder_id = ?", (existing["id"],))
            return {
                "id": existing["id"],
                "name": existing["name"],
                "position": existing["position"],
                "feed_count": feed_count["cnt"] if feed_count else 0,
                "unread_count": unread["unread_count"] if unread else 0
            }

        pos = await db.fetch_one("SELECT MAX(position) as m FROM folders")
        pos_val = (pos["m"] or 0) + 1 if pos and pos["m"] is not None else 1
        folder_id = await db.execute("INSERT INTO folders (name, position) VALUES (?, ?)", (clean_name, pos_val))
        row = await db.fetch_one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        return {
            "id": row["id"],
            "name": row["name"],
            "position": row["position"],
            "feed_count": 0,
            "unread_count": 0
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{folder_id}", response_model=FolderResponse)
@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(folder_id: int, folder: FolderUpdate):
    updates = []
    params = []
    if folder.name is not None:
        updates.append("name = ?")
        params.append(folder.name.strip())
    if folder.position is not None:
        updates.append("position = ?")
        params.append(folder.position)
    
    if updates:
        query = f"UPDATE folders SET {', '.join(updates)} WHERE id = ?"
        params.append(folder_id)
        await db.execute(query, tuple(params))
        
    row = await db.fetch_one("""
        SELECT f.*, COUNT(fd.id) as feed_count,
               (SELECT COUNT(*) FROM articles a 
                JOIN feeds fd ON a.feed_id = fd.id 
                WHERE fd.folder_id = f.id AND a.is_read = 0
                  AND (a.cluster_id IS NULL OR a.id = (
                      SELECT a2.id FROM articles a2 
                      JOIN feeds fd2 ON a2.feed_id = fd2.id 
                      WHERE a2.cluster_id = a.cluster_id 
                        AND fd2.folder_id = f.id 
                        AND a2.is_read = 0 
                      ORDER BY datetime(COALESCE(a2.published_at, a2.fetched_at)) ASC, a2.id ASC 
                      LIMIT 1
                  ))) as unread_count
        FROM folders f 
        LEFT JOIN feeds fd ON f.id = fd.folder_id 
        WHERE f.id = ? 
        GROUP BY f.id
    """, (folder_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Folder not found")
    return row

@router.delete("/{folder_id}")
async def delete_folder(folder_id: int):
    await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    return {"status": "ok"}

@router.post("/{folder_id}/refresh")
async def refresh_folder(folder_id: int):
    feeds = await db.fetch_all("SELECT id FROM feeds WHERE folder_id = ?", (folder_id,))
    if not feeds:
        return {"status": "ok", "count": 0}
    await asyncio.gather(*(poll_single_feed(f['id']) for f in feeds), return_exceptions=True)
    return {"status": "ok", "count": len(feeds)}
