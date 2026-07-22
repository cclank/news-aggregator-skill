---
name: news-aggregator-skill
description: "Comprehensive news aggregator that fetches, filters, and deeply analyzes real-time content from 44+ sources including Hacker News, Lobsters, Dev.to, GitHub, arXiv, Hugging Face Papers, AIHOT, TLDR AI, Import AI, BBC, The Guardian, Al Jazeera, France 24, Reuters fallback, AI Newsletters, WallStreetCN, Weibo, 少数派, InfoQ 中文, Podcasts, and user-defined OPML feeds. Use when user requests 'daily scans', 'tech news', 'finance updates', 'AI briefings', 'international news', 'deep analysis', or says '如意如意' to open the interactive menu."
---

# News Aggregator Skill

Fetch real-time hot news from 44+ sources (including international news + AI curated aggregators + user-defined OPML feeds), generate deep analysis reports in Chinese.

---

## 🔄 Universal Workflow (3 Steps)

**Every** news request follows the same workflow, regardless of source or combination:

### Step 1: Fetch Data
```bash
# Single source
python3 scripts/fetch_news.py --source <source_key> --no-save

# Multiple sources (comma-separated)
python3 scripts/fetch_news.py --source hackernews,github,wallstreetcn --no-save

# All sources (broad scan)
python3 scripts/fetch_news.py --source all --limit 15 --deep --no-save

# With keyword filter (auto-expand: "AI" → "AI,LLM,GPT,Claude,Agent,RAG")
python3 scripts/fetch_news.py --source hackernews --keyword "AI,LLM,GPT" --deep --no-save

# Machine-friendly run output
python3 scripts/fetch_news.py --source hackernews --json-out /tmp/hn.json --md-out /tmp/hn.md --stdout-summary

# Telegram-friendly markdown
python3 scripts/fetch_news.py --source hackernews,github --format telegram --md-out /tmp/scan_telegram.md
```

### Step 2: Generate Report
Read the output JSON and format **every** item using the **Unified Report Template** below. Translate all content to **Simplified Chinese**.

### Step 3: Save & Present
Save the report to `reports/YYYY-MM-DD/<source>_report.md`, then display the full content to the user.

---

## 📰 Unified Report Template

**All sources use this single template.** Show/hide optional fields based on data availability.

```markdown
#### N. [标题 (中文翻译)](https://original-url.com)
- **Source**: 源名 | **Time**: 时间 | **Heat**: 🔥 热度值
- **Links**: [Discussion](hn_url) | [GitHub](gh_url)     ← 仅在数据存在时显示
- **Summary**: 一句话中文摘要。
- **Deep Dive**: 💡 **Insight**: 深度分析（背景、影响、技术价值）。
```

### Source-Specific Adaptations

Only the **differences** from the universal template:

| Source | Adaptation |
|---|---|
| **Hacker News** | **MUST** include `[Discussion](hn_url)` link |
| **GitHub** | Use `🌟 Stars` for Heat, add `Lang` field, add `#Tags` in Deep Dive |
| **Hugging Face** | Use `🔥 +N` upvotes for Heat, include `[GitHub](url)` if present, write **深度解读** (not just translate abstract) |
| **Weibo** | Preserve exact heat text (e.g. "108万") |
| **AIHOT** | `summary` 已是中文编辑稿，**直接引用**不要再翻译；Heat 字段为空也别造数据；保留 `推荐理由` 风格的一句话点评 |
| **TLDR AI** | 单条标题往往是多主题混合（`Topic A 💻, Topic B ⚡, Topic C ⛪`），**拆成 bullet 列出每个主题**；`summary` 是 HTML 段落，需要拆出每个主题对应的一两句概述 |
| **Import AI** | 周刊长文，标题形如 `Import AI 458: 主题1; 主题2; 主题3`。**建议默认配 `--deep`**，否则 RSS summary 只是开头几句；Deep Dive 直接提炼 Jack Clark 的核心观点而非平铺事实 |
| **International News** | **MUST** use the Unified Report Template for every item；只使用最近 24h RSS 条目，不用更早新闻 Smart Fill；英文标题与摘要翻译成简体中文，保留原始媒体名与链接；同一事件多家媒体重复时可合并观点但不能合并链接 |
| **Reuters** | `reuters` 使用 Google News RSS 的 `site:reuters.com` fallback；报告里保留 `Reuters (Google News fallback)` source，不要写成官方公开 RSS |

---

## 🛠️ Tools

### fetch_news.py

