import html
from typing import Optional
import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser
from urllib.parse import urlparse, urljoin

def decode_html_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Unescape twice to handle double-escaped entities like &amp;#8217;
    return html.unescape(html.unescape(str(text))).strip()

async def parse_feed_metadata(url: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            d = feedparser.parse(resp.content)
            title = decode_html_text(d.feed.get('title', url))
            site_url = d.feed.get('link', '')
            desc = decode_html_text(d.feed.get('description', ''))
            
            # Favicon resolution with high-res Google favicon fallback
            favicon = None
            if site_url:
                parsed = urlparse(site_url)
                favicon = f"https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=64"
                
            return {
                "title": title,
                "site_url": site_url,
                "description": desc,
                "favicon_url": favicon
            }
        except Exception:
            return {}

def extract_image(entry, content_html: str = "") -> str | None:
    """Extract lead image from entry media tags or inline HTML."""
    # 1. Media content
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            if isinstance(m, dict) and m.get('url'):
                return m['url']
    # 2. Media thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        for m in entry.media_thumbnail:
            if isinstance(m, dict) and m.get('url'):
                return m['url']
    # 3. Enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if isinstance(enc, dict) and enc.get('type', '').startswith('image/') and enc.get('href'):
                return enc['href']
    # 4. First <img> tag in HTML content or summary
    if content_html:
        try:
            soup = BeautifulSoup(content_html, 'html.parser')
            img = soup.find('img')
            if img and img.get('src'):
                src = img['src']
                # Ignore tracking pixels and 1x1 gifs
                if not any(x in src.lower() for x in ['1x1', 'pixel', 'tracker', 'stat.gif', 'beacon']):
                    return src
        except Exception:
            pass
    return None

def clean_text_snippet(raw_html: str, max_len: int = 260) -> str:
    """Extract clean plain text snippet from HTML."""
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, 'html.parser')
        # Remove script, style, img
        for tag in soup(['script', 'style', 'img', 'video', 'audio', 'figure']):
            tag.decompose()
        text = soup.get_text(separator=' ')
        # Collapse whitespace
        text = ' '.join(text.split()).strip()
        text = decode_html_text(text)
        if len(text) > max_len:
            return text[:max_len].rsplit(' ', 1)[0] + '...'
        return text
    except Exception:
        return decode_html_text(raw_html[:max_len])

def parse_entries(content: bytes) -> list:
    d = feedparser.parse(content)
    entries = []
    for entry in d.entries:
        try:
            published = None
            if hasattr(entry, 'published'):
                published = parser.parse(entry.published).isoformat()
            elif hasattr(entry, 'updated'):
                published = parser.parse(entry.updated).isoformat()
        except:
            published = None
            
        content_text = None
        if hasattr(entry, 'content'):
            content_text = entry.content[0].value
        elif hasattr(entry, 'summary'):
            content_text = entry.summary
            
        raw_summary = entry.get('summary', '') or content_text or ''
        image_url = extract_image(entry, content_text or raw_summary)
        summary_clean = clean_text_snippet(raw_summary)

        entries.append({
            "guid": entry.get('id', entry.get('link', '')),
            "url": entry.get('link', ''),
            "title": decode_html_text(entry.get('title', 'Untitled')),
            "author": decode_html_text(entry.get('author', '')),
            "summary": summary_clean,
            "content": decode_html_text(content_text) if content_text else None,
            "image_url": image_url,
            "published_at": published
        })
    return entries
