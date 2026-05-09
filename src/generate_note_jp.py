# src/generate_note_jp.py
# -*- coding: utf-8 -*-
"""
Note記事生成スクリプト
使い方:
  python src/generate_note_jp.py                  # デフォルト: investor
  python src/generate_note_jp.py --mode investor  # 海外経済×投資家向け（既存）
  python src/generate_note_jp.py --mode exam      # 受験時事向け（新規）
  python src/generate_note_jp.py --mode light     # ライト経済向け（新規）
"""

import json
import os
import re
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from google import genai
from google.genai import types

# ─── 定数 ─────────────────────────────────────────
MODEL_ID   = "gemma-4-26b-a4b-it"
DATA_DIR   = Path("data")
JST        = timezone(timedelta(hours=9))

# ─── ユーティリティ ────────────────────────────────
def _safe(val, fmt="+.2f"):
    try:
        return format(float(val), fmt)
    except Exception:
        return str(val)

def _chg(val):
    try:
        v = float(val)
        sign = "▲" if v < 0 else "▶"
        return f"{sign}{abs(v):.2f}%"
    except Exception:
        return str(val)

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ─── SYSTEM PROMPT 定義 ──────────────────────────

SYSTEM_PROMPT_INVESTOR = """あなたは海外金融情報を日本人投資家向けにわかりやすく解説する人気のnoteクリエイターです。
ペンネームは「グローバル投資ラボ」。

【キャラクター】
- 元外資系証券アナリスト、一人称は「私」、読者は「投資家の皆さん」
- 英語一次情報を数時間〜数日前に取得し、平易な言葉で補足
- 新NISA・iDeCo・円安・日本株への具体的言及必須
- 誇張・保証表現は使用しない

【記事構成ルール】
■ TITLE: 最大40文字、数字＋具体的固有名詞必須、感情フック入り
  良い例: 「S&P500が3%急落！FRB発言で新NISAはどう動くべきか」
  悪い例: 「今週の海外経済ニュースまとめ」
■ SUBTITLE: 最大60文字で読者が得られる価値を一言
■ ハッシュタグ: 5個（#米国株 #新NISA など）

【無料公開セクション（## 見出し以降に本文開始）】
## 📰 今日、海外で起きたこと（3行サマリー）
- 数字・固有名詞を必ず含む3行箇条書き

## 🔍 なぜ私はこれを取り上げたか
- 一人称で感情・驚きを1段落
- 円・NISA・日本株への影響を2〜3段落
- 末尾に「👇 続きは有料パートで」文を必ず入れる

【有料セクション】
## 💰 機関投資家の動きを読む（数値・銘柄必須）
## 🎯 新NISA・iDeCo向け今週の具体的アクション（3〜5点、理由付き、「様子見でOK」選択肢必須）
## 📅 来週の重要スケジュール（5点前後、★評価で影響度）
## ✅ 今週の一言まとめ（前向き締め）

【CTA（記事末尾に必須）】
---
📌 **スキ♡をいただけると励みになります！**
フォローで毎日の海外マーケット情報をお届けします。
マガジン「グローバル投資ラボ週報」もぜひチェックを！

【品質チェック（出力前に自己確認）】
- [ ] タイトルに数字・固有名詞あり
- [ ] 「今週の〜」「週次〜」という表現を使っていない
- [ ] ハッシュタグ5個あり
- [ ] 無料末尾に有料誘導文あり
- [ ] アクションに「様子見でOK」選択肢あり
- [ ] CTA完備
- [ ] 投資リターン保証表現なし
"""

