import os
import sys
import json
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == 'tests' else Path(__file__).resolve().parent
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures_podcast_sample.json"

sys.path.insert(0, str(BASE_DIR / 'backend'))

from feeda.services.dedup import normalize_url, url_hash, is_duplicate_title, is_duplicate_article
from feeda.services.llm_dedup import deduplicate_articles_sync
from feeda.services.ai_summary import are_signatures_duplicate, is_digest_title

def _load_sample_fixtures():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_feed_27_fixture():
    data = _load_sample_fixtures()
    return data["feed_27"][:19]

def get_folder_5_fixture():
    data = _load_sample_fixtures()
    return data["folder_5"][:19]

def test_normalize_url_preserves_query_params_and_ports():
    """Verify that normalize_url preserves ports and meaningful query parameters while stripping tracking params."""
    # Preserves port and meaningful query parameter like ?episodeId=
    url1 = "http://podcasts.example.com:8080/?episodeId=46e387c4-d5e7-420d-9c02-d3677d026824"
    norm1 = normalize_url(url1)
    assert ":8080" in norm1
    assert "episodeid=46e387c4-d5e7-420d-9c02-d3677d026824" in norm1

    # Strips tracking parameters but keeps meaningful params like v, id, p
    url_tracking = "http://localhost:8080/watch?v=dQw4w9WgXcQ&utm_source=twitter&utm_medium=social&utm_campaign=spring"
    norm_tracking = normalize_url(url_tracking)
    assert ":8080" in norm_tracking
    assert "v=dqw4w9wgxcq" in norm_tracking
    assert "utm_source" not in norm_tracking
    assert "utm_medium" not in norm_tracking
    assert "utm_campaign" not in norm_tracking

    # Consistent parameter sorting
    url_a = "https://example.com/item?p=2&id=100"
    url_b = "https://example.com/item?id=100&p=2"
    assert normalize_url(url_a) == normalize_url(url_b)
    assert url_hash(url_a) == url_hash(url_b)

    # Empty and None handling
    assert normalize_url("") == ""
    assert normalize_url(None) == ""

def test_distinct_podcast_episodes_same_feed():
    """Verify that distinct podcast episodes from the same feed with query params are NOT marked as duplicates."""
    ep1 = {
        "id": 6845,
        "feed_id": 27,
        "feed_title": "All-In with Chamath, Jason, Sacks & Friedberg - PodAlpha Insights",
        "title": "Bryan Johnson: I Just Took the Most Powerful Dose of DMT in the World... Here's What It Was Like",
        "url": "http://podcasts.example.com:8080/?episodeId=46e387c4-d5e7-420d-9c02-d3677d026824",
        "guid": "podalpha-ep-46e387c4-d5e7-420d-9c02-d3677d026824",
        "summary": "Die Episode behandelt Bryan Johnsons Erfahrungen mit 5-MeO-DMT und Gehirnscans. PodAlpha Executive Summary.",
        "content": "<div class='rss-root'><div class='rss-link'>🎙️ All-In with Chamath, Jason, Sacks & Friedberg</div><div class='rss-highlight'><h3 class='rss-highlight-title'>🎯 PodAlpha Executive Summary</h3><p>Die Episode behandelt Bryan Johnsons Erfahrungen mit 5-MeO-DMT.</p></div></div>"
    }

    ep2 = {
        "id": 6866,
        "feed_id": 27,
        "feed_title": "All-In with Chamath, Jason, Sacks & Friedberg - PodAlpha Insights",
        "title": "Ray Dalio: Our System Is in Jeopardy - Debt, AI & the Cycle That Destroyed Rome",
        "url": "http://podcasts.example.com:8080/?episodeId=7bea282e-50d5-43ea-97f1-01d1b0d2de03",
        "guid": "podalpha-ep-7bea282e-50d5-43ea-97f1-01d1b0d2de03",
        "summary": "Ray Dalio diskutiert Makroökonomie, Schuldenzyklen, Rezessionsrisiken und Weltordnungen. PodAlpha Executive Summary.",
        "content": "<div class='rss-root'><div class='rss-link'>🎙️ All-In with Chamath, Jason, Sacks & Friedberg</div><div class='rss-highlight'><h3 class='rss-highlight-title'>🎯 PodAlpha Executive Summary</h3><p>Ray Dalio diskutiert Makroökonomie und Schuldenzyklen.</p></div></div>"
    }

    # Despite shared PodAlpha boilerplate in summary/content, distinct episodes from the same feed MUST NOT match
    assert is_duplicate_article(ep1, ep2) is False
    assert is_duplicate_article(ep2, ep1) is False

    # Deduplicating the list must keep both episodes
    deduped = deduplicate_articles_sync([dict(ep1), dict(ep2)])
    assert len(deduped) == 2
    assert {e["id"] for e in deduped} == {6845, 6866}

