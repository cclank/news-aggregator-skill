#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILE="${1:-general}"
if [[ $# -gt 0 ]]; then
  shift
fi

if [[ -f "$REPO_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_DIR/.venv/bin/activate"
elif [[ -f "$REPO_DIR/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_DIR/venv/bin/activate"
fi

OUT_DIR="$REPO_DIR/reports/openclaw"
JSON_OUT="$OUT_DIR/${PROFILE}_briefing.json"
MD_OUT="$OUT_DIR/${PROFILE}_briefing.md"
HEALTH_OUT="$OUT_DIR/source_health.json"
mkdir -p "$OUT_DIR"

set +e
SUMMARY="$(
  python3 "$SCRIPT_DIR/daily_briefing.py" \
    --profile "$PROFILE" \
    --json-out "$JSON_OUT" \
    --md-out "$MD_OUT" \
    --health-out "$HEALTH_OUT" \
    --stdout-summary \
    --no-save \
    "$@"
)"
STATUS=$?
set -e

echo "$SUMMARY"
exit "$STATUS"
