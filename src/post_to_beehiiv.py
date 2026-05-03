"""
post_to_beehiiv.py
newsletter_draft.json からbeehiivに貼り付け用のHTMLファイルを生成する
生成されたHTMLをbeehiivのPost Builderに貼り付けて送信する
"""

import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────
# Markdown → HTML 変換
# ──────────────────────────────────────────
def markdown_to_html(md: str) -> str:
    lines  = md.split("\n")
    html   = []
    in_ul  = False

    for line in lines:
        if re.match(r"^---+$", line.strip()):
            if in_ul:
                html.append("</ul>")
                in_ul = False
            html.append("<hr>")
            continue

        if line.startswith("## "):
            if in_ul:
                html.append("</ul>")
                in_ul = False
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>",
                          line[3:].strip())
            html.append(f"<h2>{text}</h2>")
            continue

        if line.startswith("### "):
            if in_ul:
                html.append("</ul>")
                in_ul = False
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>",
                          line[4:].strip())
            html.append(f"<h3>{text}</h3>")
            continue

        if line.startswith("#### "):
            if in_ul:
                html.append("</ul>")
                in_ul = False
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>",
                          line[5:].strip())
            html.append(f"<h4>{text}</h4>")
            continue

        if re.match(r"^[\-\*] ", line):
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            text = line[2:].strip()
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",          text)
            html.append(f"  <li>{text}</li>")
            continue

        if line.strip() == "":
            if in_ul:
                html.append("</ul>")
                in_ul = False
            continue

        if in_ul:
            html.append("</ul>")
            in_ul = False
        text = line.strip()
        if text:
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",          text)
            html.append(f"<p>{text}</p>")

    if in_ul:
        html.append("</ul>")

    return "\n".join(html)


# ──────────────────────────────────────────
# 投稿用ファイルを生成
# ──────────────────────────────────────────
def generate_post_files(draft: dict) -> dict:
    """
    beehiivへの貼り付け用ファイルを2種類生成する
    1. post_ready.html  : beehiivのHTML貼り付け欄に使う
    2. post_summary.txt : Subject・Previewなど投稿時に必要な情報
    """
    os.makedirs("data", exist_ok=True)

    # 1. HTML ファイル生成
    html_body = markdown_to_html(draft["body"])
    html_path = "data/post_ready.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_body)

    # 2. サマリーテキスト生成（貼り付け時の案内）
    summary = f"""
============================================================
 JAPAN FINANCE WEEKLY — 投稿用サマリー
 生成日時: {draft.get('generated_at', '')}
 対象週  : {draft.get('week_label', '')}
============================================================

【Subject Line（件名）】
{draft['subject']}

【Preview Text（プレビュー文）】
{draft.get('preview_text', '')}

【beehiivへの投稿手順】
1. https://app.beehiiv.com/posts/new を開く
2. Subject に上記「Subject Line」を貼り付ける
3. Preview に上記「Preview Text」を貼り付ける
4. Post Builderで「HTML」ブロックを追加
5. data/post_ready.html の中身を貼り付ける
6. 「Send」または「Schedule」をクリック

【本文プレビュー（先頭300文字）】
{draft['body'][:300]}...
============================================================
"""
    summary_path = "data/post_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print("✅ 投稿用ファイルを生成しました")
    print(f"   HTML    : {html_path}")
    print(f"   Summary : {summary_path}")
    print("")
    print("=" * 50)
    print(f"📋 Subject : {draft['subject']}")
    print(f"📋 Preview : {draft.get('preview_text', '')}")
    print("=" * 50)
    print("")
    print("👉 投稿手順:")
    print("   1. https://app.beehiiv.com/posts/new を開く")
    print("   2. Subjectに上記件名を設定")
    print("   3. HTMLブロックに post_ready.html の内容を貼り付ける")
    print("   4. Sendをクリック")

    log = {
        "generated_at": datetime.now().isoformat(),
        "subject":      draft["subject"],
        "preview_text": draft.get("preview_text", ""),
        "html_path":    html_path,
        "summary_path": summary_path,
        "week_label":   draft.get("week_label", ""),
    }

    with open("data/post_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    return log


if __name__ == "__main__":
    with open("data/newsletter_draft.json", encoding="utf-8") as f:
        draft = json.load(f)

    log = generate_post_files(draft)
