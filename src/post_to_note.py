# src/post_to_note.py
"""
Note API（非公式）を使ってrequestsのみで記事を投稿する
Selenium不要・GitHub Actionsで確実動作
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

BASE_URL   = "https://note.com"
OUTPUT_DIR = Path("data")


# ═══════════════════════════════════════════════
# ユーティリティ
# ═══════════════════════════════════════════════

def markdown_to_note_html(text: str) -> str:
    """
    Markdown本文をnoteエディタ形式のHTMLに変換する
    （draft_saveのbodyに必要な形式）
    """
    import uuid
    lines   = text.split("\n")
    html_parts = []

    for line in lines:
        uid = str(uuid.uuid4())

        # 空行
        if not line.strip():
            html_parts.append(
                f'<p name="{uid}" id="{uid}"><br></p>'
            )
        # h2見出し
        elif line.startswith("## "):
            content = line[3:].strip()
            html_parts.append(
                f'<h2 name="{uid}" id="{uid}">{content}</h2>'
            )
        # h3見出し
        elif line.startswith("### "):
            content = line[4:].strip()
            html_parts.append(
                f'<h3 name="{uid}" id="{uid}">{content}</h3>'
            )
        # 箇条書き
        elif line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            html_parts.append(
                f'<ul><li name="{uid}" id="{uid}">{content}</li></ul>'
            )
        # 通常段落
        else:
            # **太字** をboldタグに変換
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            html_parts.append(
                f'<p name="{uid}" id="{uid}">{content}</p>'
            )

    return "".join(html_parts)


def notify_slack(webhook_url: str, message: str) -> None:
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"text": message}, timeout=10)
        log.info("📣 Slack通知送信完了")
    except Exception as e:
        log.warning(f"Slack通知失敗（続行）: {e}")


# ═══════════════════════════════════════════════
# Note API クライアント
# ═══════════════════════════════════════════════

class NoteClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer":         "https://note.com/",
            "Origin":          "https://note.com",
            "Content-Type":    "application/json",
            "Accept":          "application/json",
        })

    # ── ログイン ─────────────────────────────────
    # NoteClient の login() と load_cookies() を修正

    def login(self, email: str, password: str) -> None:
        """
        環境変数にCookieが設定されている場合はそれを優先使用。
        ない場合はメール/パスワードでログイン。
        """
        # ★ GitHub Actions用：Secretから直接Cookieを注入
        session_cookie = os.environ.get("NOTE_SESSION_COOKIE", "")
        if session_cookie:
            log.info("🍪 環境変数からセッションCookieを注入...")
            self.session.cookies.set(
                "_note_session_v5",
                session_cookie,
                domain="note.com",
            )
            # セッション有効性を確認
            resp = self.session.get(
                "https://note.com/api/v2/users/current",
                timeout=10,
            )
            log.info(f"セッション確認: {resp.status_code} {resp.text[:100]}")
            if resp.status_code == 200:
                log.info("✅ Cookie認証成功")
                return
            else:
                log.warning("⚠️ Cookie無効、メール/パスワードでログインします")

        # 通常のメール/パスワードログイン
        log.info("🔑 noteにAPIログイン中...")
        resp = self.session.post(
            f"{BASE_URL}/api/v1/sessions/sign_in",
            json={
                "login":         email,
                "password":      password,
                "redirect_path": "",
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"ログイン失敗: {resp.status_code} {resp.text[:200]}")

        # 新しいCookieを保存
        cookie_dict = dict(self.session.cookies)
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_DIR / "note_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookie_dict, f, ensure_ascii=False, indent=2)

        log.info("✅ ログイン成功")


    # ── 既存Cookieでセッション復元 ───────────────
    def load_cookies(self) -> bool:
        cookie_path = OUTPUT_DIR / "note_cookies.json"
        if not cookie_path.exists():
            return False
        with open(cookie_path, encoding="utf-8") as f:
            cookies = json.load(f)
        for k, v in cookies.items():
            self.session.cookies.set(k, v)
        log.info("🍪 既存Cookieを読み込みました")
        return True

    # ── 新規下書き記事を作成（空で作成してIDを取得）──
    def create_draft(self) -> dict:
        log.info("📄 下書き記事を新規作成...")
        resp = self.session.post(
            f"{BASE_URL}/api/v1/text_notes",
            json={"template_key": None},
        )

        # ★ レスポンス全体をログに出す
        log.info(f"create_draft response: {resp.status_code} {resp.text[:300]}")

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"下書き作成失敗: {resp.status_code} {resp.text[:200]}")

        body = resp.json()

        # ★ "data"キーがない場合のフォールバック
        if "data" in body:
            data = body["data"]
        elif "id" in body:
            # レスポンスがそのままdataの場合
            data = body
        else:
            raise RuntimeError(f"予期しないレスポンス形式: {body}")

        note_id  = data["id"]
        note_key = data["key"]
        log.info(f"✅ 下書き作成完了: id={note_id}, key={note_key}")
        return data


    # ── 本文・タイトルを保存 ──────────────────────
    def save_draft(
        self,
        note_id: int,
        title: str,
        body_html: str,
    ) -> None:
        log.info(f"💾 下書き保存中: id={note_id}")
        resp = self.session.post(
            f"{BASE_URL}/api/v1/text_notes/draft_save",
            params={
                "id":           note_id,
                "is_temp_saved": "true",
            },
            json={
                "name":         title,
                "body":         body_html,
                "body_length":  len(body_html),
                "index":        False,
                "is_lead_form": False,
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"下書き保存失敗: {resp.status_code} {resp.text[:200]}")
        log.info("✅ 下書き保存完了")

    # ── 有料設定・タグ・公開 ──────────────────────
    def publish(
        self,
        note_id: int,
        note_key: str,
        title: str,
        body_html: str,
        hashtags: list[str],
        price: int = 500,
    ) -> str:
        log.info(f"🚀 記事を公開中: id={note_id}")

        # 公開前に最終保存（価格・タグ込み）
        resp = self.session.post(
            f"{BASE_URL}/api/v1/text_notes/draft_save",
            params={
                "id":            note_id,
                "is_temp_saved": "false",
            },
            json={
                "name":          title,
                "body":          body_html,
                "body_length":   len(body_html),
                "price":         price,
                "hashtag_list":  hashtags,
                "index":         True,
                "is_lead_form":  False,
                "publish":       True,
                "status":        "published",
            },
        )
        log.info(f"公開API応答: {resp.status_code} {resp.text[:300]}")

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"公開失敗: {resp.status_code} {resp.text[:300]}")

        article_url = f"https://note.com/notes/{note_key}"
        log.info(f"✅ 公開完了: {article_url}")
        return article_url


# ═══════════════════════════════════════════════
# メイン
# ═══════════════════════════════════════════════

def main():
    email         = os.environ["NOTE_EMAIL"]
    password      = os.environ["NOTE_PASSWORD"]
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL", "")

    # ── note_draft.json 読み込み ──────────────────
    draft_path = OUTPUT_DIR / "note_draft.json"
    if not draft_path.exists():
        raise FileNotFoundError(
            "data/note_draft.json が見つかりません。"
            "generate_note_jp.py を先に実行してください。"
        )
    with open(draft_path, encoding="utf-8") as f:
        draft = json.load(f)

    title    = draft["title"]
    body_md  = draft["body"]
    price    = draft.get("price", 500)
    hashtags_raw = draft.get(
        "hashtags",
        "#米国株 #新NISA #FRB #資産運用 #グローバル投資ラボ週報"
    )

    # ハッシュタグを#なしのリストに変換
    hashtags = [t.lstrip("#").strip() for t in hashtags_raw.split() if t.startswith("#")][:5]

    log.info(f"📄 タイトル   : {title}")
    log.info(f"🏷️  ハッシュタグ: {hashtags}")
    log.info(f"💴 価格       : {price}円")

    # ── HTML変換 ──────────────────────────────────
    body_html = markdown_to_note_html(body_md)
    log.info(f"📝 HTML変換完了: {len(body_html)}文字")

    # ── APIクライアント初期化・ログイン ───────────
    client = NoteClient()
    client.login(email, password)

    # ── 下書き作成 → 保存 → 公開 ─────────────────
    try:
        note_data = client.create_draft()
        note_id   = note_data["id"]
        note_key  = note_data["key"]

        client.save_draft(note_id, title, body_html)
        time.sleep(1)

        article_url = client.publish(
            note_id   = note_id,
            note_key  = note_key,
            title     = title,
            body_html = body_html,
            hashtags  = hashtags,
            price     = price,
        )

        notify_slack(
            slack_webhook,
            f"✅ *note記事を投稿しました*\n"
            f"📝 {title}\n"
            f"💴 {price}円\n"
            f"🔗 {article_url}",
        )
        log.info("=== 全処理完了 ===")

    except Exception as e:
        log.error(f"❌ 投稿失敗: {e}")
        notify_slack(
            slack_webhook,
            f"❌ *note投稿に失敗しました*\n"
            f"📝 {title}\n"
            f"エラー: {e}",
        )
        raise
    # ★ ローカル実行時：新しいCookieをSecretに登録するよう通知
    if not os.environ.get("NOTE_SESSION_COOKIE"):
        new_cookie = client.session.cookies.get("_note_session_v5", "")
        if new_cookie:
            log.info(f"\n{'='*50}")
            log.info("📋 GitHub Secretsを以下の値で更新してください:")
            log.info(f"   Secret名: NOTE_SESSION_COOKIE")
            log.info(f"   値: {new_cookie}")
            log.info(f"{'='*50}\n")


if __name__ == "__main__":
    main()