| Arg | Description | Default |
|---|---|---|
| `--source` | Source key(s), comma-separated. See table below. | `all` |
| `--limit` | Max items per source | `15` |
| `--keyword` | Comma-separated keyword filter | None |
| `--deep` | Download article text for richer analysis | Off |
| `--deep-top-n` | Only deep-enrich the first N items | All items |
| `--max-age-minutes` | Filter out stale items when publish time is parseable | None |
| `--save` | Force save to reports dir | Auto for single source |
| `--outdir` | Custom output directory | `reports/YYYY-MM-DD/` |
| `--json-out` | Write full run payload JSON to a fixed path | None |
| `--md-out` | Write Markdown summary to a fixed path | None |
| `--stdout-summary` | Print one-line JSON summary instead of full payload | Off |
| `--format` | Markdown format: `full` or concise `telegram` | `full` |
| `--health-out` | Stable per-source health state JSON path | `reports/source_health.json` |

### Available Sources (44+ with user OPML)

| Category | Key | Name |
|---|---|---|
| **Global News** | `hackernews` | Hacker News |
| | `36kr` | 36氪 |
| | `wallstreetcn` | 华尔街见闻 |
| | `tencent` | 腾讯新闻 |
| | `weibo` | 微博热搜 |
| | `v2ex` | V2EX |
| | `producthunt` | Product Hunt |
| | `github` | GitHub Trending |
| **Search Adapters** | `ddgs` | DuckDuckGo Search (text) |
| | `ddgs_news` | DDGS News (experimental) |
| | `tavily` | Tavily Search (stable fallback) |
| **Tech Community** (v2) | `lobsters` | Lobsters |
| | `devto` | Dev.to |
| **AI/Tech** | `huggingface` | HF Daily Papers |
| | `arxiv` | arXiv (cs.AI/cs.CL/cs.LG, v2) |
| | `ai_newsletters` | All AI Newsletters (aggregate) |
| | `bensbites` | Ben's Bites |
| | `interconnects` | Interconnects (Nathan Lambert) |
| | `oneusefulthing` | One Useful Thing (Ethan Mollick) |
| | `chinai` | ChinAI (Jeffrey Ding) |
| | `memia` | Memia |
| | `aitoroi` | AI to ROI |
| | `kdnuggets` | KDnuggets |
| **Chinese** (v2) | `sspai` | 少数派 |
| | `infoq_cn` | InfoQ 中文站（RSS 只给标题，**推荐配 `--deep`** 拿正文） |
| **AI Curated** (v3) | `aihot` | AIHOT 中文 AI 精选（跨源 + 中文编辑稿）|
| | `tldr_ai` | TLDR AI 英文日刊 |
| | `import_ai` | Import AI by Jack Clark 周刊（**推荐 `--deep`**）|
| **International News** | `international` | 最近 24h 国际新闻聚合（BBC / Guardian / Al Jazeera / France 24 / Reuters fallback）|
| | `bbc_top` | BBC Top News (24h) |
| | `bbc_world` | BBC World (24h) |
| | `bbc_chinese` | BBC 中文 (24h) |
| | `guardian_world` | The Guardian World (24h) |
| | `aljazeera` | Al Jazeera (24h) |
| | `france24` | France 24 (24h) |
| | `reuters` | Reuters via Google News RSS fallback (24h) |
| **Podcasts** | `podcasts` | All Podcasts (aggregate) |
| | `lexfridman` | Lex Fridman |
| | `80000hours` | 80,000 Hours |
| | `latentspace` | Latent Space |
| **Essays** | `essays` | All Essays (aggregate) |
| | `paulgraham` | Paul Graham |
| | `waitbutwhy` | Wait But Why |
| | `jamesclear` | James Clear |
| | `farnamstreet` | Farnam Street |
| | `scottyoung` | Scott Young |
| | `dankoe` | Dan Koe |
| **Custom** (v2) | `user` | Your OPML feeds (see below) |

### 自定义订阅源 (User OPML)

把你常看的 RSS/Atom 源写进 OPML，`--source user` 即可统一抓取。

**1. 放置 OPML 文件**（按优先级查找）：
- `~/.config/news-aggregator/user_sources.opml`（推荐，跨 skill 复用）
- `<skill_root>/user_sources.opml`（本仓库内）

**2. 文件格式**：标准 OPML 2.0，可直接从 Feedly / Inoreader / NetNewsWire 导出。参考 `user_sources.opml.example`：

```xml
<outline type="rss" text="Simon Willison" title="Simon Willison"
         xmlUrl="https://simonwillison.net/atom/everything/" />
```