SYSTEM_PROMPT_EXAM = """あなたは受験生・保護者向けに時事問題をわかりやすく解説する人気のnoteクリエイターです。
ペンネームは「受験時事ラボ」。

【キャラクター】
- 元中学受験・高校受験指導の塾講師、現在はフリーランスの教育ライター
- 一人称は「私」、読者は「受験を控えるお子さんと保護者の方」
- 今日のニュースを「入試に出る視点」で切り取ることが得意
- 小学校高学年〜高校生が読んでも理解できるやさしい言葉を使う
- 難しい語句には必ずカッコ内でひらがな読みまたは簡単な説明を入れる

【記事構成ルール】
■ TITLE: 最大40文字、「受験」「入試」「時事」のうち1語必須、数字か固有名詞を含む
  良い例: 「入試に出る！トランプ関税とは何か？3分で理解する保護者ガイド」
  良い例: 「2026年受験必須ワード：AI関連法が成立した理由を解説」
  悪い例: 「今日のニュース解説」
■ SUBTITLE: 最大60文字で「このニュースが受験でなぜ重要か」を一言
■ ハッシュタグ: 5個（#中学受験 #高校受験 #時事問題 ＋トピック別2個）

【無料公開セクション（## 見出し以降に本文開始）】
## 📰 今日のニュース（3行でわかる）
- やさしい日本語で3行。難語にはルビ（読み方）を()内に記載

## 🏫 受験で問われるポイント
- このニュースが中学受験・高校受験・大学受験のどの科目に関連するか明示
- 関連する学習単元（例：「公民：内閣の仕組み」）を記載
- 覚えるべきキーワードを太字で3〜5個提示
- 末尾に「👇 予想問題と解説は有料パートで！」文を必ず入れる

【有料セクション（500円）】
## 📝 予想問題（3問）＋解説
- 一問一答形式1問、記述式1問、選択式1問
- 各問に「この問題が出やすい学校レベル：偏差値〇〇前後」を記載
- 解説は「なぜこの答えになるか」の背景まで丁寧に

## 🔑 関連キーワード一覧
- 漢字・人物名・条約名・法律名などを表形式で整理（語句・読み・意味の3列）

## 💬 保護者向け会話ガイド
- 「お子さんとこのニュースをどう話すか」3ステップで具体的に提示
- 会話例（例：「パパ、関税ってなに？」→「そうだね、関税というのはね...」）を含める

## 📅 今後の関連ニュースカレンダー
- このトピックに関連する予定されているイベント・発表日を3〜5件

【CTA（記事末尾に必須）】
---
📌 **スキ♡をいただけると励みになります！**
「受験時事ラボ」をフォローで毎日の時事問題解説をお届け！
マガジン「2026年受験時事まとめ」もぜひチェックを！

【品質チェック（出力前に自己確認）】
- [ ] タイトルに「受験」「入試」「時事」のどれかあり
- [ ] 難語にひらがな読み・説明あり
- [ ] 関連科目・単元の明示あり
- [ ] キーワード太字3〜5個あり
- [ ] 有料誘導文あり
- [ ] 予想問題3問（一問一答・記述・選択）あり
- [ ] 保護者向け会話ガイドあり
- [ ] CTA完備
"""

SYSTEM_PROMPT_LIGHT = """あなたは経済ニュースを「子どもにも説明できる言葉」で届ける人気のnoteクリエイターです。
ペンネームは「やさしい経済ラボ」。

【キャラクター】
- 2児の父・元新聞記者、一人称は「私」、読者は「ニュースが気になるけど難しくてわからない人」
- 「難しいことをやさしく」が信条
- 投資知識ゼロでも読める、小学生の子どもに説明するような言葉を使う
- 暗くならず、「なるほど！」で終わる前向きなトーン

【記事構成ルール】
■ TITLE: 最大40文字、「なぜ」「わかりやすく」「3分で」などの導入ワードを活用
  良い例: 「円安ってなに？子どもに説明できるようになる3分解説」
  良い例: 「FRBが金利を上げると私たちの生活はどう変わる？」
  悪い例: 「FRB FOMC声明分析レポート」
■ SUBTITLE: 最大60文字で「読むと何がわかるか」を一言
■ ハッシュタグ: 5個（#経済ニュース #わかりやすく #子育て ＋トピック別2個）

【無料公開セクション（## 見出し以降に本文開始）】
## 🗞️ 今日起きたこと（1分で読める）
- 中学生でもわかる言葉で3〜4行

## 🤔 「つまりどういうこと？」
- アナロジー（例え話）を必ず1つ使って概念を説明
- 「子どもに聞かれたら何て答える？」という視点で1〜2段落
- 私たちの日常生活（食費・光熱費・旅行など）への影響を具体的に
- 末尾に「👇 もっと深く知りたい方は有料パートへ」文を必ず入れる

【有料セクション（300円）】
## 💡 もう少し詳しく：背景と原因
- 図解的な箇条書きで流れを説明
- 専門用語には必ず括弧内で説明

## 🏠 私たちの生活への具体的な影響
- スーパーの値段・旅行・住宅ローンなど生活に即した3〜5点

## 📖 この機会に知っておきたい関連ワード
- 今回登場した経済用語を3〜5語、ひと言解説

【CTA（記事末尾に必須）】
---
📌 **スキ♡をいただけると励みになります！**
「やさしい経済ラボ」をフォローで毎日のニュース解説をお届け！
マガジン「ニュースを3分で理解する」もぜひどうぞ！

【品質チェック（出力前に自己確認）】
- [ ] タイトルにやさしさを伝えるワードあり
- [ ] アナロジー（例え話）が1つ以上あり
- [ ] 日常生活への影響が具体的に書かれている
- [ ] 専門用語に説明あり
- [ ] 有料誘導文あり
- [ ] CTA完備
"""

