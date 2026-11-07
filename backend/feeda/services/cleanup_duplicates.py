import asyncio
import os
import sys
import sqlite3
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def cleanup_database_sync(db_path: str):
    logger.info(f"Opening SQLite database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    removed_count = 0
    clustered_count = 0

    # 0. Ensure schema compatibility for ai_summary and story_signature
    col_rows = cursor.execute("PRAGMA table_info(articles)").fetchall()
    existing_cols = {r['name'] for r in col_rows}
    if "ai_summary" not in existing_cols:
        cursor.execute("ALTER TABLE articles ADD COLUMN ai_summary TEXT;")
    if "story_signature" not in existing_cols:
        cursor.execute("ALTER TABLE articles ADD COLUMN story_signature TEXT;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_story_sig ON articles(story_signature);")
    conn.commit()

    # 1. Clean exact duplicates in the SAME FEED by (feed_id, guid)
    logger.info("Scanning for duplicates by (feed_id, guid)...")
    dup_guids = cursor.execute("""
        SELECT feed_id, guid, COUNT(*) as c 
        FROM articles 
        WHERE guid IS NOT NULL AND guid != '' 
        GROUP BY feed_id, guid 
        HAVING c > 1
    """).fetchall()

    for row in dup_guids:
        feed_id = row['feed_id']
        guid = row['guid']
        matching = cursor.execute("""
            SELECT id, is_read, is_starred, cluster_id, published_at 
            FROM articles 
            WHERE feed_id = ? AND guid = ? 
            ORDER BY is_read DESC, is_starred DESC, id ASC
        """, (feed_id, guid)).fetchall()

        primary_id = matching[0]['id']
        for dup in matching[1:]:
            dup_id = dup['id']
            # Re-point board_articles if any
            cursor.execute("UPDATE OR IGNORE board_articles SET article_id = ? WHERE article_id = ?", (primary_id, dup_id))
            cursor.execute("DELETE FROM board_articles WHERE article_id = ?", (dup_id,))
            cursor.execute("DELETE FROM articles WHERE id = ?", (dup_id,))
            removed_count += 1
            logger.info(f"Removed duplicate article id={dup_id} (kept primary id={primary_id}, guid='{guid}')")

    # 2. Clean exact duplicates in the SAME FEED by (feed_id, url_hash)
    logger.info("Scanning for duplicates by (feed_id, url_hash)...")
    dup_hashes = cursor.execute("""
        SELECT feed_id, url_hash, COUNT(*) as c 
        FROM articles 
        WHERE url_hash IS NOT NULL AND url_hash != '' 
        GROUP BY feed_id, url_hash 
        HAVING c > 1
    """).fetchall()

    for row in dup_hashes:
        feed_id = row['feed_id']
        uhash = row['url_hash']
        matching = cursor.execute("""
            SELECT id, is_read, is_starred, cluster_id 
            FROM articles 
            WHERE feed_id = ? AND url_hash = ? 
            ORDER BY is_read DESC, is_starred DESC, id ASC
        """, (feed_id, uhash)).fetchall()

        primary_id = matching[0]['id']
        for dup in matching[1:]:
            dup_id = dup['id']
            cursor.execute("UPDATE OR IGNORE board_articles SET article_id = ? WHERE article_id = ?", (primary_id, dup_id))
            cursor.execute("DELETE FROM board_articles WHERE article_id = ?", (dup_id,))
            cursor.execute("DELETE FROM articles WHERE id = ?", (dup_id,))
            removed_count += 1
            logger.info(f"Removed duplicate article id={dup_id} (kept primary id={primary_id}, url_hash='{uhash}')")

    # 3. Cluster matching articles ACROSS FEEDS by url_hash
    logger.info("Clustering matching articles across feeds by url_hash...")
    cross_hashes = cursor.execute("""
        SELECT url_hash, COUNT(*) as c 
        FROM articles 
        WHERE url_hash IS NOT NULL AND url_hash != '' 
        GROUP BY url_hash 
        HAVING c > 1
    """).fetchall()

    for row in cross_hashes:
        uhash = row['url_hash']
        matching = cursor.execute("""
            SELECT id, cluster_id FROM articles WHERE url_hash = ? ORDER BY id ASC
        """, (uhash,)).fetchall()

        existing_cids = [m['cluster_id'] for m in matching if m['cluster_id'] is not None]
        if existing_cids:
            cid = existing_cids[0]
        else:
            primary_id = matching[0]['id']
            cursor.execute("INSERT INTO clusters (primary_article_id) VALUES (?)", (primary_id,))
            cid = cursor.lastrowid

        for m in matching:
            if m['cluster_id'] != cid:
                cursor.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cid, m['id']))
                clustered_count += 1

    # 4. Check for multi-factor duplicates among recent articles (last 7 days or 1500 articles)
    logger.info("Scanning for story duplicates with AI summary and story signatures...")
    from feeda.services.dedup import is_duplicate_title, clean_title, is_duplicate_article
    from feeda.services.ai_summary import generate_story_signature, generate_local_summary

    recent_rows = cursor.execute("""
        SELECT id, feed_id, cluster_id, title, summary, content, ai_summary, story_signature,
               published_at, fetched_at, url, url_hash, guid, content_simhash
        FROM articles 
        WHERE (
            datetime(COALESCE(published_at, fetched_at)) >= datetime('now', '-7 days')
            OR id IN (SELECT id FROM articles ORDER BY id DESC LIMIT 1500)
        )
        ORDER BY id DESC
    """).fetchall()

    recent = [dict(r) for r in recent_rows]

    # Pre-populate missing story_signatures and ai_summaries in batch
    updates = []
    for a in recent:
        need_update = False
        if not a.get('story_signature') and (a.get('title') or a.get('summary')):
            a['story_signature'] = generate_story_signature(a.get('title') or '', a.get('content') or a.get('summary') or '')
            need_update = True
        if not a.get('ai_summary') and (a.get('title') or a.get('summary')):
            a['ai_summary'] = generate_local_summary(a.get('title') or '', content=a.get('content') or '', summary=a.get('summary') or '')
            need_update = True
        if need_update:
            updates.append((a.get('story_signature'), a.get('ai_summary'), a['id']))

    if updates:
        cursor.executemany("UPDATE articles SET story_signature = ?, ai_summary = ? WHERE id = ?", updates)
        conn.commit()

    # Compare pairwise for duplicates using is_duplicate_article
    deleted_ids = set()
    for i in range(len(recent)):
        a1 = recent[i]
        if a1['id'] in deleted_ids:
            continue
        for j in range(i + 1, min(i + 60, len(recent))):
            a2 = recent[j]
            if a2['id'] in deleted_ids:
                continue
            if is_duplicate_article(a1, a2):
                if a1['feed_id'] == a2['feed_id']:
                    # Same feed: remove duplicate if identical title
                    if clean_title(a1['title']).lower() == clean_title(a2['title']).lower():
                        target_id = max(a1['id'], a2['id'])
                        keep_id = min(a1['id'], a2['id'])
                        deleted_ids.add(target_id)
                        cursor.execute("UPDATE OR IGNORE board_articles SET article_id = ? WHERE article_id = ?", (keep_id, target_id))
                        cursor.execute("DELETE FROM board_articles WHERE article_id = ?", (target_id,))
                        cursor.execute("DELETE FROM articles WHERE id = ?", (target_id,))
                        removed_count += 1
                        logger.info(f"Removed duplicate title in same feed {a1['feed_id']}: removed id={target_id}, kept id={keep_id}")
                        if a1['id'] == target_id:
                            break
                else:
                    # Different feed: cluster them together!
                    cid = a1['cluster_id'] or a2['cluster_id']
                    if not cid:
                        cursor.execute("INSERT INTO clusters (primary_article_id) VALUES (?)", (a1['id'],))
                        cid = cursor.lastrowid
                    if a1['cluster_id'] != cid:
                        cursor.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cid, a1['id']))
                        a1['cluster_id'] = cid
                        clustered_count += 1
                    if a2['cluster_id'] != cid:
                        cursor.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cid, a2['id']))
                        a2['cluster_id'] = cid
                        clustered_count += 1

    # 5. Synchronize cluster primaries to the chronologically earliest article
    logger.info("Synchronizing cluster primaries to chronologically earliest articles...")
    all_clusters = cursor.execute("SELECT id, primary_article_id FROM clusters").fetchall()
    updated_primaries = 0
    for c in all_clusters:
        cid = c['id']
        current_primary = c['primary_article_id']
        earliest = cursor.execute("""
            SELECT id FROM articles 
            WHERE cluster_id = ? 
            ORDER BY datetime(COALESCE(published_at, fetched_at)) ASC, id ASC 
            LIMIT 1
        """, (cid,)).fetchone()
        if earliest and earliest['id'] != current_primary:
            cursor.execute("UPDATE clusters SET primary_article_id = ? WHERE id = ?", (earliest['id'], cid))
            updated_primaries += 1
            logger.info(f"Cluster {cid}: updated primary from {current_primary} to earliest {earliest['id']}")
    logger.info(f"Cluster primary sync completed: {updated_primaries} clusters updated to earliest published article.")

    conn.commit()
    conn.close()
    logger.info(f"Cleanup finished: {removed_count} duplicate articles removed, {clustered_count} articles clustered, {updated_primaries} cluster primaries updated.")
    return {"removed": removed_count, "clustered": clustered_count, "primaries_updated": updated_primaries}

def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FEEDA_DB_PATH", "backend/feeda.db")
    if not os.path.exists(db_path):
        alt = "feeda.db"
        if os.path.exists(alt):
            db_path = alt
    cleanup_database_sync(db_path)

if __name__ == "__main__":
    main()