只 `xmlUrl` 必填，其它可选。

**3. 运行**：`python3 scripts/fetch_news.py --source user --limit 15`


### daily_briefing.py (Morning Routines)

Pre-configured multi-source profiles:

```bash
python3 scripts/daily_briefing.py --profile <profile>
python3 scripts/daily_briefing.py --profile general --json-out /tmp/general.json --md-out /tmp/general.md --stdout-summary
python3 scripts/daily_briefing.py --profile general --format telegram --md-out /tmp/general_telegram.md
scripts/openclaw_run_briefing.sh general
```

Profiles are now loaded from `profiles/*.json`. Preserve existing profile names unless the user explicitly asks to add or rename one.

Search-source guidance:

- `ddgs`: use for local, no-key text search candidate recall
- `ddgs_news`: experimental news search, good for gray rollout and comparison runs
- `tavily`: keep as stable fallback until `ddgs_news` quality is proven

Profile file shape:

```json
{
  "name": "general",
  "sections": {
    "global_scan": {
      "enrich": true,
      "sources": [
        { "source": "hackernews", "limit": 5 },
        { "source": "github", "limit": 5, "keyword": "AI,LLM,GPT" }
      ]
    }
  }
}
```

| Profile | Sources | Instruction File |
|---|---|---|
| `general` | HN, 36Kr, GitHub, Weibo, PH, WallStreetCN | `instructions/briefing_general.md` |
| `finance` | WallStreetCN, 36Kr, Tencent | `instructions/briefing_finance.md` |
| `tech` | GitHub, HN, Product Hunt | `instructions/briefing_tech.md` |
| `social` | Weibo, V2EX, Tencent | `instructions/briefing_social.md` |
| `ai_daily` | HF Papers, AI Newsletters | `instructions/briefing_ai_daily.md` |
| `reading_list` | Essays, Podcasts | (Use universal template) |

**Workflow**: Execute script → Read corresponding instruction file → Generate report following both the instruction file AND the universal template.

### Unified Output Contract

Both entrypoints now emit a top-level run envelope:

- `run_at`
- `source` or `profile`
- `status`
- `sources_total`
- `sources_ok`
- `sources_failed`
- `failed_sources`
- `items`

Each item may include:

- `published_at_raw`
- `published_at_iso`
- `fetched_at`
- `age_minutes`
- `canonical_url`

Health state JSON now tracks at least:

- `updated_at`
- `sources.<source_key>.last_ok_at`
- `sources.<source_key>.last_error_at`
- `sources.<source_key>.last_error`
- `sources.<source_key>.consecutive_errors`

Canonicalization / dedupe notes:

- Strip fragments and common tracking query params such as `utm_*`, `fbclid`, `gclid`
- Normalize host casing and basic trailing slash / default port differences
- Deduplicate on `canonical_url` first, then normalized title when needed
- `daily_briefing.py` dedupes within each section; `fetch_news.py` dedupes within the current aggregated run

### Unified Exit Codes

- `0`: success with results
- `10`: success but empty results
- `20`: partial success, output generated, some sources failed
- `50`: critical failure
- `60`: timeout or missing dependency/environment

---

## ⚠️ Rules (Strict)

1. **Language**: ALL output in **Simplified Chinese (简体中文)**. Keep well-known English proper nouns (ChatGPT, Python, etc.).
2. **Time**: **MANDATORY** field. Never skip. If missing in JSON, mark as "Unknown Time". Preserve "Real-time" / "Today" / "Hot" as-is.
3. **Anti-Hallucination**: Only use data from the JSON. Never invent news items. Use simple SVO sentences. Do not fabricate causal relationships.
4. **Smart Keyword Expansion**: When user says "AI" → auto-expand to `"AI,LLM,GPT,Claude,Agent,RAG,DeepSeek"`. Similar expansions for other domains.
5. **Smart Fill**: If results < 5 items in a time window, supplement with high-value items from wider range. Mark supplementary items with ⚠️. **Exception**: International News sources are a hard 24h window; do not supplement with older items.
6. **Save**: Always save report to `reports/YYYY-MM-DD/` before displaying.

---

## 📋 Interactive Menu

When the user says **"如意如意"** or asks for "menu/help":

1. Read `templates.md`
2. Display the menu
3. Execute the user's selection using the **Universal Workflow** above

---

## Requirements

- Python 3.8+, `pip install -r requirements.txt`
- Playwright (for HF Papers & Ben's Bites): `playwright install chromium`
