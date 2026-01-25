---
name: news-aggregator-skill
description: "Comprehensive news aggregator that fetches, filters, and deeply analyzes real-time content from 8 major sources: Hacker News, GitHub Trending, Product Hunt, 36Kr, Tencent News, WallStreetCN, V2EX, and Weibo. Best for 'daily scans', 'tech news briefings', 'finance updates', and 'deep interpretations' of hot topics."
---

# News Aggregator Skill

Fetch real-time hot news from multiple sources.

## ⚠️ Global Rules (Strict Enforcement)

1.  **Mandatory Time Display**: **EVERY** report item, regardless of the source or command used (Single Source, Morning Routine, or Combinations), **MUST** include the precise publication time or relative time (e.g., "10:30", "2 hours ago", "2024-01-20").
    *   **NEVER** skip the time field.
    *   **NEVER** hallucinate the time. If it's missing in the JSON, mark it as "Unknown Time".
    *   For "Real-time" or "Trending" lists (e.g., Weibo, GitHub), preserve the "Real-time" or "Today" tag.

2.  **Logical Integrity (Anti-Hallucination)**:
    *   **NO INVENTED CAUSALITY**: Do not use "Because", "Although", "Due to", or "However" unless the source text EXPLICITLY supports this relationship.
    *   **SVO Preference**: Use simple Subject-Verb-Object sentences. Avoid complex compound sentences that force you to invent logical bridges.
    *   **Fact Check**: If you fix grammar, you arguably make a claim. If you change "A, B" to "A caused B", you MUST be 100% sure. When in doubt, leave it as two separate sentences.

## Tools

### fetch_news.py

**Usage:**

```bash
### Single Source (Limit 10)
```bash
### Global Scan (Option 12) - **Broad Fetch Strategy**
> **NOTE**: This strategy is specifically for the "Global Scan" scenario where we want to catch all trends.

```bash
#  1. Fetch broadly (Massive pool for Semantic Filtering)
python3 scripts/fetch_news.py --source all --limit 15 --deep

# 2. SEMANTIC FILTERING:
# Agent manually filters the broad list (approx 120 items) for user's topics.
```

### Single Source & Combinations (Smart Keyword Expansion)
**CRITICAL**: You MUST automatically expand the user's simple keywords to cover the entire domain field.
*   User: "AI" -> Agent uses: `--keyword "AI,LLM,GPT,Claude,Generative,Machine Learning,RAG,Agent"`
*   User: "Android" -> Agent uses: `--keyword "Android,Kotlin,Google,Mobile,App"`
*   User: "Finance" -> Agent uses: `--keyword "Finance,Stock,Market,Economy,Crypto,Gold"`

```bash
# Example: User asked for "AI news from HN" (Note the expanded keywords)
python3 scripts/fetch_news.py --source hackernews --limit 20 --keyword "AI,LLM,GPT,DeepSeek,Agent" --deep
```

### Specific Keyword Search
Only use `--keyword` for very specific, unique terms (e.g., "DeepSeek", "OpenAI").
```bash
python3 scripts/fetch_news.py --source all --limit 10 --keyword "DeepSeek" --deep
```

**Arguments:**

- `--source`: One of `hackernews`, `weibo`, `github`, `36kr`, `producthunt`, `v2ex`, `tencent`, `wallstreetcn`, `all`.
- `--limit`: Max items per source (default 10).
- `--keyword`: Comma-separated filters (e.g. "AI,GPT").
- `--deep`: **[NEW]** Enable deep fetching. Downloads and extracts the main text content of the articles.

**Output:**
JSON array. If `--deep` is used, items will contain a `content` field associated with the article text.

### daily_briefing.py (Unified Morning Routine)
Run this single script to fetch all necessary data for the morning briefing.

```bash
python3 scripts/daily_briefing.py --profile [general|finance|tech|social] > briefing_data.json
```

**Workflow:**
1.  **Execute** `scripts/daily_briefing.py` with the desired profile.
2.  **READ** the corresponding instruction file in `instructions/`:
    *   `general` -> `instructions/briefing_general.md`
    *   `finance` -> `instructions/briefing_finance.md`
    *   `tech` -> `instructions/briefing_tech.md`
    *   `social` -> `instructions/briefing_social.md`
3.  **Generate** the report strictly satisfying the volume constraints in the instruction file.



## Interactive Menu

