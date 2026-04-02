import argparse
import json
import sys
import time
import re
import concurrent.futures
import os
import threading
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import subprocess
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MISSING_DEPENDENCY_ERROR = None
try:
    import requests
    from bs4 import BeautifulSoup
    from bs4 import XMLParsedAsHTMLWarning
except ModuleNotFoundError as exc:
    MISSING_DEPENDENCY_ERROR = exc
    requests = None
    BeautifulSoup = None

# Headers for scraping to avoid basic bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

if MISSING_DEPENDENCY_ERROR is None:
    import warnings
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

EXIT_SUCCESS = 0
EXIT_EMPTY = 10
EXIT_PARTIAL = 20
EXIT_CRITICAL_FAILURE = 50
EXIT_TIMEOUT_OR_ENV = 60

LOCAL_TZ = datetime.now().astimezone().tzinfo
SOURCE_ERRORS = []
SOURCE_ERRORS_LOCK = threading.Lock()

SOURCE_DISPLAY_NAMES = {
    "fetch_hackernews": "Hacker News",
    "fetch_hackernews_api": "Hacker News API",
    "fetch_weibo": "Weibo Hot Search",
    "fetch_github": "GitHub Trending",
    "fetch_36kr": "36Kr",
    "fetch_v2ex": "V2EX",
    "fetch_tencent": "Tencent News",
    "fetch_wallstreetcn": "Wall Street CN",
    "fetch_producthunt": "Product Hunt",
    "fetch_huggingface_papers": "HF Papers",
    "fetch_ai_newsletters": "AI Newsletters",
    "fetch_podcasts": "Podcasts",
    "fetch_essays": "Essays",
    "fetch_latentspace_ainews": "Latent Space AINews",
    "fetch_tavily_search": "Tavily Search",
    "fetch_ddgs_text": "DuckDuckGo Search",
    "fetch_ddgs_news": "DDGS News",
}

HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"


def now_utc():
    return datetime.now(timezone.utc)


def to_iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_error(exc):
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout"
    if MISSING_DEPENDENCY_ERROR and isinstance(exc, type(MISSING_DEPENDENCY_ERROR)):
        return "env"
    if requests is not None and isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, (ModuleNotFoundError, ImportError, FileNotFoundError, OSError)):
        return "env"
    return "error"


def record_source_error(source_name, error, code=None, context=None):
    detail = {
        "source": source_name,
        "error": str(error),
        "code": code or classify_error(error),
    }
    if context:
        detail.update(context)
    with SOURCE_ERRORS_LOCK:
        SOURCE_ERRORS.append(detail)
    print(f"[source-error] {source_name}: {detail['error']}", file=sys.stderr)


def clear_source_errors():
    with SOURCE_ERRORS_LOCK:
        SOURCE_ERRORS.clear()


def get_recorded_source_errors():
    with SOURCE_ERRORS_LOCK:
        return [dict(item) for item in SOURCE_ERRORS]


def dedupe_failed_sources(items):
    seen = set()
    unique = []
    for item in items:
        key = (
            item.get("section"),
            item.get("source_key"),
            item.get("source"),
            item.get("error"),
            item.get("code"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def ensure_runtime_available():
    if MISSING_DEPENDENCY_ERROR is not None:
        raise RuntimeError(f"Missing dependency: {MISSING_DEPENDENCY_ERROR.name}")


def source_display_name(func, fallback=None):
    return SOURCE_DISPLAY_NAMES.get(getattr(func, "__name__", ""), fallback or getattr(func, "__name__", "unknown"))


def sanitize_filename(value):
    return "".join([c if c.isalnum() else "_" for c in value]).strip("_").lower() or "output"


def default_health_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "source_health.json")


def load_json_file(path, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def stable_source_id(value):
    return sanitize_filename(str(value or "source"))


def normalize_url(url):
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw or not raw.startswith(("http://", "https://")):
        return raw or None

    try:
        parsed = urlsplit(raw)
    except Exception:
        return raw

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
        if not path:
            path = "/"

    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "referer", "spm"}:
            continue
        query_pairs.append((key, value))
    query = urlencode(query_pairs, doseq=True)

    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized.rstrip("/") if normalized.endswith("/") and path == "/" else normalized


def normalize_title(value):
    if not value:
        return None
    lowered = value.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\s]", "", lowered)
    return lowered.strip() or None


def canonicalize_item(item):
    normalized = dict(item)
    normalized["canonical_url"] = normalize_url(normalized.get("url"))
    return normalized


def dedupe_items(items):
    deduped = []
    seen = set()
    for item in items:
        normalized = canonicalize_item(item)
        dedupe_key = normalized.get("canonical_url") or normalize_title(normalized.get("title"))
        if not dedupe_key:
            deduped.append(normalized)
            continue
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(normalized)
    return deduped


