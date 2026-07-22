
import sys
import re
import time
from datetime import datetime

MISSING_DEPENDENCY_ERROR = None
try:
    import urllib3
    import requests
    from bs4 import BeautifulSoup
except ModuleNotFoundError as exc:
    MISSING_DEPENDENCY_ERROR = exc
    requests = None
    BeautifulSoup = None

if MISSING_DEPENDENCY_ERROR is None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clean_text(text):
    if not text: return ""
    text = text.strip()
    # html.parser leaves CDATA markers intact; strip them
    text = re.sub(r'^\s*<!\[CDATA\[|\]\]>\s*$', '', text).strip()
    return text

def parse_rss_content(content, source_name, limit=5, error_callback=None):
    """
    Parses RSS/Atom content string (XML or HTML) and returns items.
    """
    try:
        if MISSING_DEPENDENCY_ERROR is not None:
            raise RuntimeError(f"Missing dependency: {MISSING_DEPENDENCY_ERROR.name}")
        # Use html.parser which is built-in and lenient 
        soup = BeautifulSoup(content, 'html.parser')
        
        items = []
        entries = soup.find_all(['item', 'entry'])
        
        for entry in entries:
            # --- Title ---
            title_tag = entry.find('title')
            if not title_tag: continue
            title = clean_text(title_tag.get_text())
            
            # --- Link ---
            link = ""
            link_tag = entry.find('link')
            if link_tag:
                if link_tag.has_attr('href'):
                    link = link_tag['href']
                elif link_tag.get_text(strip=True):
                    link = link_tag.get_text(strip=True)
                if not link:
                    link = str(link_tag.next_sibling).strip()
            
            if not link:
                guid = entry.find('guid')
                if guid and guid.get_text(strip=True).startswith('http'):
                    link = guid.get_text(strip=True)

            # --- Time ---
            pub = entry.find(['pubdate', 'published', 'updated', 'dc:date'])
            time_str = clean_text(pub.get_text()) if pub else ""
            
            # --- Summary / Content ---
            content_encoded = entry.find('content:encoded')
            description = entry.find('description')
            summary = entry.find('summary')
            content = entry.find('content')
            
            raw_summary = ""
            if content_encoded: raw_summary = content_encoded.get_text()
            elif description: raw_summary = description.get_text()
            elif summary: raw_summary = summary.get_text()
            elif content: raw_summary = content.get_text()
            
            soup_desc = BeautifulSoup(raw_summary, 'html.parser')
            _summary_text = soup_desc.get_text(separator=' ', strip=True)
            clean_summary = (_summary_text[:300] + "...") if len(_summary_text) > 300 else _summary_text
            
            # --- Heat ---
            heat = ""
            comments = entry.find('slash:comments')
            if comments:
                heat = f"{comments.get_text(strip=True)} comments"
            
            items.append({
                "source": source_name,
                "title": title,
                "url": link,
                "time": time_str,
                "heat": heat,
                "summary": clean_summary
            })
            if len(items) >= limit: break
            
        return items
    except Exception as e:
        if error_callback:
            error_callback(source_name, e)
        print(f"Content Parse failed: {e}", file=sys.stderr)
        return []

def fetch_rss_feed(url, source_name, limit=5, error_callback=None):
    """
    Robust RSS/Atom fetcher using BeautifulSoup.
    Handles various feed formats (RSS 2.0, Atom, etc.)
    """
    try:
        if MISSING_DEPENDENCY_ERROR is not None:
            raise RuntimeError(f"Missing dependency: {MISSING_DEPENDENCY_ERROR.name}")
        # User-Agent is critical
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }

        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or 'utf-8'
                return parse_rss_content(response.content, source_name, limit, error_callback=error_callback)
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 + attempt)

        raise last_error if last_error is not None else RuntimeError("Unknown RSS fetch failure")

    except Exception as e:
        if error_callback:
            error_callback(source_name, e)
        print(f"RSS Fetch failed for {url}: {e}", file=sys.stderr)
        return []