SYSTEM_PROMPTS = {
    "investor": SYSTEM_PROMPT_INVESTOR,
    "exam":     SYSTEM_PROMPT_EXAM,
    "light":    SYSTEM_PROMPT_LIGHT,
}

# ─── プロンプトビルダー ────────────────────────────

def build_note_prompt(market_data: dict, intel: dict, mode: str) -> str:
    now       = datetime.now(JST)
    day_label = now.strftime("%Y年%m月%d日（%a）")

    # ── モードに応じてトップ記事を切り替え ──────────────
    if mode in ("exam", "light"):
        top = intel.get("top_story_exam") or intel.get("top_story", {})
    else:
        top = intel.get("top_story", {})

    # top_story は {source, title, summary, ...} の平坦構造
    # 旧形式 {"source":..., "item":{...}} にも対応
    if "item" in top:
        top = top["item"]

    top_block = ""
    if top:
        top_block = f"""
【今日のフォーカス記事】
- 情報源 : {top.get('source',   '不明')}
- カテゴリ: {top.get('category', '－')}
- タイトル: {top.get('title',    '')}
- 要約   : {str(top.get('summary', top.get('description', '')))[:300]}
- センチメント: {top.get('sentiment_label', '')} ({top.get('sentiment_score', '')})
"""

    # ── 国内ニュースブロック（exam / light のみ） ────────
    domestic_block = ""
    if mode in ("exam", "light"):
        domestic = intel.get("domestic_news", [])[:5]
        if domestic:
            lines = "\n".join(
                f"- [{i.get('category','')}] {i.get('title','')} "
                f"（{i.get('source','')}）"
                for i in domestic
            )
            domestic_block = f"\n【国内ニュース（直近3日）】\n{lines}\n"

    # ── 市場データ（以降は既存コードそのまま） ───────────
    mkt = market_data.get("market_summary", {})
    market_block = f"""
【市場データ（{day_label}時点）】
| 指標     | 値                                    | 前日比                          |
|----------|---------------------------------------|---------------------------------|
| 日経平均 | {_safe(mkt.get('nikkei',  'N/A'), '.2f')} | {_chg(mkt.get('nikkei_change', 0))} |
| USD/JPY  | {_safe(mkt.get('usdjpy',  'N/A'), '.2f')} | {_chg(mkt.get('usdjpy_change', 0))} |
| 金        | {_safe(mkt.get('gold',    'N/A'), '.2f')} | {_chg(mkt.get('gold_change',   0))} |
| 原油      | {_safe(mkt.get('crude',   'N/A'), '.2f')} | {_chg(mkt.get('crude_change',  0))} |
"""

    fed_items = intel.get("fed_news", [])[:3]
    fed_block = "\n".join(
        f"- [{i['title']}]({i.get('link', '')})" for i in fed_items
    ) if fed_items else "- （データなし）"

    av_items = intel.get("alpha_vantage", [])[:3]
    av_block = "\n".join(
        f"- {i.get('title', '')} [センチメント:{i.get('sentiment_label', '')}]"
        for i in av_items
    ) if av_items else "- （データなし）"

    earnings = intel.get("earnings_calendar", [])[:5]
    earn_block = "\n".join(
        f"- {e.get('symbol', '')} | {e.get('date', '')} | "
        f"予想EPS: {e.get('eps_estimate', 'N/A')} | 予想売上: {e.get('revenue_est', 'N/A')}"
        for e in earnings
    ) if earnings else "- （データなし）"

    mode_instruction = {
        "investor": (
            "海外投資・日本人投資家の観点を中心に記事を構成してください。"
            "新NISA・iDeCo・円相場への言及を必ず入れてください。"
        ),
        "exam": (
            "中学受験・高校受験・大学受験の時事問題の観点から記事を構成してください。"
            "【国内ニュース】がある場合は、そちらを優先してフォーカス記事として扱ってください。"
            "関連する受験科目（社会・公民・地理・歴史・現代社会など）を明示し、"
            "入試で問われやすいキーワードを太字で示してください。"
            "小学生〜高校生が読める、やさしい言葉を使ってください。"
        ),
        "light": (
            "経済に詳しくない一般読者（子育て世代・主婦・学生）向けに、"
            "【国内ニュース】がある場合は、身近な話題として優先的に取り上げてください。"
            "日常生活との接点（食費・旅行・住宅ローン等）を必ず盛り込んでください。"
            "アナロジー（例え話）を必ず1つ使い、「難しくない」と感じさせてください。"
        ),
    }.get(mode, "")

    return f"""今日の日付（JST）: {day_label}
{top_block}{domestic_block}{market_block}
【FRB・中央銀行ニュース】
{fed_block}

【海外主要ニュース（AlphaVantage）】
{av_block}

【今週の決算予定】
{earn_block}

---
{mode_instruction}

上記データをもとに、**■ TITLE_A** から始まるnote記事を1本生成してください。
フォーマット:
■ TITLE: （タイトル）
■ SUBTITLE: （サブタイトル）
■ ハッシュタグ: #タグ1 #タグ2 #タグ3 #タグ4 #タグ5

（本文を ## 見出しから開始）
"""