def compact_text(value, limit):
    if not value:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def render_telegram_report(payload):
    lines = []
    label = payload.get("profile") or payload.get("source") or "run"
    lines.append(f"*{label}*")
    lines.append(
        f"状态: {payload.get('status', '')} | 信源 {payload.get('sources_ok', 0)}/{payload.get('sources_total', 0)}"
    )

    failed_sources = payload.get("failed_sources") or []
    if failed_sources:
        failed_names = []
        for item in failed_sources[:5]:
            failed_names.append(item.get("source") or item.get("source_key") or "unknown")
        lines.append(f"失败: {', '.join(failed_names)}")

    items = payload.get("items", [])
    if isinstance(items, dict):
        for section, section_items in items.items():
            if not section_items:
                continue
            lines.append("")
            lines.append(f"*{section}*")
            for index, item in enumerate(section_items[:8], start=1):
                lines.extend(render_markdown_item(index, item, output_format="telegram"))
    else:
        for index, item in enumerate(items[:12], start=1):
            lines.extend(render_markdown_item(index, item, output_format="telegram"))

    if len(lines) == 2 and not failed_sources:
        lines.append("")
        lines.append("无结果")
    return "\n".join(lines).rstrip() + "\n"


def parse_relative_time(raw):
    match = re.match(r"(?i)^\s*(\d+)\s+(minute|minutes|hour|hours|day|days)\s+ago\s*$", raw)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if "minute" in unit:
        delta = timedelta(minutes=amount)
    elif "hour" in unit:
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    return now_utc() - delta


def parse_published_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10**12:
            timestamp = timestamp / 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    raw = str(value).strip()
    if raw.startswith("⚠️"):
        raw = raw.lstrip("⚠️").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in {"today", "real-time", "hot", "updated recently", "recent"}:
        return None

    relative_dt = parse_relative_time(raw)
    if relative_dt is not None:
        return relative_dt

    if re.fullmatch(r"\d{10,13}", raw):
        return parse_published_datetime(int(raw))

    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TZ)
        return parsed
    except Exception:
        pass

    iso_candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TZ)
        return parsed
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    return None


