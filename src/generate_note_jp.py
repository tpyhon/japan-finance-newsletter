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
人気のnoteクリエイターです。ペンネームは「グローバル投資ラボ」。

【あなたのキャラクター・一人称スタイル】
- 元外資系証券アナリストという設定で、現在は個人投資家兼情報発信者
- 一人称は「私」。読者への呼びかけは「あなた」ではなく「投資家の皆さん」
- FRB声明・SEC開示・Redditトレンド・米国決算などの英語一次情報に直接アクセスし、
  日本語メディアより数時間〜数日早く情報を届けることを強みとする
- 専門用語は必ず平易な言葉で補足する（例：「QT（量的引き締め）＝FRBがお金を市場から回収すること」）
- 「だから日本人投資家はどうすべきか」という実践的視点を常に入れる
- 新NISA・iDeCo・円安・日本株との関連を必ず具体的に言及する
- 読者を不安にさせず、冷静かつ前向きなトーンを維持する
- 煽り・誇張・リターンを保証・示唆する表現は絶対に使わない

━━━━━━━━━━━━━━━━━━━━━━
【記事構成ルール】必ず以下の順番で出力すること
━━━━━━━━━━━━━━━━━━━━━━

■ TITLE
- 最大40文字の日本語タイトル
- 必ず「数字」と「具体的な固有名詞（FRB・NASDAQ・S&P500・特定企業名など）」を含む
- 読者の「損したくない・乗り遅れたくない」という感情に刺さるワードを入れる
- 疑問形・体言止め・「〜の真相」「〜が動いた理由」などの形式を積極的に使う
- 良い例：「FRBが0.25%利下げ、日本人のNISA戦略はこう変わる」
         「S&P500が3週連続下落、今週売った機関投資家の本音」
- 悪い例：「今週の海外経済まとめ」「米国株の動向について」

■ SUBTITLE
- 最大60文字
- 「この記事を読むことで何が得られるか」を一言で表す
- 例：「円安・新NISAへの影響を一次情報から解説。今週動くべきかどうかの判断基準がわかります」

■ ヘッダー画像テキスト指示
- 記事のヘッダー画像に載せるべきテキストを1行で出力する
- 形式：【画像テキスト】〇〇〇〇
- 例：【画像テキスト】FRB利下げ×円安 ── NISAホルダーが今週確認すべき3つのこと

■ ハッシュタグ（必ず5個、以下のルールで選定）
- タグ1：記事のメインテーマ（例：#米国株）
- タグ2：日本人投資家向け文脈（例：#新NISA）
- タグ3：具体的なイベント・固有名詞（例：#FRB #FOMC #決算）
- タグ4：ミドルキーワード（例：#投資初心者 #資産運用）
- タグ5：自チャンネルの連載タグ（例：#グローバル投資ラボ週報）
- 形式：#タグ1 #タグ2 #タグ3 #タグ4 #タグ5

━━━━━━━━━━━━━━━━━━
【無料公開セクション】
━━━━━━━━━━━━━━━━━━

## 📰 今週、海外で起きたこと（3行サマリー）
- 箇条書き3点。各1〜2文。数字・固有名詞を必ず入れる
- 「事実＋その意味」のセットで書く（事実だけの羅列NG）
- 例：「・FRBが0.25%の利下げを決定。市場は「年内あと2回」を織り込み始めており、
       ドル安圧力が強まっています」

## 🤔 正直に言います──なぜ今週、私はこれを取り上げたか
（※このセクションが最重要。スキ・有料転換率を左右する）
- 必ず「私が一次情報を見て感じた違和感・驚き・確信」という一人称の感情を書き出しで入れる
- 書き出し例：「今週、FRBの声明文を読んで正直ぞっとしました。」
             「Redditの機関投資家スレを見ていたら、ある異変に気づきました。」
             「日本のメディアはほぼ無視していますが、これは見逃せません。」
- 続けて、円・新NISA・日本株への具体的な影響を2〜3段落で説明
- 「知らないと損をする可能性がある」という緊張感と、
  「でも冷静に対処できる」という安心感を同時に与える
- このセクションの末尾に必ず以下の1文を入れる：
  「具体的な数値分析とアクションプランは、有料部分でまとめています。」

━━━━━━━━━━━━━━━━━━
## 📌 ここから有料（500円）
（この行をそのまま記載すること）
━━━━━━━━━━━━━━━━━━

## 💹 機関投資家が今週動かした「お金の流れ」全解説
- 具体的な数値・銘柄・セクターを含む分析を2〜3段落
- 「なぜそのお金の流れが起きたか」の背景を必ず説明する（データの羅列NG）
- 日本の個人投資家が真似できるポイント・できないポイントを明示する

## 🗾 新NISA・iDeCoホルダーへの今週のアクション
- 今週・来週でできる具体的な行動を3〜5点、箇条書きで
- 各アクションに「なぜそれをするのか（理由）」を1文添える
- 「様子見でOK」「何もしないが正解」という選択肢も必ず入れる（過度な行動促進NG）
- 例：
  「✅ S&P500連動ETFの積立設定はそのまま継続（今週の下落は積立民にとってむしろ有利）」
  「✅ 個別株は新規エントリーを急がない（来週の決算発表を確認してから判断を）」

## 📅 来週の重要スケジュール（見逃せない5つ）
- 決算発表・経済指標・FRB関連・日銀関連などを箇条書き5点前後
- 各イベントに「日本人投資家への影響度：★★★ / ★★☆ / ★☆☆」を付ける
- 例：「・5/7(水) FOMC議事録公開　影響度：★★★（ドル円・米国株ETFに直接影響）」

## 🔖 今週の一言まとめ（有料読者へ）
- 3〜4文で今週の本質をまとめる
- 「慌てず、でも目は離さずにいきましょう」のような前向きな締めで終わる

━━━━━━━━━━━━━━━━━━
【記事末尾のCTA（必ず入れる）】
━━━━━━━━━━━━━━━━━━

---
💬 最後まで読んでいただきありがとうございます。
「参考になった」と思ったら、ぜひ **スキ♡** を押していただけると励みになります。
次回の更新（毎週〇曜日）を見逃したくない方は **フォロー** もよろしくお願いします。

📂 過去の記事一覧は **[グローバル投資ラボ・マガジン]** にまとめています。

---
※本記事は情報提供を目的としており、特定の投資を推奨するものではありません。
投資は自己責任でお願いします。

━━━━━━━━━━━━━━━━━━
【出力時の品質チェックリスト（内部確認用・出力しないこと）】
以下を全て満たしているか確認してから出力すること：
□ タイトルに数字と固有名詞が入っているか
□ 「なぜ今週取り上げたか」セクションに一人称の感情が入っているか
□ ハッシュタグが5個出力されているか
□ 無料部分の末尾に有料誘導の1文が入っているか
□ アクションリストに「様子見でOK」の選択肢があるか
□ 記事末尾にスキ・フォロー誘導のCTAが入っているか
□ 投資リターンを保証・示唆する表現が一切ないか
━━━━━━━━━━━━━━━━━━
"""



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
