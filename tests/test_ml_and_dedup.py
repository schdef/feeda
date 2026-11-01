import asyncio
import os
import sys

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == 'tests' else Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "backend" / "feeda.db")
MIGRATIONS_DIR = str(BASE_DIR / "backend" / "migrations")

os.environ["FEEDA_DB_PATH"] = DB_PATH
# Ensure backend is on PYTHONPATH
sys.path.insert(0, str(BASE_DIR / 'backend'))

from feeda.services.ranker import extract_terms, update_term_weights, update_feed_affinity, score_article, rescore_articles
from feeda.services.dedup import clean_title, word_shingles, is_duplicate_title, is_duplicate_article, find_duplicate
from feeda.services.feed_parser import decode_html_text
from feeda.services.llm_dedup import deduplicate_articles_sync
from feeda.database import db
from feeda.models import ArticleResponse, MarkAllReadRequest
from feeda.app import create_app
from httpx import AsyncClient, ASGITransport

async def test_decode_html_text():
    print("\n--- 0. Testing HTML Entity Decoding ---")
    assert decode_html_text("Meta says it&#8217;ll probably delay") == "Meta says it’ll probably delay"
    assert decode_html_text("Apple &amp; Pear") == "Apple & Pear"
    assert decode_html_text("&quot;Hello World&quot;") == '"Hello World"'
    assert decode_html_text("It&#039;s a test") == "It's a test"
    # Double-escaped entities
    assert decode_html_text("Double &amp;#8217; escaped") == "Double ’ escaped"
    assert decode_html_text("Double &amp;amp; escaped") == "Double & escaped"
    assert decode_html_text("Double &amp;quot;quotes&amp;quot;") == 'Double "quotes"'
    # None or empty
    assert decode_html_text(None) == ""
    assert decode_html_text("") == ""
    print("HTML entity decoding PASSED!")

async def test_term_extraction():
    print("--- 1. Testing Term Extraction ---")
    en_text = "The machine learning algorithm will have great accuracy from data."
    en_terms = extract_terms(en_text)
    print("EN terms:", en_terms)
    assert 'the' not in en_terms
    assert 'machine' in en_terms
    assert 'learning' in en_terms
    assert 'algorithm' in en_terms

    de_text = "Künstliche Intelligenz und maschinelles Lernen bringen eine große Überraschung für Ärzte!"
    de_terms = extract_terms(de_text)
    print("DE terms:", de_terms)
    assert 'und' not in de_terms
    assert 'eine' not in de_terms
    assert 'für' not in de_terms
    assert 'künstliche' in de_terms
    assert 'überraschung' in de_terms
    assert 'große' in de_terms
    assert 'ärzte' in de_terms
    print("Term extraction PASSED!")

