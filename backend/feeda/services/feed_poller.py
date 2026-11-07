import asyncio
import httpx
import logging
from datetime import datetime
import re
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import formatdate
from ..database import db
from .feed_parser import parse_entries, decode_html_text
from .dedup import find_duplicate, url_hash, title_shingles, compute_simhash, update_cluster_primary
from .ai_summary import analyze_article
from .ranker import score_article, apply_decay, rescore_articles
from .plugin_manager import hook_manager
from .llm_dedup import cluster_unclustered_articles_background

logger = logging.getLogger(__name__)

async def fetch_og_image(url: str) -> str | None:
    """Fetch OpenGraph image from article webpage if RSS feed has no media tags."""
    if not url or not url.startswith('http'):
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 Feeda/0.1"})
            m = re.search(r'property=[\"\']og:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', resp.text) or re.search(r'content=[\"\']([^\"\']+)[\"\'][^>]+property=[\"\']og:image[\"\']', resp.text)
            if m:
                img_url = m.group(1).strip()
                if img_url.startswith('http'):
                    return img_url
    except Exception:
        pass
    return None

def feedly_to_rss_xml(feedly_json: dict, original_url: str) -> bytes:
    """
    Constructs standard RSS 2.0 XML from Feedly Cloud stream JSON.
    Extracts items: <title>, <link>, <guid>, <description>, <author>, <pubDate>.
    Returns UTF-8 encoded XML bytes.
    """
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    feed_title = feedly_json.get("title") or original_url
    ET.SubElement(channel, "title").text = feed_title
    ET.SubElement(channel, "link").text = original_url
    ET.SubElement(channel, "description").text = feed_title

    for it in feedly_json.get("items", []):
        item_el = ET.SubElement(channel, "item")
        ET.SubElement(item_el, "title").text = it.get("title", "Untitled")

        # Link
        link_val = ""
        alternate = it.get("alternate")
        if isinstance(alternate, list) and len(alternate) > 0 and isinstance(alternate[0], dict):
            link_val = alternate[0].get("href", "")
        if not link_val:
            link_val = it.get("originId") or it.get("id") or original_url
        ET.SubElement(item_el, "link").text = link_val

        # Guid
        guid_val = it.get("originId") or it.get("id") or link_val
        ET.SubElement(item_el, "guid").text = guid_val

        # Description
        desc_val = ""
        summary_obj = it.get("summary")
        content_obj = it.get("content")
        if isinstance(content_obj, dict) and content_obj.get("content"):
            desc_val = content_obj["content"]
        elif isinstance(summary_obj, dict) and summary_obj.get("content"):
            desc_val = summary_obj["content"]
        elif isinstance(summary_obj, str):
            desc_val = summary_obj
        elif isinstance(content_obj, str):
            desc_val = content_obj
        ET.SubElement(item_el, "description").text = desc_val

        # Author
        author_val = it.get("author") or ""
        if author_val:
            ET.SubElement(item_el, "author").text = author_val

        # pubDate (RFC 822 format from ms timestamp)
        ms_ts = it.get("published") or it.get("crawled")
        if ms_ts:
            try:
                ET.SubElement(item_el, "pubDate").text = formatdate(ms_ts / 1000.0, usegmt=True)
            except Exception:
                pass

        # Visual / enclosure if present
        visual = it.get("visual")
        if isinstance(visual, dict) and visual.get("url") and visual.get("url") != "none":
            ET.SubElement(item_el, "enclosure", url=visual["url"], type="image/jpeg", length="0")
        elif isinstance(it.get("enclosure"), list):
            for enc in it["enclosure"]:
                if isinstance(enc, dict) and enc.get("href"):
                    ET.SubElement(item_el, "enclosure", url=enc["href"], type=enc.get("type", "image/jpeg"), length=str(enc.get("length", 0)))

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)

