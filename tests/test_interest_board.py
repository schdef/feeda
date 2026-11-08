import asyncio
import os
import sys
from pathlib import Path
import unittest
import tempfile
import aiosqlite
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == 'tests' else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'backend'))

from feeda.database import Database
from feeda.models import InterestBoardResponse, ArticleResponse
from feeda.services.interest_grouper import (
    build_interest_board,
    classify_article_topic,
    TOPIC_CATALOG,
)
from feeda.app import create_app


class TestInterestBoard(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create a temporary SQLite database for clean isolated testing
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()

        self.db = Database()
        self.db.db_path = self.db_path
        await self.db.connect()

        # Run minimal migrations / schema setup
        await self.db.execute("""
            CREATE TABLE feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                site_url TEXT,
                favicon_url TEXT,
                description TEXT,
                poll_interval_minutes INTEGER DEFAULT 30,
                last_polled_at TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self.db.execute("""
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                cluster_id INTEGER,
                guid TEXT,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                summary TEXT,
                content TEXT,
                image_url TEXT,
                published_at TIMESTAMP,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                user_vote INTEGER DEFAULT 0,
                interest_score REAL DEFAULT 0.0,
                ai_summary TEXT,
                story_signature TEXT
            );
        """)

        # Insert a test feed
        await self.db.execute(
            "INSERT INTO feeds (id, title, url, favicon_url) VALUES (1, 'Tech News', 'https://example.com/rss', 'https://example.com/fav.png')"
        )

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_empty_database_returns_empty_groups(self):
        result = await build_interest_board(self.db, max_groups=5)
        self.assertEqual(result, {"groups": []})

    async def test_classification_logic(self):
        ai_article = {
            "title": "OpenAI releases new ChatGPT reasoning model",
            "summary": "The artificial intelligence team announced new benchmarks.",
            "story_signature": None
        }
        ev_article = {
            "title": "Tesla Cybertruck supercharger roll-out continues",
            "summary": "Electric vehicle charging stations expand nationwide.",
            "story_signature": None
        }
        cyber_article = {
            "title": "Critical zero-day vulnerability patched in popular software",
            "summary": "Hackers were exploiting the security flaw in the wild.",
            "story_signature": None
        }
        unmatched_article = {
            "title": "Traditional sourdough bread baking techniques",
            "summary": "Flour, water, salt and fermentation time.",
            "story_signature": None
        }

        self.assertEqual(classify_article_topic(ai_article), "ai-machine-learning")
        self.assertEqual(classify_article_topic(ev_article), "electric-vehicles-mobility")
        self.assertEqual(classify_article_topic(cyber_article), "cybersecurity-privacy")
        self.assertEqual(classify_article_topic(unmatched_article), "general-other")

    async def test_group_capping_and_sorting(self):
        # Insert 30 AI articles with varying scores and dates
        for i in range(1, 31):
            await self.db.execute(
                """
                INSERT INTO articles (id, feed_id, url, title, summary, interest_score, published_at, is_read)
                VALUES (?, 1, ?, ?, ?, ?, ?, 0)
                """,
                (
                    i,
                    f"https://example.com/article/{i}",
                    f"AI LLM Article #{i}",
                    "Deep learning neural networks and transformers",
                    float(i * 10),
                    f"2026-11-0{i % 9 + 1}T10:00:00"
                )
            )

        result = await build_interest_board(self.db, max_groups=5)
        self.assertEqual(len(result["groups"]), 1)
        group = result["groups"][0]
        self.assertEqual(group["slug"], "ai-machine-learning")
        self.assertEqual(group["name"], "AI & Machine Learning")
        self.assertEqual(group["emoji"], "🤖")

        # Capped to max 25 articles
        self.assertEqual(len(group["articles"]), 25)
        self.assertEqual(group["article_count"], 25)

        # Sorted by interest_score DESC
        scores = [a["interest_score"] for a in group["articles"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # Top article should have highest score (300.0)
        self.assertEqual(scores[0], 300.0)

    async def test_general_other_captures_unmatched_and_overflow(self):
        # Insert 1 AI article, 1 EV article, and 1 Unmatched article
        await self.db.execute("""
            INSERT INTO articles (id, feed_id, url, title, summary, interest_score, is_read)
            VALUES 
                (1, 1, 'https://example.com/1', 'Deep learning AI agents', 'Artificial intelligence update', 50.0, 0),
                (2, 1, 'https://example.com/2', 'Tesla Cybertruck electric car battery', 'EV mobility update', 40.0, 0),
                (3, 1, 'https://example.com/3', 'How to make homemade sourdough bread', 'Recipe steps', 20.0, 0)
        """)

        # max_groups = 5 (all 3 should fit: AI, EV, General & Other)
        res = await build_interest_board(self.db, max_groups=5)
        slugs = [g["slug"] for g in res["groups"]]
        self.assertIn("ai-machine-learning", slugs)
        self.assertIn("electric-vehicles-mobility", slugs)
        self.assertIn("general-other", slugs)
        self.assertEqual(sum(len(g["articles"]) for g in res["groups"]), 3)

        # max_groups = 2 (AI takes 1 slot, remaining EV + sourdough fold into General & Other)
        res2 = await build_interest_board(self.db, max_groups=2)
        self.assertEqual(len(res2["groups"]), 2)
        slugs2 = [g["slug"] for g in res2["groups"]]
        self.assertIn("ai-machine-learning", slugs2)
        self.assertIn("general-other", slugs2)
        # Total unread articles preserved (none lost!)
        self.assertEqual(sum(len(g["articles"]) for g in res2["groups"]), 3)

    async def test_article_response_structure_validation(self):
        await self.db.execute("""
            INSERT INTO articles (id, feed_id, url, title, summary, interest_score, is_read, is_starred)
            VALUES (1, 1, 'https://example.com/openai', 'OpenAI ChatGPT release', 'New generative AI model', 85.0, 0, 1)
        """)

        res = await build_interest_board(self.db, max_groups=5)
        # Validate through Pydantic
        validated = InterestBoardResponse(**res)
        self.assertEqual(len(validated.groups), 1)
        art = validated.groups[0].articles[0]
        self.assertEqual(art.id, 1)
        self.assertEqual(art.title, "OpenAI ChatGPT release")
        self.assertEqual(art.feed_title, "Tech News")
        self.assertEqual(art.feed_favicon_url, "https://example.com/fav.png")
        self.assertFalse(art.is_read)
        self.assertTrue(art.is_starred)
        self.assertIsNotNone(art.likelihood_tier)

    async def test_read_later_starred_articles_included_whether_read_or_not(self):
        # 1. Insert an article with is_read = 1, is_starred = 1 (read-later item that was already read)
        # 2. Insert an article with is_read = 0, is_starred = 1 (read-later item unread)
        # 3. Insert an article with is_read = 0, is_starred = 0 (normal unread article)
        # 4. Insert an article with is_read = 1, is_starred = 0 (normal read article)
        await self.db.execute("""
            INSERT INTO articles (id, feed_id, url, title, summary, interest_score, is_read, is_starred)
            VALUES 
                (1, 1, 'https://example.com/1', 'Read and Starred AI LLM', 'OpenAI ChatGPT model', 90.0, 1, 1),
                (2, 1, 'https://example.com/2', 'Unread and Starred EV', 'Tesla Cybertruck electric vehicle', 80.0, 0, 1),
                (3, 1, 'https://example.com/3', 'Unread Normal Cyber', 'Zero-day vulnerability security flaw', 70.0, 0, 0),
                (4, 1, 'https://example.com/4', 'Read Normal Article', 'General news', 60.0, 1, 0)
        """)

        res = await build_interest_board(self.db, max_groups=5)
        all_articles = [art for g in res["groups"] for art in g["articles"]]
        returned_ids = {art["id"] for art in all_articles}

        # Assert that the 2 read-later articles and the 1 unread article are included in the groups (total 3 articles)
        self.assertEqual(len(all_articles), 3)
        self.assertIn(1, returned_ids)
        self.assertIn(2, returned_ids)
        self.assertIn(3, returned_ids)

        # Assert that the normal read article (is_read = 1, is_starred = 0) is NOT included
        self.assertNotIn(4, returned_ids)

        # Assert that the already-read read-later article has is_read = True and is_starred = True
        read_starred_art = next(art for art in all_articles if art["id"] == 1)
        self.assertTrue(read_starred_art["is_read"])
        self.assertTrue(read_starred_art["is_starred"])

        # Also verify unread starred article
        unread_starred_art = next(art for art in all_articles if art["id"] == 2)
        self.assertFalse(unread_starred_art["is_read"])
        self.assertTrue(unread_starred_art["is_starred"])


class TestInterestBoardEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["FEEDA_DB_PATH"] = "backend/feeda.db"
        cls.app = create_app()

    def test_interest_board_api(self):
        with TestClient(self.app) as client:
            resp = client.get("/api/articles/interest-board")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("groups", data)
            self.assertTrue(isinstance(data["groups"], list))

            # Validate each group structure
            for group in data["groups"]:
                self.assertIn("name", group)
                self.assertIn("emoji", group)
                self.assertIn("slug", group)
                self.assertIn("article_count", group)
                self.assertIn("articles", group)
                self.assertLessEqual(len(group["articles"]), 25)
                self.assertEqual(group["article_count"], len(group["articles"]))

            # Test max_groups parameter
            resp_max3 = client.get("/api/articles/interest-board?max_groups=3")
            self.assertEqual(resp_max3.status_code, 200)
            data_max3 = resp_max3.json()
            self.assertLessEqual(len(data_max3["groups"]), 3)

            # Test route collision prevention: /api/articles/{article_id}
            if data["groups"] and data["groups"][0]["articles"]:
                art_id = data["groups"][0]["articles"][0]["id"]
                resp_single = client.get(f"/api/articles/{art_id}")
                self.assertEqual(resp_single.status_code, 200)
                self.assertEqual(resp_single.json()["id"], art_id)


if __name__ == "__main__":
    unittest.main()
