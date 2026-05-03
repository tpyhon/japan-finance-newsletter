"""
generate_note_jp.py
overseas_intel.json + weekly_data.json を読み込み
Gemma4 で note 向け日本語投資記事を生成する
"""

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL_ID = "gemma-4-26b-a4b-it"

SYSTEM_PROMPT = """あなたは海外金融情報を日本人投資家向けにわかりやすく解説する、
人気のnoteクリエイターです。

あなたの特徴：
- 英語の一次情報（FRB声明・SEC開示・Redditトレンド・米国決算）に直接アクセスし、
  日本語メディアにまだ出ていない情報を日本人にいち早く届ける
- 専門用語は使うが、必ず平易な言葉で補足する
- 「だから日本人投資家はどうすべきか」という実践的視点を常に入れる
- 新NISA・iDeCo・円安・日本株との関連を必ず言及する
- 読者を不安にさせず、冷静かつ前向きなトーンを維持する
- 煽り・誇張・投資を保証する表現は絶対に使わない

note記事の構成ルール（必ず以下の順番で書く）：

**TITLE**（最大40文字、数字と具体性を含む日本語タイトル）
**SUBTITLE**（最大60文字、記事の価値をひと言で表すサブタイトル）

## 今週の海外経済ハイライト
（3つの重要トピックを箇条書き。各1〜2文。無料公開部分）

## なぜ今、日本人投資家が知るべきか
（2〜3段落。円・新NISA・日本株との関連を具体的に説明。無料公開部分）

## 📌 ここから有料（500円）
（この行をそのまま記載すること）

## 海外投資家が今週動かしたお金の流れ
（具体的な数値・銘柄・セクターを含む分析。2〜3段落）

## 日本人投資家への具体的アクション
（今週・来週でできる具体的な行動を3〜5点。箇条書き）

## 来週の重要スケジュール
（決算・経済指標・FRB発言予定などを箇条書き）

---
※本記事は情報提供を目的としており、特定の投資を推奨するものではありません。
投資は自己責任でお願いします。"""


def _safe(val, decimals=2):
    if isinstance(val, (int, float)):
        return f"{val:,.{decimals}f}"
    return "N/A"


def _chg(val):
    if isinstance(val, (int, float)):
        return f"{val:+.2f}%"
    return "N/A"


def build_note_prompt(market_data: dict, intel: dict) -> str:
    eq   = market_data.get("equities", {})
    boj  = market_data.get("boj", {})
    week = intel.get("week_label", datetime.now().strftime("%Y-W%V"))

    def e(key):
        return eq.get(key, {})

    # FRB ニュース
    fed_block = "\n".join([
        f'- [{i.get("source","")}] {i.get("title","")}: {i.get("summary","")[:200]}'
        for i in intel.get("fed_news", [])[:4]
    ]) or "（取得なし）"

    # Alpha Vantage ニュースセンチメント
    av_block = "\n".join([
        f'- [{i.get("sentiment","")}] {i.get("title","")}: {i.get("summary","")[:150]}'
        for i in intel.get("alpha_vantage", [])[:4]
    ]) or "（取得なし）"

    # プレミアムRSS
    rss_block = "\n".join([
        f'- [{i.get("source","")}] {i.get("title","")}: {i.get("summary","")[:150]}'
        for i in intel.get("premium_rss", [])[:5]
    ]) or "（取得なし）"

    # Reddit トレンド
    reddit_block = "\n".join([
        f'- [r/{i.get("source","").replace("Reddit r/","")} 👍{i.get("score",0)}] '
        f'{i.get("title","")}'
        for i in intel.get("reddit_trends", [])[:4]
    ]) or "（取得なし）"

    # 決算カレンダー
    earnings_block = "\n".join([
        f'- {i.get("date","")} {i.get("symbol","")} '
        f'（EPS予想: {i.get("eps_estimate","N/A")}）'
        for i in intel.get("earnings_calendar", [])[:8]
    ]) or "（取得なし）"

    prompt = f"""
## 分析対象週: {week}

### 📊 マーケットデータ（参考）
| 指標 | 値 | 週次変化 |
|------|-----|---------|
| 日経225 | {_safe(e("nikkei").get("latest"))} | {_chg(e("nikkei").get("weekly_change_pct"))} |
| TOPIX ETF | {_safe(e("topix").get("latest"))} | {_chg(e("topix").get("weekly_change_pct"))} |
| USD/JPY | {_safe(e("usdjpy").get("latest"))} | {_chg(e("usdjpy").get("weekly_change_pct"))} |
| WTI原油 | {_safe(e("crude_wti").get("latest"))} | {_chg(e("crude_wti").get("weekly_change_pct"))} |
| 金 | {_safe(e("gold").get("latest"))} | {_chg(e("gold").get("weekly_change_pct"))} |
| BOJ政策金利 | {boj.get("policy_rate_pct","N/A")}% | — |

### 🏛️ FRB・米国当局の動き（英語一次情報）
{fed_block}

### 📡 Alpha Vantage ニュースセンチメント
{av_block}

### 📰 海外プロ投資家が読んでいるニュース
{rss_block}

### 💬 Reddit 投資コミュニティのトレンド（r/investing等）
{reddit_block}

### 📅 来週の米国決算カレンダー
{earnings_block}

---
上記の海外一次情報をもとに、日本人個人投資家向けのnote有料記事を作成してください。
英語が苦手な日本人が「これは知らなかった！」と感じる視点を必ず含めてください。
**TITLE** から始めてください。
"""
    return prompt


