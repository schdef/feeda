import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == 'tests' else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'backend'))

from feeda.database import db
from feeda.app import create_app

class TestStarredArticles(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()

        os.environ["FEEDA_DB_PATH"] = self.db_path
        db.db_path = self.db_path
        await db.connect()
        migrations_dir = str(BASE_DIR / "backend" / "migrations")
        await db.run_migrations(migrations_dir)

        # Insert a sample feed
        await db.execute(
            "INSERT INTO feeds (id, title, url, site_url) VALUES (?, ?, ?, ?)",
            (1, "Tech Feed", "https://example.com/rss", "https://example.com")
        )

        with patch("feeda.services.seeder.seed_database", new_callable=AsyncMock), \
             patch("feeda.app.feed_poller_task", new_callable=AsyncMock):
            self.app = create_app()

    async def asyncTearDown(self):
        await db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_starred_with_low_interest_score_returned(self):
        """Verify that starred articles with low interest score are returned when is_starred=True."""
        # Insert articles: one high-score unstarred, one low-score starred, one low-score unstarred
        await db.execute("""
            INSERT INTO articles (id, feed_id, url, url_hash, title, interest_score, is_starred, is_read, published_at)
            VALUES 
            (101, 1, 'http://example.com/high', 'hash_high', 'High Score Story', 10.0, 0, 0, datetime('now')),
            (102, 1, 'http://example.com/low-starred', 'hash_low_starred', 'Low Starred Story', -5.0, 1, 0, datetime('now')),
            (103, 1, 'http://example.com/low-unstarred', 'hash_low_unstarred', 'Low Unstarred Story', -6.0, 0, 0, datetime('now'))
        """)

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Default articles call filters out low interest score
            resp_default = await client.get("/api/articles")
            self.assertEqual(resp_default.status_code, 200)
            default_ids = [a["id"] for a in resp_default.json()["articles"]]
            self.assertIn(101, default_ids)
            self.assertNotIn(102, default_ids)
            self.assertNotIn(103, default_ids)

            # 2. Querying with is_starred=true returns the low-interest starred article!
            resp_starred = await client.get("/api/articles?is_starred=true")
            self.assertEqual(resp_starred.status_code, 200)
            data = resp_starred.json()
            starred_ids = [a["id"] for a in data["articles"]]
            self.assertEqual(starred_ids, [102])
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["articles"][0]["interest_score"], -5.0)

            # 3. Even if likelihood=likely is passed along with is_starred=true, it should still return the article
            resp_starred_likely = await client.get("/api/articles?is_starred=true&likelihood=likely")
            self.assertEqual(resp_starred_likely.status_code, 200)
            likely_starred_ids = [a["id"] for a in resp_starred_likely.json()["articles"]]
            self.assertIn(102, likely_starred_ids)

    async def test_multiple_starred_in_same_cluster_preserved(self):
        """Verify that multiple starred articles in the same cluster are preserved when is_starred=True."""
        # Create cluster 42
        await db.execute("INSERT INTO clusters (id) VALUES (42)")

        # Insert 3 articles in the same cluster: 2 are starred, 1 is not starred
        cluster_id = 42
        await db.execute("""
            INSERT INTO articles (id, feed_id, cluster_id, url, url_hash, title, interest_score, is_starred, is_read, published_at)
            VALUES 
            (201, 1, ?, 'http://example.com/c1', 'hash_c1', 'Cluster Article 1', 5.0, 1, 0, '2026-11-08 10:00:00'),
            (202, 1, ?, 'http://example.com/c2', 'hash_c2', 'Cluster Article 2', 5.0, 1, 0, '2026-11-08 11:00:00'),
            (203, 1, ?, 'http://example.com/c3', 'hash_c3', 'Cluster Article 3', 5.0, 0, 0, '2026-11-08 12:00:00')
        """, (cluster_id, cluster_id, cluster_id))

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. With normal stream (dedup=true), cluster deduplication collapses cluster articles
            resp_normal = await client.get("/api/articles?dedup=true")
            self.assertEqual(resp_normal.status_code, 200)
            normal_ids = [a["id"] for a in resp_normal.json()["articles"]]
            # Only one article from cluster 42 should be present
            cluster_articles_present = [aid for aid in normal_ids if aid in (201, 202, 203)]
            self.assertEqual(len(cluster_articles_present), 1)

            # 2. When is_starred=true, both starred articles (201 and 202) MUST be preserved!
            resp_starred = await client.get("/api/articles?is_starred=true")
            self.assertEqual(resp_starred.status_code, 200)
            data = resp_starred.json()
            starred_ids = [a["id"] for a in data["articles"]]
            self.assertIn(201, starred_ids)
            self.assertIn(202, starred_ids)
            self.assertNotIn(203, starred_ids)
            self.assertEqual(data["total"], 2)

    async def test_starred_older_than_6_months_returned(self):
        """Verify that starred articles older than 6 months are returned when is_starred=True."""
        # Insert an article published 2 years ago (2024-01-01), one starred, one unstarred
        await db.execute("""
            INSERT INTO articles (id, feed_id, url, url_hash, title, interest_score, is_starred, is_read, published_at)
            VALUES 
            (301, 1, 'http://example.com/old-starred', 'hash_old_starred', 'Old Starred Article', 5.0, 1, 0, '2024-01-01 10:00:00'),
            (302, 1, 'http://example.com/old-unstarred', 'hash_old_unstarred', 'Old Unstarred Article', 5.0, 0, 0, '2024-01-01 10:00:00')
        """)

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Normal likely stream drops older articles
            resp_likely = await client.get("/api/articles?likelihood=likely")
            self.assertEqual(resp_likely.status_code, 200)
            likely_ids = [a["id"] for a in resp_likely.json()["articles"]]
            self.assertNotIn(301, likely_ids)
            self.assertNotIn(302, likely_ids)

            # 2. is_starred=true returns the old starred article
            resp_starred = await client.get("/api/articles?is_starred=true")
            self.assertEqual(resp_starred.status_code, 200)
            data = resp_starred.json()
            starred_ids = [a["id"] for a in data["articles"]]
            self.assertIn(301, starred_ids)
            self.assertNotIn(302, starred_ids)

            # 3. is_starred=true with sort=score still returns the old starred article
            resp_starred_score = await client.get("/api/articles?is_starred=true&sort=score")
            self.assertEqual(resp_starred_score.status_code, 200)
            score_ids = [a["id"] for a in resp_starred_score.json()["articles"]]
            self.assertIn(301, score_ids)

    async def test_stats_starred_count_matches_database(self):
        """Verify stats.starred_count matches SELECT COUNT(*) FROM articles WHERE is_starred = 1."""
        await db.execute("INSERT INTO clusters (id) VALUES (99)")
        await db.execute("""
            INSERT INTO articles (id, feed_id, cluster_id, url, url_hash, title, interest_score, is_starred, is_read, published_at)
            VALUES 
            (401, 1, 99, 'http://example.com/s1', 'hash_s1', 'Starred 1', 1.0, 1, 0, '2024-01-01 00:00:00'),
            (402, 1, 99, 'http://example.com/s2', 'hash_s2', 'Starred 2', -2.0, 1, 1, '2026-11-08 00:00:00'),
            (403, 1, NULL, 'http://example.com/s3', 'hash_s3', 'Starred 3', 8.0, 1, 0, '2026-11-08 12:00:00'),
            (404, 1, NULL, 'http://example.com/s4', 'hash_s4', 'Unstarred', 8.0, 0, 0, '2026-11-08 12:00:00')
        """)

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/stats")
            self.assertEqual(resp.status_code, 200)
            stats = resp.json()
            self.assertEqual(stats["starred_count"], 3)

            # Verify list_articles returns the exact same 3 articles
            resp_list = await client.get("/api/articles?is_starred=true")
            self.assertEqual(resp_list.status_code, 200)
            list_data = resp_list.json()
            self.assertEqual(list_data["total"], 3)
            self.assertEqual(len(list_data["articles"]), 3)