def test_feed_27_all_19_episodes_preserved():
    """Verify that deduplicating all unread episodes from feed 27 preserves all 19 episodes using isolated test data."""
    rows = get_feed_27_fixture()

    assert len(rows) == 19, f"Expected 19 unread episodes in feed 27, found {len(rows)}"

    # Run sync deduplication
    deduped = deduplicate_articles_sync(rows)
    assert len(deduped) == 19, f"Expected all 19 episodes to be preserved, but got {len(deduped)}"

    # Check pairwise is_duplicate_article is False for every pair
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            assert is_duplicate_article(rows[i], rows[j]) is False, (
                f"False positive duplicate between {rows[i]['id']} ('{rows[i]['title']}') "
                f"and {rows[j]['id']} ('{rows[j]['title']}')"
            )

def test_distinct_articles_different_feeds_boilerplate_not_duplicated():
    """Verify that articles across different feeds with completely distinct titles are not collapsed by boilerplate."""
    art_a = {
        "id": 901,
        "feed_id": 10,
        "feed_title": "AI Weekly",
        "title": "OpenAI announces new enterprise governance framework",
        "url": "https://ai-weekly.com/articles/openai-governance",
        "guid": "guid-ai-901",
        "summary": "OpenAI today published guidance for enterprise risk management and audit logs.",
        "content": "<p>OpenAI today published guidance for enterprise risk management and audit logs.</p><footer>Subscribe to our weekly technology newsletter and podcast for more insightful updates and analysis!</footer>"
    }

    art_b = {
        "id": 902,
        "feed_id": 20,
        "feed_title": "Tech Digest",
        "title": "SpaceX successfully tests next-generation Raptor vacuum engine",
        "url": "https://tech-digest.com/news/spacex-raptor-v3",
        "guid": "guid-td-902",
        "summary": "SpaceX completed a 300-second full duration burn of its updated Raptor engine in McGregor.",
        "content": "<p>SpaceX completed a 300-second full duration burn of its updated Raptor engine in McGregor.</p><footer>Subscribe to our weekly technology newsletter and podcast for more insightful updates and analysis!</footer>"
    }

    # Distinct titles and completely different news stories should never be collapsed by shared footer boilerplate
    assert is_duplicate_article(art_a, art_b) is False
    assert is_duplicate_article(art_b, art_a) is False

    deduped = deduplicate_articles_sync([dict(art_a), dict(art_b)])
    assert len(deduped) == 2

def test_syndication_and_true_duplicates_still_collapsed():
    """Verify that actual duplicate articles (exact URLs, duplicate titles, syndication) are still correctly collapsed."""
    # 1. Exact URL / GUID match within same feed (e.g. re-fetch or updated timestamp)
    art_orig = {
        "id": 1001,
        "feed_id": 5,
        "feed_title": "Ars Technica",
        "title": "New study reveals surprising insights into battery degradation",
        "url": "https://arstechnica.com/science/2026/11/battery-study/?utm_source=rss",
        "guid": "ars-battery-1001"
    }
    art_refetch = {
        "id": 1002,
        "feed_id": 5,
        "feed_title": "Ars Technica",
        "title": "New study reveals surprising insights into battery degradation",
        "url": "https://arstechnica.com/science/2026/11/battery-study/?utm_source=twitter",
        "guid": "ars-battery-1001"
    }
    assert is_duplicate_article(art_orig, art_refetch) is True

    # 2. Duplicate title across different syndication feeds
    art_syn1 = {
        "id": 2001,
        "feed_id": 11,
        "feed_title": "TechCrunch",
        "title": "Anthropic unveils Claude 3.5 Sonnet updates - TechCrunch",
        "url": "https://techcrunch.com/2026/11/claude-update",
        "guid": "tc-2001"
    }
    art_syn2 = {
        "id": 2002,
        "feed_id": 12,
        "feed_title": "The Verge",
        "title": "Anthropic unveils Claude 3.5 Sonnet updates — The Verge",
        "url": "https://theverge.com/2026/11/claude-update-verge",
        "guid": "verge-2002"
    }
    assert is_duplicate_article(art_syn1, art_syn2) is True

    # 3. High content overlap with title token correlation
    art_c1 = {
        "id": 3001,
        "title": "Moon water discovery confirmed by NASA",
        "content": "NASA scientists confirmed the presence of abundant water ice deposits in permanently shadowed craters of the lunar south pole."
    }
    art_c2 = {
        "id": 3002,
        "title": "NASA discovers lunar ice at south pole of Moon",
        "content": "NASA scientists confirmed the presence of abundant water ice deposits in permanently shadowed craters of the lunar south pole today."
    }
    assert is_duplicate_article(art_c1, art_c2) is True

