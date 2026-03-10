#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

bash scripts/run_full_briefing_for_openclaw.sh github --deep-top-n 3 --max-age-minutes 1440 "$@"
