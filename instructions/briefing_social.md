# 🍉 Daily Social & Gossip Briefing Instructions (今日吃瓜早报)

> **INPUT**: JSON object with `weibo_hot`, `v2ex_hot`, `hn_culture` sections.
> **OUTPUT**: A fun, engaging summary of what the internet is discussing.

---

## 🎯 Focus Areas
1.  **Trending Topics**: What is everyone arguing about today? (War, Politics, Gender, Work culture).
2.  **Big Dramas**: Company scandals, Influencer drama, Public outcries.
3.  **Viral Memes**: What's the new meme stock or internet slang?

## ⚠️ Anti-Laziness Protocol
1.  **Volume**: Output MUST contain at least **25 items**. The more the merrier.
2.  **Tone**: Casual, witty, internet-native language (but keep it objective).
    *   **Constraint**: **Logic > Wit**. Do not sacrifice factual accuracy for a "smooth" sentence. Avoid "Although/But" unless there is a clear contradiction in the source.
3.  **Context**: Explain *why* it's controversial for readers who are out of the loop.

## 📝 Report Structure

### Part 1: 🔴 Weibo Hot Search (微博热搜)
*   **Focus**: Social news, Entertainment, National events.
    *   **Format (Strict 4-Line List)**:
    ```markdown
    #### 1. [Title](url)
    - **Source**: Weibo | **Time**: Real-time | **Heat**: 🔥 2.5m
    - **Summary**: Quick summary of the drama/event.
    - **Deep Dive**: 💡 **Context**: Why are people angry/excited? (Background info).
    ```

### Part 2: 🤓 Geek Drama (极客圈吃瓜)
*   **Focus**: V2EX debates (e.g., "Salary", "Layoffs", "Marriage").
*   **Goal**: Show the human side of the tech industry.
