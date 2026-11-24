import asyncio
import os
import sys
import tempfile
import unittest
import math
from pathlib import Path
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from feeda.database import Database
import feeda.database
import feeda.services.ranker as ranker_module
from feeda.services.ranker import (
    STOP_WORDS,
    extract_terms,
    score_article,
    rescore_articles,
    update_term_weights,
    apply_decay,
    prune_stop_words_from_term_weights,
)
from feeda.services.interest_grouper import (
    classify_article_category,
    backfill_article_categories,
)
from feeda.services import feed_poller
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

    async def test_database_execute_many_and_write_lock(self):
        # Empty params_list should be a safe no-op
        await self.db.execute_many("INSERT INTO term_weights (term, positive_score) VALUES (?, ?)", [])

        # Batch insert via execute_many
        rows_to_insert = [(f"batchterm{i}", float(i + 1)) for i in range(25)]
        await self.db.execute_many(
            "INSERT INTO term_weights (term, positive_score) VALUES (?, ?)",
            rows_to_insert,
        )
        stored = await self.db.fetch_all("SELECT term, positive_score FROM term_weights WHERE term LIKE 'batchterm%'")
        self.assertEqual(len(stored), 25)

        # Simulate a Database instance created via __new__ with _conn swapped directly
        bypassed_db = Database.__new__(Database)
        bypassed_db._conn = self.db._conn
        await bypassed_db.execute_many(
            "UPDATE term_weights SET positive_score = positive_score + ? WHERE term = ?",
            [(10.0, "batchterm0"), (10.0, "batchterm1")],
        )
        r0 = await self.db.fetch_one("SELECT positive_score FROM term_weights WHERE term = 'batchterm0'")
        self.assertAlmostEqual(r0["positive_score"], 11.0, places=3)

        # Concurrent writes serialized cleanly via _write_lock
        await asyncio.gather(*(
            self.db.execute(
                "INSERT INTO term_weights (term, positive_score) VALUES (?, ?) ON CONFLICT(term) DO UPDATE SET positive_score = positive_score + ?",
                ("concurrent_term", 1.0, 1.0),
            )
            for _ in range(15)
        ))
        rc = await self.db.fetch_one("SELECT positive_score FROM term_weights WHERE term = 'concurrent_term'")
        self.assertAlmostEqual(rc["positive_score"], 15.0, places=3)

    async def test_batched_scoring_rescore_and_coalescing(self):
        feed_id = await self.db.execute("INSERT INTO feeds (title, url) VALUES ('Perf Feed', 'http://perf.example.com')")

        # Seed 30 terms (>1 term, verifies batched IN (...) query instead of 30 sequential SELECTs)
        terms = [f"perfterm{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(30)]
        await self.db.execute_many(
            "INSERT INTO term_weights (term, positive_score, negative_score) VALUES (?, 3.0, 1.0)",
            [(t,) for t in terms],
        )

        # Insert 650 unread articles (> 500 batch size) + 1 starred article
        article_params = [
            (feed_id, f"Title {' '.join(terms[:10])} {i}", f"http://perf.example.com/{i}", f"perf_hash_{i}", 0.0, 0, 1 if i == 0 else 0)
            for i in range(650)
        ]
        await self.db.execute_many(
            "INSERT INTO articles (feed_id, title, url, url_hash, interest_score, is_read, is_starred) VALUES (?, ?, ?, ?, ?, ?, ?)",
            article_params,
        )

        # Spy on fetch_one/fetch_all for score_article fallback path
        fetch_one_calls = 0
        fetch_all_calls = 0
        orig_fetch_one = self.db.fetch_one
        orig_fetch_all = self.db.fetch_all

        async def spy_fetch_one(q, p=()):
            nonlocal fetch_one_calls
            fetch_one_calls += 1
            return await orig_fetch_one(q, p)

        async def spy_fetch_all(q, p=()):
            nonlocal fetch_all_calls
            fetch_all_calls += 1
            return await orig_fetch_all(q, p)

        sample_article = {
            "title": " ".join(terms),
            "summary": "",
            "content": "",
            "feed_id": feed_id,
            "published_at": None,
            "is_starred": False,
            "user_vote": 0,
        }
        with patch.object(self.db, "fetch_one", side_effect=spy_fetch_one), \
             patch.object(self.db, "fetch_all", side_effect=spy_fetch_all):
            fallback_score = await score_article(sample_article, self.db)

        # 1 batched fetch_all for all 30 term_weights + 2 fetch_one (feed_affinity, starred count)
        self.assertEqual(fetch_all_calls, 1)
        self.assertEqual(fetch_one_calls, 2)

        # Preloaded maps must match fallback score with 0 DB calls
        preloaded_score = await score_article(
            sample_article,
            self.db,
            term_weights_map={t: (3.0, 1.0) for t in terms},
            feed_affinity_map={},
            starred_counts_map={feed_id: 1},
        )
        self.assertAlmostEqual(fallback_score, preloaded_score, places=4)

        # Test batched update_term_weights uses execute_many once
        art_row = await self.db.fetch_one("SELECT id FROM articles WHERE feed_id = ? LIMIT 1", (feed_id,))
        with patch.object(self.db, "execute_many", wraps=self.db.execute_many) as spy_exec_many:
            await update_term_weights(art_row["id"], "star", self.db)
            self.assertEqual(spy_exec_many.call_count, 1)

        # Test rescore_articles updates all 650 articles across >1 batch of 500
        with patch.object(self.db, "execute_many", wraps=self.db.execute_many) as spy_rescore_many:
            await rescore_articles(self.db)
            self.assertEqual(spy_rescore_many.call_count, 2)  # 500 + 150

        rescored = await self.db.fetch_all("SELECT interest_score FROM articles WHERE feed_id = ?", (feed_id,))
        self.assertEqual(len(rescored), 650)
        self.assertTrue(all(r["interest_score"] > 0.0 for r in rescored))

        # Test coalescing: 5 concurrent rescore_articles calls should run _run_rescore_once at most 2 times
        run_count = 0
        orig_run_once = ranker_module._run_rescore_once

        async def slow_run_once(database):
            nonlocal run_count
            run_count += 1
            await asyncio.sleep(0.02)
            return await orig_run_once(database)

        with patch.object(ranker_module, "_run_rescore_once", side_effect=slow_run_once):
            await asyncio.gather(*(rescore_articles(self.db) for _ in range(5)))

        self.assertEqual(run_count, 2)

    async def test_backfill_article_categories_batched(self):
        feed_id = await self.db.execute("INSERT INTO feeds (title, url) VALUES ('Backfill Feed', 'http://backfill.example.com')")

        # Insert 1,100 uncategorized articles (> 2 batches of 500)
        rows = []
        for i in range(1100):
            if i % 3 == 0:
                title = f"OpenAI launches new LLM benchmark {i}"
            elif i % 3 == 1:
                title = f"Tesla Cybertruck battery update {i}"
            else:
                title = f"Random miscellaneous note {i}"
            rows.append((feed_id, title, f"http://backfill.example.com/{i}", f"bf_hash_{i}", 0))

        await self.db.execute_many(
            "INSERT INTO articles (feed_id, title, url, url_hash, is_read) VALUES (?, ?, ?, ?, ?)",
            rows,
        )

        # Cap via limit=10
        await backfill_article_categories(self.db, limit=10)
        remaining_after_limit = await self.db.fetch_one(
            "SELECT COUNT(*) as c FROM articles WHERE feed_id = ? AND (category IS NULL OR category_slug IS NULL)",
            (feed_id,),
        )
        self.assertEqual(remaining_after_limit["c"], 1090)

        # Backfill all remaining in 500-row execute_many batches
        with patch.object(self.db, "execute_many", wraps=self.db.execute_many) as spy_many:
            await backfill_article_categories(self.db)
            self.assertEqual(spy_many.call_count, 3)  # 500 + 500 + 90

        remaining = await self.db.fetch_one(
            "SELECT COUNT(*) as c FROM articles WHERE feed_id = ? AND (category IS NULL OR category_slug IS NULL)",
            (feed_id,),
        )
        self.assertEqual(remaining["c"], 0)

        ai_count = await self.db.fetch_one(
            "SELECT COUNT(*) as c FROM articles WHERE feed_id = ? AND category_slug = 'ai-machine-learning'",
            (feed_id,),
        )
        self.assertGreater(ai_count["c"], 300)

    async def test_feed_poller_dedup_and_semaphore(self):
        self.assertIsInstance(feed_poller._active_feed_polls, set)
        self.assertIsInstance(feed_poller._poll_semaphore, asyncio.Semaphore)

        in_flight = 0
        max_concurrent = 0

        async def fake_impl(fid: int):
            nonlocal in_flight, max_concurrent
            in_flight += 1
            max_concurrent = max(max_concurrent, in_flight)
            await asyncio.sleep(0.02)
            in_flight -= 1
            if fid == 9992:
                raise RuntimeError("boom")

        with patch.object(feed_poller, "_poll_single_feed_impl", side_effect=fake_impl):
            results = await asyncio.gather(
                *(feed_poller.poll_single_feed(fid) for fid in range(9990, 9997)),
                return_exceptions=True,
            )

        self.assertLessEqual(max_concurrent, 3)
        self.assertEqual(len(feed_poller._active_feed_polls), 0)
        self.assertIsInstance(results[2], RuntimeError)
