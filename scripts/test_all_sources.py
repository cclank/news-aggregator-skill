
import subprocess
import os
import sys
import shutil
import json
from datetime import datetime

def get_all_sources():
    """Retrieve all source keys from fetch_news.py --list-sources"""
    cmd = [sys.executable, 'scripts/fetch_news.py', '--list-sources']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing sources: {result.stderr}")
        return []
    
    lines = result.stdout.strip().split('\n')
    sources = []
    start_collecting = False
    for line in lines:
        if line.startswith('---'):
            start_collecting = True
            continue
        if start_collecting and line.strip():
            key = line.split('|')[0].strip()
            if key:
                sources.append(key)
    return sources

def test_source(source, out_dir):
    """Run fetch_news.py for a single source"""
    print(f"Testing {source}...", end=' ', flush=True)
    json_out = os.path.join(out_dir, f"{source}.json")
    cmd = [
        sys.executable, 
        'scripts/fetch_news.py', 
        '--source', source, 
        '--limit', '1', 
        '--json-out', json_out,
        '--stdout-summary',
    ]
    
    start_time = datetime.now()
    try:
        # Timeout after 30s to prevent hanging
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        duration = (datetime.now() - start_time).total_seconds()
        summary_line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        summary = json.loads(summary_line) if summary_line else {}

        if result.returncode in (0, 10, 20) and os.path.exists(json_out):
            note = summary.get("status") or ""
            if result.returncode == 20:
                print(f"⚠️ PARTIAL ({duration:.1f}s)")
                return True, duration, note or "partial_success"
            if result.returncode == 10:
                print(f"⚠️ EMPTY ({duration:.1f}s)")
                return True, duration, note or "empty"
            print(f"✅ PASS ({duration:.1f}s)")
            return True, duration, note

        detail = result.stderr.strip() or summary.get("status") or "unknown failure"
        print(f"❌ FAIL ({duration:.1f}s)")
        return False, duration, detail
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT (45s)")
        return False, 45, "Timeout"
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, 0, str(e)

def main():
    # Setup
    test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_results')
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    print(f"Starting systematic source test...")
    print(f"Output directory: {test_dir}\n")
    
    sources = get_all_sources()
    print(f"Found {len(sources)} sources to test.\n")
    
    results = []
    
    for source in sources:
        success, duration, error = test_source(source, test_dir)
        results.append({
            'source': source,
            'success': success,
            'duration': duration,
            'error': error
        })
        
    # Generate Summary
    summary_path = os.path.join(test_dir, 'summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 🧪 News Source Test Report\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        passed = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        f.write(f"## Summary\n")
        f.write(f"- **Total**: {len(results)}\n")
        f.write(f"- **Passed**: {len(passed)}\n")
        f.write(f"- **Failed**: {len(failed)}\n\n")
        
        f.write("## ❌ Failures\n")
        if not failed:
            f.write("None! 🎉\n")
        else:
            for r in failed:
                f.write(f"- **{r['source']}**: {r['error']}\n")
        
        f.write("\n## 📋 Detailed Results\n")
        f.write("| Source | Status | Duration | Note |\n")
        f.write("|---|---|---|---|\n")
        for r in results:
            status = "✅ PASS" if r['success'] else "❌ FAIL"
            error_msg = r['error'] if r['error'] else ""
            f.write(f"| {r['source']} | {status} | {r['duration']:.1f}s | {error_msg} |\n")
            
    print(f"\nTest passed: {len(passed)}/{len(results)}")
    print(f"Report saved to: {summary_path}")

if __name__ == "__main__":
    main()
