# 💰 Daily Finance Briefing Instructions (今日财经早报)

> **INPUT**: JSON object with `market_overview`, `china_finance`, `global_finance`, `crypto` sections.
> **OUTPUT**: A professional financial analysis report.

---

## 🎯 Focus Areas
1.  **Market Sentiment**: Bull/Bear signals, VIX, fear/greed indicators.
2.  **Policy Shifts**: Central bank decisions (Fed/PBOC), extensive regulations.
3.  **Big Tech Earnings**: FAANG, BAT earnings reports impacting the market.
4.  **Macro Trends**: Inflation (CPI/PPI), Employment, GDP.

## ⚠️ Anti-Laziness Protocol
1.  **Volume**: Output MUST contain at least **20 distinct items**.
1.  **Volume**: Output MUST contain at least **20 distinct items**.
2.  **Synthesis**: Do not just list headlines. Group them by "Macro", "Sector", "Crypto".
3.  **Deep Insight (CRITICAL)**: "Market Insight" must go beyond surface level.
    *   **Bad**: "This is good for AI."
    *   **Good**: "Signals a capital rotation from hardware to software layers; likely to boost SaaS valuations by 10-15% in Q3."
    *   **Bad**: "Fed raised rates."
    *   **Good**: "25bps hike was priced in, but the hawkish tone on 2025 cuts triggered a 2% drop in 10Y Treasuries, pressuring growth stocks."

## 📝 Report Structure

### Part 1: 🌏 Macro & Market Overview (宏观与大盘)
*   **Data Source**: WallstreetCN, Global Finance
*   **Format**:
*   **Format (Strict 4-Line Block)**:
    ```markdown
    #### 1. [Title (Translated)](original_url)
    > **Time**: 09:48 | **Impact**: 🔴 Bearish / 🟢 Bullish | **Heat**: 🔥 999
    > **Summary**: Concise summary in Chinese.
    > **Deep Dive**: 💡 **Insight**: [Deep analysis of market implications, quantitative impact, or connecting dots].
    ```

### Part 2: 🇨🇳 China Market Deep Dive (A股/港股/中概)
*   **Data Source**: 36Kr Finance, Tencent Finance
*   **Focus**: Regulatory changes, IPOs, Sector rotations.

### Part 3: ₿ Crypto & Future Tech (加密与前沿)
*   **Data Source**: Hacker News (Crypto keywords), WallstreetCN
*   **Focus**: Bitcoin ETF, Web3 policy, major hacks or upgrades.
