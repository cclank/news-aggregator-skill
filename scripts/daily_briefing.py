import json
import concurrent.futures
import sys
import os
from fetch_news import (
    fetch_hackernews, fetch_github, fetch_producthunt, 
    fetch_weibo, fetch_36kr, fetch_tencent, fetch_v2ex, fetch_wallstreetcn,
    enrich_items_with_content
)

import argparse

# --- Profile Configurations ---

PROFILES = {
    # 1. 综合早报 (General Morning Routine)
    "general": {
        "global_scan": {
            "sources": [
                (fetch_hackernews, 5, None),
                (fetch_producthunt, 5, None),
                (fetch_github, 5, None),
                (fetch_weibo, 5, None),
                (fetch_36kr, 5, None),
                (fetch_tencent, 5, None),
                (fetch_wallstreetcn, 5, None),
                (fetch_v2ex, 5, None)
            ],
            "enrich": True
        },
        "hn_ai": {
            "sources": [(fetch_hackernews, 20, "AI,LLM,GPT,DeepSeek,Github Copilot,Claude,OpenAI")],
            "enrich": True
        },
        "github_trending": {
            "sources": [(fetch_github, 15, None)],
            "enrich": True
        }
    },

    # 2. 财经早报 (Finance)
    "finance": {
        "market_overview": {
            "sources": [
                (fetch_wallstreetcn, 30, None),
                (fetch_hackernews, 10, "Economy,Inflation,Fed,Stock,Finance")
            ],
            "enrich": True
        },
        "china_finance": {
            "sources": [
                (fetch_36kr, 20, "财报,营收,上市,IPO,基金,投资"),
                (fetch_tencent, 15, "财经,股票,基金")
            ],
            "enrich": True
        },
        "crypto": {
            "sources": [
                (fetch_hackernews, 15, "Bitcoin,Crypto,Ethereum,Blockchain,Web3,DeFi"),
                (fetch_wallstreetcn, 10, "比特币,加密货币")
            ],
            "enrich": True
        }
    },

    # 3. 科技早报 (Tech)
    "tech": {
        "ai_frontier": {
            "sources": [
                (fetch_hackernews, 25, "AI,LLM,Transformer,Diffusion,Model,RAG"),
                (fetch_github, 10, "AI,LLM,GPT")
            ],
            "enrich": True
        },
        "dev_tools": {
            "sources": [
                (fetch_producthunt, 20, "Developer Tools,Coding,API"),
                (fetch_github, 15, None)
            ],
            "enrich": True
        },
        "startups": {
            "sources": [(fetch_36kr, 20, "融资,首发,独角兽,创投"), (fetch_producthunt, 10, None)],
            "enrich": True
        }
    },

    # 4. 吃瓜早报 (Social/Gossip)
    "social": {
        "weibo_hot": {
            "sources": [(fetch_weibo, 40, None)],
            "enrich": False # No need for deep verify, just title/heat
        },
        "v2ex_hot": {
            "sources": [(fetch_v2ex, 30, None)],
            "enrich": True # Content is fun
        }
    }
}


def fetch_section(section_name, config):
    print(f"[{section_name}] Starting fetch...", file=sys.stderr)
    results = []
    
    # Run source fetchers for this section in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {}
        for func, limit, kw in config["sources"]:
            future = executor.submit(func, limit, kw)
            future_map[future] = f"{func.__name__}"
            
        for future in concurrent.futures.as_completed(future_map):
            fname = future_map[future]
            try:
                items = future.result()
                results.extend(items)
                print(f"[{section_name}] {fname} returned {len(items)} items", file=sys.stderr)
            except Exception as e:
                print(f"[{section_name}] {fname} failed: {e}", file=sys.stderr)

    # Enforce Smart Fill Logic logic if needed? 
    # Actually, for the briefing, we are already fetching heavily (e.g. 5 from 8 sources = 40 items for global).
    # So we likely don't need explicit smart fill here if we fetch enough upfront.
    
    # Enrich if requested
    if config["enrich"] and results:
        print(f"[{section_name}] Enriching content for {len(results)} items...", file=sys.stderr)
        results = enrich_items_with_content(results, max_workers=10)
        
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='general', choices=PROFILES.keys(), help='Briefing Profile: general, finance, tech, social')
    args = parser.parse_args()
    
    config = PROFILES.get(args.profile, PROFILES['general'])
    
    final_data = {}
    
    # Fetch all sections
    for section, sec_config in config.items():
        final_data[section] = fetch_section(section, sec_config)
        
    # Output result
    print(json.dumps(final_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
