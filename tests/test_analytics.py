import os
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from feeda.database import Database
from feeda.models import (
    InterestTrendsResponse,
    LearningInspectorResponse,
    TopicTrendItem,
)
from feeda.services.analytics import (
    get_interest_trends,
    get_learning_inspector_data,
    seed_demo_reading_activity,
    get_period_dates,
    extract_category_hot_topics,
    format_topic_name,
)
from feeda.app import create_app
import feeda.database


class TestAnalytics(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create a temporary SQLite database for clean isolated testing
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()

        self.db = Database()
        self.db.db_path = self.db_path
        await self.db.connect()

        # Run real migrations
        migrations_dir = str(BASE_DIR / "backend" / "migrations")
        await self.db.run_migrations(migrations_dir)

        # Patch global db instance so create_app() and routers use this isolated db
        self.orig_db_path = feeda.database.db.db_path
        self.orig_db_conn = feeda.database.db._conn
        feeda.database.db.db_path = self.db_path
        feeda.database.db._conn = self.db._conn

        self.app = create_app()
        self.transport = ASGITransport(app=self.app)

    async def asyncTearDown(self):
        feeda.database.db.db_path = self.orig_db_path
        feeda.database.db._conn = self.orig_db_conn
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_period_date_calculations(self):
        """Verify period parsing and date window ranges."""
        now = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        start_7d, end_7d, days_7d = get_period_dates("7d", end_dt=now)
        self.assertEqual(days_7d, 7)
        self.assertEqual((end_7d - start_7d).days, 7)

        start_14d, end_14d, days_14d = get_period_dates("14d", end_dt=now)
        self.assertEqual(days_14d, 14)
        self.assertEqual((end_14d - start_14d).days, 14)

        start_30d, end_30d, days_30d = get_period_dates("30d", end_dt=now)
        self.assertEqual(days_30d, 30)
        self.assertEqual((end_30d - start_30d).days, 30)

        start_all, end_all, days_all = get_period_dates("all", end_dt=now)
        self.assertEqual(days_all, 30)
        self.assertEqual((end_all - start_all).days, 90)

    def test_topic_formatting(self):
        """Verify display name normalization."""
        self.assertEqual(format_topic_name("openai"), "OpenAI")
        self.assertEqual(format_topic_name("chatgpt"), "ChatGPT")
        self.assertEqual(format_topic_name("nvidia"), "NVIDIA")
        self.assertEqual(format_topic_name("blackwell"), "NVIDIA Blackwell")
        self.assertEqual(format_topic_name("deepseek"), "DeepSeek")
        self.assertEqual(format_topic_name("cisa"), "CISA")
        self.assertEqual(format_topic_name("quantum computing"), "Quantum Computing")

    async def test_empty_database_demo_mode_trends(self):
        """When database has 0 reads/interactions, GET /interest-trends should return demo data."""
        trends = await get_interest_trends(self.db, period="7d")
        self.assertTrue(trends.is_demo)
        self.assertEqual(trends.period, "7d")
        self.assertIsNotNone(trends.hotspot)
        self.assertEqual(trends.hotspot.name, "AI & Machine Learning")
        self.assertEqual(len(trends.hotspot.top_topics), 5)
        self.assertGreaterEqual(len(trends.hotspot.top_articles), 1)
        self.assertGreaterEqual(len(trends.hotspot.source_feeds), 1)

        # Verify categories structure
        self.assertGreaterEqual(len(trends.categories), 5)
        for cat in trends.categories:
            self.assertEqual(len(cat.daily_trend), 7)
            self.assertGreaterEqual(len(cat.top_topics), 1)
            self.assertGreaterEqual(cat.share_pct, 0.0)
            self.assertGreaterEqual(len(cat.top_articles), 1)
            self.assertGreaterEqual(len(cat.source_feeds), 1)
            self.assertTrue(len(cat.top_articles[0].title) > 0)
            self.assertTrue(len(cat.top_articles[0].url) > 0)

        # Verify daily timeline
        self.assertEqual(len(trends.daily_timeline), 7)
        for item in trends.daily_timeline:
            self.assertIn("ai-machine-learning", item.by_category)
            self.assertGreaterEqual(item.total_reads, 0)

        # Verify unread catch up
        self.assertEqual(len(trends.unread_catch_up), 6)
        for unread_art in trends.unread_catch_up:
            self.assertFalse(unread_art.is_read)
            self.assertGreater(unread_art.interest_score, 0.0)
            self.assertTrue(len(unread_art.title) > 0)
            self.assertTrue(len(unread_art.url) > 0)

    async def test_empty_database_demo_mode_learning_inspector(self):
        """When database has 0 learned terms, GET /learning-inspector should return demo data."""
        inspector = await get_learning_inspector_data(self.db, limit=30)
        self.assertTrue(inspector.is_demo)
        self.assertEqual(inspector.model_summary.decay_factor, 0.97)
        self.assertGreater(inspector.model_summary.total_learned_terms, 0)
        self.assertGreater(len(inspector.top_positive_terms), 0)
        self.assertGreater(len(inspector.top_negative_terms), 0)
        self.assertGreater(len(inspector.feed_affinities), 0)
        self.assertGreater(len(inspector.recent_events), 0)
        self.assertIn("save_to_board", inspector.action_weights)
        self.assertEqual(inspector.action_weights["save_to_board"], 4.0)
        self.assertEqual(inspector.action_weights["star"], 3.5)
        self.assertEqual(inspector.action_weights["vote_down"], -3.0)

    async def test_api_endpoints_demo_fallback(self):
        """Test API endpoints via HTTP client in demo mode."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Test period parameter variations
            for period in ("7d", "14d", "30d", "all"):
                resp = await client.get(f"/api/analytics/interest-trends?period={period}")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data["is_demo"])
                self.assertEqual(data["period"], period)
                self.assertIsNotNone(data["hotspot"])
                self.assertGreaterEqual(len(data["categories"]), 5)
                expected_days = 7 if period == "7d" else (14 if period == "14d" else 30)
                self.assertEqual(len(data["daily_timeline"]), expected_days)
                self.assertIn("unread_catch_up", data)
                self.assertEqual(len(data["unread_catch_up"]), 6)
                self.assertIn("top_articles", data["hotspot"])
                self.assertGreaterEqual(len(data["hotspot"]["top_articles"]), 1)
                self.assertIn("source_feeds", data["hotspot"])
                self.assertGreaterEqual(len(data["hotspot"]["source_feeds"]), 1)

            # 2. Test learning inspector endpoint
            resp_insp = await client.get("/api/analytics/learning-inspector?limit=10")
            self.assertEqual(resp_insp.status_code, 200)
            data_insp = resp_insp.json()
            self.assertTrue(data_insp["is_demo"])
            self.assertIn("model_summary", data_insp)
            self.assertIn("top_positive_terms", data_insp)
            self.assertIn("top_negative_terms", data_insp)

    async def test_seed_demo_activity_and_live_trends(self):
        """
        Test seeding demo activity transitions the system to real live data.
        Verifies AC 3, AC 7, AC 8.
        """
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Trigger seeding
            seed_resp = await client.post("/api/analytics/seed-demo-activity")
            self.assertEqual(seed_resp.status_code, 200)
            seed_data = seed_resp.json()
            self.assertEqual(seed_data["status"], "ok")
            self.assertGreater(seed_data["articles_seeded"], 0)

            # 2. Check live interest trends
            trends_resp = await client.get("/api/analytics/interest-trends?period=7d")
            self.assertEqual(trends_resp.status_code, 200)
            trends_data = trends_resp.json()
            self.assertFalse(trends_data["is_demo"])  # Live data active!
            self.assertIsNotNone(trends_data["hotspot"])
            self.assertGreater(len(trends_data["categories"]), 0)

            hotspot = trends_data["hotspot"]
            self.assertIn(hotspot["slug"], ("ai-machine-learning", "big-tech-software", "electric-vehicles-mobility"))
            self.assertGreater(hotspot["read_count"], 0)
            self.assertGreater(hotspot["total_dwell_seconds"], 0)
            self.assertGreater(len(hotspot["top_topics"]), 0)
            self.assertIn("top_articles", hotspot)
            self.assertGreaterEqual(len(hotspot["top_articles"]), 1)
            self.assertIn("source_feeds", hotspot)
            self.assertGreaterEqual(len(hotspot["source_feeds"]), 1)

            # Check unread catch up is populated from seeded unread articles
            self.assertIn("unread_catch_up", trends_data)
            self.assertGreaterEqual(len(trends_data["unread_catch_up"]), 1)
            for u in trends_data["unread_catch_up"]:
                self.assertFalse(u["is_read"])
                self.assertGreater(len(u["title"]), 0)

            # 3. Check live learning inspector
            insp_resp = await client.get("/api/analytics/learning-inspector?limit=20")
            self.assertEqual(insp_resp.status_code, 200)
            insp_data = insp_resp.json()
            self.assertFalse(insp_data["is_demo"])  # Live data active!

            pos_terms = [t["term"] for t in insp_data["top_positive_terms"]]
            self.assertTrue(any(t in pos_terms for t in ("openai", "reasoning", "model", "deepseek", "blackwell", "rust")))

            # Negative terms should contain downvoted keywords like 'rumors', 'celebrity', 'clickbait'
            neg_terms = [t["term"] for t in insp_data["top_negative_terms"]]
            self.assertTrue(any(t in neg_terms for t in ("rumors", "celebrity", "clickbait", "gossip")))

            # Feed affinities should be present
            self.assertGreater(len(insp_data["feed_affinities"]), 0)
            self.assertGreater(insp_data["feed_affinities"][0]["affinity_score"], 0.0)

            # Recent events should log the seeded interactions
            self.assertGreater(len(insp_data["recent_events"]), 0)
            latest_event = insp_data["recent_events"][0]
            self.assertIn("article_title", latest_event)
            self.assertIn("action", latest_event)
            self.assertIsInstance(latest_event["boosted_terms"], list)

    async def test_top_articles_and_unread_catch_up(self):
        """Verify top_articles and unread_catch_up with decoded HTML titles and source_feeds."""
        # Insert a feed
        feed_id = await self.db.execute("""
            INSERT INTO feeds (title, url, site_url, poll_interval_minutes)
            VALUES ('TechCrunch &amp; Friends', 'https://techcrunch.com/feed', 'https://techcrunch.com', 30)
        """)

        now_iso = datetime.now(timezone.utc).isoformat()
        # Insert read article with HTML entity in title
        art1_id = await self.db.execute("""
            INSERT INTO articles (
                feed_id, url, url_hash, title, summary,
                published_at, fetched_at, is_read, read_at,
                interest_score, story_signature
            ) VALUES (?, ?, 'hash1', 'OpenAI &amp; NVIDIA partner on &quot;Next-Gen&quot; GPUs', 'Summary', ?, ?, 1, ?, 9.5, 'entity:openai,nvidia|keys:ai,gpu')
        """, (feed_id, "https://example.com/art1", now_iso, now_iso, now_iso))

        # Insert unread article
        art2_id = await self.db.execute("""
            INSERT INTO articles (
                feed_id, url, url_hash, title, summary,
                published_at, fetched_at, is_read,
                interest_score, story_signature
            ) VALUES (?, ?, 'hash2', 'DeepSeek&#39;s New AI Architecture Revealed', 'Summary', ?, ?, 0, 8.8, 'entity:deepseek|keys:ai,model')
        """, (feed_id, "https://example.com/art2", now_iso, now_iso))

        # Add interaction for art1 so it registers reads
        await self.db.execute("""
            INSERT INTO interactions (article_id, action, dwell_time_seconds, created_at)
            VALUES (?, 'read', 60.0, ?)
        """, (art1_id, now_iso))

        trends = await get_interest_trends(self.db, period="7d")
        self.assertFalse(trends.is_demo)
        self.assertIsNotNone(trends.hotspot)

        # Verify decoded HTML in top_articles
        self.assertGreaterEqual(len(trends.hotspot.top_articles), 1)
        top_art = trends.hotspot.top_articles[0]
        self.assertEqual(top_art.title, 'OpenAI & NVIDIA partner on "Next-Gen" GPUs')
        self.assertEqual(top_art.feed_title, "TechCrunch & Friends")
        self.assertEqual(top_art.url, "https://example.com/art1")
        self.assertEqual(top_art.interest_score, 9.5)
        self.assertIn("TechCrunch & Friends", trends.hotspot.source_feeds)

        # Verify unread_catch_up
        self.assertGreaterEqual(len(trends.unread_catch_up), 1)
        unread_art = trends.unread_catch_up[0]
        self.assertEqual(unread_art.id, art2_id)
        self.assertEqual(unread_art.title, "DeepSeek's New AI Architecture Revealed")
        self.assertEqual(unread_art.feed_title, "TechCrunch & Friends")
        self.assertFalse(unread_art.is_read)
        self.assertEqual(unread_art.interest_score, 8.8)
