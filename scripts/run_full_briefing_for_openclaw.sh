#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_ROOT="$(cd "$REPO_DIR/.." && pwd)"
TASK_STATE_PY="$OPENCLAW_ROOT/scripts/task_state.py"
PROFILE="${1:-}"
CHANNEL_ID="${OPENCLAW_BRIEFING_CHANNEL_ID:-1486008443583332382}"
TODAY_UTC="$(date -u +%F)"
TASK_ID="full-${PROFILE}-${TODAY_UTC}"
RUN_KEY="full-${PROFILE}:${TODAY_UTC}"
DEDUPE_KEY="discord:${CHANNEL_ID}:${PROFILE}:${TODAY_UTC}"

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

python3 "$TASK_STATE_PY" start \
  --task-id "$TASK_ID" \
  --task-type "full_briefing" \
  --run-key "$RUN_KEY" \
  --source cron \
  --status running \
  --step generating \
  --delivery-mode direct_message_tool \
  --delivery-status pending \
  --delivery-dedupe-key "$DEDUPE_KEY" \
  --channel-provider discord \
  --channel-target "$CHANNEL_ID" >/dev/null

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

if [[ $STATUS -eq 0 && -f "$MD_OUT" ]]; then
  python3 "$TASK_STATE_PY" generated \
    --task-id "$TASK_ID" \
    --artifact-path "$MD_OUT" \
    --content-file "$MD_OUT" \
    --content-format markdown \
    --step awaiting_delivery \
    --delivery-status pending \
    --delivery-dedupe-key "$DEDUPE_KEY" \
    --note "full briefing generated for delivery" >/dev/null
else
  python3 "$TASK_STATE_PY" update \
    --task-id "$TASK_ID" \
    --status failed \
    --step generation_failed \
    --error "wrapper exit code $STATUS" \
    --note "briefing wrapper did not produce deliverable artifact" >/dev/null || true
fi

exit "$STATUS"