async def test_dedup_functions():
    print("\n--- 2. Testing Deduplication Logic ---")
    t1 = "Breaking News: Major discovery in quantum physics - SPIEGEL ONLINE"
    t2 = "Major discovery in quantum physics | BBC News"
    cleaned1 = clean_title(t1)
    cleaned2 = clean_title(t2)
    print("Cleaned t1:", cleaned1)
    print("Cleaned t2:", cleaned2)
    assert "SPIEGEL" not in cleaned1
    assert "BBC" not in cleaned2

    is_dup = is_duplicate_title(t1, t2)
    print(f"Titles duplicate? {is_dup}")
    assert is_dup is True

    # Test enhanced clean_title normalization
    print("Testing clean_title enhancements...")
    ct1 = clean_title("Breaking: &quot;Major Discovery&quot; in AI (theverge.com)")
    print("ct1:", ct1)
    assert ct1 == '"Major Discovery" in AI'
    ct2 = clean_title("[Update] Ask HN: What’s your stack? (news.ycombinator.com)")
    print("ct2:", ct2)
    assert ct2 == "What's your stack?"
    ct3 = clean_title("Report: Meta’s new “Llama” AI model - TechCrunch")
    print("ct3:", ct3)
    assert ct3 == 'Meta\'s new "Llama" AI model'
    print("clean_title enhancements PASSED!")

    # Test content SimHash matching
    print("Testing SimHash content matching...")
    from feeda.services.dedup import compute_simhash, hamming_distance, is_duplicate_article
    content_html_a = "<p>Scientists at CERN have observed a rare particle decay predicted by the Standard Model of physics.</p>"
    content_html_b = "<div>Scientists at CERN have observed a rare particle decay predicted by the Standard Model of physics.</div>"
    h_a = compute_simhash(content_html_a)
    h_b = compute_simhash(content_html_b)
    h_dist = hamming_distance(h_a, h_b)
    print(f"SimHash distance (HTML tags stripped): {h_dist}")
    assert h_dist == 0

    doc_base = """
    The European Space Agency has confirmed that its Euclid space telescope has captured its first full-color images of the cosmos.
    Never before has a telescope been able to create such razor-sharp astronomical images across such a large patch of the sky.
    The images showcase five different regions of the nearby and distant universe, including the Perseus cluster of galaxies.
    Scientists will use these observations to study the mysterious influences of dark matter and dark energy throughout cosmic history.
    The telescope is located 1.5 million kilometers from Earth at the Second Lagrange Point.
    """
    doc_mod = doc_base.replace("Agency", "Agencys", 1)
    dist_minor = hamming_distance(compute_simhash(doc_base), compute_simhash(doc_mod))
    print(f"SimHash distance on minor wording difference: {dist_minor}")
    assert dist_minor <= 3, f"Expected distance <= 3, got {dist_minor}"

    # Test is_duplicate_article content matching
    art_c1 = {"id": 1, "title": "Moon discovery", "content": "NASA astronauts have discovered substantial water ice on the southern pole of the moon during exploration."}
    art_c2 = {"id": 2, "title": "Moon water found", "content": "NASA astronauts have discovered substantial water ice on the southern pole of the moon during recent exploration."}
    assert is_duplicate_article(art_c1, art_c2) is True
    print("SimHash content matching PASSED!")

    # Test is_duplicate_article invariants
    print("Testing is_duplicate_article invariants...")
    from feeda.services.dedup import is_duplicate_article
    vit_d1 = {"id": 4192, "title": "I didn't know I was lacking in Vitamin D until I collapsed at work", "feed_title": "Hacker News", "url": "https://bbc.com/news/1"}
    vit_d2 = {"id": 4193, "title": "I didn't know I was lacking in Vitamin D until I collapsed at work - BBC News", "feed_title": "BBC News", "url": "https://bbc.com/news/1"}
    vit_d3 = {"id": 4194, "title": "I didn't know I was lacking in Vitamin D until I collapsed at work", "feed_title": "Aggregator", "url": "https://other.com/news/1"}

    # Same ID must be duplicate (fixes previous bug!)
    assert is_duplicate_article(vit_d1, vit_d1) is True
    # Same URL must be duplicate
    assert is_duplicate_article(vit_d1, vit_d2) is True
    # Different URL & ID but duplicate title must be duplicate
    assert is_duplicate_article(vit_d1, vit_d3) is True
    print("is_duplicate_article assertions PASSED!")

    # Test deduplicate_articles_sync on identical repeated articles (e.g. infinite scroll pagination overlap)
    same_id_array = [dict(vit_d1), dict(vit_d1), dict(vit_d1)]
    deduped_identical = deduplicate_articles_sync(same_id_array)
    assert len(deduped_identical) == 1
    assert deduped_identical[0]["id"] == 4192
    assert deduped_identical[0]["cluster_count"] == 1

    # Test deduplicate_articles_sync on different sources of the Vitamin D story
    vit_d_sources = [dict(vit_d1), dict(vit_d2), dict(vit_d3)]
    deduped_vit = deduplicate_articles_sync(vit_d_sources)
    print(f"Vitamin D multi-source before dedup: {len(vit_d_sources)}, after dedup: {len(deduped_vit)}")
    assert len(deduped_vit) == 1
    assert deduped_vit[0]["id"] == 4192
    assert deduped_vit[0]["cluster_count"] >= 2
    assert "Hacker News" in deduped_vit[0]["cluster_sources"]
    assert "BBC News" in deduped_vit[0]["cluster_sources"]

    # Test deduplicate_articles_sync general
    articles_list = [
        {"id": 1, "title": "Quantum breakthrough announced - TechCrunch", "url": "https://techcrunch.com/quantum", "feed_title": "TechCrunch", "interest_score": 1.2},
        {"id": 2, "title": "Quantum breakthrough announced - Verge", "url": "https://verge.com/quantum", "feed_title": "The Verge", "interest_score": 1.1},
        {"id": 3, "title": "Completely unrelated story about cooking", "url": "https://food.com/soup", "feed_title": "Food Daily", "interest_score": 0.3}
    ]
    deduped = deduplicate_articles_sync(articles_list)
    print(f"Articles before dedup: {len(articles_list)}, after dedup: {len(deduped)}")
    assert len(deduped) == 2
    assert deduped[0]["cluster_count"] == 2
    assert "TechCrunch" in deduped[0]["cluster_sources"]
    assert "The Verge" in deduped[0]["cluster_sources"]
    print("Deduplication PASSED!")

async def test_likelihood_monotonicity():
    print("\n--- 2.5 Testing Likelihood Monotonicity Invariants ---")
    db.db_path = DB_PATH
    await db.connect()
    from feeda.routers.articles import compute_likelihood_tier, get_likelihood_thresholds
    likely_th, high_th, min_score, max_score = await get_likelihood_thresholds()
    print(f"Thresholds: likely={likely_th:.2f}, high={high_th:.2f}, min={min_score:.2f}, max={max_score:.2f}")
    assert high_th > likely_th, f"Invariant violated: high_threshold ({high_th}) must be > likely_threshold ({likely_th})"

    # Strict monotonicity & boundary checks
    assert compute_likelihood_tier(likely_th - 0.001, likely_th, high_th) == "low"
    assert compute_likelihood_tier(likely_th, likely_th, high_th) == "medium"
    assert compute_likelihood_tier((likely_th + high_th) / 2.0, likely_th, high_th) == "medium"
    assert compute_likelihood_tier(high_th, likely_th, high_th) == "high"
    assert compute_likelihood_tier(high_th + 100.0, likely_th, high_th) == "high"

    # Extreme value checks
    assert compute_likelihood_tier(-100.0, 10.0, 20.0) == "low"
    assert compute_likelihood_tier(9.99, 10.0, 20.0) == "low"
    assert compute_likelihood_tier(10.0, 10.0, 20.0) == "medium"
    assert compute_likelihood_tier(15.0, 10.0, 20.0) == "medium"
    assert compute_likelihood_tier(20.0, 10.0, 20.0) == "high"
    assert compute_likelihood_tier(5000.0, 10.0, 20.0) == "high"
    print("Likelihood monotonicity tests PASSED!")

