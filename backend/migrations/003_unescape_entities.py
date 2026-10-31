#!/usr/bin/env python3
import html
import os
import sqlite3
import sys
from typing import Optional

def decode_html_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Unescape twice to handle double-escaped entities like &amp;#8217;
    return html.unescape(html.unescape(str(text))).strip()

def run_migration(db_path: Optional[str] = None):
    if not db_path:
        db_path = os.environ.get("FEEDA_DB_PATH")
    if not db_path:
        candidates = [
            "/root/feeda/backend/feeda.db",
            os.path.join(os.path.dirname(__file__), "../feeda.db"),
            os.path.abspath("backend/feeda.db"),
            os.path.abspath("feeda.db"),
        ]
        for c in candidates:
            if os.path.exists(c):
                db_path = c
                break

    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), "../feeda.db")

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Query all articles with title, summary, or content containing '&'
    cur.execute("""
        SELECT id, title, summary, author, content
        FROM articles
        WHERE title LIKE '%&%' OR summary LIKE '%&%' OR content LIKE '%&%'
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} candidate articles with '&' in title, summary, or content.")

    updated_count = 0
    for row in rows:
        art_id, title, summary, author, content = row
        new_title = decode_html_text(title)
        new_summary = decode_html_text(summary)
        new_author = decode_html_text(author) if author else author
        new_content = decode_html_text(content) if content else content

        if new_title != title or new_summary != summary or new_author != author or new_content != content:
            cur.execute("""
                UPDATE articles
                SET title = ?, summary = ?, author = ?, content = ?
                WHERE id = ?
            """, (new_title, new_summary, new_author, new_content, art_id))
            updated_count += 1

    print(f"Updated {updated_count} articles with unescaped HTML entities.")

    # Rebuild FTS index
    print("Rebuilding articles_fts index...")
    try:
        cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        print("articles_fts index rebuilt successfully.")
    except Exception as e:
        print(f"Warning during FTS rebuild: {e}")

    conn.commit()
    conn.close()
    print("Migration 003_unescape_entities completed successfully.")

if __name__ == "__main__":
    target_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_migration(target_path)
