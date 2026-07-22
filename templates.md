# 🗞️ News Aggregator 指令菜单

请回复 **序号** 执行任务。所有报告均自动保存到 `reports/YYYY-MM-DD/` 并以中文呈现。

---

### 🎯 核心新闻源

| # | 名称 | 命令 |
|---|---|---|
| 1 | 🦄 硅谷热点 (Hacker News) | `--source hackernews` |
| 2 | 🐙 开源趋势 (GitHub Trending) | `--source github` |
| 3 | 🚀 创投快讯 (36Kr) | `--source 36kr` |
| 4 | 🐱 产品猎人 (Product Hunt) | `--source producthunt` |
| 5 | 🤓 极客社区 (V2EX) | `--source v2ex` |
| 6 | 🐧 腾讯科技 (Tencent News) | `--source tencent` |
| 7 | 📈 华尔街见闻 (WallStreetCN) | `--source wallstreetcn` |
| 8 | 🔴 微博热搜 (Weibo) | `--source weibo` |
| 9 | 🤗 HF 每日论文 (Hugging Face) | `--source huggingface` |

---

### 📧 AI 行业内参

| # | 名称 | 命令 |
|---|---|---|
| 10 | 🧪 Latent Space AINews (swyx) | `--source latentspace_ainews` |
| 11 | ChinAI (Jeffrey Ding) | `--source chinai` |
| 12 | Memia (Ben Reid) | `--source memia` |
| 13 | Ben's Bites | `--source bensbites` |
| 14 | One Useful Thing (Ethan Mollick) | `--source oneusefulthing` |
| 15 | Interconnects (Nathan Lambert) | `--source interconnects` |
| 16 | AI to ROI | `--source aitoroi` |
| 17 | KDnuggets | `--source kdnuggets` |
| 18 | 🧠 全部 AI 内参聚合 | `--source ai_newsletters --limit 3` |

---

### ✍️ 深度思考 & 播客

| # | 名称 | 命令 |
|---|---|---|
| 19 | Paul Graham | `--source paulgraham` |
| 20 | Wait But Why | `--source waitbutwhy` |
| 21 | James Clear | `--source jamesclear` |
| 22 | Farnam Street | `--source farnamstreet` |
| 23 | Scott Young | `--source scottyoung` |
| 24 | Dan Koe | `--source dankoe` |
| 25 | 📚 全部文章聚合 | `--source essays --limit 3` |
| 26 | Lex Fridman Podcast | `--source lexfridman` |
| 27 | Latent Space (swyx) | `--source latentspace` |
| 28 | 80,000 Hours | `--source 80000hours` |
| 29 | 🎧 全部播客聚合 | `--source podcasts --limit 3` |

---

### ☕️ 每日早报 (Daily Briefings)

| # | 名称 | 命令 |
|---|---|---|
| 30 | 🌅 综合早报 (General) | `daily_briefing.py --profile general --no-save` |
| 31 | 💰 财经早报 (Finance) | `daily_briefing.py --profile finance --no-save` |
| 32 | 🤖 科技早报 (Tech) | `daily_briefing.py --profile tech --no-save` |
| 33 | 🍉 吃瓜早报 (Social) | `daily_briefing.py --profile social --no-save` |
| 34 | 🧠 AI 深度日报 (AI Daily) | `daily_briefing.py --profile ai_daily --no-save` |
| 35 | 📚 深度阅读清单 | `daily_briefing.py --profile reading_list --no-save` |

---

### 🆕 扩展源 (v2)

| # | 名称 | 命令 |
|---|---|---|
| 36 | 🦞 Lobsters 技术深度 | `--source lobsters` |
| 37 | 👩‍💻 Dev.to 开发者热门 | `--source devto` |
| 38 | 📜 arXiv AI 最新论文 (cs.AI/CL/LG) | `--source arxiv` |
| 39 | 📕 少数派 (sspai) | `--source sspai` |
| 40 | 💻 InfoQ 中文 (软件工程/AI) | `--source infoq_cn --deep` |

---

### 🎯 AI 精选聚合 (v3) —— 二次精选，密度最高

> 这一档是别人的编辑团队替你筛过的 AI 高价值内容，单源信息密度顶 5-10 个原始信源。

| # | 名称 | 命令 |
|---|---|---|
| 41 | 🔥 AIHOT 中文 AI 精选（跨源 + 中文编辑稿） | `--source aihot` |
| 42 | 📨 TLDR AI（英文日刊，每天 5-10 主题摘要） | `--source tldr_ai` |
| 43 | 📜 Import AI by Jack Clark（英文周刊深度评论） | `--source import_ai --deep` |
| 44 | 🌐 AI 精选三件套（一次拉全） | `--source aihot,tldr_ai,import_ai` |

---

### 🔧 自定义订阅源

| # | 名称 | 命令 |
|---|---|---|
| 45 | 🔧 我的订阅源 (OPML) | `--source user` |

> 💡 **首次使用 OPML（45）**：先 `cp user_sources.opml.example user_sources.opml`，编辑里面的 `<outline xmlUrl="...">` 加自己的源；或从 Feedly/Inoreader 导出 OPML 覆盖即可。

---

### 🌍 国际新闻源

| # | 名称 | 命令 |
|---|---|---|
| 46 | 🌍 国际新闻聚合 (最近 24h) | `--source international --limit 20` |
| 47 | 📰 BBC Top News (最近 24h) | `--source bbc_top` |
| 48 | 🌐 BBC World (最近 24h) | `--source bbc_world` |
| 49 | 🈶 BBC 中文 (最近 24h) | `--source bbc_chinese` |
| 50 | 🗞️ The Guardian World (最近 24h) | `--source guardian_world` |
| 51 | 🛰️ Al Jazeera (最近 24h) | `--source aljazeera` |
| 52 | 🇫🇷 France 24 (最近 24h) | `--source france24` |
| 53 | 🧭 Reuters fallback (Google News RSS, 最近 24h) | `--source reuters` |

> 💡 **输出与时间窗口**：国际新闻源必须按统一报告模板输出；抓取只保留最近 24 小时内容，不用旧闻补位。`reuters` 使用 Google News RSS 的 `site:reuters.com` 检索结果。Reuters 官方公开 RSS 不稳定；如有 Reuters Connect 账号，可把 authenticated RSS 放进 OPML。

---

### 🔀 自由组合

直接指定多个源，用逗号分隔：

```
hackernews,github,wallstreetcn
```

例如：*"帮我看看 HN 和 GitHub 今天有什么热点"* → Agent 自动执行 `--source hackernews,github`

---

**✨ 请输入序号 (1-53) 或源名组合来执行**