async def test_backend_api():
    print("\n--- 3. Testing Backend Endpoints ---")
    db.db_path = DB_PATH
    await db.connect()
    await db.run_migrations(MIGRATIONS_DIR)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check articles endpoint with likelihood
        r = await client.get("/api/articles?likelihood=likely")
        assert r.status_code == 200, r.text
        data = r.json()
        print(f"Likely articles count: {len(data['articles'])}, total: {data['total']}")
        assert len(data['articles']) > 0
        first = data['articles'][0]
        assert "likelihood_tier" in first
        assert first["likelihood_tier"] in ["high", "medium"]
        assert "interest_score" in first
        print(f"Sample article: score={first['interest_score']}, tier={first['likelihood_tier']}")
        for a in data["articles"]:
            assert a["likelihood_tier"] != "low", f"Article in 'likely' had low tier: id={a['id']}, score={a['interest_score']}"
            assert a["likelihood_tier"] in ("high", "medium")

        # Test open article endpoint
        art_id = first["id"]
        r_open = await client.post(f"/api/articles/{art_id}/open")
        assert r_open.status_code == 200, r_open.text
        assert r_open.json() == {"status": "ok", "article_id": art_id}
        print(f"Opened article {art_id} successfully")

        # Let background rescoring finish
        await asyncio.sleep(0.5)

        # Test star endpoint (read later signal)
        r_star = await client.post(f"/api/articles/{art_id}/star")
        assert r_star.status_code == 200, r_star.text
        print(f"Starred article {art_id} successfully")

        await asyncio.sleep(0.5)

        # Test likelihood not_likely vs likely vs all
        r_all = await client.get("/api/articles?likelihood=all")
        assert r_all.status_code == 200
        print(f"All articles count: {len(r_all.json()['articles'])}")

        # Test cross-page pagination deduplication
        print("Testing cross-page pagination deduplication...")
        r_p1 = await client.get("/api/articles?page=1&limit=20&dedup=true")
        r_p2 = await client.get("/api/articles?page=2&limit=20&dedup=true")
        assert r_p1.status_code == 200 and r_p2.status_code == 200
        p1_articles = r_p1.json()["articles"]
        p2_articles = r_p2.json()["articles"]
        p1_ids = {a["id"] for a in p1_articles}
        p2_ids = {a["id"] for a in p2_articles}
        overlap = p1_ids.intersection(p2_ids)
        print(f"Pagination p1 ({len(p1_ids)}), p2 ({len(p2_ids)}), overlap: {overlap}")
        assert len(overlap) == 0, f"Cross-page pagination returned duplicate articles: {overlap}"
        p1_cids = {a["cluster_id"] for a in p1_articles if a.get("cluster_id")}
        p2_cids = {a["cluster_id"] for a in p2_articles if a.get("cluster_id")}
        cluster_overlap = p1_cids.intersection(p2_cids)
        assert len(cluster_overlap) == 0, f"Cross-page pagination returned duplicate clusters: {cluster_overlap}"
        print("Cross-page pagination deduplication PASSED!")

        r_not_likely = await client.get("/api/articles?likelihood=not_likely&limit=50")
        assert r_not_likely.status_code == 200
        not_likely_data = r_not_likely.json()
        print(f"Not-likely articles count: {len(not_likely_data['articles'])}, total: {not_likely_data['total']}")
        assert len(not_likely_data["articles"]) > 0
        for a in not_likely_data["articles"]:
            assert a["likelihood_tier"] == "low", f"Article in 'not_likely' had non-low tier {a['likelihood_tier']}: id={a['id']}, score={a['interest_score']}"
            assert a["likelihood_tier"] != "high", f"Top Match appeared in Less Likely: id={a['id']}"
            assert a["likelihood_tier"] != "medium"

        # Test mark_all_read with older_than
        r_mark = await client.post("/api/articles/mark-all-read", json={"older_than": "1d"})
        assert r_mark.status_code == 200, r_mark.text
        print("Mark all read older than 1d OK")

        # Test stats endpoint with today_unread_count and for_you_unread_count
        r_stats = await client.get("/api/stats")
        assert r_stats.status_code == 200, r_stats.text
        stats_data = r_stats.json()
        assert "today_unread_count" in stats_data
        assert "for_you_unread_count" in stats_data
        assert isinstance(stats_data["today_unread_count"], int)
        assert isinstance(stats_data["for_you_unread_count"], int)
        print(f"Stats check PASSED: {stats_data}")

        # Test today endpoint and verify synchronization with stats
        r_today = await client.get("/api/articles?today=true&is_read=false")
        assert r_today.status_code == 200, r_today.text
        today_data = r_today.json()
        assert "articles" in today_data
        assert "total" in today_data
        print(f"Today unread endpoint: total={today_data['total']}, stats today_unread={stats_data['today_unread_count']}")
        assert today_data["total"] == stats_data["today_unread_count"]
        for ta in today_data["articles"]:
            assert ta["is_read"] is False

        # Test for-you endpoint and verify synchronization with stats
        r_foryou = await client.get("/api/articles/for-you")
        assert r_foryou.status_code == 200, r_foryou.text
        foryou_data = r_foryou.json()
        assert "articles" in foryou_data
        assert "total" in foryou_data
        assert "page" in foryou_data
        assert "limit" in foryou_data
        assert "has_more" in foryou_data
        print(f"For-You endpoint: total={foryou_data['total']}, articles={len(foryou_data['articles'])}, stats for_you_unread={stats_data['for_you_unread_count']}")
        assert foryou_data["total"] == stats_data["for_you_unread_count"]
        for fa in foryou_data["articles"]:
            assert fa["likelihood_tier"] == "high", f"Expected high, got {fa['likelihood_tier']}"
            assert fa["is_read"] is False

        # Temporarily mark articles unread to verify non-zero for_you_unread_count and tier monotonicity
        await db.execute("UPDATE articles SET is_read = 0 WHERE id IN (SELECT id FROM articles ORDER BY interest_score DESC LIMIT 20)")
        await db.execute("UPDATE articles SET is_read = 0 WHERE id IN (SELECT id FROM articles ORDER BY interest_score ASC LIMIT 20)")

        r_stats_unread = await client.get("/api/stats")
        stats_unread = r_stats_unread.json()
        assert stats_unread["for_you_unread_count"] > 0, "Expected non-zero for_you_unread_count"

        # Test for-you endpoint with default is_read=False, is_read=True, and is_read=None/all
        from feeda.routers.articles import for_you
        # Direct python function call verification
        direct_default = await for_you()
        for a in direct_default["articles"]:
            assert a["is_read"] is False, f"Expected is_read=False by default, got {a['is_read']}"

        direct_false = await for_you(is_read=False)
        for a in direct_false["articles"]:
            assert a["is_read"] is False, f"Expected is_read=False, got {a['is_read']}"

        direct_true = await for_you(is_read=True)
        for a in direct_true["articles"]:
            assert a["is_read"] is True, f"Expected is_read=True, got {a['is_read']}"

        direct_none = await for_you(is_read=None)
        assert direct_none["total"] >= direct_false["total"]
        print(f"Direct for_you calls: default unread={direct_default['total']}, true read={direct_true['total']}, all={direct_none['total']}")

        # HTTP Endpoint verification
        r_foryou_default = await client.get("/api/articles/for-you")
        assert r_foryou_default.status_code == 200
        for fa in r_foryou_default.json()["articles"]:
            assert fa["is_read"] is False

        r_foryou_read = await client.get("/api/articles/for-you?is_read=true")
        assert r_foryou_read.status_code == 200
        for fa in r_foryou_read.json()["articles"]:
            assert fa["is_read"] is True

        r_foryou_all = await client.get("/api/articles/for-you?is_read=all")
        assert r_foryou_all.status_code == 200
        assert r_foryou_all.json()["total"] >= r_foryou_default.json()["total"]
        print(f"For-You is_read verification PASSED (default unread: {r_foryou_default.json()['total']}, read: {r_foryou_read.json()['total']}, all: {r_foryou_all.json()['total']})")

        # Query /api/articles?likelihood=not_likely and assert EVERY article has likelihood_tier == 'low', and NONE have 'high' or 'medium'
        r_nl_unread = await client.get("/api/articles?likelihood=not_likely&limit=50")
        assert r_nl_unread.status_code == 200
        nl_articles = r_nl_unread.json()["articles"]
        assert len(nl_articles) > 0, "Expected not_likely articles"
        for a in nl_articles:
            assert a["likelihood_tier"] == "low", f"Expected low, got {a['likelihood_tier']} (score: {a['interest_score']})"
            assert a["likelihood_tier"] != "high", f"CRITICAL: Top Match in Less Likely! id={a['id']}, score={a['interest_score']}"
            assert a["likelihood_tier"] != "medium"

        # Query /api/articles?likelihood=likely and assert that NO article has likelihood_tier == 'low'
        r_l_unread = await client.get("/api/articles?likelihood=likely&limit=50")
        assert r_l_unread.status_code == 200
        l_articles = r_l_unread.json()["articles"]
        assert len(l_articles) > 0, "Expected likely articles"
        for a in l_articles:
            assert a["likelihood_tier"] != "low", f"Expected medium/high, got low for id={a['id']}, score={a['interest_score']}"
            assert a["likelihood_tier"] in ("high", "medium")

        # Test mark_read endpoint triggering open_article boost
        r_read = await client.post(f"/api/articles/{art_id}/read")
        assert r_read.status_code == 200, r_read.text
        print(f"Mark read (open_article) {art_id} successfully")

        # Test chronological priority and multi-source attribution
        print("\n--- Testing Chronological Earliest Priority & Multi-Source Attribution ---")
        from feeda.services.dedup import update_cluster_primary, create_cluster
        fa_row = await db.fetch_one("SELECT id FROM feeds WHERE url = 'http://alpha.com/rss'")
        if fa_row:
            feed_a_id = fa_row['id']
        else:
            feed_a_id = await db.execute("INSERT INTO feeds (title, url, site_url) VALUES ('Feed Alpha', 'http://alpha.com/rss', 'http://alpha.com')")

        fb_row = await db.fetch_one("SELECT id FROM feeds WHERE url = 'http://beta.com/rss'")
        if fb_row:
            feed_b_id = fb_row['id']
        else:
            feed_b_id = await db.execute("INSERT INTO feeds (title, url, site_url) VALUES ('Feed Beta', 'http://beta.com/rss', 'http://beta.com')")

        # Insert Article A: Published at 10:00 (Later)
        import uuid
        tag = uuid.uuid4().hex[:8]
        title_a = f"Mars Rover spots water signs {tag}"
        title_b = f"Mars Rover spots water signs {tag} - BBC"
        art_a_id = await db.execute(f"""
            INSERT INTO articles (feed_id, title, url, url_hash, published_at, interest_score, is_read)
            VALUES (?, ?, 'http://alpha.com/mars/{tag}', 'hash_mars_a_{tag}', '2026-10-30 10:00:00', 50.0, 0)
        """, (feed_a_id, title_a))

        # Insert Article B: Published at 08:00 (Earlier!)
        art_b_id = await db.execute(f"""
            INSERT INTO articles (feed_id, title, url, url_hash, published_at, interest_score, is_read)
            VALUES (?, ?, 'http://beta.com/mars/{tag}', 'hash_mars_b_{tag}', '2026-10-30 08:00:00', 50.0, 0)
        """, (feed_b_id, title_b))

        # Cluster them
        cid = await create_cluster(db, art_a_id)
        await db.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cid, art_b_id))
        primary_id = await update_cluster_primary(db, cid)
        print(f"Cluster {cid}: art_a={art_a_id} (10:00), art_b={art_b_id} (08:00) -> primary={primary_id}")
        assert primary_id == art_b_id, f"Expected earliest published article {art_b_id} to be primary, got {primary_id}"

        # Query API to verify Article B is returned as primary with cluster_count=2 and other source Feed Alpha
        r_mars = await client.get(f"/api/articles?feed_id={feed_b_id}&likelihood=all")
        assert r_mars.status_code == 200
        mars_articles = [a for a in r_mars.json()["articles"] if a.get("cluster_id") == cid]
        assert len(mars_articles) == 1, f"Expected exactly 1 clustered article returned, got {len(mars_articles)}"
        returned_art = mars_articles[0]
        assert returned_art["id"] == art_b_id, f"Expected primary {art_b_id}, got {returned_art['id']}"
        assert returned_art["cluster_count"] == 2
        print(f"Returned article cluster_sources: {returned_art['cluster_sources']}")
        assert "Feed Alpha" in returned_art["cluster_sources"]

        # Article A should NOT be returned because it's a non-primary duplicate in cluster cid
        r_mars_a = await client.get(f"/api/articles?feed_id={feed_a_id}&likelihood=all")
        assert r_mars_a.status_code == 200
        mars_a_articles = [a for a in r_mars_a.json()["articles"] if a.get("cluster_id") == cid]
        assert len(mars_a_articles) == 0, f"Expected secondary article to be filtered out, got {len(mars_a_articles)}"

        # Check get_article endpoint for the primary article
        r_get_art = await client.get(f"/api/articles/{art_b_id}")
        assert r_get_art.status_code == 200
        get_art_data = r_get_art.json()
        assert get_art_data["cluster_count"] == 2
        assert "Feed Alpha" in get_art_data["cluster_sources"]
        print("Chronological priority and multi-source attribution PASSED!")

        # Cleanup test articles and cluster
        await db.execute("DELETE FROM articles WHERE id IN (?, ?)", (art_a_id, art_b_id))
        await db.execute("DELETE FROM clusters WHERE id = ?", (cid,))

        # Test refresh-all feeds
        from unittest.mock import patch, AsyncMock
        with patch("feeda.services.feed_poller.poll_single_feed", new_callable=AsyncMock):
            r_refresh = await client.post("/api/feeds/refresh-all")
            assert r_refresh.status_code == 200, r_refresh.text
            assert r_refresh.json()["status"] == "refreshing"
            print("Refresh all feeds OK")

        # Test GET /api/feeds/search
        print("\n--- 4. Testing Feed Search Endpoint ---")
        r_search = await client.get("/api/feeds/search?q=technology")
        assert r_search.status_code == 200, r_search.text
        search_data = r_search.json()
        assert "results" in search_data
        print(f"Feed search returned {len(search_data['results'])} results")
        assert len(search_data["results"]) > 0
        first_search = search_data["results"][0]
        assert "title" in first_search
        assert "url" in first_search
        assert "is_subscribed" in first_search
        assert "subscribers" in first_search
        print(f"Sample search result: {first_search['title']} ({first_search['url']}), is_subscribed={first_search['is_subscribed']}")

        # Test GET /api/feeds/suggestions
        print("\n--- 5. Testing Feed Suggestions Endpoint ---")
        r_sug0 = await client.get("/api/feeds/suggestions?refresh=0")
        assert r_sug0.status_code == 200, r_sug0.text
        sug_data0 = r_sug0.json()
        assert "suggestions" in sug_data0
        assert "topics" in sug_data0
        print(f"Suggestions (refresh=0): topics={sug_data0['topics']}, count={len(sug_data0['suggestions'])}")
        assert len(sug_data0["suggestions"]) > 0
        first_sug = sug_data0["suggestions"][0]
        assert "reason" in first_sug
        assert "Based on your interest in:" in first_sug["reason"]
        assert first_sug["is_subscribed"] is False

        # Test refresh gives diverse topics
        r_sug1 = await client.get("/api/feeds/suggestions?refresh=1")
        assert r_sug1.status_code == 200, r_sug1.text
        sug_data1 = r_sug1.json()
        print(f"Suggestions (refresh=1): topics={sug_data1['topics']}, count={len(sug_data1['suggestions'])}")
        assert "suggestions" in sug_data1
        assert "topics" in sug_data1
        assert sug_data1["topics"] != sug_data0["topics"] or len(sug_data1["topics"]) != len(sug_data0["topics"])

        # Test Personal Boards Endpoints
        print("\n--- 6. Testing Feedly Personal Boards Endpoints ---")
        # 1. Create a board
        r_create = await client.post("/api/boards", json={"name": "AI & Deep Learning", "description": "Important ML reads"})
        assert r_create.status_code == 200, r_create.text
        board = r_create.json()
        board_id = board["id"]
        assert board["name"] == "AI & Deep Learning"
        assert board["description"] == "Important ML reads"
        assert board["article_count"] == 0
        print(f"Created board: id={board_id}, name='{board['name']}'")

        # 2. List boards
        r_list = await client.get("/api/boards")
        assert r_list.status_code == 200, r_list.text
        boards_data = r_list.json()
        assert "boards" in boards_data
        assert any(b["id"] == board_id for b in boards_data["boards"])
        print(f"List boards PASSED (total boards: {len(boards_data['boards'])})")

        # 3. Update board
        r_update = await client.put(f"/api/boards/{board_id}", json={"description": "Updated ML reads"})
        assert r_update.status_code == 200, r_update.text
        assert r_update.json()["description"] == "Updated ML reads"
        print(f"Updated board description successfully")

        # 4. Save article to board with note
        r_save = await client.post(f"/api/boards/{board_id}/articles", json={"article_id": art_id, "note": "Crucial research note"})
        assert r_save.status_code == 200, r_save.text
        assert r_save.json()["status"] == "ok"
        print(f"Saved article {art_id} to board {board_id} with note")

        # Let background rescoring execute
        await asyncio.sleep(0.5)

        # 5. List articles in board
        r_board_arts = await client.get(f"/api/boards/{board_id}/articles")
        assert r_board_arts.status_code == 200, r_board_arts.text
        board_arts = r_board_arts.json()
        assert "articles" in board_arts
        assert board_arts["total"] >= 1
        found_art = next((a for a in board_arts["articles"] if a["id"] == art_id), None)
        assert found_art is not None
        assert found_art["board_note"] == "Crucial research note"
        assert found_art["board_added_at"] is not None
        print(f"Board articles check PASSED (found article {art_id} with note: '{found_art['board_note']}')")

        # 6. Update note on saved article
        r_up_note = await client.put(f"/api/boards/{board_id}/articles/{art_id}/note", json={"note": "Revised note"})
        assert r_up_note.status_code == 200, r_up_note.text
        assert r_up_note.json()["note"] == "Revised note"

        # Verify updated note
        r_board_arts2 = await client.get(f"/api/boards/{board_id}/articles")
        found_art2 = next((a for a in r_board_arts2.json()["articles"] if a["id"] == art_id), None)
        assert found_art2["board_note"] == "Revised note"
        print("Update note on board article PASSED")

        # 7. Check article boards endpoint GET /api/articles/{article_id}/boards
        r_art_boards = await client.get(f"/api/articles/{art_id}/boards")
        assert r_art_boards.status_code == 200, r_art_boards.text
        art_boards_data = r_art_boards.json()
        assert art_boards_data["article_id"] == art_id
        assert any(b["board_id"] == board_id and b["note"] == "Revised note" for b in art_boards_data["boards"])
        print(f"Article boards membership check PASSED: {art_boards_data}")

        # 8. Remove article from board
        r_del_art = await client.delete(f"/api/boards/{board_id}/articles/{art_id}")
        assert r_del_art.status_code == 200, r_del_art.text
        r_board_arts3 = await client.get(f"/api/boards/{board_id}/articles")
        assert not any(a["id"] == art_id for a in r_board_arts3.json()["articles"])
        print("Remove article from board PASSED")

        # 9. Delete board
        r_del_board = await client.delete(f"/api/boards/{board_id}")
        assert r_del_board.status_code == 200, r_del_board.text
        r_check_del = await client.get(f"/api/boards/{board_id}")
        assert r_check_del.status_code == 404
        print("Board deletion PASSED")


    print("Backend API test PASSED!")

