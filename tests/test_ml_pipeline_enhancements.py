import os
import sys
import tempfile
import unittest
import math
from pathlib import Path
from httpx import AsyncClient, ASGITransport

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from feeda.database import Database
import feeda.database
from feeda.services.ranker import (
    STOP_WORDS,
    extract_terms,
    score_article,
    apply_decay,
    prune_stop_words_from_term_weights,
)
from feeda.services.interest_grouper import classify_article_category
from feeda.routers.articles import get_likelihood_thresholds
from feeda.app import create_app


class TestMLPipelineEnhancements(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()

        self.db = Database()
        self.db.db_path = self.db_path
        await self.db.connect()

        migrations_dir = str(BASE_DIR / "backend" / "migrations")
        await self.db.run_migrations(migrations_dir)

        self.orig_db_path = feeda.database.db.db_path
        self.orig_db_conn = feeda.database.db._conn
        feeda.database.db.db_path = self.db_path
        feeda.database.db._conn = self.db._conn

        self.app = create_app()

    async def asyncTearDown(self):
        await self.db.close()
        feeda.database.db.db_path = self.orig_db_path
        feeda.database.db._conn = self.orig_db_conn
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_stop_words_expansion_and_pruning(self):
        # 1. Verify English stop words
        en_stop_words = [
            "its", "it", "has", "have", "had", "having", "more", "most", "can", "could",
            "will", "would", "shall", "should", "may", "might", "must", "one", "two",
            "three", "first", "after", "before", "over", "under", "into", "onto", "than",
            "then", "were", "been", "being", "there", "their", "they", "them", "these",
            "those", "about", "also", "such", "some", "any", "other", "only", "very",
            "just", "even", "now", "new", "out", "how", "what", "when", "where", "which",
            "who", "whom", "why", "all", "both", "each", "few"
        ]
        for w in en_stop_words:
            self.assertIn(w, STOP_WORDS)

        # 2. Verify German stop words
        de_stop_words = [
            "hat", "haben", "hatte", "hatten", "mehr", "kann", "können", "koennen", "konnte",
            "konnten", "muss", "müssen", "muessen", "musste", "mussten", "soll", "sollen",
            "sollte", "sollten", "will", "wollen", "wollte", "wollten", "wird", "werden",
            "wurde", "wurden", "dieser", "dieses", "diesem", "diesen", "diese", "jede",
            "jeder", "jedes", "jedem", "jeden", "alle", "aller", "alles", "allem", "allen",
            "noch", "schon", "sehr", "immer", "wieder", "beim", "unter", "ueber", "vor",
            "nach", "zwischen", "gegen", "ohne", "fuer", "durch", "sein", "seine", "seiner",
            "seinem", "seinen", "seines", "ihr", "ihre", "ihrer", "ihrem", "ihren", "ihres",
            "wir", "uns", "unser", "unsere", "euch", "euer", "eure"
        ]
        for w in de_stop_words:
            self.assertIn(w, STOP_WORDS)

        # 3. Verify extract_terms filters them out
        terms = extract_terms("More than two people could have had their issues before and after.")
        self.assertNotIn("more", terms)
        self.assertNotIn("than", terms)
        self.assertNotIn("two", terms)
        self.assertNotIn("could", terms)
        self.assertNotIn("have", terms)
        self.assertNotIn("their", terms)
        self.assertNotIn("after", terms)
        self.assertIn("people", terms)
        self.assertIn("issues", terms)

        # 4. Test pruning contaminated stop words from term_weights
        await self.db.execute("INSERT INTO term_weights (term, positive_score) VALUES ('having', 5.0)")
        await self.db.execute("INSERT INTO term_weights (term, positive_score) VALUES ('können', 4.0)")
        await self.db.execute("INSERT INTO term_weights (term, positive_score) VALUES ('quantum', 8.0)")

        await prune_stop_words_from_term_weights(self.db)

        rows = await self.db.fetch_all("SELECT term FROM term_weights")
        terms_in_db = {r["term"] for r in rows}
        self.assertNotIn("having", terms_in_db)
        self.assertNotIn("können", terms_in_db)
        self.assertIn("quantum", terms_in_db)

    async def test_length_normalization_scoring(self):
        # Populate term_weights with known values using distinct alphabetic words (no digits)
        word_list = [f"termword{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(100)]
        for w in word_list:
            await self.db.execute(
                "INSERT INTO term_weights (term, positive_score, negative_score) VALUES (?, 2.0, 0.0)",
                (w,)
            )

        # Article A: concise (15 unique terms)
        art_short = {
            "title": " ".join(word_list[:15]),
            "summary": "",
            "content": "",
            "feed_id": None,
            "published_at": None,
            "is_starred": False,
            "user_vote": 0
        }
        score_short = await score_article(art_short, self.db)

        # Article B: long (100 unique terms)
        art_long = {
            "title": "Long article title",
            "summary": " ".join(word_list[:50]),
            "content": " ".join(word_list[50:100]),
            "feed_id": None,
            "published_at": None,
            "is_starred": False,
            "user_vote": 0
        }
        score_long = await score_article(art_long, self.db)

        # Raw sum would be: short ~ 30, long ~ 200 (6.67x).
        # With damping, norm_factor for 100 terms is log(110)/log(25) ~ 1.46.
        # Short norm_factor is log(25)/log(25) = 1.0.
        # So score_long is tempered and reasonably bounded (e.g. ~4.5x, not 6.67x+).
        self.assertGreater(score_short, 0.0)
        self.assertGreater(score_long, score_short)
        self.assertLess(score_long, score_short * 5.0)

    async def test_robust_quantile_threshold_prevents_starvation(self):
        # Insert feed
        feed_id = await self.db.execute("INSERT INTO feeds (title, url) VALUES ('Feed 1', 'http://test.com')")

        # 30 diverse topic titles to avoid title deduplication clustering
        topics = [
            "Breakthrough in Quantum Computing Physics",
            "Global Renewable Energy Capacity Expansion",
            "New Deep Sea Marine Species Discovered",
            "Mars Rover Perseverance Drills Rock Sample",
            "Human Gut Microbiome Impact on Brain Health",
            "Commercial Aviation Safest Year on Record",
            "Advancements in Solid State Battery Chemistry",
            "Fusion Reactor Sustains Record Plasma Temp",
            "Archaeologists Unearth Ancient Lost City",
            "Space Telescope Detects Water Vapor Atmosphere",
            "Neuroscientists Map Complete Fruit Fly Brain",
            "Electric Cargo Ships Begin Transatlantic Voyages",
            "Superconducting Materials Discovered at Room Temp",
            "Deep Learning Model Predicts Protein Interactions",
            "Geothermal Energy Plant Powers Entire Metropolitan Island",
            "Vertical Farming Yields Surpass Traditional Agriculture",
            "CRISPR Therapy Treats Rare Genetic Eye Disorder",
            "Autonomous Drones Reforest Burned Mountain Wilderness",
            "Next Generation Solar Cells Exceed Forty Percent Efficiency",
            "New Antibiotic Class Discovered in Soil Bacteria",
            "High Speed Magnetic Levitation Train Completes Trial",
            "Quantum Cryptography Secures Continental Banking Network",
            "Global Helium Reserves Replenished by New Volcanic Field",
            "Direct Air Carbon Capture Facility Opens at Scale",
            "Brain Computer Interface Enables Paralyzed Patient Speech",
            "Desalination Plant Uses Wave Energy Exclusively",
            "Synthetic Biology Produces Biodegradable Plastic Alternatives",
            "Ancient Tree Rings Reveal Extreme Solar Storm Patterns",
            "Autonomous Underwater Vehicles Map Deep Ocean Trench",
            "Nuclear Microreactors Provide Off Grid Clean Power",
        ]

        # Insert 30 articles with scores 1 to 30
        for i, title in enumerate(topics, 1):
            await self.db.execute("""
                INSERT INTO articles (feed_id, title, url, url_hash, interest_score, is_read, published_at)
                VALUES (?, ?, ?, ?, ?, 0, datetime('now'))
            """, (feed_id, title, f"http://test.com/{i}", f"hash_{i}", float(i)))

        # Insert 1 outlier with score 100.0 (in old code spread_above*0.25 would push high_th to 38.67, starving all 30 articles)
        await self.db.execute("""
            INSERT INTO articles (feed_id, title, url, url_hash, interest_score, is_read, published_at)
            VALUES (?, 'Outlier Monopolizing Score Story', 'http://test.com/outlier', 'hash_outlier', 100.0, 0, datetime('now'))
        """, (feed_id,))

        likely_th, high_th, min_score, max_score = await get_likelihood_thresholds(self.db)

        self.assertEqual(max_score, 100.0)
        # In old code: spread_above = 100 - 18.23 = 81.77; min_high = 18.23 + 81.77 * 0.25 = 38.67
        # In new code: high_threshold is bounded by top 25% quantile (24.00), strictly <= 25.0!
        self.assertLessEqual(high_th, 25.0, f"high_threshold {high_th} exceeded top 25% quantile!")
        self.assertGreater(high_th, likely_th)

        # Query /api/articles/for-you and verify multiple articles are returned (no starvation)
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/articles/for-you")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            # Top 25% of 31 articles (scores 24..30 + 100) is 8 articles!
            self.assertGreaterEqual(data["total"], 7)
            self.assertGreaterEqual(len(data["articles"]), 7)
            for a in data["articles"]:
                self.assertEqual(a["likelihood_tier"], "high")

    async def test_decay_retention(self):
        await self.db.execute(
            "INSERT INTO term_weights (term, positive_score, negative_score) VALUES ('docker', 10.0, 5.0)"
        )
        await apply_decay(self.db)
        row = await self.db.fetch_one("SELECT positive_score, negative_score FROM term_weights WHERE term = 'docker'")
        # 10.0 * 0.985 = 9.85
        self.assertAlmostEqual(row["positive_score"], 9.85, places=3)
        self.assertAlmostEqual(row["negative_score"], 4.925, places=3)

    async def test_categorization_and_api(self):
        # 1. Test classify_article_category helper
        name, emoji, slug = classify_article_category(
            title="OpenAI releases new ChatGPT model with deep reasoning",
            summary="New frontier model surpasses benchmarks in mathematics."
        )
        self.assertEqual(name, "AI & Machine Learning")
        self.assertEqual(emoji, "🤖")
        self.assertEqual(slug, "ai-machine-learning")

        ev_name, ev_emoji, ev_slug = classify_article_category(
            title="Tesla Cybertruck production expands with new battery tech",
            summary="Electric vehicle automaker boosts autonomous driving capabilities."
        )
        self.assertEqual(ev_name, "Electric Vehicles & Mobility")
        self.assertEqual(ev_emoji, "🚗")
        self.assertEqual(ev_slug, "electric-vehicles-mobility")

        sec_name, sec_emoji, sec_slug = classify_article_category(
            title="Critical zero-day vulnerability patched in Linux kernel",
            summary="Security researchers discover ransomware exploit."
        )
        self.assertEqual(sec_name, "Cybersecurity & Privacy")
        self.assertEqual(sec_emoji, "🔒")
        self.assertEqual(sec_slug, "cybersecurity-privacy")

        gen_name, gen_emoji, gen_slug = classify_article_category(
            title="Uncategorized random text",
            summary="Nothing in particular."
        )
        self.assertEqual(gen_name, "General & Other")
        self.assertEqual(gen_emoji, "📰")
        self.assertEqual(gen_slug, "general-other")

        # 2. Insert article and test API output
        feed_id = await self.db.execute("INSERT INTO feeds (title, url) VALUES ('AI News', 'http://ai.example.com')")
        art_id = await self.db.execute("""
            INSERT INTO articles (feed_id, title, url, url_hash, summary, interest_score, is_read, category, category_emoji, category_slug)
            VALUES (?, 'Claude 3.5 Sonnet Announcement', 'http://ai.example.com/1', 'hash_ai_1', 'Anthropic introduces latest model', 15.0, 0, 'AI & Machine Learning', '🤖', 'ai-machine-learning')
        """, (feed_id,))

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # /api/articles
            r_list = await client.get("/api/articles?likelihood=all")
            self.assertEqual(r_list.status_code, 200)
            items = r_list.json()["articles"]
            self.assertTrue(len(items) > 0)
            target = next(a for a in items if a["id"] == art_id)
            self.assertEqual(target["category"], "AI & Machine Learning")
            self.assertEqual(target["category_emoji"], "🤖")
            self.assertEqual(target["category_slug"], "ai-machine-learning")

            # /api/articles/{id}
            r_single = await client.get(f"/api/articles/{art_id}")
            self.assertEqual(r_single.status_code, 200)
            single = r_single.json()
            self.assertEqual(single["category"], "AI & Machine Learning")
            self.assertEqual(single["category_emoji"], "🤖")
            self.assertEqual(single["category_slug"], "ai-machine-learning")

            # /api/articles without pre-assigned category backfilled gracefully
            art_id_uncat = await self.db.execute("""
                INSERT INTO articles (feed_id, title, url, url_hash, summary, interest_score, is_read)
                VALUES (?, 'Rivian announces R2 electric vehicle SUV', 'http://ai.example.com/2', 'hash_ai_2', 'New electric car details', 12.0, 0)
            """, (feed_id,))
            r_uncat = await client.get(f"/api/articles/{art_id_uncat}")
            self.assertEqual(r_uncat.status_code, 200)
            uncat_data = r_uncat.json()
            self.assertEqual(uncat_data["category"], "Electric Vehicles & Mobility")
            self.assertEqual(uncat_data["category_emoji"], "🚗")
            self.assertEqual(uncat_data["category_slug"], "electric-vehicles-mobility")
