#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE="${1:-}"

if [[ -z "$PROFILE" ]]; then
  echo '{"status":"error","exit_code":2,"error":"missing profile","message":"Usage: bash scripts/run_full_briefing_for_openclaw.sh <profile> [extra args...]"}'
  exit 2
fi
shift || true

OUT_DIR="$REPO_DIR/reports/openclaw-full"
mkdir -p "$OUT_DIR"
JSON_OUT="$OUT_DIR/${PROFILE}_full.json"
MD_OUT="$OUT_DIR/${PROFILE}_full.md"

RUNNER="$SCRIPT_DIR/run_full_briefing_local.sh"
if [[ ! -x "$RUNNER" ]]; then
  chmod +x "$RUNNER"
fi

set +e
RAW_OUTPUT="$($RUNNER "$PROFILE" --outdir "$OUT_DIR" "$@" 2>&1)"
STATUS=$?
set -e

SUMMARY_LINE="$(printf '%s\n' "$RAW_OUTPUT" | tail -n 1)"
if printf '%s' "$SUMMARY_LINE" | grep -q '^{'; then
  python3 - <<'PY' "$SUMMARY_LINE" "$STATUS" "$JSON_OUT" "$MD_OUT"
import json, sys
summary = json.loads(sys.argv[1])
status = int(sys.argv[2])
json_out = sys.argv[3]
md_out = sys.argv[4]
summary['wrapper_exit_code'] = status
summary['json_out'] = json_out
summary['md_out'] = md_out
print(json.dumps(summary, ensure_ascii=False))
PY
else
  python3 - <<'PY' "$STATUS" "$JSON_OUT" "$MD_OUT" "$RAW_OUTPUT"
import json, sys
status = int(sys.argv[1])
json_out = sys.argv[2]
md_out = sys.argv[3]
raw = sys.argv[4]
print(json.dumps({
    'status': 'error' if status else 'success',
    'exit_code': status,
    'json_out': json_out,
    'md_out': md_out,
    'raw_output': raw[-4000:],
}, ensure_ascii=False))
PY
fi

exit "$STATUS"
