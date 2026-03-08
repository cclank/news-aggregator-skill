# 📝 Engineering Mistake Log (犯错笔记)

## 📌 Issue: WallStreetCN Timestamp Ambiguity (2026-01-24)

### 1. The Error (错误现场)
- **Problem**: The AI report stated "OpenAI Revenue... 1h ago", but the actual event was ~12h ago.
- **My Code**:
  ```python
  time_str = datetime.fromtimestamp(ts).strftime('%H:%M') if ts else ""
  # Output: "09:35"
  ```
- **The Result**: The AI received "Time: 09:35" at 21:30. Lacking the date, it possibly interpreted it as "09:35 PM" (Future?) or just "21:35" (Recent?), or generalized incorrectly. It calculated "1h ago" erroneously.

### 2. The Root Cause (根本原因)
- **Data Loss**: Converting a Unix timestamp (absolute) to `HH:MM` (relative/cyclic) destroys crucial date information.
- **Context Dependent**: "09:35" is only meaningful if you *know* it's today. If the news was from yesterday 09:35, the string is identical, making it impossible to distinguish "12h ago" from "36h ago".

### 3. The Fix (修复方案)
- **Absolute Time**: ALWAYS use full date-time format for machine processing.
  ```python
  time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
  # Output: "2026-01-24 09:35"
  ```
- **Lesson**: Don't format for "Human Readability" in the raw data layer. Let the UI/Presentation layer (Markdown generation) decide how to display it ("1h ago"). The data layer must remain precise.

---

## 📌 Issue: Algolia API Query Failure (2026-01-24)

### 1. The Error (错误现场)
I attempted to construct a search query for the Algolia HN API by simply joining keywords with `OR`.
- **My Code**: 
  ```python
  query_str = " OR ".join(keywords)
  # Resulted in: "AI OR LLM OR Github Copilot OR OpenAI"
  ```
- **The Result**: The API returned **0 hits** for this query, despite plenty of data existing.

### 2. The Root Cause (根本原因)
- **Syntax Ignorance**: I assumed Algolia's search engine would intelligently handle multi-word phrases (like "Github Copilot") within a boolean string without quotes. 
- **Tokenization Ambiguity**: In many search engines, `A OR B C` is interpreted as `A OR (B AND C)`. The phrase `Github Copilot` (with a space) broke the `OR` chain logic or was malformed for the specific `search_by_date` endpoint parser.
- **Lack of Verification**: I deployed this change without a dedicated unit test for the query string construction, assuming "it's just a string join".

### 3. The Fix (修复方案)
- **Quoted Phrases**: Explicitly wrap multi-word terms in quotes.
  ```python
  passed_keywords = [f'"{k}"' if ' ' in k else k for k in keywords]
  query_str = " OR ".join(passed_keywords)
  # Result: "AI OR LLM OR \"Github Copilot\" OR OpenAI"
  ```
- **Fallback Mechanism**: Added a "retry with simple query" logic. If the complex boolean query returns 0 hits, the script now automatically tries searching for just the first keyword (e.g., "AI") to ensure we get *some* relevant data rather than empty json.

### 4. Lessons Learned (教训)
1.  **Don't Guess APIs**: Search API syntaxes (Solr, Elasticsearch, Algolia) vary subtly. Always verify complex boolean queries in a debug script first.
2.  **Empty Data is Dangerous**: For an AI Agent, "Empty Data" is the mother of Hallucination. If a fetcher returns 0 items, the AI will often try to "help" by inventing them.
3.  **Fail Gracefully**: Hard filters (complex queries) usually need a soft fallback (broad queries).

---

## 📌 Issue: AI Logical Phrasing Failure (2026-01-24)

### 1. The Error (错误现场)
- **Text**: "U23国足这次杀入决赛圈（虽然半决赛赢了）..."
- **Problem**: The connector "虽然" (although) creates a nonsensical contrast. Winning a semi-final is the *cause* of entering the final, not a contradiction.
- **Why**: The AI likely tried to be "chatty" or "nuanced" but failed, possibly attempting to say "Although it's just U23..." or "Although the final hasn't happened yet..." but truncated the thought.

### 2. The Fix (修复方案)
- **Immediate**: Manually corrected to "半决赛大胜晋级决赛" (Won semis, advanced to finals).
- **Verification**: User challenged "How do you know they won big?".
- **Fact Check**: Performed web search. Validated: China U23 beat Vietnam U23 3-0 on Jan 20th. (3-0 qualifies as "Big Win").
- **Lesson**: **Grammar fixes are also Fact claims.** When changing "Although A, B" to "Because A (Big), B", I added the qualifier "Big". Even if it turns out true, I should have verified *before* writing it to avoid being questioned.

### 3. Prevention (预防)
- **Prompting**: Direct the model to use simple, declarative sentences ("SVO") for news summaries to avoid logic traps like "Although/However" when the causal link is weak.
75: 
76: ---
77: 
78: ## 📌 Issue: Stale Cache Hallucination | 陈旧缓存误导 (2026-02-17)
79: 
80: ### 1. The Error (错误现场)
81: - **Problem**: The AI generated a WallStreetCN report with dates from **2026-01-27**, while the current date was **2026-02-17**.
82: - **Step**: I ran the fetcher, but the report generator script was missing. I pro-actively searched the filesystem for "raw data" and found `wallstreetcn_raw.json` in the root directory.
83: - **Result**: The file was a legacy artifact from a month ago. I assumed it was fresh and used it for the report.
84: 
85: ### 2. The Root Cause (根本原因)
86: - **Heuristic Bias**: "If a file exists in the root with a matching name, it's probably the current output." This assumption is dangerous in long-lived or shared workspaces.
87: - **Ignoring Primary Evidence**: The CLI tool output actually contained the correct 02-17 data, but I preferred reading a "file" for stability during Markdown generation and chose the wrong one.
88: - **SKILL.md Deviation**: `SKILL.md` specifies that reports/data go to `reports/YYYY-MM-DD/`. I looked in the project root instead, which is not the standard output path for this skill.
89: 
90: ### 3. Prevention (预防)
91: 1.  **CLI Output First**: Always prioritze stdout of the current tool execution as the ultimate source of truth.
92: 2.  **Verify Timestamp**: Before reading any "raw" or "cache" file, check its last modified time or internal date fields.
93: 3.  **Strict Path Adherence**: Follow the data storage patterns defined in documentation (`reports/` folder) rather than guessing where temporary files might be.
