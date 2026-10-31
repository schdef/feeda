from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Response
import xml.etree.ElementTree as ET
from html import escape
from typing import List, Optional
from datetime import datetime, timezone
import httpx

from ..models import (
    FeedCreate, FeedUpdate, FeedResponse, FeedListResponse,
    FeedSearchResponse, FeedSuggestionsResponse
)
from ..database import db
from ..services.feed_parser import parse_feed_metadata
from ..services.feed_discovery import search_feeds, get_feed_suggestions

router = APIRouter(prefix="/api/feeds", tags=["feeds"])

@router.get("", response_model=FeedListResponse)
async def list_feeds():
    feeds = await db.fetch_all("""
        SELECT f.*, 
               (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0) as unread_count
        FROM feeds f
        ORDER BY f.title
    """)
    folders = await db.fetch_all("""
        SELECT f.id, f.name, f.position,
               (SELECT COUNT(*) FROM feeds fd WHERE fd.folder_id = f.id) as feed_count,
               (SELECT COUNT(*) FROM articles a JOIN feeds fd ON a.feed_id = fd.id WHERE fd.folder_id = f.id AND a.is_read = 0) as unread_count
        FROM folders f
        ORDER BY f.position
    """)
    return {"feeds": feeds, "folders": folders}

@router.get("/search", response_model=FeedSearchResponse)
async def search_feeds_endpoint(q: str):
    results = await search_feeds(q)
    return {"results": results}

@router.get("/suggestions", response_model=FeedSuggestionsResponse)
async def get_suggestions_endpoint(refresh: Optional[int] = 0):
    return await get_feed_suggestions(refresh=refresh)

