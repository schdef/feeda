import asyncio
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == 'tests' else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'backend'))

from feeda.app import create_app
from feeda.database import db
from feeda.services.feed_poller import poll_single_feed

class TestFolderRefreshEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_path = cls.temp_db_file.name
        cls.temp_db_file.close()

        os.environ["FEEDA_DB_PATH"] = cls.db_path
        db.db_path = cls.db_path
        asyncio.run(db.connect())
        migrations_dir = str(BASE_DIR / "backend" / "migrations")
        asyncio.run(db.run_migrations(migrations_dir))

        with patch("feeda.app.feed_poller_task", new_callable=AsyncMock):
            cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        asyncio.run(db.close())
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def setUp(self):
        async def clean():
            await db.connect()
            await db.execute("DELETE FROM folders WHERE name LIKE 'Test Refresh%' OR name LIKE 'Poller Test%'")
            await db.execute("DELETE FROM feeds WHERE title LIKE 'Refresh Feed%' OR title LIKE 'Poller Feed%'")
        asyncio.run(clean())

    def tearDown(self):
        async def clean():
            await db.connect()
            await db.execute("DELETE FROM folders WHERE name LIKE 'Test Refresh%' OR name LIKE 'Poller Test%'")
            await db.execute("DELETE FROM feeds WHERE title LIKE 'Refresh Feed%' OR title LIKE 'Poller Feed%'")
        asyncio.run(clean())

    def test_refresh_empty_folder(self):
        with TestClient(self.app) as client:
            resp = client.post("/api/folders/999999/refresh")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), {"status": "ok", "count": 0})

    def test_refresh_folder_with_feeds(self):
        async def setup_data():
            await db.connect()
            folder_id = await db.execute("INSERT INTO folders (name, position) VALUES (?, ?)", ("Test Refresh Folder", 8888))
            f1 = await db.execute("INSERT INTO feeds (url, title, folder_id) VALUES (?, ?, ?)", ("http://example.com/rf1", "Refresh Feed 1", folder_id))
            f2 = await db.execute("INSERT INTO feeds (url, title, folder_id) VALUES (?, ?, ?)", ("http://example.com/rf2", "Refresh Feed 2", folder_id))
            return folder_id, f1, f2

        folder_id, f1, f2 = asyncio.run(setup_data())

        with patch("feeda.routers.folders.poll_single_feed", new_callable=AsyncMock) as mock_poll:
            mock_poll.return_value = None
            with TestClient(self.app) as client:
                resp = client.post(f"/api/folders/{folder_id}/refresh")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.json(), {"status": "ok", "count": 2})
                self.assertEqual(mock_poll.call_count, 2)
                mock_poll.assert_any_call(f1)
                mock_poll.assert_any_call(f2)