# ─── 記事パーサー ─────────────────────────────────

def _parse_article(raw: str, mode: str) -> dict:
    """Gemmaの出力からtitle/subtitle/hashtags/bodyを抽出する"""
    lines = raw.split("\n")
    title = subtitle = hashtags = ""

    for i, line in enumerate(lines):
        s = line.strip()

        # タイトル抽出
        if not title and re.search(
            r'(■\s*TITLE|\*\*TITLE\*\*|^TITLE[：:]|^#\s*TITLE)', s, re.I
        ):
            cleaned = re.sub(
                r'(■\s*TITLE|\*\*TITLE\*\*|TITLE[：:]?)', '', s, flags=re.I
            ).strip(' :()*"\'　：')
            title = cleaned or next(
                (ln.strip(' :()*"\'　：')
                 for ln in lines[i + 1:i + 3]
                 if ln.strip() and not re.search(r'(SUBTITLE|■|##)', ln, re.I)),
                ""
            )

        # サブタイトル抽出
        elif not subtitle and re.search(
            r'(■\s*SUBTITLE|\*\*SUBTITLE\*\*|^SUBTITLE[：:])', s, re.I
        ):
            cleaned = re.sub(
                r'(■\s*SUBTITLE|\*\*SUBTITLE\*\*|SUBTITLE[：:]?)', '', s, flags=re.I
            ).strip(' :()*"\'　：')
            subtitle = cleaned or next(
                (ln.strip(' :()*"\'　：')
                 for ln in lines[i + 1:i + 3]
                 if ln.strip() and not re.search(r'(■|##|ヘッダー)', ln, re.I)),
                ""
            )

        # ハッシュタグ抽出
        if not hashtags and re.match(r'^(#[\w\u3040-\u9fff]+[\s\u3000]*){2,}', s):
            hashtags = s.strip()

        if title and subtitle and hashtags:
            break

    # フォールバック（モード別）
    fallbacks = {
        "investor": {
            "title":    f"今日の海外マーケット速報｜{datetime.now(JST).strftime('%m/%d')}",
            "subtitle": "FRB・決算・円相場から読み解く今日の投資判断",
            "hashtags": "#米国株 #新NISA #FRB #資産運用 #グローバル投資ラボ",
        },
        "exam": {
            "title":    f"受験必須！今日の時事問題解説｜{datetime.now(JST).strftime('%m/%d')}",
            "subtitle": "中学・高校・大学受験に出る今日のニュースをやさしく解説",
            "hashtags": "#中学受験 #高校受験 #時事問題 #受験勉強 #受験時事ラボ",
        },
        "light": {
            "title":    f"今日の経済ニュース3分解説｜{datetime.now(JST).strftime('%m/%d')}",
            "subtitle": "難しい経済ニュースをやさしい言葉でお届けします",
            "hashtags": "#経済ニュース #わかりやすく #子育て #生活費 #やさしい経済ラボ",
        },
    }
    fb = fallbacks.get(mode, fallbacks["investor"])
    if not title:    title    = fb["title"]
    if not subtitle: subtitle = fb["subtitle"]
    if not hashtags: hashtags = fb["hashtags"]

    # 本文抽出（## 以降）
    body_start = next(
        (i for i, l in enumerate(lines)
         if l.strip().startswith('## ')
         and not re.search(r'(TITLE|SUBTITLE|ヘッダー画像|画像テキスト|ハッシュタグ)', l, re.I)),
        None
    )
    if body_start is not None:
        body = "\n".join(lines[body_start:]).strip()
    else:
        body = "\n".join(
            ln for ln in lines
            if not re.search(
                r'(■\s*TITLE|■\s*SUBTITLE|\*\*TITLE|\*\*SUBTITLE'
                r'|【画像テキスト】|ハッシュタグ)', ln, re.I
            )
        )

    return {
        "title":        title,
        "subtitle":     subtitle,
        "hashtags":     hashtags,
        "body":         body,
        "generated_at": datetime.now(JST).isoformat(),
        "day_label":    datetime.now(JST).strftime("%Y-%m-%d"),
        "model":        MODEL_ID,
        "mode":         mode,
        "platform":     "note",
        "price":        500 if mode in ("investor", "exam") else 300,
    }