async def test_opml_import_export():
    print("\n--- 7. Testing OPML Import and Export ---")
    db.db_path = DB_PATH
    await db.connect()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        import time
        import xml.etree.ElementTree as ET
        ts = int(time.time() * 1000)
        f1_name = f"Tech Folder {ts}"
        f2_name = f"Science Folder {ts}"
        feed1_url = f"https://tech.example.com/feed_{ts}.xml"
        feed2_url = f"https://gadgets.example.com/feed_{ts}.xml"
        feed3_url = f"https://science.example.com/feed_{ts}.xml"
        
        sample_opml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Feeda Test OPML</title>
  </head>
  <body>
    <outline text="{f1_name}" title="{f1_name}">
      <outline type="rss" text="Tech Feed 1" title="Tech Feed 1" xmlUrl="{feed1_url}" htmlUrl="https://tech.example.com" />
      <outline text="Nested Subfolder">
        <outline type="rss" text="Tech Feed 2" title="Tech Feed 2" xmlUrl="{feed2_url}" htmlUrl="https://gadgets.example.com" />
      </outline>
    </outline>
    <outline text="{f2_name}" title="{f2_name}">
      <outline type="rss" text="Science Feed 1" title="Science Feed 1" xmlUrl="{feed3_url}" htmlUrl="https://science.example.com" />
    </outline>
  </body>
