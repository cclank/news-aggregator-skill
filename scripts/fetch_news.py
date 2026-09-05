import argparse
import json
import requests
from bs4 import BeautifulSoup
import sys
import io
import time
import re
import concurrent.futures
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import subprocess

# Windows console defaults to cp936/GBK; force UTF-8 so Chinese JSON output isn't mangled.
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Headers for scraping to avoid basic bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

from bs4 import XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def filter_by_hours(items, hours=24):
    """Keep only items published within the last N hours.
    Items whose time cannot be parsed are kept (fail-open)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = []
    for item in items:
        t = item.get('time', '')
        try:
            pub = parsedate_to_datetime(str(t))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub >= cutoff:
                result.append(item)
        except Exception:
            result.append(item)  # unparseable → keep
    return result


def filter_items(items, keyword=None):
    if not keyword:
        return items
    keywords = [k.strip() for k in keyword.split(',') if k.strip()]
    pattern = '|'.join([r'\b' + re.escape(k) + r'\b' for k in keywords])
    regex = r'(?i)(' + pattern + r')'
    return [item for item in items if re.search(regex, item['title'])]

def fetch_url_content(url):
    """
    Fetches the content of a URL and extracts text from paragraphs.
    Truncates to 3000 characters.
    """
    if not url or not url.startswith('http'):
        return ""
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
         # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        # Simple cleanup
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text[:3000]
    except Exception:
        return ""

def enrich_items_with_content(items, max_workers=10):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(fetch_url_content, item['url']): item for item in items}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                content = future.result()
                if content:
                    item['content'] = content
            except Exception:
                item['content'] = ""
    return items

# --- Source Fetchers ---

def fetch_hackernews(limit=5, keyword=None):
    if keyword:
        # Use Algolia API for keyword search (Much better recall for specific topics like "AI")
        try:
            # 24h window
            timestamp_24h = int(time.time() - 24 * 3600)
            
            # Query builder strategy
            raw_keywords = [k.strip() for k in keyword.split(',')]
            
            # 1. Try Complex Query with Quoted Phrases
            # "Github Copilot" needs quotes in Algolia search string if mixed with OR
            quoted_keywords = [f'"{k}"' if ' ' in k else k for k in raw_keywords]
            query_str = " OR ".join(quoted_keywords)
            
            api_url = f"http://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=created_at_i>{timestamp_24h}&hitsPerPage={limit*2}&query={requests.utils.quote(query_str)}"
            
            data = requests.get(api_url, timeout=10).json()
            hits = data.get('hits', [])
            
            # 2. Level 2 Fallback: If 0 results, try just the first keyword (usually the most broad, e.g. "AI")
            if not hits and raw_keywords:
                simple_query = raw_keywords[0]
                api_url_simple = f"http://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=created_at_i>{timestamp_24h}&hitsPerPage={limit*2}&query={requests.utils.quote(simple_query)}"
                data = requests.get(api_url_simple, timeout=10).json()
                hits = data.get('hits', [])

            items = []
            for hit in hits:
                items.append({
                    "source": "Hacker News",
                    "title": hit.get('title'),
                    "url": hit.get('url') or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    "hn_url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    "heat": f"{hit.get('points', 0)} points",
                    "time": "Today" # Algolia return is recent by definition of filter
                })
            
            # Only return if we actually found something. 
            # If we found nothing after all attempts, we might want to fall back to scraping frontpage 
            # but frontpage is unlikely to have keyword matches if deep search failed. 
            # However, returning [] is better than hallucinating.
            return items[:limit]
            
        except Exception as e:
            print(f"HN Algolia failed: {e}", file=sys.stderr)
            # Fallback to scraping logic below if API completely errors out (e.g. network/timeout)
            pass

    # Fallback / Default: Scrape Front Page
    base_url = "https://news.ycombinator.com"
    news_items = []
    page = 1
    max_pages = 5
    
    while len(news_items) < limit and page <= max_pages:
        url = f"{base_url}/news?p={page}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200: break
        except: break

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('.athing')
        if not rows: break
        
        page_items = []
        for row in rows:
            try:
                id_ = row.get('id')
                title_line = row.select_one('.titleline a')
                if not title_line: continue
                title = title_line.get_text()
                link = title_line.get('href')
                
                # Metadata
                score_span = soup.select_one(f'#score_{id_}')
                score = score_span.get_text() if score_span else "0 points"
                
                # Age/Time
                age_span = soup.select_one(f'.age a[href="item?id={id_}"]')
                time_str = age_span.get_text() if age_span else ""
                
                if link and link.startswith('item?id='): link = f"{base_url}/{link}"
                
                page_items.append({
                    "source": "Hacker News", 
                    "title": title, 
                    "url": link, 
                    "hn_url": f"{base_url}/item?id={id_}",
                    "heat": score,
                    "time": time_str
                })
            except: continue
        
        news_items.extend(filter_items(page_items, keyword))
        if len(news_items) >= limit: break
        page += 1
        time.sleep(0.5)

    return news_items[:limit]

def fetch_weibo(limit=5, keyword=None):
    # Use the PC Ajax API which returns JSON directly and is less rate-limited than scraping s.weibo.com
    url = "https://weibo.com/ajax/side/hotSearch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://weibo.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        items = data.get('data', {}).get('realtime', [])
        
        all_items = []
        for item in items:
            # key 'note' is usually the title, sometimes 'word'
            title = item.get('note', '') or item.get('word', '')
            if not title: continue
            
            # 'num' is the heat value
            heat = item.get('num', 0)
            
            # Construct URL (usually search query)
            # Web UI uses: https://s.weibo.com/weibo?q=%23TITLE%23&Refer=top
            full_url = f"https://s.weibo.com/weibo?q={requests.utils.quote(title)}&Refer=top"
            
            all_items.append({
                "source": "Weibo Hot Search", 
                "title": title, 
                "url": full_url, 
                "heat": f"{heat}",
                "time": "Real-time"
            })
            
        return filter_items(all_items, keyword)[:limit]
    except Exception: 
        return []

def fetch_github(limit=5, keyword=None):
    if keyword:
         # Use GitHub Search for keywords
         query = f"{keyword.split(',')[0]} sort:updated" # Use first kw as primary
         url = f"https://github.com/search?q={requests.utils.quote(query)}&type=repositories"
         # Note: GitHub Search page is hard to scrape due to login requirements (often).
         # Fallback strat: Topics? "https://github.com/topics/{kw}?o=desc&s=updated"
         topic_url = f"https://github.com/topics/{keyword.split(',')[0].strip()}?o=desc&s=updated"
         try:
             response = requests.get(topic_url, headers=HEADERS, timeout=10)
             if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                items = []
                for article in soup.select('article.border'):
                     # Topic page structure changes often, but let's try generic selector
                     h3 = article.select_one('h3 a') 
                     # Actually standard topic page: <h3 class="f3"><a href="/user/repo">...
                     if not h3: continue
                     repo_link = h3['href'] # /user/repo
                     title = repo_link.strip('/')
                     link = "https://github.com" + repo_link
                     
                     desc = ""
                     desc_div = article.select_one('.color-fg-muted')
                     if desc_div: desc = desc_div.get_text(strip=True)
                     
                     items.append({
                        "source": "GitHub Trending", 
                        "title": f"{title} - {desc}", 
                        "url": link,
                        "heat": "Topic Match",
                        "time": "Updated recently"
                     })
                if items: return items[:limit]
         except: pass

    # Default Trending
    try:
        response = requests.get("https://github.com/trending", headers=HEADERS, timeout=10)
    except: return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    items = []
    for article in soup.select('article.Box-row'):
        try:
            h2 = article.select_one('h2 a')
            if not h2: continue
            title = h2.get_text(strip=True).replace('\n', '').replace(' ', '')
            link = "https://github.com" + h2['href']
            
            desc = article.select_one('p')
            desc_text = desc.get_text(strip=True) if desc else ""
            
            # Stars (Heat)
            # usually the first 'Link--muted' with a SVG star
            stars_tag = article.select_one('a[href$="/stargazers"]')
            stars = stars_tag.get_text(strip=True) if stars_tag else ""
            
            items.append({
                "source": "GitHub Trending", 
                "title": f"{title} - {desc_text}", 
                "url": link,
                "heat": f"{stars} stars",
                "time": "Today"
            })
        except: continue
    return filter_items(items, keyword)[:limit]

def fetch_36kr(limit=5, keyword=None):
    try:
        response = requests.get("https://36kr.com/newsflashes", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = []
        for item in soup.select('.newsflash-item'):
            title = item.select_one('.item-title').get_text(strip=True)
            href = item.select_one('.item-title')['href']
            time_tag = item.select_one('.time')
            time_str = time_tag.get_text(strip=True) if time_tag else ""
            
            items.append({
                "source": "36Kr", 
                "title": title, 
                "url": f"https://36kr.com{href}" if not href.startswith('http') else href,
                "time": time_str,
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except: return []

def fetch_v2ex(limit=5, keyword=None):
    try:
        # Hot topics json
        data = requests.get("https://www.v2ex.com/api/topics/hot.json", headers=HEADERS, timeout=10).json()
        items = []
        for t in data:
            # V2EX API fields: created, replies (heat)
            replies = t.get('replies', 0)
            created = t.get('created', 0)
            # convert epoch to readable if possible, simpler to just leave as is or basic format
            # Let's keep it simple
            items.append({
                "source": "V2EX", 
                "title": t['title'], 
                "url": t['url'],
                "heat": f"{replies} replies",
                "time": "Hot"
            })
        return filter_items(items, keyword)[:limit]
    except: return []

def fetch_tencent(limit=5, keyword=None):
    try:
        url = "https://i.news.qq.com/web_backend/v2/getTagInfo?tagId=aEWqxLtdgmQ%3D"
        data = requests.get(url, headers={"Referer": "https://news.qq.com/"}, timeout=10).json()
        items = []
        for news in data['data']['tabs'][0]['articleList']:
            items.append({
                "source": "Tencent News", 
                "title": news['title'], 
                "url": news.get('url') or news.get('link_info', {}).get('url'),
                "time": news.get('pub_time', '') or news.get('publish_time', '')
            })
        return filter_items(items, keyword)[:limit]
    except: return []

def fetch_wallstreetcn(limit=5, keyword=None):
    try:
        url = "https://api-one.wallstcn.com/apiv1/content/information-flow?channel=global-channel&accept=article&limit=30"
        data = requests.get(url, timeout=10).json()
        items = []
        for item in data['data']['items']:
            res = item.get('resource')
            if res and (res.get('title') or res.get('content_short')):
                 ts = res.get('display_time', 0)
                 time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else ""
                 items.append({
                     "source": "Wall Street CN", 
                     "title": res.get('title') or res.get('content_short'), 
                     "url": res.get('uri'),
                     "time": time_str
                 })
        return filter_items(items, keyword)[:limit]
    except: return []

def fetch_producthunt(limit=5, keyword=None):
    try:
        # Using RSS for speed and reliability without API key
        response = requests.get("https://www.producthunt.com/feed", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = []
        for entry in soup.find_all(['item', 'entry']):
            title = entry.find('title').get_text(strip=True)
            link_tag = entry.find('link')
            url = link_tag.get('href') or link_tag.get_text(strip=True) if link_tag else ""
            
            pubBox = entry.find('pubDate') or entry.find('published')
            pub = pubBox.get_text(strip=True) if pubBox else ""
            
            items.append({
                "source": "Product Hunt", 
                "title": title, 
                "url": url,
                "time": pub,
                "heat": "Top Product" # RSS implies top rank
            })
        return filter_items(items, keyword)[:limit]
    except: return []

# --- New Fetchers (RSS/API) ---

from rss_parser import fetch_rss_feed

# fetch_tldr_ai removed: all known feed URLs (feed.tldr.tech/ai, tldr.tech/ai/rss) return 404.

def fetch_huggingface_papers(limit=5, keyword=None):
    items = []
    # User requested a "Good Solution" without fallback.
    # We use Playwright (which is installed) to bypass the SSL/fingerprinting connection issues.
    # Logic extracted to scripts/fetch_hf_papers_playwright.py for reusability
    
    try:
        import subprocess
        import sys
        import os
        
        # Locate the standalone script
        script_path = os.path.join(os.path.dirname(__file__), "fetch_hf_papers_playwright.py")
        
        # Run the playwright script in a subprocess
        cmd = [sys.executable, script_path, "--limit", str(limit)]
        # Increase timeout for detail fetch (10 pages * 5s = 50s + startup)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            for paper in data:
                items.append({
                    "source": "HF Papers",
                    "title": paper['title'],
                    "url": paper['url'],
                    "github": paper.get('github', ''),
                    "heat": paper.get('heat', ''),
                    "time": datetime.now().strftime("%Y-%m-%d"), # Daily Papers are today's papers
                    "summary": paper.get('summary', '')
                })
        else:
             print(f"HF Playwright Failed: {result.stderr}", file=sys.stderr)
             
    except Exception as e:
        print(f"HF Playwright Exception: {e}", file=sys.stderr)
            
    return filter_items(items[:limit], keyword)


def fetch_latentspace_ainews(limit=5, keyword=None):
    """Fetch AINews daily roundups from Latent Space Substack RSS.
    Filters for posts with [AINews] title prefix, separating them from podcast episodes."""
    items = []
    try:
        response = requests.get("https://www.latent.space/feed", headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for entry in soup.find_all('item'):
            title_tag = entry.find('title')
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            
            # Filter: only AINews posts (title starts with [AINews])
            if not title.startswith('[AINews]'):
                continue
            
            # Extract link from guid (Substack RSS has link text empty, guid has the URL)
            guid_tag = entry.find('guid')
            link = guid_tag.get_text(strip=True) if guid_tag else ""
            
            # Fallback: try link tag
            if not link:
                link_tag = entry.find('link')
                if link_tag:
                    link = link_tag.get_text(strip=True) or (link_tag.get('href') or '')
            
            # Publication date
            pub_tag = entry.find('pubdate') or entry.find('published')
            pub_date = pub_tag.get_text(strip=True) if pub_tag else ""
            # Simplify date if possible
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_date)
                pub_date = dt.strftime('%Y-%m-%d')
            except Exception:
                pass
            
            # Content snippet from description
            desc_tag = entry.find('description')
            content = ""
            if desc_tag:
                desc_html = desc_tag.get_text(strip=True)
                desc_soup = BeautifulSoup(desc_html, 'html.parser')
                content = desc_soup.get_text(separator=' ', strip=True)[:2000]
            
            items.append({
                "source": "Latent Space AINews",
                "title": title,
                "url": link,
                "time": pub_date,
                "heat": "Daily Roundup",
                "content": content
            })
    except Exception as e:
        print(f"Latent Space AINews fetch error: {e}", file=sys.stderr)
    
    return filter_items(items[:limit], keyword)


# --- Extended Sources (v2): Lobsters / Dev.to / arXiv / Papers with Code / 少数派 / 即刻 / User OPML ---

def fetch_lobsters(limit=5, keyword=None):
    """Lobsters hottest stories via official JSON API."""
    items = []
    try:
        data = requests.get("https://lobste.rs/hottest.json", headers=HEADERS, timeout=10).json()
        for story in data:
            tags = ",".join(story.get('tags', []))
            items.append({
                "source": "Lobsters",
                "title": story.get('title', ''),
                "url": story.get('url') or story.get('short_id_url') or story.get('comments_url', ''),
                "comments_url": story.get('comments_url', ''),
                "heat": f"{story.get('score', 0)} points",
                "time": story.get('created_at', '')[:10] if story.get('created_at') else '',
                "tags": tags,
            })
    except Exception as e:
        print(f"Lobsters fetch error: {e}", file=sys.stderr)
    return filter_items(items[:limit], keyword)


def fetch_devto(limit=5, keyword=None):
    """Dev.to top articles of the past 24h via official JSON API."""
    items = []
    try:
        url = "https://dev.to/api/articles?top=1&per_page=30"
        data = requests.get(url, headers=HEADERS, timeout=10).json()
        for art in data:
            tag_list = art.get('tag_list', [])
            tags = ",".join(tag_list) if isinstance(tag_list, list) else str(tag_list)
            items.append({
                "source": "Dev.to",
                "title": art.get('title', ''),
                "url": art.get('url', ''),
                "heat": f"{art.get('positive_reactions_count', 0)} reactions",
                "time": (art.get('published_at') or '')[:10],
                "summary": art.get('description', ''),
                "tags": tags,
            })
    except Exception as e:
        print(f"Dev.to fetch error: {e}", file=sys.stderr)
    return filter_items(items[:limit], keyword)


def fetch_sspai(limit=5, keyword=None):
    """少数派 latest articles via RSS."""
    return filter_items(fetch_rss_feed("https://sspai.com/feed", "少数派", limit * 2)[:limit], keyword)


# NOTE: Papers with Code (paperswithcode.com) was acquired/merged by Hugging Face
# and now 302-redirects to huggingface.co/papers/trending. Duplicates `huggingface` source.
# Removed from v2 sources. Use --source huggingface for trending papers.


def fetch_arxiv(limit=5, keyword=None, categories=None):
    """arXiv latest submissions in given CS categories via official Atom API.
    arXiv 接口偶尔较慢，最多重试 3 次（timeout=45s，退避 2s/4s）。"""
    cats = categories or ['cs.AI', 'cs.CL', 'cs.LG']
    cat_query = '+OR+'.join(f'cat:{c}' for c in cats)
    url = (
        f"http://export.arxiv.org/api/query"
        f"?search_query={cat_query}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={limit * 2}"
    )
    items = []
    from rss_parser import parse_rss_content
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=45)
            response.encoding = response.apparent_encoding or 'utf-8'
            items = parse_rss_content(response.content, "arXiv", limit * 2)
            if items:
                break
        except Exception as e:
            print(f"arXiv attempt {attempt + 1}/3 error: {e}", file=sys.stderr)
        if attempt < 2:
            time.sleep(2 * (attempt + 1))  # 2s, 4s
    return filter_items(items[:limit], keyword)


def fetch_infoq_cn(limit=5, keyword=None):
    """InfoQ 中文站最新文章 via RSS。"""
    return filter_items(fetch_rss_feed("https://www.infoq.cn/feed.xml", "InfoQ 中文", limit * 2)[:limit], keyword)


def fetch_aihot(limit=15, keyword=None):
    """AIHOT (aihot.virxact.com) AI 精选聚合，跨源中文编辑稿，日更 ~50 条。
    默认拉最近 24h 内容（日更源，50 条/天，取最多 limit 条）。"""
    raw = fetch_rss_feed("https://aihot.virxact.com/rss", "AIHOT", max(limit * 4, 50))
    items = filter_by_hours(raw, hours=24)
    return filter_items(items[:limit], keyword)


def fetch_tldr_ai(limit=3, keyword=None):
    """TLDR AI 英文每日 AI 摘要，5-10 主题/期。
    默认拉最近 48h（日刊时间戳为午夜 UTC，48h 确保任意时段都能拿到最新 1-2 期）。"""
    raw = fetch_rss_feed("https://tldr.tech/api/rss/ai", "TLDR AI", limit * 4)
    items = filter_by_hours(raw, hours=48)
    return filter_items(items[:limit], keyword)


def fetch_import_ai(limit=2, keyword=None):
    """Import AI by Jack Clark（前 OpenAI/Anthropic 联创）周更深度评论。
    默认拉最近 7 天（周刊，1 条 = 1 期 = 1 周），通常返回最新 1 期。"""
    raw = fetch_rss_feed("https://importai.substack.com/feed", "Import AI", limit * 4)
    items = filter_by_hours(raw, hours=168)  # 7 days
    return filter_items(items[:limit], keyword)


INTERNATIONAL_NEWS_SOURCES = [
    ("BBC Top News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Chinese", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("France 24", "http://www.france24.com/en/rss"),
]

REUTERS_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q=site%3Areuters.com%20when%3A1d&hl=en-US&gl=US&ceid=US%3Aen"
)

INTERNATIONAL_NEWS_MAX_AGE_HOURS = 24


def fetch_recent_rss_feed(url, source_name, limit=10, keyword=None, hours=INTERNATIONAL_NEWS_MAX_AGE_HOURS):
    """Fetch an RSS feed and keep only items from the recent time window."""
    raw = fetch_rss_feed(url, source_name, max(limit * 4, 30))
    items = filter_by_hours(raw, hours=hours)
    return filter_items(items, keyword)[:limit]


def create_recent_rss_fetcher(url, name, hours=INTERNATIONAL_NEWS_MAX_AGE_HOURS):
    def fetcher(limit=5, keyword=None):
        return fetch_recent_rss_feed(url, name, limit, keyword, hours)
    return fetcher


def fetch_reuters(limit=10, keyword=None):
    """Reuters public fallback via Google News RSS.
    Reuters.com no longer exposes a reliable unauthenticated public RSS feed."""
    items = fetch_rss_feed(
        REUTERS_GOOGLE_NEWS_RSS,
        "Reuters (Google News fallback)",
        max(limit * 4, 30),
    )
    items = filter_by_hours(items, hours=INTERNATIONAL_NEWS_MAX_AGE_HOURS)
    for item in items:
        title = item.get('title', '')
        if title.endswith(' - Reuters'):
            item['title'] = title[:-10]
        item['fallback'] = "Google News RSS search for site:reuters.com"
    return filter_items(items, keyword)[:limit]


def fetch_international(limit=15, keyword=None):
    """Aggregate official international RSS feeds plus Reuters fallback."""
    per_source = max(2, min(5, limit // 3))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        tasks = [
            (name, executor.submit(fetch_recent_rss_feed, url, name, per_source, keyword))
            for name, url in INTERNATIONAL_NEWS_SOURCES
        ]
        tasks.append(("Reuters", executor.submit(fetch_reuters, per_source, keyword)))

        item_groups = []
        for name, future in tasks:
            try:
                items = future.result()
                if items:
                    item_groups.append(items)
            except Exception as e:
                print(f"International fetch error for {name}: {e}", file=sys.stderr)

    merged = []
    max_group_len = max((len(group) for group in item_groups), default=0)
    for index in range(max_group_len):
        for group in item_groups:
            if index < len(group):
                merged.append(group[index])
            if len(merged) >= limit:
                return merged
    return merged


def fetch_user_feeds(limit=5, keyword=None):
    """Fetch user-defined RSS feeds from an OPML file.
    Looks at ~/.config/news-aggregator/user_sources.opml first,
    then <skill_root>/user_sources.opml."""
    try:
        # Add scripts/ to path for direct import
        sys.path.insert(0, os.path.dirname(__file__))
        from fetch_user_feeds import find_opml_file, parse_opml, fetch_all_feeds
        opml_path = find_opml_file()
        if not opml_path:
            print("No OPML configured. See user_sources.opml.example", file=sys.stderr)
            return []
        feeds = parse_opml(opml_path)
        if not feeds:
            return []
        items = fetch_all_feeds(feeds, limit_per_feed=3)
        return filter_items(items[:limit], keyword)
    except Exception as e:
        print(f"User feeds error: {e}", file=sys.stderr)
        return []


# --- Source Definitions (Global for Access) ---

AI_NEWSLETTER_SOURCES = [
    # Bens Bites is protected by Cloudflare -> Use Playwright
    ("Ben's Bites", "https://www.bensbites.com/feed"), 
    ("Interconnects", "https://www.interconnects.ai/feed"),  # Fixed: needs www.
    ("One Useful Thing", "https://www.oneusefulthing.org/feed"), 
    # Removed: The Rundown (beehiiv feed 404), The Neuron (403 Forbidden)
    ("ChinAI", "https://chinai.substack.com/feed"),
    ("Memia", "https://memia.substack.com/feed"),
    ("AI to ROI", "https://ai2roi.substack.com/feed"),
    ("AI Weekly", "https://aiweekly.co/feed"),
    ("KDnuggets", "https://www.kdnuggets.com/feed"),
]

# ... (rest of sources)

def fetch_rss_with_playwright(url, source_name, limit=5):
    """Fallback fetcher using Playwright to bypass Cloudflare"""
    try:
        # Special handling for Ben's Bites which uses custom Homepage Scraper
        if "Ben's Bites" in source_name:
             script_path = os.path.join(os.path.dirname(__file__), "fetch_bensbites.py")
             # No arguments needed, script hardcodes URL
             cmd = [sys.executable, script_path]
             
             
             result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
             
             if result.returncode == 0:
                 try:
                    data = json.loads(result.stdout)
                    if not data: raise ValueError("Empty JSON")
                    return data
                 except Exception:
                    # Fallback for Ben's Bites if parsing fails
                    return [{
                        "source": "Ben's Bites",
                        "title": "Ben's Bites (Visit Site)",
                        "url": "https://bensbites.beehiiv.com/",
                        "time": "Today",
                        "summary": "Auto-fetch failed. Please verify on site.",
                    }]
             else:
                 return [{
                        "source": "Ben's Bites",
                        "title": "Ben's Bites (Check Site)",
                        "url": "https://bensbites.beehiiv.com/",
                        "time": "Today",
                        "summary": "Fetch process failed.",
                    }]

        # User generic Playwright script for all OTHER protected feeds
        
        if result.returncode == 0:
            from rss_parser import parse_rss_content
            # Result stdout should be the HTML/XML content
            return parse_rss_content(result.stdout, source_name, limit)
        else:
            print(f"Playwright fetch failed for {source_name}: {result.stderr}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"Playwright exception for {source_name}: {e}", file=sys.stderr)
        return []


PODCAST_SOURCES = [
    ("Lex Fridman", "https://lexfridman.com/feed/podcast"),
    # Removed: Cognitive Rev (megaphone.fm feed 404)
    ("80000 Hours", "https://feeds.transistor.fm/80-000-hours-podcast"),
    ("Latent Space", "https://latent.space/feed"),
]

ESSAY_SOURCES = [
    ("Wait But Why", "https://waitbutwhy.com/feed"),
    ("James Clear", "https://jamesclear.com/feed"),
    ("Farnam Street", "https://fs.blog/feed"),
    ("Paul Graham", "http://www.aaronsw.com/2002/feeds/pgessays.rss"), 
    ("Scott Young", "https://www.scotthyoung.com/blog/feed/"),
    ("Dan Koe", "https://thedankoe.com/feed/"),
]

def fetch_ai_newsletters(limit=5, keyword=None):
    """Aggregate Fetcher for AI Newsletters"""
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss_feed, url, name, 3): name for name, url in AI_NEWSLETTER_SOURCES}
        for future in concurrent.futures.as_completed(futures):
            all_items.extend(future.result())
    return filter_items(all_items, keyword)[:limit]

def fetch_podcasts(limit=5, keyword=None):
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss_feed, url, name, 3): name for name, url in PODCAST_SOURCES}
        for future in concurrent.futures.as_completed(futures):
            all_items.extend(future.result())
    return filter_items(all_items, keyword)[:limit]

def fetch_essays(limit=5, keyword=None):
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss_feed, url, name, 3): name for name, url in ESSAY_SOURCES}
        for future in concurrent.futures.as_completed(futures):
            all_items.extend(future.result())
    return filter_items(all_items, keyword)[:limit]

def create_single_rss_fetcher(url, name):
    def fetcher(limit=5, keyword=None):
        return filter_items(fetch_rss_feed(url, name, limit), keyword)[:limit]
    return fetcher


def save_report(data, source_name, out_dir):
    """
    Saves JSON and generates a simple Markdown report.
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    # Sanitize source name for filename
    safe_name = "".join([c if c.isalnum() else "_" for c in source_name]).lower()
    timestamp = datetime.now().strftime("%H%M")
    
    # 1. Save JSON
    json_path = os.path.join(out_dir, f"{safe_name}_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return json_path

def main():
    parser = argparse.ArgumentParser()
    sources_map = {
        'hackernews': fetch_hackernews, 'weibo': fetch_weibo, 'github': fetch_github,
        '36kr': fetch_36kr, 'v2ex': fetch_v2ex, 'tencent': fetch_tencent,
        'wallstreetcn': fetch_wallstreetcn, 'producthunt': fetch_producthunt,
        # Aggregates
        'huggingface': fetch_huggingface_papers,
        'ai_newsletters': fetch_ai_newsletters, 'podcasts': fetch_podcasts,
        'essays': fetch_essays,
        # Standalone AI Sources
        'latentspace_ainews': fetch_latentspace_ainews,
        # Extended (v2): tech community / academic / Chinese deep-content / user OPML
        'lobsters': fetch_lobsters,
        'devto': fetch_devto,
        'sspai': fetch_sspai,
        'infoq_cn': fetch_infoq_cn,
        'arxiv': fetch_arxiv,
        # Curated AI aggregators (v3): one feed = many original sources, pre-curated
        'aihot': fetch_aihot,
        'tldr_ai': fetch_tldr_ai,
        'import_ai': fetch_import_ai,
        # International news (official RSS where available; Reuters uses a marked fallback)
        'international': fetch_international,
        'bbc_top': create_recent_rss_fetcher("https://feeds.bbci.co.uk/news/rss.xml", "BBC Top News"),
        'bbc_world': create_recent_rss_fetcher("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
        'bbc_chinese': create_recent_rss_fetcher("https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", "BBC Chinese"),
        'guardian_world': create_recent_rss_fetcher("https://www.theguardian.com/world/rss", "The Guardian World"),
        'aljazeera': create_recent_rss_fetcher("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera"),
        'france24': create_recent_rss_fetcher("http://www.france24.com/en/rss", "France 24"),
        'reuters': fetch_reuters,
        'user': fetch_user_feeds,
    }

    # Dynamic Registration of Sub-sources
    # AI Newsletters
    for name, url in AI_NEWSLETTER_SOURCES:
        key = name.lower().replace(' ', '').replace("'", "")
        # Check if this source needs Playwright
        if "Ben's Bites" in name or "The Rundown" in name:
             sources_map[key] = lambda limit=10, k=None, u=url, n=name: filter_items(fetch_rss_with_playwright(u, n, limit), k)[:limit]
        else:
             sources_map[key] = create_single_rss_fetcher(url, name)
        
    # Podcasts
    for name, url in PODCAST_SOURCES:
        key = name.lower().replace(' ', '')
        sources_map[key] = create_single_rss_fetcher(url, name)

    # Essays
    for name, url in ESSAY_SOURCES:
        key = name.lower().replace(' ', '')
        sources_map[key] = create_single_rss_fetcher(url, name)
    
    parser.add_argument('--source', default='all', help='Source(s) to fetch from (comma-separated). Now supports sub-sources like "chinai", "paulgraham"')
    parser.add_argument('--limit', type=int, default=10, help='Limit per source. Default 10')
    parser.add_argument('--keyword', help='Comma-sep keyword filter')
    parser.add_argument('--deep', action='store_true', help='Download article content for detailed summarization')
    parser.add_argument('--save', action='store_true', help='Save output to reports directory (JSON + MD)')
    parser.add_argument('--no-save', action='store_true', dest='no_save', help='Skip saving JSON files to disk (only output to stdout)')
    parser.add_argument('--outdir', help='Custom output directory for saved reports')
    parser.add_argument('--list-sources', action='store_true', help='List all available source keys')
    
    args = parser.parse_args()

    if args.list_sources:
        print(f"{'Source Key':<20} | {'Source Name'}")
        print("-" * 40)
        for key in sorted(sources_map.keys()):
            print(f"{key:<20}")
        return
    
    to_run = []
    if args.source == 'all':
        to_run = list(sources_map.values())
    else:
        requested_sources = [s.strip() for s in args.source.split(',')]
        for s in requested_sources:
            if s in sources_map: to_run.append(sources_map[s])
            
    results = []
    
    def run_fetchers(fetchers, limit, kw):
        res = []
        for func in fetchers:
            try:
                res.extend(func(limit, kw))
            except: pass
        return res

    # Primary Fetch
    results = run_fetchers(to_run, args.limit, args.keyword)
        
    # Smart Fill Logic (Only if keyword is used and results are sparse)
    MIN_ITEMS = 5
    if args.keyword and len(results) < MIN_ITEMS:
        sys.stderr.write(f"Smart Fill triggered: Found {len(results)} items, filling gaps...\n")
        
        # Secondary Fetch (Broad, no keyword)
        # We fetch enough to potentially fill the gap, limit=MIN_ITEMS is a safe bet for each source
        fill_limit = MIN_ITEMS 
        fill_results = run_fetchers(to_run, limit=fill_limit, kw=None)
        
        # Deduplicate and Append
        existing_urls = {item.get('url') for item in results}
        existing_titles = {item.get('title') for item in results}
        
        for item in fill_results:
            if len(results) >= MIN_ITEMS:
                break
                
            u = item.get('url')
            t = item.get('title')
            
            if u not in existing_urls and t not in existing_titles:
                # Mark as smart fill
                item['smart_fill'] = True
                
                # Add warning to time field as per SKILL.md
                if 'time' in item:
                    item['time'] = f"⚠️ {item['time']}"
                
                results.append(item)
                existing_urls.add(u)
                existing_titles.add(t)

    if args.deep and results:
        sys.stderr.write(f"Deep fetching content for {len(results)} items...\n")
        results = enrich_items_with_content(results)
        
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    # Save Report if requested or if running a single source (implicit convenience)
    # Skip saving when --no-save is set (agent reads from stdout)
    if not getattr(args, 'no_save', False) and (args.save or args.source != 'all'):
        if args.outdir:
            out_dir = args.outdir
        else:
            today = datetime.now().strftime('%Y-%m-%d')
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports', today)
            
        md_file = save_report(results, args.source, out_dir)
        sys.stderr.write(f"\n[Saved] Raw Data: {md_file} (Agent to process)\n")

if __name__ == "__main__":
    main()