class TestFeedPollerHardening(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()

        os.environ["FEEDA_DB_PATH"] = self.db_path
        db.db_path = self.db_path
        await db.connect()
        migrations_dir = str(BASE_DIR / "backend" / "migrations")
        await db.run_migrations(migrations_dir)

    async def asyncTearDown(self):
        await db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_feed_poller_unique_constraint_hardening(self):
        folder_id = await db.execute("INSERT INTO folders (name, position) VALUES (?, ?)", ("Poller Test Hardening Folder", 8899))
        feed_id = await db.execute("INSERT INTO feeds (url, title, folder_id) VALUES (?, ?, ?)", ("http://example.com/poller_hardening_feed", "Poller Feed", folder_id))

        try:
            fake_entries = [
                {
                    "title": "Article 1",
                    "url": "http://example.com/item1",
                    "guid": "guid-1",
                    "summary": "Summary 1",
                    "content": "Content 1",
                    "author": "Author 1",
                    "published_at": "2026-11-08T12:00:00",
                    "image_url": None,
                },
                {
                    "title": "Article 2",
                    "url": "http://example.com/item2",
                    "guid": "guid-2",
                    "summary": "Summary 2",
                    "content": "Content 2",
                    "author": "Author 2",
                    "published_at": "2026-11-08T12:01:00",
                    "image_url": None,
                }
            ]

            original_execute = db.execute

            # Simulate UNIQUE constraint failure on the first entry insertion
            first_insert = True
            async def mock_execute(query, params=()):
                nonlocal first_insert
                if "INSERT INTO articles" in query and first_insert:
                    first_insert = False
                    raise Exception("UNIQUE constraint failed: articles.feed_id, articles.url_hash")
                return await original_execute(query, params)

            with patch("feeda.services.feed_poller.fetch_feed_content", new_callable=AsyncMock) as mock_fetch, \
                 patch("feeda.services.feed_poller.parse_entries") as mock_parse, \
                 patch("feeda.services.feed_poller.analyze_article", new_callable=AsyncMock) as mock_analyze, \
                 patch("feeda.services.feed_poller.find_duplicate", new_callable=AsyncMock) as mock_dup, \
                 patch("feeda.services.feed_poller.score_article", new_callable=AsyncMock) as mock_score, \
                 patch("feeda.services.feed_poller.cluster_unclustered_articles_background", new_callable=AsyncMock), \
                 patch.object(db, "execute", side_effect=mock_execute):

                mock_fetch.return_value = (b"<rss></rss>", {}, False)
                mock_parse.return_value = fake_entries
                mock_analyze.return_value = {"ai_summary": "Summary", "story_signature": "sig"}
                mock_dup.return_value = None
                mock_score.return_value = 0.5

                # Run poll_single_feed - should NOT raise exception even though first insert threw UNIQUE constraint
                await poll_single_feed(feed_id)

                # Feed should not have failed (error_count == 0)
                feed_data = await db.fetch_one("SELECT error_count, last_error FROM feeds WHERE id = ?", (feed_id,))
                self.assertEqual(feed_data["error_count"], 0)
                self.assertIsNone(feed_data["last_error"])

                # Second article should have been inserted
                articles = await db.fetch_all("SELECT * FROM articles WHERE feed_id = ?", (feed_id,))
                self.assertEqual(len(articles), 1)
                self.assertEqual(articles[0]["url"], "http://example.com/item2")

        finally:
            await db.execute("DELETE FROM articles WHERE feed_id = ?", (feed_id,))
            await db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
            await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))

    async def test_feed_poller_update_error_hardening(self):
        folder_id = await db.execute("INSERT INTO folders (name, position) VALUES (?, ?)", ("Poller Test Update Folder", 8898))
        feed_id = await db.execute("INSERT INTO feeds (url, title, folder_id) VALUES (?, ?, ?)", ("http://example.com/poller_update_feed", "Poller Feed", folder_id))

        try:
            # Pre-insert existing article
            await db.execute("""
                INSERT INTO articles (feed_id, guid, url, url_hash, title, author, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (feed_id, "guid-1", "http://example.com/item1", "hash1", "Old Title", "Author", "Old Summary"))

            fake_entries = [
                {
                    "title": "New Title 1",
                    "url": "http://example.com/item1",
                    "guid": "guid-1",
                    "summary": "New Summary 1",
                    "content": "Content 1",
                    "author": "Author 1",
                    "published_at": "2026-11-08T12:00:00",
                    "image_url": None,
                },
                {
                    "title": "Article 2",
                    "url": "http://example.com/item2",
                    "guid": "guid-2",
                    "summary": "Summary 2",
                    "content": "Content 2",
                    "author": "Author 2",
                    "published_at": "2026-11-08T12:01:00",
                    "image_url": None,
                }
            ]

            original_execute = db.execute
            async def mock_execute(query, params=()):
                if "UPDATE articles" in query:
                    raise Exception("Mock update failed")
                return await original_execute(query, params)

            with patch("feeda.services.feed_poller.fetch_feed_content", new_callable=AsyncMock) as mock_fetch, \
                 patch("feeda.services.feed_poller.parse_entries") as mock_parse, \
                 patch("feeda.services.feed_poller.analyze_article", new_callable=AsyncMock) as mock_analyze, \
                 patch("feeda.services.feed_poller.find_duplicate", new_callable=AsyncMock) as mock_dup, \
                 patch("feeda.services.feed_poller.score_article", new_callable=AsyncMock) as mock_score, \
                 patch("feeda.services.feed_poller.cluster_unclustered_articles_background", new_callable=AsyncMock), \
                 patch.object(db, "execute", side_effect=mock_execute):

                mock_fetch.return_value = (b"<rss></rss>", {}, False)
                mock_parse.return_value = fake_entries
                mock_analyze.return_value = {"ai_summary": "Summary", "story_signature": "sig"}
                mock_dup.return_value = None
                mock_score.return_value = 0.5

                # Should not crash on update error, should continue to article 2
                await poll_single_feed(feed_id)

                feed_data = await db.fetch_one("SELECT error_count, last_error FROM feeds WHERE id = ?", (feed_id,))
                self.assertEqual(feed_data["error_count"], 0)
                self.assertIsNone(feed_data["last_error"])

                articles = await db.fetch_all("SELECT * FROM articles WHERE feed_id = ?", (feed_id,))
                self.assertEqual(len(articles), 2)

        finally:
            await db.execute("DELETE FROM articles WHERE feed_id = ?", (feed_id,))
            await db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
            await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))


if __name__ == "__main__":
    unittest.main()
