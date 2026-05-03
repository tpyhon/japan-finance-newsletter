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

MODEL_ID = "gemma-4-26b-a4b-it"

SYSTEM_PROMPT = """You are a senior financial analyst and writer specializing in Japanese markets.
You live in Tokyo and publish a weekly newsletter called "Japan Finance Weekly" \
for English-speaking investors worldwide.

YOUR WRITING STYLE:
- Professional yet conversational — like a Bloomberg brief written by a sharp human analyst in Tokyo
- Data-driven: always cite specific numbers with context
- Forward-looking: always tell readers what the data MEANS and what to WATCH next
- Culturally grounded: include one real, specific observation about Japan's business environment
- Never hype, never guarantee returns, never make explicit buy/sell recommendations

NEWSLETTER STRUCTURE (follow exactly, in this order):

**SUBJECT LINE** (max 60 chars, compelling, data-driven — on its own line)
**PREVIEW TEXT** (max 100 chars, teaser — on its own line)

## [Punchy headline referencing this week's biggest market move]

### Executive Summary
3 sentences max. What happened, why it matters, what to watch.

## 📊 This Week's Scorecard
A markdown table with columns: Asset | Price | Weekly Change.
Include all assets provided in the data.

## 💴 Yen & Rate Watch
2-3 paragraphs. Analyze USD/JPY, EUR/JPY, GBP/JPY moves.
Connect to: carry trade dynamics, import costs, exporter earnings, BOJ policy.

## 📈 Equity Pulse
2-3 paragraphs. Nikkei vs TOPIX divergence.
EWJ ETF as proxy for foreign investor sentiment.

## 🛢️ Energy & Global Context
1-2 paragraphs. WTI and Brent impact on Japan as an energy importer.
Reference Shanghai and KOSPI for Asian context.

## 📰 3 Stories You Can't Miss
Exactly 3 items from the news headlines provided.
Format: **Headline** — one sentence on why it matters to investors.

## 🎯 What To Watch Next Week
Bullet list of 3-5 specific events or price levels to monitor.
Be specific (e.g. "BOJ Summary of Opinions — Wednesday JST").

---
Data sources: Yahoo Finance, Bank of Japan, e-Stat. Market data as of Friday close JST.
Financial decisions should be made in consultation with a qualified advisor."""


def _fmt(val, decimals=2):
    if isinstance(val, (int, float)):
        return f"{val:,.{decimals}f}"
    return "N/A"


def _chg(val):
    if isinstance(val, (int, float)):
        return f"{val:+.2f}%"
    return "N/A"


