"""
generate_newsletter.py
weekly_data.json を読み込み Gemma4 でニュースレター本文を生成する
"""

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# 使用モデル：Gemma4（gemma-3-27b-it は Gemma3。Gemma4は下記）
MODEL_ID = "gemma-4-26b-a4b-it"  # ← 後で確認して変更


SYSTEM_PROMPT = """You are a senior financial analyst and writer specializing in Japanese markets.
You live in Japan and write a weekly newsletter for English-speaking investors worldwide.

Your writing style:
- Professional yet conversational, like a Bloomberg brief written by a human living in Tokyo
- Data-driven: always cite specific numbers
- Culturally insightful: include observations only someone living in Japan would notice
- Honest about uncertainty: never hype or guarantee returns

You must always end every newsletter with this exact disclaimer:
---
*This newsletter is AI-assisted. All market data sourced from public APIs (Yahoo Finance, BOJ).
This is not financial advice. Past performance does not guarantee future results.
Always consult a qualified financial advisor before making investment decisions.*
---"""


def build_prompt(data: dict) -> str:
    """weekly_data.jsonの内容からプロンプトを生成"""

    nikkei  = data["equities"].get("nikkei", {})
    topix   = data["equities"].get("topix", {})
    usdjpy  = data["equities"].get("usdjpy", {})
    eurjpy  = data["equities"].get("eurjpy", {})
    ej_etf  = data["equities"].get("ej_etf", {})
    boj     = data["boj"]
    news    = data["news"]
    week    = data["week_label"]

    news_block = "\n".join([
        f'- [{item["source"]}] {item["title"]}: {item["summary"][:150]}'
        for item in news
    ])

    prompt = f"""
## Weekly Market Data — {week}

### Equity & FX
- Nikkei 225 : {nikkei.get('latest', 'N/A'):,} ({nikkei.get('weekly_change_pct', 'N/A'):+}% WoW)
- TOPIX ETF  : {topix.get('latest', 'N/A')} ({topix.get('weekly_change_pct', 'N/A'):+}% WoW)
- USD/JPY    : {usdjpy.get('latest', 'N/A')} ({usdjpy.get('weekly_change_pct', 'N/A'):+}% WoW)
- EUR/JPY    : {eurjpy.get('latest', 'N/A')} ({eurjpy.get('weekly_change_pct', 'N/A'):+}% WoW)
- EWJ ETF    : {ej_etf.get('latest', 'N/A')} ({ej_etf.get('weekly_change_pct', 'N/A'):+}% WoW)
- BOJ Rate   : {boj.get('policy_rate_pct', 'N/A')}%

### News Headlines This Week
{news_block}

---

Please write a complete weekly newsletter issue with the following structure:

**SUBJECT LINE** (max 60 chars, compelling, data-driven)

**PREVIEW TEXT** (max 100 chars, teaser for email preview)

**BODY:**

## [Punchy headline referencing this week's biggest market move]

### Executive Summary
(3 sentences max. What happened, why it matters, what to watch next week.)

### 1. Yen Watch 💴
(150-200 words. Analyze USD/JPY and EUR/JPY moves this week.
What's driving yen weakness/strength? BOJ policy implications.
What should international investors watching Japan think about this?)

### 2. Equity Pulse 📈
(150-200 words. Nikkei vs TOPIX divergence if any.
EWJ ETF as a proxy for foreign investor sentiment.
Sector or thematic observations.)

### 3. Japan Insight 🗾
(100-150 words. ONE cultural or on-the-ground observation from Japan
that connects to this week's financial data.
This must feel like it was written by someone actually living in Tokyo —
something you'd only notice if you were here.)

### What to Watch Next Week
(3 bullet points. Upcoming events, data releases, or risks.)

[ADD THE DISCLAIMER AT THE END]
"""
    return prompt


def generate_newsletter(data: dict) -> dict:
    """Gemma4でニュースレターを生成してdictで返す"""

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    prompt = build_prompt(data)

    print(f"🤖 Generating newsletter with {MODEL_ID}...")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )

    full_text = response.text

    # SUBJECT LINE と PREVIEW TEXT を本文から切り出す
    subject     = ""
    preview     = ""
    body_lines  = []
    in_body     = False

    for line in full_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("**SUBJECT LINE**"):
            subject = stripped.replace("**SUBJECT LINE**", "").strip(" :()*")
        elif stripped.startswith("**PREVIEW TEXT**"):
            preview = stripped.replace("**PREVIEW TEXT**", "").strip(" :()*")
        elif stripped.startswith("**BODY:**"):
            in_body = True
        elif in_body:
            body_lines.append(line)

    # パースできなかった場合は全文をbodyにする
    if not subject:
        subject = f"Japan Finance Weekly — {data['week_label']}"
    if not preview:
        preview = f"Nikkei {data['equities']['nikkei'].get('latest','')}" \
                  f" | USD/JPY {data['equities']['usdjpy'].get('latest','')}"
    body = "\n".join(body_lines).strip() if body_lines else full_text

    result = {
        "subject":      subject,
        "preview_text": preview,
        "body":         body,
        "generated_at": datetime.now().isoformat(),
        "week_label":   data["week_label"],
        "model":        MODEL_ID,
    }

    # 保存
    os.makedirs("data", exist_ok=True)
    path = "data/newsletter_draft.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ Newsletter draft saved to {path}")
    return result


if __name__ == "__main__":
    with open("data/weekly_data.json", encoding="utf-8") as f:
        data = json.load(f)

    result = generate_newsletter(data)

    print("\n── Draft Preview ──")
    print(f"Subject : {result['subject']}")
    print(f"Preview : {result['preview_text']}")
    print(f"Body    : {result['body'][:300]}...")
