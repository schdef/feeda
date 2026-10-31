from ..database import db

SEED_DATA = {
    "Lean": [
        {"title": "BASIC thinking", "url": "https://www.basicthinking.de/blog/feed/", "favicon": "https://www.basicthinking.de/favicon.ico"},
        {"title": "Gründerszene", "url": "https://www.businessinsider.de/gruenderszene/feed/", "favicon": "https://www.businessinsider.de/favicon.ico"},
        {"title": "Agile Zone", "url": "https://feeds.dzone.com/agile", "favicon": "https://dzone.com/favicon.ico"},
        {"title": "The Digital Project Manager", "url": "https://thedigitalprojectmanager.com/feed/", "favicon": "https://thedigitalprojectmanager.com/favicon.ico"}
    ],
    "Aktuell": [
        {"title": "SPIEGEL ONLINE - Schlagzeilen", "url": "https://www.spiegel.de/schlagzeilen/tops/index.rss", "favicon": "https://www.spiegel.de/favicon.ico"}
    ],
    "Coding": [
        {"title": "codecentric Blog", "url": "https://blog.codecentric.de/feed", "favicon": "https://www.codecentric.de/favicon.ico"},
        {"title": "InfoQ", "url": "https://feed.infoq.com/", "favicon": "https://www.infoq.com/favicon.ico"},
        {"title": "The Netflix Tech Blog", "url": "https://netflixtechblog.com/feed", "favicon": "https://netflixtechblog.com/favicon.ico"}
    ],
    "Serien": [
        {"title": "Serienjunkies.de - News", "url": "https://www.serienjunkies.de/news/rssfeed.xml", "favicon": "https://www.serienjunkies.de/favicon.ico"}
    ],
    "Tech": [
        {"title": "Hacker News", "url": "https://hnrss.org/frontpage", "favicon": "https://news.ycombinator.com/favicon.ico"}
    ],
    "Blockchain": []
}

async def seed_database(background_tasks=None):
    count_row = await db.fetch_one("SELECT COUNT(*) as c FROM feeds")
    if count_row and count_row['c'] > 1:
        return {"status": "already seeded"}
        
    for idx, (folder_name, feeds) in enumerate(SEED_DATA.items()):
        folder = await db.fetch_one("SELECT id FROM folders WHERE name = ?", (folder_name,))
        if folder:
            folder_id = folder["id"]
        else:
            folder_id = await db.execute("INSERT INTO folders (name, position) VALUES (?, ?)", (folder_name, idx + 1))
            
        for feed in feeds:
            existing = await db.fetch_one("SELECT id FROM feeds WHERE url = ?", (feed["url"],))
            if not existing:
                feed_id = await db.execute("""
                    INSERT INTO feeds (url, title, favicon_url, folder_id, poll_interval_minutes)
                    VALUES (?, ?, ?, ?, ?)
                """, (feed["url"], feed["title"], feed["favicon"], folder_id, 60))
                
                if background_tasks:
                    from .feed_poller import poll_single_feed
                    background_tasks.add_task(poll_single_feed, feed_id)
                    
    return {"status": "seeded"}
