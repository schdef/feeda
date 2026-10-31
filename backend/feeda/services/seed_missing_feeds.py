import sqlite3
import os

FEEDS_DATA = {
    "Tech": [
        ("Hacker News", "https://hnrss.org/frontpage", "https://news.ycombinator.com"),
        ("Make: DIY Projects and Ideas for Makers", "https://makezine.com/feed/", "https://makezine.com"),
        ("New on MIT Technology Review", "https://www.technologyreview.com/feed/", "https://www.technologyreview.com"),
        ("TechCrunch", "https://techcrunch.com/feed/", "https://techcrunch.com"),
        ("The Verge - All Posts", "https://www.theverge.com/rss/index.xml", "https://www.theverge.com"),
        ("TorrentFreak", "https://torrentfreak.com/feed/", "https://torrentfreak.com"),
        ("haus:automation", "https://haus-automatisierung.com/feed.xml", "https://haus-automatisierung.com"),
        ("meintechblog.de", "https://www.meintechblog.de/feed/", "https://www.meintechblog.de"),
        ("neunetz.com", "https://neunetz.com/feed/", "https://neunetz.com"),
        ("Product Hunt", "https://www.producthunt.com/feed", "https://www.producthunt.com"),
        ("Technology Review", "https://www.heise.de/rss/heise-atom.xml", "https://www.heise.de/tr/"),
    ],
    "Blockchain": [
        ("BTC-ECHO", "https://www.btc-echo.de/feed/", "https://www.btc-echo.de"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "https://www.coindesk.com"),
        ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/", "https://bitcoinmagazine.com"),
    ]
}

def seed_feeds_in_db(db_path: str):
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    added_count = 0
    updated_count = 0

    for folder_name, feeds in FEEDS_DATA.items():
        # 1. Get or create folder
        folder_row = cur.execute("SELECT id FROM folders WHERE name = ?", (folder_name,)).fetchone()
        if folder_row:
            folder_id = folder_row[0]
        else:
            cur.execute("INSERT INTO folders (name, position) VALUES (?, ?)", (folder_name, 99))
            folder_id = cur.lastrowid
            print(f"Created folder '{folder_name}' (id: {folder_id})")

        # 2. Insert or update feeds
        for title, url, site_url in feeds:
            existing = cur.execute("SELECT id, folder_id, title FROM feeds WHERE url = ?", (url,)).fetchone()
            if existing:
                feed_id, curr_folder, curr_title = existing
                if curr_folder != folder_id or curr_title != title:
                    cur.execute("UPDATE feeds SET folder_id = ?, title = ? WHERE id = ?", (folder_id, title, feed_id))
                    updated_count += 1
                    print(f"Updated feed '{title}' in folder '{folder_name}'")
            else:
                cur.execute("""
                    INSERT INTO feeds (folder_id, title, url, site_url, poll_interval_minutes)
                    VALUES (?, ?, ?, ?, ?)
                """, (folder_id, title, url, site_url, 30))
                added_count += 1
                print(f"Added feed '{title}' in folder '{folder_name}'")

    con.commit()
    con.close()
    print(f"Seeding complete in {db_path}: {added_count} added, {updated_count} updated.")

if __name__ == "__main__":
    import sys
    db_file = sys.argv[1] if len(sys.argv) > 1 else "backend/feeda.db"
    seed_feeds_in_db(db_file)
