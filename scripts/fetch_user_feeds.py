"""
用户自定义 RSS/Atom 订阅源聚合器。

读取 OPML 文件（兼容 Feedly / Inoreader / NetNewsWire 导出格式），
并发抓取每个订阅源，输出统一 JSON 到 stdout。

OPML 查找优先级:
  1. ~/.config/news-aggregator/user_sources.opml
  2. <skill_root>/user_sources.opml

用法:
    python fetch_user_feeds.py --limit 15 --per-feed 3
"""
import sys
import os
import json
import argparse
import concurrent.futures
from xml.etree import ElementTree as ET

# 复用 rss_parser
sys.path.insert(0, os.path.dirname(__file__))
from rss_parser import fetch_rss_feed


def find_opml_file():
    """按优先级查找 OPML 文件，返回第一个存在的路径或 None。"""
    candidates = [
        os.path.expanduser("~/.config/news-aggregator/user_sources.opml"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_sources.opml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def parse_opml(path):
    """解析 OPML，返回 [(name, xml_url), ...] 列表。"""
    tree = ET.parse(path)
    root = tree.getroot()
    feeds = []
    for outline in root.iter("outline"):
        xml_url = outline.get("xmlUrl")
        if not xml_url:
            continue
        name = outline.get("title") or outline.get("text") or xml_url
        feeds.append((name, xml_url))
    return feeds


def fetch_all_feeds(feeds, limit_per_feed=3):
    """并发抓取所有 feed，返回合并后的 items 列表。"""
    all_items = []
    if not feeds:
        return all_items
    max_workers = min(8, len(feeds))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {
            executor.submit(fetch_rss_feed, url, name, limit_per_feed): name
            for name, url in feeds
        }
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as e:
                print(f"User feed '{name}' fetch error: {e}", file=sys.stderr)
    return all_items


def main():
    parser = argparse.ArgumentParser(
        description="Fetch user-defined RSS feeds from OPML and emit JSON."
    )
    parser.add_argument("--opml", help="Override OPML file path")
    parser.add_argument("--limit", type=int, default=15, help="Total max items returned")
    parser.add_argument("--per-feed", type=int, default=3, help="Max items per individual feed")
    args = parser.parse_args()

    opml_path = args.opml or find_opml_file()
    if not opml_path:
        print("[]")
        print(
            "No OPML file found. Copy user_sources.opml.example to "
            "~/.config/news-aggregator/user_sources.opml or to skill root.",
            file=sys.stderr,
        )
        return

    try:
        feeds = parse_opml(opml_path)
    except Exception as e:
        print(f"Failed to parse OPML {opml_path}: {e}", file=sys.stderr)
        print("[]")
        return

    if not feeds:
        print("[]")
        print(f"No <outline xmlUrl=...> entries in {opml_path}", file=sys.stderr)
        return

    print(f"Fetching {len(feeds)} feeds from {opml_path}...", file=sys.stderr)
    items = fetch_all_feeds(feeds, args.per_feed)
    print(json.dumps(items[:args.limit], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
