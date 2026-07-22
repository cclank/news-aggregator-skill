#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILE="${1:-}"
if [[ -z "$PROFILE" ]]; then
  echo "Usage: bash scripts/run_full_briefing_local.sh <profile> [--deep-top-n N] [--max-age-minutes N] [--outdir DIR]" >&2
  echo "Example: bash scripts/run_full_briefing_local.sh tech --deep-top-n 3 --max-age-minutes 1440" >&2
  exit 2
fi
shift || true

case "$PROFILE" in
  tech)
    DEFAULT_DEEP_TOP_N=3
    DEFAULT_MAX_AGE_MINUTES=1440
    ;;
  ai_daily)
    DEFAULT_DEEP_TOP_N=5
    DEFAULT_MAX_AGE_MINUTES=2880
    ;;
  general|finance|social|github|reading_list)
    DEFAULT_DEEP_TOP_N=0
    DEFAULT_MAX_AGE_MINUTES=1440
    ;;
  *)
    echo "Unsupported profile: $PROFILE" >&2
    echo "Supported: general finance tech social github ai_daily reading_list" >&2
    exit 2
    ;;
esac

OUT_DIR="$REPO_DIR/reports/manual"
DEEP_TOP_N="$DEFAULT_DEEP_TOP_N"
MAX_AGE_MINUTES="$DEFAULT_MAX_AGE_MINUTES"
PASS_THROUGH=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deep-top-n)
      DEEP_TOP_N="${2:?missing value for --deep-top-n}"
      shift 2
      ;;
    --max-age-minutes)
      MAX_AGE_MINUTES="${2:?missing value for --max-age-minutes}"
      shift 2
      ;;
    --outdir)
      OUT_DIR="${2:?missing value for --outdir}"
      shift 2
      ;;
    *)
      PASS_THROUGH+=("$1")
      shift
      ;;
  esac
done

PYTHON_BIN="$REPO_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing virtualenv Python: $PYTHON_BIN" >&2
  echo "Create it first with: python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt" >&2
  exit 60
fi

mkdir -p "$OUT_DIR"
JSON_OUT="$OUT_DIR/${PROFILE}_full.json"
MD_OUT="$OUT_DIR/${PROFILE}_full.md"

CMD=(
  "$PYTHON_BIN" "$SCRIPT_DIR/daily_briefing.py"
  --profile "$PROFILE"
  --json-out "$JSON_OUT"
  --md-out "$MD_OUT"
  --stdout-summary
)

if [[ "$DEEP_TOP_N" != "0" ]]; then
  CMD+=(--deep-top-n "$DEEP_TOP_N")
fi

if [[ -n "$MAX_AGE_MINUTES" ]]; then
  CMD+=(--max-age-minutes "$MAX_AGE_MINUTES")
fi

if [[ ${#PASS_THROUGH[@]} -gt 0 ]]; then
  CMD+=("${PASS_THROUGH[@]}")
fi

echo "[run_full_briefing_local] profile=$PROFILE"
echo "[run_full_briefing_local] json=$JSON_OUT"
echo "[run_full_briefing_local] md=$MD_OUT"
echo "[run_full_briefing_local] deep_top_n=$DEEP_TOP_N"
echo "[run_full_briefing_local] max_age_minutes=$MAX_AGE_MINUTES"

"${CMD[@]}"
