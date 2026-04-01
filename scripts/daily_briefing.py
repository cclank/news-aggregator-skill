import json
import concurrent.futures
import sys
import os
from pathlib import Path
from fetch_news import (
    build_sources_map,
    clear_source_errors,
    default_health_path,
    MISSING_DEPENDENCY_ERROR,
    annotate_items,
    apply_deep_enrichment,
    count_items,
    dedupe_items,
    dedupe_failed_sources,
    determine_status_and_exit_code,
    emit_stdout_summary,
    filter_items_by_age,
    get_recorded_source_errors,
    now_utc,
    record_source_error,
    source_display_name,
    to_iso,
    update_health_state,
    write_json_file,
    write_markdown_file
)

import argparse

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def load_profiles():
    sources_map = build_sources_map()
    profiles = {}

    for path in sorted(PROFILES_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as handle:
            raw_profile = json.load(handle)

        profile_name = raw_profile.get("name") or path.stem
        raw_sections = raw_profile.get("sections", raw_profile)
        sections = {}

        for section_name, raw_section in raw_sections.items():
            resolved_sources = []
            for source_spec in raw_section.get("sources", []):
                source_key = source_spec["source"]
                if source_key not in sources_map:
                    raise ValueError(f"Unknown source key '{source_key}' in profile '{profile_name}'")
                resolved_sources.append(
                    (
                        sources_map[source_key],
                        int(source_spec.get("limit", 10)),
                        source_spec.get("keyword"),
                    )
                )
            sections[section_name] = {
                "sources": resolved_sources,
                "enrich": bool(raw_section.get("enrich", False)),
            }

        profiles[profile_name] = sections

    if not profiles:
        raise ValueError(f"No profile configs found in {PROFILES_DIR}")
    return profiles


def fetch_section(section_name, config, run_at, max_age_minutes=None, deep_top_n=None):
    print(f"[{section_name}] Starting fetch...", file=sys.stderr)
    results = []
    
    # Run source fetchers for this section in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {}
        for func, limit, kw in config["sources"]:
            future = executor.submit(func, limit, kw)
            future_map[future] = {
                "source": source_display_name(func),
                "source_key": func.__name__,
            }
            
        for future in concurrent.futures.as_completed(future_map):
            source_info = future_map[future]
            try:
                items = future.result()
                results.extend(items)
                print(f"[{section_name}] {source_info['source']} returned {len(items)} items", file=sys.stderr)
            except Exception as e:
                record_source_error(
                    source_info["source"],
                    e,
                    context={"section": section_name, "source_key": source_info["source_key"]},
                )
                print(f"[{section_name}] {source_info['source']} failed: {e}", file=sys.stderr)

    results = dedupe_items(results)
    results = annotate_items(results, run_at)
    results = filter_items_by_age(results, max_age_minutes)

    # Enrich if requested
    if config["enrich"] and results:
        deep_limit = len(results) if deep_top_n is None else min(len(results), max(deep_top_n, 0))
        print(f"[{section_name}] Enriching content for {deep_limit} item(s)...", file=sys.stderr)
        apply_deep_enrichment(results, deep_top_n, max_workers=10)
        
    return results

def save_individual_sources(data, base_dir):
    """
    Splits the aggregated data by 'source' and saves individual JSON files.
    """
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    source_map = {}
    total_count = 0
    
    # Flatten and grouping
    for section, items in data.items():
        for item in items:
            src = item.get('source', 'Unknown')
            # Sanitize filename
            safe_name = "".join([c if c.isalnum() else "_" for c in src])
            if safe_name not in source_map:
                source_map[safe_name] = []
            source_map[safe_name].append(item)
            total_count += 1
            
    # Save
    print(f"Saving {len(source_map)} individual source files to {base_dir}...", file=sys.stderr)
    for src, items in source_map.items():
        fpath = os.path.join(base_dir, f"{src}.json")
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

    return list(source_map.keys())

def main():
    profiles = load_profiles()
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='general', choices=profiles.keys(), help='Briefing Profile')
    parser.add_argument('--outdir', help='Optional output directory for individual files')
    parser.add_argument('--no-save', action='store_true', help='Skip saving JSON files to disk (only output to stdout)')
    parser.add_argument('--json-out', help='Write run JSON to this path')
    parser.add_argument('--md-out', help='Write Markdown summary to this path')
    parser.add_argument('--stdout-summary', action='store_true', help='Print a one-line machine-readable JSON summary to stdout')
    parser.add_argument('--max-age-minutes', type=int, help='Drop items older than this many minutes when age can be determined')
    parser.add_argument('--deep-top-n', type=int, help='Only deep-enrich the first N items in each section')
    parser.add_argument('--format', choices=['full', 'telegram'], default='full', help='Markdown output format')
    parser.add_argument('--health-out', default=default_health_path(), help='Write per-source health state JSON to this path')
    args = parser.parse_args()
    
    run_at = now_utc()
    if MISSING_DEPENDENCY_ERROR is not None:
        payload = {
            "run_at": to_iso(run_at),
            "profile": args.profile,
            "status": "timeout_or_env",
            "sources_total": 1,
            "sources_ok": 0,
            "sources_failed": 1,
            "failed_sources": [{
                "source": "runtime",
                "source_key": "runtime",
                "error": f"Missing dependency: {MISSING_DEPENDENCY_ERROR.name}",
                "code": "env",
            }],
            "items": {},
        }
        if args.json_out:
            write_json_file(payload, args.json_out)
        if args.md_out:
            write_markdown_file(payload, args.md_out, output_format=args.format)
        update_health_state(
            args.health_out,
            run_at,
            [{"source_key": "runtime", "source": "runtime"}],
            payload["failed_sources"],
        )
        if args.stdout_summary:
            emit_stdout_summary(payload, 60, args.json_out, args.md_out, output_format=args.format, health_out=args.health_out)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 60

    clear_source_errors()
    config = profiles.get(args.profile, profiles['general'])
    final_data = {}
    
    # Fetch all sections
    for section, sec_config in config.items():
        final_data[section] = fetch_section(
            section,
            sec_config,
            run_at,
            max_age_minutes=args.max_age_minutes,
            deep_top_n=args.deep_top_n,
        )
    
    failed_sources = dedupe_failed_sources(get_recorded_source_errors())
    sources_total = sum(len(sec_config["sources"]) for sec_config in config.values())
    sources_failed = min(len({item.get("section", item.get("source")) for item in failed_sources}), sources_total)
    sources_ok = max(sources_total - sources_failed, 0)
    status, exit_code = determine_status_and_exit_code(count_items(final_data), failed_sources)
    payload = {
        "run_at": to_iso(run_at),
        "profile": args.profile,
        "status": status,
        "sources_total": sources_total,
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "failed_sources": failed_sources,
        "items": final_data,
    }
    
    json_out = args.json_out
    md_out = args.md_out
    out_dir = args.outdir
    if not args.no_save:
        if not out_dir:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports', today)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        if not json_out:
            json_out = os.path.join(out_dir, f"{args.profile}_briefing_unified.json")

    if json_out:
        write_json_file(payload, json_out)
    if md_out:
        write_markdown_file(payload, md_out, output_format=args.format)

    requested_sources = []
    for sec_config in config.values():
        for func, _, _ in sec_config["sources"]:
            requested_sources.append({"source_key": func.__name__, "source": source_display_name(func)})
    update_health_state(args.health_out, run_at, requested_sources, failed_sources)

    if args.stdout_summary:
        emit_stdout_summary(payload, exit_code, json_out, md_out, output_format=args.format, health_out=args.health_out)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if not args.no_save:
        # Save Individual Sources
        sources_saved = save_individual_sources(final_data, out_dir)
        print(f"Saved unified report and {len(sources_saved)} individual source files to {out_dir}", file=sys.stderr)
    else:
        print(f"JSON output sent to stdout only (--no-save mode)", file=sys.stderr)
    if json_out:
        print(f"Unified JSON: {json_out}", file=sys.stderr)
    if md_out:
        print(f"Markdown summary: {md_out}", file=sys.stderr)
    if args.health_out:
        print(f"Health state: {args.health_out}", file=sys.stderr)
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
