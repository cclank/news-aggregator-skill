# Schedule Morning Global Scan

The goal is to automate a global news scan at 6:30 AM daily. Since the AI agent cannot wake up to process the data, we will implement a "headless" reporting pipeline that fetches data and generates a readable Markdown report automatically.

## User Review Required

> [!NOTE]
> **AI Analysis Limitation**: The automated report will contained "raw" summaries fetched from the source. It will **not** contain the "Deep Dive" insights (Core Value, Inspiration, Scenarios) that I usually provide, as that requires my active intelligence.
> **Action Required**: You currently need to approve the `crontab` command to install the schedule.

## Proposed Changes

### Scripts

#### [NEW] [daily_scan.sh](file:///Users/lank/code/skillMake/news-aggregator-skill/scripts/daily_scan.sh)
- A bash script acting as the entry point.
- Activates the Python virtual environment.
- Runs `fetch_news.py` with `--source all --limit 15 --deep`.
- Pipes the output to a temporary JSON file.
- Calls `generate_basic_report.py` to convert JSON to Markdown.
- Saves the report in a date-based subdirectory `reports/YYYY-MM-DD/` with a timestamped filename.

#### [NEW] [generate_basic_report.py](file:///Users/lank/code/skillMake/news-aggregator-skill/scripts/generate_basic_report.py)
- A simple Python script.
- Reads JSON input from stdin or file.
- Formats it into the standard `SKILL.md` Markdown style (excluding the AI Deep Dive section).
- Outputs to stdout or file.

### System Configuration
- Use `crontab` to schedule `scripts/daily_scan.sh` at 06:30 daily.

## Verification Plan

### Automated Execution Test
- Run `bash scripts/daily_scan.sh` manually.
- Verify a new file `reports/YYYY-MM-DD/global_scan_HHMM.md` is created.
- Verify the content of the markdown file is readable and contains news from multiple sources.

### Manual Verification
- Check `crontab -l` after installation to confirm the job is listed.
