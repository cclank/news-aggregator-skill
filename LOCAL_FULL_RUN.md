# Local Full Briefing Run

Use local full runs for heavy briefing jobs instead of OpenClaw cron agentTurn.

## Prerequisites

```bash
cd /Users/qihan/.openclaw/workspace/news-aggregator-skill
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Full Tech Briefing

```bash
cd /Users/qihan/.openclaw/workspace/news-aggregator-skill
bash scripts/run_full_briefing_local.sh tech --deep-top-n 3 --max-age-minutes 1440
```

Outputs:
- `reports/manual/tech_full.json`
- `reports/manual/tech_full.md`

## Full AI Daily

```bash
cd /Users/qihan/.openclaw/workspace/news-aggregator-skill
bash scripts/run_full_briefing_local.sh ai_daily --deep-top-n 5 --max-age-minutes 2880
```

Outputs:
- `reports/manual/ai_daily_full.json`
- `reports/manual/ai_daily_full.md`

## Notes

- This path uses `.venv/bin/python` explicitly to avoid shell activation issues.
- Prefer local full runs for heavy jobs; keep OpenClaw cron on lightweight digests.
- You can override the output directory:

```bash
bash scripts/run_full_briefing_local.sh tech --outdir ./reports/custom
```