async def fetch_feed_content(url: str, headers: dict) -> tuple[bytes, dict, bool]:
    """
    Attempts to fetch feed directly. If 403, 503, or Cloudflare challenge is encountered,
    attempts fallback via public CORS/RSS proxies.
    Returns (content_bytes, response_headers, used_proxy).
    """
    headers_client = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    
    needs_fallback = False
    direct_status = None
    direct_err_msg = ""
    
    async with httpx.AsyncClient(headers=headers_client, timeout=12.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 304:
                return b"", resp.headers, False
                
            direct_status = resp.status_code
            if resp.status_code in (403, 503):
                needs_fallback = True
            elif "cf-mitigated" in resp.headers or b"challenges.cloudflare.com" in resp.content or b"Just a moment..." in resp.content:
                needs_fallback = True
            else:
                resp.raise_for_status()
                entries = parse_entries(resp.content)
                if not entries and (b"cloudflare" in resp.content.lower() or b"cf-ray" in resp.content.lower()):
                    needs_fallback = True
                else:
                    return resp.content, resp.headers, False
        except httpx.HTTPStatusError as e:
            direct_status = e.response.status_code
            direct_err_msg = str(e)
            if direct_status in (403, 503):
                needs_fallback = True
            else:
                raise
        except Exception as e:
            # Re-raise generic errors (like DNS resolution failure or network unreachable)
            raise

        if needs_fallback:
            logger.info(f"Feed {url} encountered direct issue ({direct_status or direct_err_msg}). Trying fallback...")

            # 1. First try Feedly Cloud Stream API
            try:
                encoded_url = urllib.parse.quote(url)
                feedly_url = f"https://cloud.feedly.com/v3/streams/contents?streamId=feed%2F{encoded_url}&count=30"
                f_resp = await client.get(feedly_url, headers={"User-Agent": "Mozilla/5.0 Feeda/0.1"})
                if f_resp.status_code == 200:
                    feedly_json = f_resp.json()
                    if feedly_json.get("items"):
                        logger.info(f"Feedly Cloud fallback succeeded for {url} ({len(feedly_json['items'])} items)")
                        rss_xml = feedly_to_rss_xml(feedly_json, url)
                        return rss_xml, f_resp.headers, True
            except Exception as fe:
                logger.debug(f"Feedly Cloud fallback failed for {url}: {fe}")

            # 2. Proceed with existing proxy list
            encoded_url = urllib.parse.quote(url)
            proxy_urls = [
                f"https://api.allorigins.win/raw?url={encoded_url}",
                f"https://corsproxy.io/?{encoded_url}",
                f"https://api.codetabs.com/v1/proxy?quest={encoded_url}",
            ]
            
            last_proxy_err = None
            for proxy_url in proxy_urls:
                try:
                    p_resp = await client.get(proxy_url, headers={"User-Agent": "Mozilla/5.0 Feeda/0.1"})
                    if p_resp.status_code == 200 and p_resp.content:
                        p_entries = parse_entries(p_resp.content)
                        if p_entries:
                            logger.info(f"Proxy fallback succeeded for {url} via {proxy_url[:40]}")
                            return p_resp.content, p_resp.headers, True
                except Exception as pe:
                    last_proxy_err = pe
                    logger.debug(f"Proxy {proxy_url[:40]} failed: {pe}")
            
            raise Exception(f"Direct request failed ({direct_status or direct_err_msg}) and proxy fallbacks failed: {last_proxy_err}")

async def poll_single_feed(feed_id: int):
    feed = await db.fetch_one("SELECT * FROM feeds WHERE id = ?", (feed_id,))
    if not feed: return
    
    headers = {}
    if feed['etag']: headers['If-None-Match'] = feed['etag']
    if feed['last_modified']: headers['If-Modified-Since'] = feed['last_modified']
    
    try:
        content, resp_headers, used_proxy = await fetch_feed_content(feed['url'], headers)
        
        # 304 Not Modified
        if not content and not used_proxy:
            await db.execute("UPDATE feeds SET last_polled_at = CURRENT_TIMESTAMP, error_count = 0, last_error = NULL WHERE id = ?", (feed_id,))
            return
            
        entries = parse_entries(content)
        for entry in entries:
            uhash = url_hash(entry['url'])
            guid = entry.get('guid')

            # Check if this article already exists in this feed by guid or url_hash
            existing_article = None
            if guid:
                existing_article = await db.fetch_one(
                    "SELECT id, cluster_id FROM articles WHERE feed_id = ? AND guid = ?",
                    (feed_id, guid)
                )
            if not existing_article:
                existing_article = await db.fetch_one(
                    "SELECT id, cluster_id FROM articles WHERE feed_id = ? AND url_hash = ?",
                    (feed_id, uhash)
                )

            if existing_article:
                # Update existing article rather than inserting a duplicate
                entry['title'] = decode_html_text(entry.get('title'))
                entry['summary'] = decode_html_text(entry.get('summary'))
                entry['author'] = decode_html_text(entry.get('author'))
                if entry.get('content'):
                    entry['content'] = decode_html_text(entry['content'])
                await db.execute("""
                    UPDATE articles 
                    SET title = ?, summary = ?, content = ?, published_at = ?, url = ?, url_hash = ?
                    WHERE id = ?
                """, (entry['title'], entry['summary'], entry.get('content'), entry['published_at'], entry['url'], uhash, existing_article['id']))
                continue

            entry['title'] = decode_html_text(entry.get('title'))
            entry['summary'] = decode_html_text(entry.get('summary'))
            entry['author'] = decode_html_text(entry.get('author'))
            if entry.get('content'):
                entry['content'] = decode_html_text(entry['content'])
            
            await hook_manager.run('process_article', entry)
            
            ai_data = await analyze_article(entry['title'], entry.get('content') or "", entry.get('summary') or "")
            entry['ai_summary'] = ai_data.get('ai_summary')
            entry['story_signature'] = ai_data.get('story_signature')

            shingles = ",".join(title_shingles(entry['title']))
            simhash_val = compute_simhash(entry['content'] or entry['summary'] or "")
            
            cluster_id = await find_duplicate(entry, db)
            
            image_url = entry.get('image_url')
            if not image_url:
                image_url = await fetch_og_image(entry['url'])

            entry['feed_id'] = feed_id
            score = await score_article(entry, db)

            await db.execute("""
                INSERT INTO articles (feed_id, cluster_id, guid, url, url_hash, title, author, summary, content, image_url, published_at, title_shingles, content_simhash, interest_score, ai_summary, story_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (feed_id, cluster_id, entry['guid'], entry['url'], uhash, entry['title'], entry['author'], entry['summary'], entry['content'], image_url, entry['published_at'], shingles, simhash_val, score, entry['ai_summary'], entry['story_signature']))

            if cluster_id:
                await update_cluster_primary(db, cluster_id)

            await db.execute("""
                INSERT INTO feed_affinity (feed_id, articles_received, articles_read, affinity_score)
                VALUES (?, 1, 0, 0.5)
                ON CONFLICT(feed_id) DO UPDATE SET articles_received = articles_received + 1
            """, (feed_id,))
            
        etag = resp_headers.get('ETag') if not used_proxy else None
        last_mod = resp_headers.get('Last-Modified') if not used_proxy else None
        
        await db.execute("""
            UPDATE feeds SET last_polled_at = CURRENT_TIMESTAMP, etag = ?, last_modified = ?, error_count = 0, last_error = NULL
            WHERE id = ?
        """, (etag, last_mod, feed_id))
        
        asyncio.create_task(cluster_unclustered_articles_background(db))
        
    except Exception as e:
        logger.error(f"Error polling feed {feed_id}: {e}")
        await db.execute("""
            UPDATE feeds SET last_polled_at = CURRENT_TIMESTAMP, error_count = error_count + 1, last_error = ? 
            WHERE id = ?
        """, (str(e), feed_id))

async def feed_poller_task():
    await asyncio.sleep(10)
    last_decay_time = datetime.utcnow()
    while True:
        try:
            now = datetime.utcnow()
            if (now - last_decay_time).total_seconds() >= 3600 * 2:
                await apply_decay(db)
                await rescore_articles(db)
                last_decay_time = now
            
            # Simple polling: get all feeds that need polling
            feeds = await db.fetch_all("""
                SELECT id, poll_interval_minutes, last_polled_at, error_count
                FROM feeds
            """)
            
            now = datetime.utcnow()
            for feed in feeds:
                poll = False
                if not feed['last_polled_at']:
                    poll = True
                else:
                    try:
                        last = datetime.fromisoformat(feed['last_polled_at'])
                        minutes_since = (now - last).total_seconds() / 60.0
                        
                        # backoff
                        interval = feed['poll_interval_minutes']
                        if feed['error_count'] > 0:
                            interval = min(interval * (2 ** min(feed['error_count'], 6)), 360)
                            
                        if minutes_since >= interval:
                            poll = True
                    except:
                        poll = True
                        
                if poll:
                    asyncio.create_task(poll_single_feed(feed['id']))
                    
        except Exception as e:
            logger.error(f"Poller loop error: {e}")
            
        await asyncio.sleep(60)