</opml>"""

        # 1. Test POST /api/feeds/opml/import with UTF-8 BOM
        bom_content = b"\xef\xbb\xbf" + sample_opml.encode("utf-8")
        files = {"file": ("test.opml", bom_content, "application/xml")}
        r_imp = await client.post("/api/feeds/opml/import", files=files)
        assert r_imp.status_code == 200, f"Import failed: {r_imp.text}"
        imp_data = r_imp.json()
        print(f"Import response: {imp_data}")
        assert imp_data["imported_feeds"] == 3
        assert imp_data["imported_folders"] >= 2
        assert imp_data["skipped_feeds"] == 0

        # Check folders exist in database
        folder1 = await db.fetch_one("SELECT * FROM folders WHERE name = ?", (f1_name,))
        assert folder1 is not None, f"Folder {f1_name} was not created"
        folder2 = await db.fetch_one("SELECT * FROM folders WHERE name = ?", (f2_name,))
        assert folder2 is not None, f"Folder {f2_name} was not created"

        # Check feeds exist in database
        feed1 = await db.fetch_one("SELECT * FROM feeds WHERE url = ?", (feed1_url,))
        assert feed1 is not None, f"Feed {feed1_url} was not created"
        assert feed1["folder_id"] == folder1["id"]

        feed3 = await db.fetch_one("SELECT * FROM feeds WHERE url = ?", (feed3_url,))
        assert feed3 is not None, f"Feed {feed3_url} was not created"
        assert feed3["folder_id"] == folder2["id"]

        # 2. Test re-importing the same OPML -> should skip existing feeds
        r_imp2 = await client.post("/api/feeds/opml/import", files=files)
        assert r_imp2.status_code == 200, f"Re-import failed: {r_imp2.text}"
        imp_data2 = r_imp2.json()
        print(f"Re-import response (dedup check): {imp_data2}")
        assert imp_data2["imported_feeds"] == 0
        assert imp_data2["imported_folders"] == 0
        assert imp_data2["skipped_feeds"] == 3

        # 2b. Test Inoreader-style OPML with category attribute at root
        inoreader_opml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <body>
    <outline type="rss" text="Inoreader Feed" xmlUrl="https://inoreader.example.com/feed_{ts}.xml" htmlUrl="https://inoreader.example.com" category="Inoreader Category {ts}" />
  </body>
</opml>"""
        r_ino = await client.post("/api/feeds/opml/import", files={"file": ("inoreader.opml", inoreader_opml.encode("utf-8"), "application/xml")})
        assert r_ino.status_code == 200
        ino_data = r_ino.json()
        assert ino_data["imported_feeds"] == 1
        assert ino_data["imported_folders"] == 1
        assert ino_data["skipped_feeds"] == 0
        cat_folder = await db.fetch_one("SELECT * FROM folders WHERE name = ?", (f"Inoreader Category {ts}",))
        assert cat_folder is not None
        ino_feed = await db.fetch_one("SELECT * FROM feeds WHERE url = ?", (f"https://inoreader.example.com/feed_{ts}.xml",))
        assert ino_feed is not None
        assert ino_feed["folder_id"] == cat_folder["id"]
        print("Inoreader category attribute import PASSED!")

        # 3. Test GET /api/feeds/opml/export
        r_exp = await client.get("/api/feeds/opml/export")
        assert r_exp.status_code == 200, f"Export failed: {r_exp.text}"
        assert r_exp.headers.get("content-disposition") == 'attachment; filename="feeda-export.opml"'
        assert "application/xml" in r_exp.headers.get("content-type", "")

        export_text = r_exp.text
        assert '<?xml version="1.0" encoding="UTF-8"?>' in export_text
        assert '<opml version="2.0">' in export_text
        
        # Verify valid XML structure
        exp_root = ET.fromstring(r_exp.content)
        assert exp_root.tag == "opml"
        exp_body = exp_root.find("body")
        assert exp_body is not None

        # Verify presence of folders and feeds in exported XML
        assert f1_name in export_text
        assert f2_name in export_text
        assert feed1_url in export_text
        assert feed2_url in export_text
        assert feed3_url in export_text
        print("OPML Import and Export tests PASSED!")