def generate_note_article(market_data: dict, intel: dict) -> dict:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = build_note_prompt(market_data, intel)

    print(f"🤖 Generating note article with {MODEL_ID}...")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.75,
            max_output_tokens=3000,
        ),
    )

    full_text = response.text
    lines     = full_text.split("\n")

    # タイトル・サブタイトル・本文をパース
    title    = ""
    subtitle = ""

    for line in lines:
        s = line.strip()
        u = s.upper()
        if not title and "**TITLE**" in u:
            for token in ["**TITLE**", "**Title**", "TITLE:", "Title:",
                          "**TITLE:**", "**Title:**"]:
                s = s.replace(token, "")
            title = s.strip(" :()*\"'　：")   # 全角コロンも除去
        elif not subtitle and "**SUBTITLE**" in u:
            for token in ["**SUBTITLE**", "**Subtitle**", "SUBTITLE:", "Subtitle:",
                          "**SUBTITLE:**", "**Subtitle:**"]:
                s = s.replace(token, "")
            subtitle = s.strip(" :()*\"'　：")  # 全角コロンも除去
        if title and subtitle:
            break

    # BODY = 最初の ## 見出しから末尾まで
    body_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if (s.startswith("## ")
                and "TITLE"    not in s.upper()
                and "SUBTITLE" not in s.upper()):
            body_start = i
            break

    if body_start is not None:
        body = "\n".join(lines[body_start:]).strip()
    else:
        cleaned = [
            ln for ln in lines
            if not any(kw in ln.upper()
                       for kw in ["**TITLE", "**SUBTITLE"])
        ]
        body = "\n".join(cleaned).strip()

    # フォールバック
    if not title:
        title = f"今週の海外経済と日本人投資家への影響 — {intel.get('week_label','')}"
    if not subtitle:
        subtitle = "FRB・Reddit・決算カレンダーから読み解く今週の投資判断"

    result = {
        "title":        title,
        "subtitle":     subtitle,
        "body":         body,
        "generated_at": datetime.now().isoformat(),
        "week_label":   intel.get("week_label", ""),
        "model":        MODEL_ID,
        "platform":     "note",
        "price":        500,
    }

    os.makedirs("data", exist_ok=True)
    path = "data/note_draft.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # note投稿用テキストも保存
    txt_path = "data/note_post.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write(f"note 投稿用テキスト｜{result['week_label']}\n")
        f.write(f"価格: {result['price']}円\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"【タイトル】\n{title}\n\n")
        f.write(f"【サブタイトル/説明文】\n{subtitle}\n\n")
        f.write("【本文】\n")
        f.write(body)

    print(f"✅ note draft saved to {path}")
    print(f"📝 note post text saved to {txt_path}")
    return result


if __name__ == "__main__":
    with open("data/weekly_data.json", encoding="utf-8") as f:
        market_data = json.load(f)
    with open("data/overseas_intel.json", encoding="utf-8") as f:
        intel = json.load(f)

    result = generate_note_article(market_data, intel)

    print("\n── Draft Preview ──")
    print(f"タイトル   : {result['title']}")
    print(f"サブタイトル: {result['subtitle']}")
    print(f"\n本文（先頭200文字）:\n{result['body'][:200]}")
