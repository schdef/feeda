import asyncio
import os
import sys
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path(__file__).resolve().parent
MIGRATIONS_DIR = str(BASE_DIR / "backend" / "migrations")
sys.path.insert(0, str(BASE_DIR / "backend"))

from feeda.database import db, Database
from feeda.app import create_app

@pytest.fixture(scope="session", autouse=True)
def guard_no_live_db():
    """Ensure no test session ever falls back to backend/feeda.db."""
    temp_guard = tempfile.NamedTemporaryFile(suffix="_guard.db", delete=False)
    guard_path = temp_guard.name
    temp_guard.close()
    os.environ["FEEDA_DB_PATH"] = guard_path
    db.db_path = guard_path
    yield guard_path
    if os.path.exists(guard_path):
        os.remove(guard_path)

async def setup_test_database():
    """Create a temporary SQLite database, run migrations, and return (db, path)."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = temp_file.name
    temp_file.close()

    os.environ["FEEDA_DB_PATH"] = db_path
    db.db_path = db_path
    await db.connect()
    await db.run_migrations(MIGRATIONS_DIR)
    return db, db_path

async def teardown_test_database(db_instance, db_path: str):
    """Close the database and remove the temporary file."""
    await db_instance.close()
    if os.path.exists(db_path):
        os.remove(db_path)

async def seed_test_dataset(db_instance):
    """Seed a realistic dataset of feeds, folders, articles, term weights, and feed affinity."""
    folder_id = await db_instance.execute(
        "INSERT INTO folders (id, name, position) VALUES (1, 'Technology', 1)"
    )
    feed_id = await db_instance.execute(
        "INSERT INTO feeds (id, folder_id, title, url, site_url) VALUES (1, 1, 'Tech News', 'https://example.com/rss', 'https://example.com')"
    )

    # 25 High & Medium articles published today
    for i in range(1, 26):
        score = 26.0 - i
        await db_instance.execute("""
            INSERT INTO articles (id, feed_id, url, url_hash, title, summary, interest_score, is_read, published_at)
            VALUES (?, 1, ?, ?, ?, 'Article summary about technology and AI.', ?, 0, datetime('now'))
        """, (i, f"http://example.com/art{i}", f"hash_art_{i}", f"High/Medium Tech Story {i}", score))

    # 25 Low tier articles published 2 days ago (eligible for older_than 1d mark-read)
    for i in range(26, 51):
        score = 25.0 - i  # -1.0 down to -25.0
        await db_instance.execute("""
            INSERT INTO articles (id, feed_id, url, url_hash, title, summary, interest_score, is_read, published_at)
            VALUES (?, 1, ?, ?, ?, 'Article summary about low-interest news.', ?, 0, datetime('now', '-2 days'))
        """, (i, f"http://example.com/art{i}", f"hash_art_{i}", f"Low Score Story {i}", score))

    # Populate term_weights and feed_affinity for recommendation and suggestion endpoints
    await db_instance.execute("""
        INSERT INTO term_weights (term, positive_score, negative_score)
        VALUES ('technology', 10.0, 0.0), ('ai', 8.0, 0.0), ('coding', 6.0, 0.0)
    """)
    await db_instance.execute("""
        INSERT INTO feed_affinity (feed_id, affinity_score)
        VALUES (1, 0.9)
    """)

@pytest.fixture
async def test_db():
    """Async fixture providing an isolated temporary database with migrations and seed data."""
    test_db_inst, path = await setup_test_database()
    await seed_test_dataset(test_db_inst)
    yield test_db_inst
    await teardown_test_database(test_db_inst, path)