def test_newsletter_digest_not_collapsed_with_standalone_story():
    """Verify that multi-topic digests (like MIT Technology Review's 'The Download')
    are not collapsed with standalone stories that mention the same company."""
    # Digest article mentioning Anthropic IPO along with power grids and exercise pills
    art_digest = {
        "id": 3118,
        "feed_id": 12,
        "feed_title": "MIT Technology Review",
        "title": "The Download: Anthropic’s IPO, smarter power grids, and exercise pills",
        "url": "https://www.technologyreview.com/2026/03/12/1113063/the-download-anthropics-ipo-smarter-power-grids-and-exercise-pills/",
        "guid": "https://www.technologyreview.com/2026/03/12/1113063/the-download-anthropics-ipo-smarter-power-grids-and-exercise-pills/",
        "summary": "This is today’s edition of The Download, our weekday newsletter providing a daily dose of tech news.",
        "content": "This is today’s edition of The Download, our weekday newsletter that provides a daily dose of what’s going on in the world of technology. Anthropic is weighing an IPO. Smarter power grids. Exercise pills.",
        "story_signature": "entity:anthropic,ipo|cluster:|action:|keys:download,anthropic,ipo,smarter"
    }

    # Standalone news story from The Verge about Anthropic and Wall Street
    art_standalone = {
        "id": 3765,
        "feed_id": 14,
        "feed_title": "The Verge",
        "title": "Anthropic is asking Wall Street to believe in AGI",
        "url": "https://www.theverge.com/news/637375/anthropic-ipo-wall-street-agi-semianalysis",
        "guid": "https://www.theverge.com/news/637375/anthropic-ipo-wall-street-agi-semianalysis",
        "summary": "Today on Decoder, I’m joined by Joey Brookhart, an analyst at the chip and AI research firm SemiAnalysis.",
        "content": "Today on Decoder, I’m joined by Joey Brookhart, an analyst at the chip and AI research firm SemiAnalysis. Anthropic is asking Wall Street to believe in AGI ahead of its planned IPO.",
        "story_signature": "entity:agi,anthropic,ipo,semianalysis|cluster:|action:|keys:anthropic,asking,wall,street"
    }

    # Verify is_digest_title correctly identifies the newsletter
    assert is_digest_title(art_digest["title"]) is True
    assert is_digest_title(art_standalone["title"]) is False

    # Signatures must NOT be duplicate
    assert are_signatures_duplicate(
        art_digest["story_signature"],
        art_standalone["story_signature"],
        art_digest["title"],
        art_standalone["title"]
    ) is False

    # Also without titles, distinct keys check must prevent duplicate collapse
    assert are_signatures_duplicate(
        art_digest["story_signature"],
        art_standalone["story_signature"]
    ) is False

    # is_duplicate_article must be False in both directions
    assert is_duplicate_article(art_digest, art_standalone) is False
    assert is_duplicate_article(art_standalone, art_digest) is False

    # Deduplicating list preserves both
    deduped = deduplicate_articles_sync([dict(art_digest), dict(art_standalone)])
    assert len(deduped) == 2
    assert {a["id"] for a in deduped} == {3118, 3765}

def test_folder_5_tech_all_19_unread_articles_preserved():
    """Verify that deduplicating all unread articles from Folder 5 (Tech) preserves all 19 articles (0 dropped) using isolated test data."""
    rows = get_folder_5_fixture()

    assert len(rows) == 19, f"Expected 19 unread articles in folder 5, found {len(rows)}"

    # Run sync deduplication
    deduped = deduplicate_articles_sync(rows)
    assert len(deduped) == 19, f"Expected all 19 articles to be preserved, but got {len(deduped)}"

    # Check pairwise is_duplicate_article is False for every pair
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            assert is_duplicate_article(rows[i], rows[j]) is False, (
                f"False positive duplicate between {rows[i]['id']} ('{rows[i]['title']}') "
                f"and {rows[j]['id']} ('{rows[j]['title']}')"
            )

def test_rule_b_distinct_keys_requirement():
    """Verify that Rule B does not double-count entity words as keys and requires >= 2 distinct keys."""
    # Two articles sharing 2 entities (e.g. apple, google), but keys only repeat 'apple' (0 distinct keys),
    # no action or cluster match -> NOT duplicates
    sig_no_distinct_keys_1 = "entity:apple,google|cluster:|action:|keys:apple,tech"
    sig_no_distinct_keys_2 = "entity:apple,google|cluster:|action:|keys:apple,mobile"
    assert are_signatures_duplicate(
        sig_no_distinct_keys_1,
        sig_no_distinct_keys_2,
        "Apple and Google face regulatory hearing",
        "Google and Apple update mobile developer guidelines"
    ) is False

    # Two articles sharing 2 entities + 2 distinct keypoints describing the same story event
    sig_shared_keys_1 = "entity:apple,google|cluster:|action:|keys:antitrust,doj,hearing,penalty"
    sig_shared_keys_2 = "entity:apple,google|cluster:|action:|keys:antitrust,doj,investigation,regulators"
    assert are_signatures_duplicate(
        sig_shared_keys_1,
        sig_shared_keys_2,
        "DOJ antitrust hearing targets Apple and Google",
        "Apple and Google face DOJ antitrust scrutiny"
    ) is True