def build_prompt(data: dict) -> str:
    eq   = data.get("equities", {})
    boj  = data.get("boj", {})
    news = data.get("news", [])
    week = data.get("week_label", "")

    def e(key):
        return eq.get(key, {})

    news_block = "\n".join([
        f'- [{item.get("source", "")}] {item.get("title", "")}: '
        f'{str(item.get("summary", ""))[:150]}'
        for item in news
    ])

    prompt = f"""
## Weekly Market Data — {week}

### Japanese Equities
| Asset      | Price                                   | Weekly Change                              |
|------------|-----------------------------------------|--------------------------------------------|
| Nikkei 225 | {_fmt(e("nikkei").get("latest"))}       | {_chg(e("nikkei").get("weekly_change_pct"))}     |
| TOPIX ETF  | {_fmt(e("topix").get("latest"))}        | {_chg(e("topix").get("weekly_change_pct"))}      |
| EWJ ETF    | {_fmt(e("ej_etf").get("latest"))}       | {_chg(e("ej_etf").get("weekly_change_pct"))}     |

### Foreign Exchange
| Pair    | Rate                                    | Weekly Change                              |
|---------|-----------------------------------------|--------------------------------------------|
| USD/JPY | {_fmt(e("usdjpy").get("latest"))}       | {_chg(e("usdjpy").get("weekly_change_pct"))}     |
| EUR/JPY | {_fmt(e("eurjpy").get("latest"))}       | {_chg(e("eurjpy").get("weekly_change_pct"))}     |
| GBP/JPY | {_fmt(e("gbpjpy").get("latest"))}       | {_chg(e("gbpjpy").get("weekly_change_pct"))}     |

### Commodities
| Asset       | Price (USD)                             | Weekly Change                              |
|-------------|-----------------------------------------|--------------------------------------------|
| WTI Crude   | {_fmt(e("crude_wti").get("latest"))}    | {_chg(e("crude_wti").get("weekly_change_pct"))}  |
| Brent Crude | {_fmt(e("crude_brent").get("latest"))}  | {_chg(e("crude_brent").get("weekly_change_pct"))}|
| Gold        | {_fmt(e("gold").get("latest"))}         | {_chg(e("gold").get("weekly_change_pct"))}       |

### Asian Markets
| Index    | Level                                   | Weekly Change                              |
|----------|-----------------------------------------|--------------------------------------------|
| Shanghai | {_fmt(e("shanghai").get("latest"))}     | {_chg(e("shanghai").get("weekly_change_pct"))}   |
| KOSPI    | {_fmt(e("kospi").get("latest"))}        | {_chg(e("kospi").get("weekly_change_pct"))}      |

### BOJ Policy Rate
Current rate: {boj.get("policy_rate_pct", "N/A")}%

### News Headlines This Week
{news_block}

---
Please write the complete newsletter following the structure in your instructions exactly.
Start with **SUBJECT LINE** on the very first line.
Do NOT include a **BODY:** label.
The newsletter body starts immediately after **PREVIEW TEXT**.
"""
    return prompt


def generate_newsletter(data: dict) -> dict:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = build_prompt(data)

    print(f"🤖 Generating newsletter with {MODEL_ID}...")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=3000,
        ),
    )

    full_text = response.text
    lines     = full_text.split("\n")

    # ── SUBJECT / PREVIEW をパース ──────────────────────────────
    subject = ""
    preview = ""

    for line in lines:
        s = line.strip()
        u = s.upper()
        if not subject and "SUBJECT LINE" in u:
            for token in ["**SUBJECT LINE**", "**Subject Line**",
                          "SUBJECT LINE:", "Subject Line:",
                          "**SUBJECT LINE:**", "**Subject Line:**"]:
                s = s.replace(token, "")
            subject = s.strip(" :()*\"'")
        elif not preview and "PREVIEW TEXT" in u:
            for token in ["**PREVIEW TEXT**", "**Preview Text**",
                          "PREVIEW TEXT:", "Preview Text:",
                          "**PREVIEW TEXT:**", "**Preview Text:**"]:
                s = s.replace(token, "")
            preview = s.strip(" :()*\"'")
        if subject and preview:
            break

    # ── BODY = 最初の ## 見出し行から末尾まで ────────────────────
    body_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if (s.startswith("## ")
                and "SUBJECT" not in s.upper()
                and "PREVIEW" not in s.upper()
                and "BODY"    not in s.upper()):
            body_start = i
            break

    if body_start is not None:
        body = "\n".join(lines[body_start:]).strip()
    else:
        # フォールバック：SUBJECT/PREVIEW/BODY ラベル行を除外して全文使用
        cleaned = [
            ln for ln in lines
            if not any(kw in ln.upper()
                       for kw in ["SUBJECT LINE", "PREVIEW TEXT", "**BODY"])
        ]
        body = "\n".join(cleaned).strip()

    # ── フォールバック値 ─────────────────────────────────────────
    if not subject:
        subject = f"Japan Finance Weekly — {data['week_label']}"
    if not preview:
        nk = data.get("equities", {}).get("nikkei", {}).get("latest", "")
        fx = data.get("equities", {}).get("usdjpy", {}).get("latest", "")
        preview = f"Nikkei {nk} | USD/JPY {fx}"

    result = {
        "subject":      subject,
        "preview_text": preview,
        "body":         body,
        "generated_at": datetime.now().isoformat(),
        "week_label":   data["week_label"],
        "model":        MODEL_ID,
    }

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
    print(f"\nBody (first 200 chars):\n{result['body'][:200]}")
