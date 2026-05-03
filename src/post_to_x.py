"""post_to_x.py - generate X (Twitter) post text for manual copy-paste"""
import json
import os
import datetime
from dotenv import load_dotenv

load_dotenv()


def build_tweet_text(draft: dict) -> str:
    subject = draft.get("subject", "Japan Finance Weekly")
    preview = draft.get("preview_text", "")

    tweet = f"📊 {subject}\n\n{preview}\n\n🗾 #JapanFinance #Nikkei #investing"

    # 280文字超えた場合はpreviewを切り詰める
    if len(tweet) > 280:
        max_preview = 280 - len(f"📊 {subject}\n\n…\n\n🗾 #JapanFinance #Nikkei #investing")
        preview_cut = preview[:max_preview]
        tweet = f"📊 {subject}\n\n{preview_cut}…\n\n🗾 #JapanFinance #Nikkei #investing"

    return tweet


def generate_x_post(draft: dict) -> str:
    tweet_text = build_tweet_text(draft)

    os.makedirs("data", exist_ok=True)

    # テキストファイルとして保存
    txt_path = "data/x_post.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write("X (Twitter) 投稿用テキスト\n")
        f.write(f"生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 50 + "\n\n")
        f.write(tweet_text)
        f.write("\n\n" + "=" * 50 + "\n")
        f.write(f"文字数: {len(tweet_text)} / 280\n")
        f.write("=" * 50 + "\n")

    # ログ保存
    log = {
        "generated_at": datetime.datetime.now().isoformat(),
        "tweet_text": tweet_text,
        "char_count": len(tweet_text),
        "txt_path": txt_path,
    }
    with open("data/x_post_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    # ターミナルにも表示
    print("✅ X投稿用テキストを生成しました！")
    print(f"📁 ファイル: {txt_path}")
    print(f"📝 文字数: {len(tweet_text)} / 280")
    print("\n" + "=" * 50)
    print("【コピペ用テキスト】")
    print("=" * 50)
    print(tweet_text)
    print("=" * 50)

    return tweet_text


if __name__ == "__main__":
    with open("data/newsletter_draft.json", encoding="utf-8") as f:
        draft = json.load(f)
    generate_x_post(draft)