def annotate_item(item, fetched_at):
    normalized = canonicalize_item(item)
    published_raw = normalized.get("published_at_raw", normalized.get("time"))
    published_dt = parse_published_datetime(published_raw)
    normalized["published_at_raw"] = published_raw if published_raw not in ("", None) else None
    normalized["published_at_iso"] = to_iso(published_dt)
    normalized["fetched_at"] = to_iso(fetched_at)
    if published_dt is None:
        normalized["age_minutes"] = None
    else:
        age_seconds = (fetched_at - published_dt.astimezone(timezone.utc)).total_seconds()
        normalized["age_minutes"] = max(int(age_seconds // 60), 0)
    return normalized


def annotate_items(items, fetched_at):
    return [annotate_item(item, fetched_at) for item in items]


def filter_items_by_age(items, max_age_minutes):
    if max_age_minutes is None:
        return items
    filtered = []
    dropped = 0
    for item in items:
        age_minutes = item.get("age_minutes")
        if age_minutes is not None and age_minutes > max_age_minutes:
            dropped += 1
            continue
        filtered.append(item)
    if dropped:
        print(f"Filtered {dropped} item(s) older than {max_age_minutes} minutes", file=sys.stderr)
    return filtered


def apply_deep_enrichment(items, deep_top_n=None, max_workers=10):
    if not items:
        return items
    if deep_top_n is None:
        enrich_items_with_content(items, max_workers=max_workers)
        return items
    limit = max(int(deep_top_n), 0)
    if limit == 0:
        return items
    enrich_items_with_content(items[:limit], max_workers=max_workers)
    return items


def count_items(items):
    if isinstance(items, dict):
        return sum(len(section_items) for section_items in items.values())
    return len(items)


def determine_status_and_exit_code(item_count, failed_sources):
    if item_count > 0:
        if failed_sources:
            return "partial", EXIT_PARTIAL
        return "success", EXIT_SUCCESS
    if failed_sources:
        if any(item.get("code") in {"timeout", "env"} for item in failed_sources):
            return "timeout_or_env", EXIT_TIMEOUT_OR_ENV
        return "critical_failure", EXIT_CRITICAL_FAILURE
    return "empty", EXIT_EMPTY


def write_json_file(payload, path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_markdown_report(payload, output_format="full"):
    if output_format == "telegram":
        return render_telegram_report(payload)

    lines = [
        "# News Aggregator Run",
        "",
        f"- run_at: {payload.get('run_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- sources_total: {payload.get('sources_total', 0)}",
        f"- sources_ok: {payload.get('sources_ok', 0)}",
        f"- sources_failed: {payload.get('sources_failed', 0)}",
    ]
    if "source" in payload:
        lines.append(f"- source: {payload.get('source')}")
    if "profile" in payload:
        lines.append(f"- profile: {payload.get('profile')}")

    failed_sources = payload.get("failed_sources") or []
    if failed_sources:
        lines.extend(["", "## Failed Sources", ""])
        for item in failed_sources:
            section = f" section={item['section']}" if item.get("section") else ""
            lines.append(
                f"- {item.get('source', item.get('source_key', 'unknown'))}{section}: [{item.get('code', 'error')}] {item.get('error', '')}"
            )

    lines.extend(["", "## Items", ""])
    items = payload.get("items", [])
    if isinstance(items, dict):
        for section, section_items in items.items():
            lines.extend([f"### {section}", ""])
            if not section_items:
                lines.append("- No items")
                lines.append("")
                continue
            for index, item in enumerate(section_items, start=1):
                lines.extend(render_markdown_item(index, item, output_format=output_format))
                lines.append("")
    else:
        if not items:
            lines.append("- No items")
        for index, item in enumerate(items, start=1):
            lines.extend(render_markdown_item(index, item, output_format=output_format))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown_item(index, item, output_format="full"):
    if output_format == "telegram":
        title = compact_text(item.get("title") or "(untitled)", 110)
        meta = [item.get("source", "Unknown")]
        if item.get("time"):
            meta.append(str(item["time"]))
        if item.get("heat"):
            meta.append(str(item["heat"]))
        lines = [f"{index}. {title}", f"   {' | '.join(meta)}"]
        summary = compact_text(item.get("summary") or item.get("content"), 180)
        if summary:
            lines.append(f"   {summary}")
        if item.get("url"):
            lines.append(f"   {item['url']}")
        return lines

    title = item.get("title") or "(untitled)"
    url = item.get("url") or ""
    header = f"{index}. **{title}**"
    if url:
        header = f"{index}. [{title}]({url})"
    parts = [header]
    meta = [
        f"source={item.get('source', 'Unknown')}",
        f"time={item.get('time', 'Unknown Time') or 'Unknown Time'}",
    ]
    if item.get("age_minutes") is not None:
        meta.append(f"age_minutes={item['age_minutes']}")
    if item.get("heat"):
        meta.append(f"heat={item['heat']}")
    parts.append(f"   {' | '.join(meta)}")
    if item.get("summary"):
        parts.append(f"   summary={item['summary']}")
    if item.get("content"):
        parts.append(f"   content={item['content'][:280]}")
    if item.get("canonical_url") and item.get("canonical_url") != item.get("url"):
        parts.append(f"   canonical_url={item['canonical_url']}")
    return parts


def write_markdown_file(payload, path, output_format="full"):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_markdown_report(payload, output_format=output_format))


def emit_stdout_summary(payload, exit_code, json_out=None, md_out=None, output_format="full", health_out=None):
    summary = {
        "run_at": payload.get("run_at"),
        "status": payload.get("status"),
        "exit_code": exit_code,
        "items": count_items(payload.get("items", [])),
        "sources_total": payload.get("sources_total", 0),
        "sources_ok": payload.get("sources_ok", 0),
        "sources_failed": payload.get("sources_failed", 0),
    }
    if "source" in payload:
        summary["source"] = payload["source"]
    if "profile" in payload:
        summary["profile"] = payload["profile"]
    if json_out:
        summary["json_out"] = json_out
    if md_out:
        summary["md_out"] = md_out
    if output_format != "full":
        summary["format"] = output_format
    if health_out:
        summary["health_out"] = health_out
    print(json.dumps(summary, ensure_ascii=False))


def update_health_state(health_path, run_at, requested_sources, failed_sources):
    if not health_path:
        return

    state = load_json_file(health_path, {"updated_at": None, "sources": {}})
    sources_state = state.setdefault("sources", {})
    failures_by_id = {}
    unique_requested = {}

    for item in failed_sources or []:
        candidates = []
        if item.get("source_key"):
            candidates.append(stable_source_id(item["source_key"]))
        if item.get("source"):
            candidates.append(stable_source_id(item["source"]))
        for candidate in candidates:
            failures_by_id.setdefault(candidate, []).append(item)

    for requested in requested_sources:
        source_key = requested.get("source_key") or requested.get("key") or requested.get("source")
        source_name = requested.get("source") or requested.get("name") or source_key
        unique_requested[stable_source_id(source_key or source_name)] = {
            "source_key": source_key,
            "source": source_name,
        }

    for requested in unique_requested.values():
        source_key = requested.get("source_key") or requested.get("key") or requested.get("source")
        source_name = requested.get("source") or requested.get("name") or source_key
        source_id = stable_source_id(source_key or source_name)
        entry = sources_state.setdefault(
            source_id,
            {
                "source": source_name,
                "source_key": source_key,
                "last_ok_at": None,
                "last_error_at": None,
                "last_error": None,
                "consecutive_errors": 0,
            },
        )
        entry["source"] = source_name
        entry["source_key"] = source_key
        matched_failures = failures_by_id.get(source_id, [])
        if not matched_failures and source_name:
            matched_failures = failures_by_id.get(stable_source_id(source_name), [])
        if matched_failures:
            last_failure = matched_failures[-1]
            entry["last_error_at"] = to_iso(run_at)
            entry["last_error"] = last_failure.get("error")
            entry["consecutive_errors"] = int(entry.get("consecutive_errors", 0)) + 1
        else:
            entry["last_ok_at"] = to_iso(run_at)
            entry["last_error"] = None
            entry["consecutive_errors"] = 0

    state["updated_at"] = to_iso(run_at)
    write_json_file(state, health_path)

def filter_items(items, keyword=None):
    if not keyword:
        return items
    keywords = [k.strip() for k in keyword.split(',') if k.strip()]
    pattern = '|'.join([r'\b' + re.escape(k) + r'\b' for k in keywords])
    regex = r'(?i)(' + pattern + r')'
    return [item for item in items if re.search(regex, item['title'])]


def get_url_parts(url):
    try:
        parsed = urlsplit(url or "")
    except Exception:
        return "", ""
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    return host, path


def item_age_minutes_from_time(raw_time, now=None):
    published_dt = parse_published_datetime(raw_time)
    if published_dt is None:
        return None
    current = now or now_utc()
    age_seconds = (current - published_dt.astimezone(timezone.utc)).total_seconds()
    return max(int(age_seconds // 60), 0)


def apply_search_quality_filters(items, source_key, max_age_minutes=None):
    filtered = []
    dropped = 0
    current = now_utc()

    for item in items:
        host, path = get_url_parts(item.get("url"))
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        title_lower = title.lower()
        summary_lower = summary.lower()

        age_minutes = item_age_minutes_from_time(item.get("time"), current)
        if max_age_minutes is not None and age_minutes is not None and age_minutes > max_age_minutes:
            dropped += 1
            continue

        if host and path in {"", "/"}:
            dropped += 1
            continue

        if source_key == "ddgs_news":
            if host.endswith("msn.com"):
                dropped += 1
                continue
            if title_lower.startswith("latest crypto") or title_lower.startswith("latest bitcoin"):
                dropped += 1
                continue

        if source_key == "tavily":
            low_signal_title = any(token in title_lower for token in ["how to buy", "buy ", "purchase options", "easy how to buy", "guide"]) \
                or any(token in summary_lower for token in ["how to buy", "purchase options", "web3 wallet", "isn't available on the binance exchange"])
            low_signal_path = any(token in path.lower() for token in ["/how-to-buy/", "/buy/", "/price/", "/price-prediction/"])
            if low_signal_title or low_signal_path:
                dropped += 1
                continue

        filtered.append(item)

    if dropped:
        print(f"Filtered {dropped} low-signal item(s) from {source_key}", file=sys.stderr)
    return filtered


def load_env_value_from_file(key, path=None):
    env_path = path or os.getenv("OPENCLAW_SECRETS_ENV") or os.path.expanduser("~/.config/openclaw/secrets.env")
    if not env_path or not os.path.exists(env_path):
        return None

    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                raw_key, raw_value = line.split("=", 1)
                if raw_key.strip() != key:
                    continue
                value = raw_value.strip().strip('"').strip("'")
                if value:
                    os.environ.setdefault(key, value)
                return value or None
    except Exception:
        return None


def resolve_tavily_api_key():
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        return api_key
    return load_env_value_from_file("TAVILY_API_KEY")


def normalize_tavily_query(keyword=None):
    if not keyword:
        return "Bitcoin Ethereum crypto market news"
    keywords = [part.strip() for part in keyword.split(",") if part.strip()]
    if not keywords:
        return keyword.strip()
    return " ".join(keywords)


def normalize_ddgs_query(keyword=None):
    return normalize_tavily_query(keyword)


def ddgs_query_variants(keyword=None, search_type="text"):
    variants = []
    if not keyword and search_type == "news":
        return ["crypto market", "business news", "world news"]
    primary = normalize_ddgs_query(keyword)
    if primary:
        variants.append(primary)
    if keyword:
        keywords = [part.strip() for part in keyword.split(",") if part.strip()]
        if keywords:
            fallback = normalize_ddgs_query(keywords[0])
            if fallback and fallback not in variants:
                variants.append(fallback)
    return variants or [normalize_ddgs_query(None)]


def load_ddgs():
    from ddgs import DDGS
    return DDGS


def run_ddgs_query(search_type, query, backend, max_results):
    DDGS = load_ddgs()
    results = DDGS()
    payload = getattr(results, search_type)(query, backend=backend, max_results=max_results)
    return list(payload)


def normalize_ddgs_text_result(result, query, backend):
    title = result.get("title") or result.get("href") or "DuckDuckGo Result"
    return {
        "source": "DuckDuckGo Search",
        "title": title,
        "url": result.get("href"),
        "time": "Real-time",
        "heat": "",
        "summary": compact_text(result.get("body", ""), 280) or "",
        "provider": "ddgs",
        "provider_type": "text",
        "provider_backend": backend,
        "provider_query": query,
    }


def normalize_ddgs_news_result(result, query, backend):
    title = result.get("title") or result.get("url") or "DDGS News Result"
    return {
        "source": "DDGS News",
        "title": title,
        "url": result.get("url"),
        "time": result.get("date") or "Real-time",
        "heat": "",
        "summary": compact_text(result.get("body", ""), 280) or "",
        "provider": "ddgs",
        "provider_type": "news",
        "provider_backend": backend,
        "provider_query": query,
    }


def fetch_ddgs_text(limit=5, keyword=None):
    attempts = [
        ("duckduckgo", "DuckDuckGo Search"),
        ("auto", "DuckDuckGo Search"),
    ]
    last_error = None
    for query in ddgs_query_variants(keyword, search_type="text"):
        for backend, source_name in attempts:
            try:
                results = run_ddgs_query("text", query, backend, max(1, min(int(limit) * 2, 20)))
            except Exception as exc:
                last_error = exc
                continue
            if not results:
                last_error = RuntimeError(f"DDGS text returned no results for backend={backend}")
                continue
            items = [normalize_ddgs_text_result(result, query, backend) for result in results[:limit]]
            filtered = filter_items(items, keyword)[:limit]
            if filtered:
                return filtered
            return items[:limit]

    if last_error is not None:
        record_source_error("DuckDuckGo Search", last_error, context={"source_key": "ddgs"})
    return []


def fetch_ddgs_news(limit=5, keyword=None):
    last_error = None
    max_age_minutes = int(os.getenv("DDGS_NEWS_MAX_AGE_MINUTES", "4320"))
    for query in ddgs_query_variants(keyword, search_type="news"):
        for _ in range(2):
            try:
                results = run_ddgs_query("news", query, "auto", max(1, min(int(limit) * 2, 20)))
            except Exception as exc:
                last_error = exc
                continue

            if not results:
                last_error = RuntimeError("DDGS news returned no results for backend=auto")
                continue

            items = [normalize_ddgs_news_result(result, query, "auto") for result in results[:limit]]
            filtered = filter_items(items, keyword)
            filtered = apply_search_quality_filters(filtered, "ddgs_news", max_age_minutes=max_age_minutes)[:limit]
            if filtered:
                return filtered
            filtered_items = apply_search_quality_filters(items, "ddgs_news", max_age_minutes=max_age_minutes)[:limit]
            if filtered_items:
                return filtered_items

            last_error = RuntimeError("DDGS news results were filtered as low-signal")
            continue

    if last_error is not None:
        record_source_error("DDGS News", last_error, context={"source_key": "ddgs_news"})
    return []


def fetch_tavily_search(limit=5, keyword=None):
    query = normalize_tavily_query(keyword)
    api_key = resolve_tavily_api_key()
    if not api_key:
        record_source_error("Tavily Search", RuntimeError("Missing TAVILY_API_KEY"), code="env")
        return []

    url = os.getenv("TAVILY_SEARCH_URL", "https://api.tavily.com/search")
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        "max_results": max(1, min(int(limit) * 2, 10)),
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        record_source_error("Tavily Search", e)
        return []

    items = []
    for result in data.get("results", [])[: max(1, min(int(limit) * 2, 10))]:
        title = result.get("title") or result.get("url") or "Tavily Result"
        summary = result.get("content") or result.get("raw_content") or ""
        published = result.get("published_date") or result.get("published_at") or result.get("date") or "Real-time"
        score = result.get("score")
        heat = f"score {float(score):.2f}" if isinstance(score, (int, float)) else (str(score) if score is not None else "")
        items.append({
            "source": "Tavily Search",
            "title": title,
            "url": result.get("url"),
            "time": published,
            "heat": heat,
            "summary": compact_text(summary, 280) or "",
        })

    filtered = filter_items(items, keyword)
    filtered = apply_search_quality_filters(filtered, "tavily")[:limit]
    if filtered:
        return filtered
    return apply_search_quality_filters(items, "tavily")[:limit]

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
            return filter_items(items, keyword)[:limit]
            
        except Exception as e:
            record_source_error("Hacker News", e)
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
        except Exception as e:
            record_source_error("Hacker News", e)
            break

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


def _humanize_age_from_unix(unix_ts, reference_ts=None):
    try:
        created = int(unix_ts)
    except (TypeError, ValueError):
        return "Unknown"

    now_ts = int(reference_ts if reference_ts is not None else time.time())
    delta = max(now_ts - created, 0)
    if delta < 60:
        return "Just now"
    if delta < 3600:
        minutes = max(delta // 60, 1)
        return f"{minutes}m ago"
    if delta < 86400:
        hours = max(delta // 3600, 1)
        return f"{hours}h ago"
    days = max(delta // 86400, 1)
    return f"{days}d ago"


def _clean_hn_text(value):
    if not value:
        return None
    text = BeautifulSoup(str(value), 'html.parser').get_text(' ', strip=True)
    text = ' '.join(text.split())
    return text or None


def fetch_hackernews_api(limit=5, keyword=None):
    display_name = "Hacker News API"
    endpoint = lambda name: f"{HN_API_BASE_URL}/{name}.json"

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        fetch_depth = min(max(limit * (6 if keyword else 3), 20), 80)
        endpoints = ["topstories", "beststories", "newstories"]
        if keyword and re.search(r"(?i)(show hn|ask hn|launch|startup|yc|founder)", keyword):
            endpoints.extend(["showstories", "askstories"])

        candidate_ids = []
        seen_ids = set()
        for list_name in endpoints:
            try:
                ids_response = session.get(endpoint(list_name), timeout=(5, 10))
                ids_response.raise_for_status()
                ids = ids_response.json() or []
            except Exception as exc:
                record_source_error(display_name, exc, context={"source_key": "fetch_hackernews_api", "list": list_name})
                continue
            for item_id in ids[:fetch_depth]:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                candidate_ids.append(item_id)

        if not candidate_ids:
            return []

        def fetch_item(item_id):
            response = session.get(endpoint(f"item/{item_id}"), timeout=(5, 10))
            response.raise_for_status()
            return response.json()

        items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(fetch_item, item_id) for item_id in candidate_ids]
            for future in concurrent.futures.as_completed(futures):
                try:
                    item = future.result()
                except Exception:
                    continue
                if not item or item.get("deleted") or item.get("dead"):
                    continue
                if item.get("type") != "story":
                    continue

                title = _clean_hn_text(item.get("title"))
                if not title:
                    continue

                hn_url = f"https://news.ycombinator.com/item?id={item['id']}"
                summary = compact_text(_clean_hn_text(item.get("text")), 240)
                score = item.get("score", 0)
                descendants = item.get("descendants")
                heat = f"{score} points"
                if descendants is not None:
                    heat += f" • {descendants} comments"

                items.append({
                    "source": display_name,
                    "title": title,
                    "url": item.get("url") or hn_url,
                    "hn_url": hn_url,
                    "heat": heat,
                    "time": _humanize_age_from_unix(item.get("time")),
                    "published_at_raw": item.get("time"),
                    "summary": summary,
                })

        items.sort(key=lambda entry: entry.get("published_at_raw") or 0, reverse=True)
        items = filter_items(items, keyword)
        return items[:limit]
    except Exception as e:
        record_source_error(display_name, e, context={"source_key": "fetch_hackernews_api"})
        return []


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
    except Exception as e:
        record_source_error("Weibo Hot Search", e)
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
                     segments = [segment for segment in repo_link.split('/') if segment]
                     if len(segments) != 2:
                         continue
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
         except Exception as e:
             record_source_error("GitHub Trending", e)
             pass

    # Default Trending
    try:
        response = requests.get("https://github.com/trending", headers=HEADERS, timeout=10)
    except Exception as e:
        record_source_error("GitHub Trending", e)
        return []
    
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
    except Exception as e:
        record_source_error("36Kr", e)
        return []

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
    except Exception as e:
        record_source_error("V2EX", e)
        return []

def fetch_tencent(limit=5, keyword=None):
    try:
        url = "https://i.news.qq.com/web_backend/v2/getTagInfo?tagId=aEWqxLtdgmQ%3D"
        data = requests.get(url, headers={"Referer": "https://news.qq.com/"}, timeout=10).json()
        items = []
        tabs = data.get("data", {}).get("tabs", [])
        article_list = tabs[0].get("articleList", []) if tabs else []
        for news in article_list:
            title = (
                news.get("title")
                or news.get("name")
                or news.get("topic_name")
                or news.get("card_title")
            )
            if not title:
                continue
            items.append({
                "source": "Tencent News", 
                "title": title,
                "url": news.get('url') or news.get('link_info', {}).get('url'),
                "time": news.get('pub_time', '') or news.get('publish_time', '')
            })
        return filter_items(items, keyword)[:limit]
    except Exception as e:
        record_source_error("Tencent News", e)
        return []

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
    except Exception as e:
        record_source_error("Wall Street CN", e)
        return []

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
    except Exception as e:
        record_source_error("Product Hunt", e)
        return []

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
             record_source_error("HF Papers", result.stderr or "Playwright subprocess failed", code="env" if "ModuleNotFoundError" in (result.stderr or "") else None)
             print(f"HF Playwright Failed: {result.stderr}", file=sys.stderr)
             
    except Exception as e:
        record_source_error("HF Papers", e)
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
        record_source_error("Latent Space AINews", e)
        print(f"Latent Space AINews fetch error: {e}", file=sys.stderr)
    
    return filter_items(items[:limit], keyword)


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
    ("KDnuggets", "https://www.kdnuggets.com/feed"),
]

# ... (rest of sources)

def fetch_rss_with_playwright(url, source_name, limit=5):
    """Fallback fetcher using Playwright to bypass Cloudflare"""
    try:
        # Special handling for Ben's Bites which uses custom Homepage Scraper
        if "Ben's Bites" in source_name:
            script_path = os.path.join(os.path.dirname(__file__), "fetch_bensbites.py")
            cmd = [sys.executable, script_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if not data:
                        raise ValueError("Empty JSON")
                    return data
                except Exception as e:
                    record_source_error("Ben's Bites", e)
                    return [{
                        "source": "Ben's Bites",
                        "title": "Ben's Bites (Visit Site)",
                        "url": "https://bensbites.beehiiv.com/",
                        "time": "Today",
                        "summary": "Auto-fetch failed. Please verify on site.",
                    }]

            record_source_error("Ben's Bites", result.stderr or "Fetch process failed")
            return [{
                "source": "Ben's Bites",
                "title": "Ben's Bites (Check Site)",
                "url": "https://bensbites.beehiiv.com/",
                "time": "Today",
                "summary": "Fetch process failed.",
            }]

        script_path = os.path.join(os.path.dirname(__file__), "fetch_generic_playwright.py")
        cmd = [sys.executable, script_path, url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode == 0:
            from rss_parser import parse_rss_content
            return parse_rss_content(result.stdout, source_name, limit, error_callback=record_source_error)

        record_source_error(source_name, result.stderr or "Playwright fetch failed")
        print(f"Playwright fetch failed for {source_name}: {result.stderr}", file=sys.stderr)
        return []
    except Exception as e:
        record_source_error(source_name, e)
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
        futures = {executor.submit(fetch_rss_feed, url, name, 3, record_source_error): name for name, url in AI_NEWSLETTER_SOURCES}
        for future in concurrent.futures.as_completed(futures):
            all_items.extend(future.result())
    return filter_items(all_items, keyword)[:limit]

def fetch_podcasts(limit=5, keyword=None):
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss_feed, url, name, 3, record_source_error): name for name, url in PODCAST_SOURCES}
        for future in concurrent.futures.as_completed(futures):
            all_items.extend(future.result())
    return filter_items(all_items, keyword)[:limit]

def fetch_essays(limit=5, keyword=None):
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss_feed, url, name, 3, record_source_error): name for name, url in ESSAY_SOURCES}
        for future in concurrent.futures.as_completed(futures):
            all_items.extend(future.result())
    return filter_items(all_items, keyword)[:limit]

def create_single_rss_fetcher(url, name):
    def fetcher(limit=5, keyword=None):
        return filter_items(fetch_rss_feed(url, name, limit, record_source_error), keyword)[:limit]
    return fetcher


def save_report(payload, source_name, out_dir):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    safe_name = sanitize_filename(source_name)
    timestamp = datetime.now().strftime("%H%M")
    json_path = os.path.join(out_dir, f"{safe_name}_{timestamp}.json")
    write_json_file(payload, json_path)
    return json_path


def default_reports_dir():
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", today)


def build_sources_map():
    sources_map = {
        "hackernews": fetch_hackernews,
        "hackernews_api": fetch_hackernews_api,
        "weibo": fetch_weibo,
        "github": fetch_github,
        "36kr": fetch_36kr,
        "v2ex": fetch_v2ex,
        "tencent": fetch_tencent,
        "wallstreetcn": fetch_wallstreetcn,
        "producthunt": fetch_producthunt,
        "huggingface": fetch_huggingface_papers,
        "ai_newsletters": fetch_ai_newsletters,
        "podcasts": fetch_podcasts,
        "essays": fetch_essays,
        "latentspace_ainews": fetch_latentspace_ainews,
        "tavily": fetch_tavily_search,
        "ddgs": fetch_ddgs_text,
        "ddgs_news": fetch_ddgs_news,
    }

    for name, url in AI_NEWSLETTER_SOURCES:
        key = name.lower().replace(" ", "").replace("'", "")
        if "Ben's Bites" in name or "The Rundown" in name:
            sources_map[key] = lambda limit=10, k=None, u=url, n=name: filter_items(fetch_rss_with_playwright(u, n, limit), k)[:limit]
        else:
            sources_map[key] = create_single_rss_fetcher(url, name)

    for name, url in PODCAST_SOURCES:
        key = name.lower().replace(" ", "")
        sources_map[key] = create_single_rss_fetcher(url, name)

    for name, url in ESSAY_SOURCES:
        key = name.lower().replace(" ", "")
        sources_map[key] = create_single_rss_fetcher(url, name)
    return sources_map


def print_sources_list(sources_map):
    print(f"{'Source Key':<20} | Source Name")
    print("-" * 60)
    for key in sorted(sources_map.keys()):
        func = sources_map[key]
        print(f"{key:<20} | {source_display_name(func, key)}")


def write_payload_outputs(payload, json_out=None, md_out=None, output_format="full"):
    if json_out:
        write_json_file(payload, json_out)
    if md_out:
        write_markdown_file(payload, md_out, output_format=output_format)


def build_run_payload(source_name, run_at, items, failed_sources, sources_total, requested_key_count=None):
    failed_sources = dedupe_failed_sources(failed_sources)
    failed_requested = set()
    for item in failed_sources:
        key = item.get("source_key") or item.get("source")
        if key:
            failed_requested.add(key)
    sources_failed = min(len(failed_requested), sources_total) if sources_total else 0
    if requested_key_count is not None and not sources_failed and failed_sources:
        sources_failed = min(len(failed_sources), requested_key_count)
    sources_ok = max(sources_total - sources_failed, 0)
    status, exit_code = determine_status_and_exit_code(count_items(items), failed_sources)
    payload = {
        "run_at": to_iso(run_at),
        "source": source_name,
        "status": status,
        "sources_total": sources_total,
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "failed_sources": failed_sources,
        "items": items,
    }
    return payload, exit_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="all", help='Source(s) to fetch from (comma-separated). Now supports sub-sources like "chinai", "paulgraham"')
    parser.add_argument("--limit", type=int, default=10, help="Limit per source. Default 10")
    parser.add_argument("--keyword", help="Comma-sep keyword filter")
    parser.add_argument("--deep", action="store_true", help="Download article content for detailed summarization")
    parser.add_argument("--deep-top-n", type=int, help="Only deep-enrich the first N items")
    parser.add_argument("--max-age-minutes", type=int, help="Drop items older than this many minutes when age can be determined")
    parser.add_argument("--save", action="store_true", help="Save output to reports directory (JSON)")
    parser.add_argument("--no-save", action="store_true", dest="no_save", help="Skip saving JSON files to disk (only output to stdout)")
    parser.add_argument("--outdir", help="Custom output directory for saved reports")
    parser.add_argument("--json-out", help="Write run JSON to this path")
    parser.add_argument("--md-out", help="Write Markdown summary to this path")
    parser.add_argument("--stdout-summary", action="store_true", help="Print a one-line machine-readable JSON summary to stdout")
    parser.add_argument("--format", choices=["full", "telegram"], default="full", help="Markdown output format")
    parser.add_argument("--health-out", default=default_health_path(), help="Write per-source health state JSON to this path")
    parser.add_argument("--list-sources", action="store_true", help="List all available source keys")

    args = parser.parse_args()
    sources_map = build_sources_map()

    if args.list_sources:
        print_sources_list(sources_map)
        return EXIT_SUCCESS

    run_at = now_utc()
    clear_source_errors()

    if MISSING_DEPENDENCY_ERROR is not None:
        failed_sources = [{
            "source": "runtime",
            "source_key": "runtime",
            "error": f"Missing dependency: {MISSING_DEPENDENCY_ERROR.name}",
            "code": "env",
        }]
        payload, exit_code = build_run_payload(args.source, run_at, [], failed_sources, sources_total=1, requested_key_count=1)
        write_payload_outputs(payload, args.json_out, args.md_out, output_format=args.format)
        update_health_state(
            args.health_out,
            run_at,
            [{"source_key": "runtime", "source": "runtime"}],
            failed_sources,
        )
        if args.stdout_summary:
            emit_stdout_summary(payload, exit_code, args.json_out, args.md_out, output_format=args.format, health_out=args.health_out)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return exit_code

    requested_specs = []
    requested_keys = []
    if args.source == "all":
        requested_specs = [{"key": key, "func": func, "name": source_display_name(func, key)} for key, func in sources_map.items()]
        requested_keys = [spec["key"] for spec in requested_specs]
    else:
        for raw_key in [item.strip() for item in args.source.split(",") if item.strip()]:
            requested_keys.append(raw_key)
            if raw_key in sources_map:
                func = sources_map[raw_key]
                requested_specs.append({"key": raw_key, "func": func, "name": source_display_name(func, raw_key)})
            else:
                record_source_error(raw_key, ValueError(f"Unknown source key: {raw_key}"), code="error", context={"source_key": raw_key})

    def run_fetchers(specs, limit, keyword):
        aggregated = []
        for spec in specs:
            try:
                aggregated.extend(spec["func"](limit, keyword))
            except Exception as exc:
                record_source_error(spec["name"], exc, context={"source_key": spec["key"]})
        return aggregated

    results = run_fetchers(requested_specs, args.limit, args.keyword)

    min_items = 5
    smart_fill_excluded = {"ddgs", "ddgs_news"}
    if (
        args.keyword
        and len(results) < min_items
        and requested_specs
        and not set(requested_keys).issubset(smart_fill_excluded)
    ):
        sys.stderr.write(f"Smart Fill triggered: Found {len(results)} items, filling gaps...\n")
        fill_results = run_fetchers(requested_specs, limit=min_items, keyword=None)
        existing_urls = {normalize_url(item.get("url")) for item in results}
        existing_titles = {normalize_title(item.get("title")) for item in results}
        for item in fill_results:
            if len(results) >= min_items:
                break
            url = normalize_url(item.get("url"))
            title = normalize_title(item.get("title"))
            if url not in existing_urls and title not in existing_titles:
                item["smart_fill"] = True
                if item.get("time"):
                    item["time"] = f"⚠️ {item['time']}"
                results.append(item)
                existing_urls.add(url)
                existing_titles.add(title)

    results = dedupe_items(results)
    results = annotate_items(results, run_at)
    results = filter_items_by_age(results, args.max_age_minutes)

    if args.deep and results:
        deep_limit = len(results) if args.deep_top_n is None else min(len(results), max(args.deep_top_n, 0))
        sys.stderr.write(f"Deep fetching content for {deep_limit} item(s)...\n")
        apply_deep_enrichment(results, args.deep_top_n)

    failed_sources = get_recorded_source_errors()
    payload, exit_code = build_run_payload(
        args.source,
        run_at,
        results,
        failed_sources,
        sources_total=len(requested_keys) if requested_keys else len(requested_specs),
        requested_key_count=len(requested_keys),
    )

    json_out = args.json_out
    md_out = args.md_out
    if not args.no_save and (args.save or args.source != "all"):
        out_dir = args.outdir or default_reports_dir()
        os.makedirs(out_dir, exist_ok=True)
        if not json_out:
            timestamp = datetime.now().strftime("%H%M")
            json_out = os.path.join(out_dir, f"{sanitize_filename(args.source)}_{timestamp}.json")

    write_payload_outputs(payload, json_out, md_out, output_format=args.format)
    update_health_state(
        args.health_out,
        run_at,
        [{"source_key": spec["key"], "source": spec["name"]} for spec in requested_specs] or [{"source_key": key, "source": key} for key in requested_keys],
        failed_sources,
    )

    if args.stdout_summary:
        emit_stdout_summary(payload, exit_code, json_out, md_out, output_format=args.format, health_out=args.health_out)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if json_out:
        sys.stderr.write(f"[Saved] JSON: {json_out}\n")
    if md_out:
        sys.stderr.write(f"[Saved] Markdown: {md_out}\n")
    if args.health_out:
        sys.stderr.write(f"[Saved] Health: {args.health_out}\n")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