When the user says **"news-aggregator-skill 如意如意"** (or similar "menu/help" triggers):
1.  **READ** the content of `templates.md` in the skill directory.
2.  **DISPLAY** the list of available commands to the user exactly as they appear in the file.
3.  **GUIDE** the user to select a number or copy the command to execute.
4.  **Morning Routine (Recommended)**: For the best quality, guide the user to run the "Three-Course Morning Routine" (Options 12, 13, 14) **sequentially**, rather than combining them into one request. This ensures each report gets full AI Context attention.

### Smart Time Filtering & Reporting (CRITICAL)
If the user requests a specific time window (e.g., "past X hours") and the results are sparse (< 5 items):
1.  **Prioritize User Window**: First, list all items that strictly fall within the user's requested time (Time < X).
2.  **Smart Fill**: If the list is short, you MUST include high-value/high-heat items from a wider range (e.g. past 24h) to ensure the report provides at least 5 meaningful insights.
    *   **Annotation**: Clearly mark these older items (e.g., "⚠️ 18h ago", "🔥 24h Hot") so the user knows they are supplementary.
3.  **High Value**: Always prioritize "SOTA", "Major Release", or "High Heat" items even if they slightly exceed the time window.
4.  **GitHub Trending Exception**: For purely list-based sources like **GitHub Trending**, strictly return the valid items from the fetched list (e.g. Top 10). **List ALL fetched items**. Do **NOT** perform "Smart Fill".
    *   **Deep Analysis (Required)**: For EACH item, you **MUST** leverage your AI capabilities to analyze:
        *   **Core Value (核心价值)**: What specific problem does it solve? Why is it trending?
        *   **Inspiration (启发思考)**: What technical or product insights can be drawn?
        *   **Scenarios (场景标签)**: 3-5 keywords (e.g. `#RAG #LocalFirst #Rust`).

### 6. Response Guidelines (CRITICAL)

**Format & Style:**
- **Language**: Simplified Chinese (简体中文). **(IMPORTANT: Translate Title, Summary, and Analysis into Chinese)**
- **Style**: Magazine/Newsletter style (e.g., "The Economist" or "Morning Brew" vibe). Professional, concise, yet engaging.
- **Structure**:
    - **Global Headlines**: **Top 15-20** critical stories across all domains. (For Global Scan, aim for comprehensive coverage, not just a few highlights).
    - **Tech & AI**: Specific section for AI, LLM, and Tech items.
    - **Finance / Social**: Other strong categories if relevant.
- **Item Format Template (STRICT)**:
    *Switching to List Format for better rendering. Do NOT use Blockquotes (>).*
    ```markdown
    #### 1. [Title (Translated)](https://original-url.com)
    - **Source**: SourceName | **Time**: X hours ago | **Heat**: 🔥 999
    - **Summary**: [Hacker News Discussion](hn_url) (if valid) + One sentence summary in Chinese.
    - **Deep Dive**: 💡 **Insight**: Deep analysis, market impact, or technical context.
    ```
    - **Zero Hallucination & Diligence (CRITICAL)**:
        - **Truth**: You must **ONLY** use data present in the provided JSON. **NEVER** invent news items.
        - **Diligence**: Do NOT use "No significant updates" as an excuse to skip analysis. You MUST exhaustively review the JSON.
        - **Fallback**: Only state "No significant updates" if the fetching script truly returned 0 relevant items. **If the source is empty, state so clearly (e.g., "Source returned 0 items"). DO NOT fabricate news to fill the space.**
- **Key Rules**:
    - **Hacker News (HN)**: For HN items, you **MUST** provide the link to the HN discussion page (comments) in addition to the original article link.
    - **Translation**: Translate titles, summaries, and deep dive analysis into **Simplified Chinese**.
    - **Title**: MUST be a clickable link. Do NOT use plain text titles.
    - **Metadata**: Source, Time, and Heat MUST be visible immediately below the title.
    - **Time**: **MANDATORY FIELD**. You MUST include the time provided in the JSON (e.g., "2 hours ago", "2024-01-20", "Real-time", "Today").
        - If the JSON says "Real-time", "Today", or "Hot", display it exactly as is.
        - **DO NOT SKIP THIS FIELD**.
    - **Deep Interpretation (Bulleted)**: 2-3 bullet points explaining *why* this matters, technical details, or context. (Required for "Deep Scan").

**Output Artifact:**
- Always save the full report to a date-based subdirectory in `reports/` (e.g., `reports/YYYY-MM-DD/filename_HHMM.md`). If the directory does not exist, you MUST create it first.
- **IMPORTANT**: The Agent (You) are responsible for formatting the JSON output into Markdown. **Do not rely on external scripts for summarization.**
- Present the full report content to the user in the chat.