@router.post("", response_model=FeedResponse)
async def create_feed(feed: FeedCreate):
    try:
        # Fetch metadata
        meta = await parse_feed_metadata(feed.url)
        
        feed_id = await db.execute("""
            INSERT INTO feeds (url, title, site_url, favicon_url, description, folder_id, poll_interval_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (feed.url, meta.get('title', feed.url), meta.get('site_url'), 
              meta.get('favicon_url'), meta.get('description'), 
              feed.folder_id, feed.poll_interval_minutes))
              
        row = await db.fetch_one("SELECT * FROM feeds WHERE id = ?", (feed_id,))
        row['unread_count'] = 0
        return row
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refresh-all")
async def refresh_all_feeds(background_tasks: BackgroundTasks):
    feeds = await db.fetch_all("SELECT id FROM feeds")
    from ..services.feed_poller import poll_single_feed
    for f in feeds:
        background_tasks.add_task(poll_single_feed, f['id'])
    return {"status": "refreshing", "count": len(feeds)}

@router.put("/{feed_id}", response_model=FeedResponse)
async def update_feed(feed_id: int, feed: FeedUpdate):
    updates = []
    params = []
    for field, value in feed.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ?")
        params.append(value)
        
    if updates:
        params.append(feed_id)
        await db.execute(f"UPDATE feeds SET {', '.join(updates)} WHERE id = ?", tuple(params))
        
    row = await db.fetch_one("SELECT * FROM feeds WHERE id = ?", (feed_id,))
    row['unread_count'] = 0
    return row

@router.delete("/{feed_id}")
async def delete_feed(feed_id: int):
    await db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    return {"status": "ok"}

@router.post("/{feed_id}/refresh")
async def refresh_feed(feed_id: int, background_tasks: BackgroundTasks):
    from ..services.feed_poller import poll_single_feed
    background_tasks.add_task(poll_single_feed, feed_id)
    return {"status": "refreshing"}


@router.post("/opml/import")
async def import_opml(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    content = await file.read()
    try:
        # Strip UTF-8 BOM if present
        xml_text = content.decode('utf-8-sig', errors='replace')
        root = ET.fromstring(xml_text.encode('utf-8'))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {e}")
    
    body = root.find("body")
    if body is None:
        body = root
        
    imported_feeds = 0
    imported_folders = 0
    skipped_feeds = 0
    folder_cache = {}
    seen_urls = set()

    async def get_or_create_folder(folder_name: str) -> Optional[int]:
        nonlocal imported_folders
        clean_name = folder_name.strip()
        if not clean_name:
            return None
        if clean_name in folder_cache:
            return folder_cache[clean_name]
            
        folder = await db.fetch_one("SELECT id FROM folders WHERE name = ?", (clean_name,))
        if folder:
            f_id = folder["id"]
        else:
            pos = await db.fetch_one("SELECT MAX(position) as m FROM folders")
            pos_val = (pos["m"] or 0) + 1 if pos and pos["m"] is not None else 1
            f_id = await db.execute("INSERT INTO folders (name, position) VALUES (?, ?)", (clean_name, pos_val))
            imported_folders += 1
            
        folder_cache[clean_name] = f_id
        return f_id

    async def process_outline(outline_elem, current_folder_name: Optional[str] = None):
        nonlocal imported_feeds, skipped_feeds
        
        attrib = {k.lower(): v for k, v in outline_elem.attrib.items()}
        xml_url = attrib.get("xmlurl", "").strip()
        title_attr = outline_elem.attrib.get("title") or outline_elem.attrib.get("text") or ""
        outline_title = title_attr.strip()
        html_url = attrib.get("htmlurl", "").strip()
        category_attr = attrib.get("category", "").strip()
        
        children = outline_elem.findall("outline")
        
        # Determine folder name for children or this element
        sub_folder_name = current_folder_name
        if children and outline_title:
            sub_folder_name = outline_title
            await get_or_create_folder(outline_title)
        elif not xml_url and outline_title and not children:
            # Standalone empty folder outline
            await get_or_create_folder(outline_title)

        if xml_url:
            feed_folder_name = current_folder_name
            if not feed_folder_name and category_attr:
                feed_folder_name = category_attr.split(",")[0].strip()
                
            folder_id = None
            if feed_folder_name:
                folder_id = await get_or_create_folder(feed_folder_name)
                
            feed_title = outline_title if outline_title else xml_url
            
            if xml_url in seen_urls:
                skipped_feeds += 1
            else:
                seen_urls.add(xml_url)
                existing = await db.fetch_one("SELECT id FROM feeds WHERE url = ?", (xml_url,))
                if existing:
                    skipped_feeds += 1
                else:
                    feed_id = await db.execute("""
                        INSERT INTO feeds (url, title, site_url, folder_id, poll_interval_minutes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (xml_url, feed_title, html_url, folder_id, 60))
                    imported_feeds += 1
                    from ..services.feed_poller import poll_single_feed
                    background_tasks.add_task(poll_single_feed, feed_id)
                    
        for child in children:
            await process_outline(child, current_folder_name=sub_folder_name)

    for outline in body.findall("outline"):
        await process_outline(outline, current_folder_name=None)
        
    return {
        "imported_feeds": imported_feeds,
        "imported_folders": imported_folders,
        "skipped_feeds": skipped_feeds
    }

@router.get("/opml/export")
async def export_opml():
    folders = await db.fetch_all("SELECT id, name FROM folders ORDER BY position, name")
    feeds = await db.fetch_all("SELECT id, title, url, site_url, folder_id FROM feeds ORDER BY title")
    
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        '  <head>',
        '    <title>Feeda Export</title>',
        f'    <dateCreated>{date_str}</dateCreated>',
        '  </head>',
        '  <body>',
    ]
    
    feeds_by_folder = {}
    for f in feeds:
        feeds_by_folder.setdefault(f['folder_id'], []).append(f)
        
    handled_folder_ids = set()
    for folder in folders:
        handled_folder_ids.add(folder['id'])
        folder_feeds = feeds_by_folder.get(folder['id'], [])
        if folder_feeds:
            folder_title = escape(folder["name"] or "Untitled Folder", quote=True)
            lines.append(f'    <outline text="{folder_title}" title="{folder_title}">')
            for feed in folder_feeds:
                f_title = escape(feed["title"] or feed["url"], quote=True)
                f_url = escape(feed["url"] or "", quote=True)
                f_site = escape(feed["site_url"] or "", quote=True)
                lines.append(f'      <outline type="rss" text="{f_title}" title="{f_title}" xmlUrl="{f_url}" htmlUrl="{f_site}" />')
            lines.append('    </outline>')
            
    unfoldered = [f for f in feeds if f['folder_id'] is None or f['folder_id'] not in handled_folder_ids]
    for feed in unfoldered:
        f_title = escape(feed["title"] or feed["url"], quote=True)
        f_url = escape(feed["url"] or "", quote=True)
        f_site = escape(feed["site_url"] or "", quote=True)
        lines.append(f'    <outline type="rss" text="{f_title}" title="{f_title}" xmlUrl="{f_url}" htmlUrl="{f_site}" />')
        
    lines.append('  </body>')
    lines.append('</opml>')
    
    return Response(
        content="\n".join(lines),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="feeda-export.opml"'}
    )


@router.post("/seed")
async def seed_feeds(background_tasks: BackgroundTasks):
    from ..services.seeder import seed_database
    return await seed_database(background_tasks)