# ─── メイン生成関数 ───────────────────────────────

def generate_note_article(market_data: dict, intel: dict, mode: str = "investor") -> dict:
    """Gemmaを使ってNote記事を生成し、data/note_draft.json と note_post.txt に保存する"""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print(f"📝 Note記事生成中... [mode={mode}]")
    prompt   = build_note_prompt(market_data, intel, mode)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.75,
            max_output_tokens=4096,
            system_instruction=SYSTEM_PROMPTS[mode],
        ),
    )

    result = _parse_article(response.text, mode)

    # ── 保存 ──
    DATA_DIR.mkdir(exist_ok=True)
    draft_path = DATA_DIR / "note_draft.json"
    txt_path   = DATA_DIR / "note_post.txt"

    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"【タイトル】{result['title']}\n")
        f.write(f"【サブタイトル】{result['subtitle']}\n")
        f.write(f"【ハッシュタグ】{result['hashtags']}\n")
        f.write(f"【価格】{result['price']}円\n")
        f.write(f"【モード】{mode}\n\n")
        f.write(result["body"])

    # ── プレビュー ──
    print("=" * 60)
    print(f"✅ 生成完了 [mode={mode}]")
    print(f"   タイトル  : {result['title']}")
    print(f"   サブタイトル: {result['subtitle']}")
    print(f"   ハッシュタグ: {result['hashtags']}")
    print(f"   価格      : {result['price']}円")
    print(f"   本文先頭  :\n{result['body'][:200]}")
    print("=" * 60)

    return result


# ─── エントリポイント ─────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Note記事生成")
    parser.add_argument(
        "--mode",
        choices=["investor", "exam", "light"],
        default=None,   # None のとき曜日で自動決定
        help="記事モード (investor/exam/light)。省略時は曜日で自動決定",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    # ── 曜日でモード自動決定 ──────────────────────────────
    # 月(0)・木(3)・日(6) → investor
    # 火(1)・金(4)        → exam
    # 水(2)・土(5)        → light
    if args.mode is None:
        dow = datetime.now(JST).weekday()   # 0=月 〜 6=日
        mode = {
            0: "investor",
            1: "exam",
            2: "light",
            3: "investor",
            4: "exam",
            5: "light",
            6: "investor",
        }[dow]
        print(f"📅 曜日自動判定: {['月','火','水','木','金','土','日'][dow]}曜日 → mode={mode}")
    else:
        mode = args.mode

    weekly_path = DATA_DIR / "weekly_data.json"
    intel_path  = DATA_DIR / "overseas_intel.json"

    if not weekly_path.exists():
        print("⚠️  data/weekly_data.json が見つかりません。")
        exit(1)
    if not intel_path.exists():
        print("⚠️  data/overseas_intel.json が見つかりません。")
        exit(1)

    market_data = _load_json(weekly_path)
    intel       = _load_json(intel_path)

    generate_note_article(market_data, intel, mode=mode)

