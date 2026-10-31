from fastapi import APIRouter, HTTPException
from typing import List
from ..models import FolderCreate, FolderUpdate, FolderResponse
from ..database import db

router = APIRouter(prefix="/api/folders", tags=["folders"])

@router.get("", response_model=List[FolderResponse])
async def list_folders():
    rows = await db.fetch_all("""
        SELECT f.*, COUNT(fd.id) as feed_count 
        FROM folders f 
        LEFT JOIN feeds fd ON f.id = fd.folder_id 
        GROUP BY f.id ORDER BY f.position
    """)
    return rows

@router.post("", response_model=FolderResponse)
async def create_folder(folder: FolderCreate):
    try:
        folder_id = await db.execute("INSERT INTO folders (name) VALUES (?)", (folder.name,))
        row = await db.fetch_one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        row['feed_count'] = 0
        return row
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(folder_id: int, folder: FolderUpdate):
    updates = []
    params = []
    if folder.name is not None:
        updates.append("name = ?")
        params.append(folder.name)
    if folder.position is not None:
        updates.append("position = ?")
        params.append(folder.position)
    
    if updates:
        query = f"UPDATE folders SET {', '.join(updates)} WHERE id = ?"
        params.append(folder_id)
        await db.execute(query, tuple(params))
        
    row = await db.fetch_one("SELECT f.*, COUNT(fd.id) as feed_count FROM folders f LEFT JOIN feeds fd ON f.id = fd.folder_id WHERE f.id = ? GROUP BY f.id", (folder_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Folder not found")
    return row

@router.delete("/{folder_id}")
async def delete_folder(folder_id: int):
    await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    return {"status": "ok"}