async def test_feed_poller_proxy_fallback():
    print("\n--- 8. Testing Feed Poller Proxy Fallback ---")
    import time
    from feeda.services.feed_poller import fetch_feed_content, poll_single_feed
    from unittest.mock import patch
    import httpx
    
    sample_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Proxy Feed</title>
        <link>https://example.com</link>
        <description>Test Proxy Feed</description>
        <item>
          <title>Article From Proxy</title>
          <link>https://example.com/proxy-article-1</link>
          <guid>proxy-article-1</guid>
          <description>Article content from proxy fallback</description>
        </item>
      </channel>
    </rss>"""

    dummy_url = f"https://cloudflare-protected.example.com/rss_{int(time.time()*1000)}.xml"
    feed_id = await db.execute("""
        INSERT INTO feeds (url, title, poll_interval_minutes, error_count)
        VALUES (?, 'Protected Feed', 60, 4)
    """, (dummy_url,))

    orig_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "allorigins.win" in url_str or "corsproxy" in url_str or "codetabs" in url_str:
            return httpx.Response(
                status_code=200,
                headers={"Content-Type": "application/xml"},
                content=sample_rss,
                request=httpx.Request("GET", url_str)
            )
        elif "cloudflare-protected.example.com" in url_str:
            return httpx.Response(
                status_code=403,
                headers={"cf-mitigated": "challenge", "Server": "cloudflare"},
                content=b"<!DOCTYPE html><html><title>Just a moment...</title></html>",
                request=httpx.Request("GET", url_str)
            )
        return await orig_get(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        content, headers, used_proxy = await fetch_feed_content(dummy_url, {})
        assert used_proxy is True
        assert b"Article From Proxy" in content
        print("fetch_feed_content fallback logic PASSED!")

        await poll_single_feed(feed_id)
        
        updated_feed = await db.fetch_one("SELECT * FROM feeds WHERE id = ?", (feed_id,))
        assert updated_feed is not None
        assert updated_feed["error_count"] == 0
        assert updated_feed["last_error"] is None
        assert updated_feed["last_polled_at"] is not None

        art = await db.fetch_one("SELECT * FROM articles WHERE feed_id = ?", (feed_id,))
        assert art is not None
        assert art["title"] == "Article From Proxy"
        print("poll_single_feed proxy fallback integration PASSED!")

    await db.execute("DELETE FROM articles WHERE feed_id = ?", (feed_id,))
    await db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))

async def test_feedly_cloud_fallback():
    print("\n--- 9. Testing Feedly Cloud Fallback & feedly_to_rss_xml ---")
    import time
    from feeda.services.feed_poller import feedly_to_rss_xml, fetch_feed_content, poll_single_feed
    from feeda.services.feed_parser import parse_entries
    from unittest.mock import patch
    import httpx

    # 1. Direct unit test of feedly_to_rss_xml
    sample_feedly_json = {
        "title": "Feedly Cloud Source",
        "description": "Feed description from Feedly",
        "items": [
            {
                "id": "feedly-item-12345",
                "title": "Streamlined Project Management 2026",
                "alternate": [{"href": "https://example.com/project-mgmt-guide"}],
                "author": "Dr. Alex Taylor",
                "published": 1700000000000,
                "summary": {"content": "<p>A comprehensive overview of agile strategies.</p>"}
            },
            {
                "originId": "feedly-item-67890",
                "title": "Secondary Post",
                "alternate": [{"href": "https://example.com/secondary"}],
                "crawled": 1700003600000,
                "content": {"content": "<p>Full content text here.</p>"}
            }
        ]
    }

    original_url = "https://feedly-test.example.com/rss.xml"
    rss_bytes = feedly_to_rss_xml(sample_feedly_json, original_url)
    assert isinstance(rss_bytes, bytes)
    assert b"Streamlined Project Management 2026" in rss_bytes
    assert b"Dr. Alex Taylor" in rss_bytes
    assert b"feedly-item-12345" in rss_bytes
    assert b"https://example.com/project-mgmt-guide" in rss_bytes

    entries = parse_entries(rss_bytes)
    assert len(entries) == 2
    assert entries[0]["title"] == "Streamlined Project Management 2026"
    assert entries[0]["url"] == "https://example.com/project-mgmt-guide"
    assert entries[0]["guid"] == "feedly-item-12345"
    assert entries[0]["author"] == "Dr. Alex Taylor"
    assert entries[0]["published_at"] == "2023-11-14T22:13:20+00:00"
    assert "comprehensive overview" in entries[0]["summary"]
    print("feedly_to_rss_xml unit test PASSED!")

    # 2. Integration test: mock direct request failure (Cloudflare 403 Turnstile) + Feedly Cloud success
    dummy_feedly_url = f"https://cloudflare-cf.example.com/feed_{int(time.time()*1000)}.xml"
    f_id = await db.execute("""
        INSERT INTO feeds (url, title, poll_interval_minutes, error_count, last_error)
        VALUES (?, 'CF Protected Feedly Stream', 60, 5, 'Cloudflare 403 Turnstile')
    """, (dummy_feedly_url,))

    orig_get = httpx.AsyncClient.get

    async def mock_feedly_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "cloud.feedly.com" in url_str:
            return httpx.Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                json=sample_feedly_json,
                request=httpx.Request("GET", url_str)
            )
        elif "cloudflare-cf.example.com" in url_str:
            return httpx.Response(
                status_code=403,
                headers={"cf-mitigated": "challenge", "Server": "cloudflare"},
                content=b"<!DOCTYPE html><html><title>Just a moment...</title>Cloudflare Turnstile</html>",
                request=httpx.Request("GET", url_str)
            )
        return await orig_get(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "get", mock_feedly_get):
        content, headers, used_fallback = await fetch_feed_content(dummy_feedly_url, {})
        assert used_fallback is True
        assert b"Streamlined Project Management 2026" in content
        print("fetch_feed_content Feedly Cloud fallback PASSED!")

        await poll_single_feed(f_id)

        updated_feed = await db.fetch_one("SELECT * FROM feeds WHERE id = ?", (f_id,))
        assert updated_feed is not None
        assert updated_feed["error_count"] == 0
        assert updated_feed["last_error"] is None
        assert updated_feed["last_polled_at"] is not None

        art = await db.fetch_one("SELECT * FROM articles WHERE feed_id = ? ORDER BY id ASC", (f_id,))
        assert art is not None
        assert art["title"] == "Streamlined Project Management 2026"
        assert art["author"] == "Dr. Alex Taylor"
        assert art["published_at"] == "2023-11-14T22:13:20+00:00"
        print("poll_single_feed Feedly Cloud integration PASSED!")

    await db.execute("DELETE FROM articles WHERE feed_id = ?", (f_id,))
    await db.execute("DELETE FROM feeds WHERE id = ?", (f_id,))

async def main():
    await test_decode_html_text()
    await test_term_extraction()
    await test_dedup_functions()
    await test_likelihood_monotonicity()
    await test_backend_api()
    await test_opml_import_export()
    await test_feed_poller_proxy_fallback()
    await test_feedly_cloud_fallback()
    print("\nALL TESTS PASSED SUCCESSFULLY!")
    import os
    os._exit(0)

if __name__ == '__main__':
    asyncio.run(main())
