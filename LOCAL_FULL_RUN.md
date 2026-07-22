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

## Full GitHub Briefing

```bash
cd /Users/qihan/.openclaw/workspace/news-aggregator-skill
bash scripts/run_full_github_local.sh
```

Outputs:
- `reports/manual/github_full.json`
- `reports/manual/github_full.md`

## OpenClaw handoff wrapper

If you want OpenClaw to send Telegram after a full local run, use this wrapper:

```bash
bash scripts/run_full_briefing_for_openclaw.sh tech --deep-top-n 3 --max-age-minutes 1440
bash scripts/run_full_briefing_for_openclaw.sh ai_daily --deep-top-n 5 --max-age-minutes 2880
```

It prints a single-line JSON summary to stdout, suitable for an OpenClaw task to parse, while writing full outputs to:
- `reports/openclaw-full/<profile>_full.json`
- `reports/openclaw-full/<profile>_full.md`

The wrapper also records restart-safe task state in `~/.openclaw/state/`:
- creates a task record before the run starts
- writes the generated markdown artifact on success
- creates a delivery record with a stable dedupe key for the Discord handoff

Recommended OpenClaw pattern:
1. Run `run_full_briefing_for_openclaw.sh`
2. Parse stdout JSON summary
3. If success/partial, read the generated Markdown file
4. Use the OpenClaw `message` tool to send Telegram
5. If failure, send only the compact error
6. After the send succeeds, mark the delivery as delivered with the same dedupe key

## Notes

- This path uses `.venv/bin/python` explicitly to avoid shell activation issues.
- Prefer local full runs for heavy jobs; keep OpenClaw cron on lightweight digests.
- You can override the output directory:

```bash
bash scripts/run_full_briefing_local.sh tech --outdir ./reports/custom
```
