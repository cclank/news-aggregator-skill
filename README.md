# 🗞️ News Aggregator Skill

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/cclank/news-aggregator-skill.svg?style=social&label=Star)](https://github.com/cclank/news-aggregator-skill)
[![GitHub forks](https://img.shields.io/github/forks/cclank/news-aggregator-skill.svg?style=social&label=Fork)](https://github.com/cclank/news-aggregator-skill/network)

**全网科技/金融/AI深度新闻聚合助手，专为智能 Agent 打造的高效信息引擎。**

---

## ✨ 核心特性

- **🌍 全网多源聚合**：一站式覆盖跨越硅谷科技、中国创投、开源社区、金融市场以及顶级 AI 播客/硬核推文的 33 个高价值信源。
- **🚀 完美支持 OpenClaw**：专为原生大模型 Agent 平台（如 OpenClaw、Code Agent）深度定制，即插即用，沉浸式体验信息流。
- **🆓 开箱即用 (Zero-Config)**：纯净抓取，**无需配置任何第三方 API Key**，告别繁琐的环境变量和额度焦虑。
- **🧠 AI 智能深度阅读 (Deep Fetch)**：智能穿透防爬虫机制（内置 Playwright 绕过 Cloudflare），抓取完整正文内容交给大模型过滤、提炼与总结。
- **📰 场景化早报 (Daily Briefings)**：内置多套场景预设（综合早报、财经早报、科技早报、吃瓜早报、AI深度日报），一键生成杂志级排版的 Markdown 中文报告。
- **🗂️ 外置 Profile 配置**：早报 profile 现存放于 `profiles/*.json`，默认 profile 名称与行为保持兼容，便于 OpenClaw 侧配置化管理。
- **📨 Telegram 友好输出**：支持 `--format telegram` 输出更短的 Markdown，适合 Telegram 或其它消息推送渠道。
- **🩺 信源健康状态**：每次运行都会更新健康状态 JSON，记录 `last_ok_at`、`last_error_at`、`last_error`、`consecutive_errors`。
- **🔗 轻量 Canonical 去重**：基础 URL 归一化与去重内置在运行路径中，减少重复内容与 tracking 链接噪音。
- **🪄 魔法交互菜单**：支持通过专属口令唤醒全局交互式菜单，告别繁琐长难句，只需输入序号即可指哪打哪。

---

## 📚 聚合信源图谱

系统现已覆盖全球 **33** 个主流高价值信息渠道，随取随用：

### 🎯 核心新闻源
- **全球科技**：🦄 Hacker News (`hackernews`), 🐱 Product Hunt (`producthunt`)
- **开源进展**：🐙 GitHub Trending (`github`), 🤓 V2EX (`v2ex`)
- **国内风控**：🚀 36Kr (`36kr`), 🐧 腾讯科技 (`tencent`)
- **社会金融**：🔴 微博热搜 (`weibo`), 📈 华尔街见闻 (`wallstreetcn`)
- **AI 论文**：🤗 Hugging Face Papers (`huggingface`)

### 🔎 搜索适配源
- **DuckDuckGo Text Search** (`ddgs`) - 本地免 Key 文本检索，优先使用 `backend="duckduckgo"`，失败后退到 `auto`
- **DDGS News** (`ddgs_news`) - 实验性新闻检索，当前使用 `backend="auto"`，适合灰度验证，不建议单独替代稳定新闻链路
- **Tavily Search** (`tavily`) - 仍保留为稳定兜底搜索源，需要 `TAVILY_API_KEY`

### 📧 AI 行业内参 (Newsletters & Creators)
- **🧪 Latent Space AINews** (`latentspace_ainews`) - *（近期新增）*
- **ChinAI (Jeffrey Ding)** (`chinai`)
- **Memia (Ben Reid)** (`memia`)
- **Ben's Bites** (`bensbites`)
- **One Useful Thing (Ethan Mollick)** (`oneusefulthing`)
- **Interconnects (Nathan Lambert)** (`interconnects`)
- **AI to ROI & KDnuggets** 等...

### ✍️ 深度思考 & 播客
- **行业泰斗专栏**: Paul Graham, James Clear, Wait But Why, Scott Young...
- **顶级硬核播客**: Lex Fridman Podcast, Latent Space (swyx), 80,000 Hours...

---

## 📥 安装指南

### 第一步：安装到 Code Agent

选择以下任一方式将 Skill 添加到您的 Agent：

#### 方法 A：使用 Openskills CLI (推荐)
会自动处理路径依赖和配置同步。
```bash
# 安装 skill
openskills install git@github.com:cclank/news-aggregator-skill.git

# 同步配置到 Agent
openskills sync
```

#### 方法 B：使用 NPX
直接从远程仓库添加。
```bash
npx skills add https://github.com/cclank/news-aggregator-skill
```

#### 方法 C：手动集成
```bash
git clone git@github.com:cclank/news-aggregator-skill.git YourProject/.claude/skills/news-aggregator-skill
```

### 第二步：安装 Python 依赖
进入已安装的 Skill 目录，执行依赖安装（如果您的 Agent 足够聪明，可要求其自动配置）：
```bash
cd YourProject/.claude/skills/news-aggregator-skill
pip install -r requirements.txt
playwright install chromium
```

---

## 🚀 如何使用

### 1. 🔮 唤醒交互菜单 (推荐)

最简单、最迷人的使用方式，来自专属交互彩蛋，直接召唤智能指令菜单：

> **"news-aggregator-skill 如意如意"**

系统将立即为您展示多达 35 个功能选项的精美列表，直接回复数字序号即可生成完美排版的今日大盘！

### 2. 🗣️ 自然语言触发

您也可以直接通过对话指定需求：

- **场景日报**："帮我跑一份 💰财经早报，看看今天华市有什么动静。"
- **深度穿透**："抓取 5 条最新的 GitHub 趋势，记得开启 Deep Fetch 深入阅读下他们的 README。"
- **硬核科研**："看看今天 HuggingFace 有什么新发的神仙论文？"
- **自由组合**："帮我把 Hacker News, 华尔街见闻 和 微博热搜 今天的前十条揉在一起生成一个早报。"

### 3. 🖥️ Local Full Briefing (Recommended for Heavy Jobs)

For heavy full-briefing runs, prefer local execution over OpenClaw cron agentTurn.

#### Full Tech Briefing
```bash
cd /path/to/news-aggregator-skill
bash scripts/run_full_briefing_local.sh tech --deep-top-n 3 --max-age-minutes 1440
```

#### Full AI Daily
```bash
cd /path/to/news-aggregator-skill
bash scripts/run_full_briefing_local.sh ai_daily --deep-top-n 5 --max-age-minutes 2880
```

#### Full GitHub Briefing
```bash
cd /Users/qihan/.openclaw/workspace/news-aggregator-skill
bash scripts/run_full_github_local.sh
```

Outputs will be written to `reports/manual/` by default.

### 4. 🧱 CLI Hardening

`scripts/fetch_news.py` 与 `scripts/daily_briefing.py` 现在共享一套输出与退出码约定：

- `--json-out <path>`: 将完整运行结果写入 JSON 文件
- `--md-out <path>`: 将本次运行写入 Markdown 摘要
- `--stdout-summary`: 在 stdout 打印单行 JSON 摘要，适合 OpenClaw / shell wrapper
- `--format full|telegram`: Markdown 输出格式，`telegram` 更适合消息推送
- `--health-out <path>`: 写入稳定的信源健康状态 JSON
- `--max-age-minutes <n>`: 过滤掉可识别发布时间且超过 `n` 分钟的条目
- `--deep-top-n <n>`: 仅对前 `n` 条结果执行 Deep Fetch

统一退出码：

- `0`: 成功且有结果
- `10`: 成功但结果为空
- `20`: 部分成功，已有输出，但部分信源失败
- `50`: 严重失败
- `60`: 超时或缺少依赖/运行环境

统一 JSON 顶层字段：

- `run_at`
- `source` 或 `profile`
- `status`
- `sources_total`
- `sources_ok`
- `sources_failed`
- `failed_sources`
- `items`

每个条目现在尽量带上 freshness 字段：

- `published_at_raw`
- `published_at_iso`
- `fetched_at`
- `age_minutes`
- `canonical_url`

健康状态文件的核心字段：

- `updated_at`
- `sources.<source_key>.last_ok_at`
- `sources.<source_key>.last_error_at`
- `sources.<source_key>.last_error`
- `sources.<source_key>.consecutive_errors`

Canonical 化 / 去重行为：

- 去掉 URL fragment
- 移除常见 tracking 参数，如 `utm_*`、`fbclid`、`gclid`
- 统一 host 大小写并清理默认端口 / 多余尾斜杠
- 优先用 `canonical_url`，其次用标准化标题做轻量去重
- `fetch_news.py` 对当前聚合结果去重，`daily_briefing.py` 在各 section 内去重

OpenClaw wrapper:

```bash
scripts/openclaw_run_briefing.sh general
```

它会在存在时自动激活仓库内 `.venv` / `venv`，并固定写入：

- `reports/openclaw/<profile>_briefing.json`
- `reports/openclaw/<profile>_briefing.md`
- `reports/openclaw/source_health.json`

Telegram 模式示例：

```bash
python3 scripts/fetch_news.py --source hackernews,github --format telegram --md-out /tmp/scan_telegram.md
python3 scripts/daily_briefing.py --profile general --format telegram --md-out /tmp/general_telegram.md
scripts/openclaw_run_briefing.sh general --format telegram
```

DDGS 搜索源示例：

```bash
python3 scripts/fetch_news.py --source ddgs --keyword "Bitcoin,Ethereum,Crypto" --no-save
python3 scripts/fetch_news.py --source ddgs_news --keyword "crypto market,Binance" --no-save
```

说明：

- `ddgs` 适合 text search 候选链接召回
- `ddgs_news` 目前仍按实验源管理
- `tavily` 继续作为稳定 fallback 保留

`daily_briefing.py` 的 profile 定义现位于 `profiles/*.json`。单个 profile 文件结构如下：

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

---

## 💡 开发与扩展

欢迎提交 PR 为框架接入新的全球优质信源。我们期望共建一个**最纯净、最高效、抗干扰**的防降智信息获取舱。

📝 **License**: MIT License
