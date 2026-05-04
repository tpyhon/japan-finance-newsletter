# src/generate_x_posts.py
# Fetches Japan economic news from RSS feeds, generates 10 English X posts
# per run using Gemma-4, and saves them to data/x_daily_posts.txt
# Run locally as needed (e.g., via Windows Task Scheduler once per day)

import os
import json
import time
import hashlib
import feedparser
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from google import genai

# ── Config ──────────────────────────────────────────────────────────────────
MODEL           = "gemma-4-26b-a4b-it"
POSTS_PER_RUN   = 10
MAX_CHARS       = 260          # leave margin below 280
SEEN_FILE       = Path(__file__).resolve().parent.parent / "data" / "seen_articles.json"
OUTPUT_FILE     = Path(__file__).resolve().parent.parent / "data" / "x_daily_posts.txt"
LOOKBACK_HOURS  = 48           # ignore articles older than this

# ── RSS Sources (English, Japan economy/finance focus) ───────────────────────
RSS_FEEDS = [
    # 既存の英語ニュースソース（typeを追加）
    {"name": "Japan Times – Economy", "url": "https://www.japantimes.co.jp/feed/",                              "weight": 3, "type": "news"},
    {"name": "Japan Times – Business","url": "https://www.japantimes.co.jp/business/",                          "weight": 2, "type": "news"},
    {"name": "Kyodo News",            "url": "https://english.kyodonews.net/list/feed/rss4kyodonews-fzone",     "weight": 3, "type": "news"},
    {"name": "NHK World",             "url": "https://www3.nhk.or.jp/nhkworld/data/en/news/backstory/rss.xml",  "weight": 2, "type": "news"},
    {"name": "Reuters Asia",          "url": "https://feeds.reuters.com/reuters/businessNews",                  "weight": 2, "type": "news"},

    # 一次情報ソース（日本語・高優先度）
    {"name": "BOJ Press Releases",    "url": "https://www.boj.or.jp/en/announcements/release_2026/index.htm/rss.xml", "weight": 5, "type": "primary"},
    {"name": "MOF Japan",             "url": "https://www.mof.go.jp/rss/mof_rss.xml",                          "weight": 5, "type": "primary"},
    {"name": "JPX (TSE Disclosure)",  "url": "https://www.jpx.co.jp/english/rss/index.html",                   "weight": 4, "type": "primary"},
]

# Finance/economy keywords to filter relevant articles
KEYWORDS = [
    "japan", "nikkei", "topix", "yen", "boj", "bank of japan",
    "japanese", "tokyo", "gdp", "inflation", "interest rate",
    "fiscal", "trade", "exports", "imports", "economy", "stocks",
    "ipo", "earnings", "corporate", "semiconductor", "toyota",
    "sony", "softbank", "honda", "hitachi", "panasonic",
    "usd/jpy", "currency", "forex", "market", "investment",
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_seen() -> set:
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # prune entries older than 7 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        data = {k: v for k, v in data.items() if v >= cutoff}
        return set(data.keys()), data
    return set(), {}

def save_seen(seen_dict: dict):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_dict, f, ensure_ascii=False, indent=2)

def article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in KEYWORDS)

def fetch_articles() -> list[dict]:
    """Fetch and filter recent Japan economy articles from all RSS feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    articles = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                # parse publication date
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if pub and pub < cutoff:
                    continue  # too old

                title   = getattr(entry, "title",   "").strip()
                summary = getattr(entry, "summary", "").strip()
                link    = getattr(entry, "link",    "").strip()

                if not title or not link:
                    continue
                if not is_relevant(title, summary):
                    continue

                articles.append({
                    "id":      article_id(link),
                    "source":  feed_info["name"],
                    "title":   title,
                    "summary": summary[:300],
                    "url":     link,
                    "pub":     pub.isoformat() if pub else "",
                    "weight":  feed_info["weight"],
                })
        except Exception as e:
            print(f"  ⚠️  Feed error [{feed_info['name']}]: {e}")

    return articles

# ── Gemini tweet generation ───────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a sharp financial journalist running "Japan Finance Weekly",
a newsletter for global (English-speaking) investors interested in Japan.
Your X (Twitter) posts are concise, insightful, and occasionally contrarian.
Tone: professional but not stuffy. No fluff. Lead with the most surprising fact.
"""

def build_tweet_prompt(article: dict) -> str:
    # 一次情報ソース（BOJ・MOF等）の場合はプロンプトを切り替え
    if article.get("type") == "primary":
        hook_instruction = (
            "Start with '🇯🇵 JUST IN (Japanese source):' as the first line. "
            "Emphasize this is sourced directly from Japanese authorities, "
            "not yet widely covered in English media."
        )
    else:
        hook_instruction = (
            "Start with a compelling hook: a number, %, surprising fact, or bold claim."
        )

    return f"""{SYSTEM_PROMPT}

Write ONE X (Twitter) post in English about the news below.

Rules:
- Maximum {MAX_CHARS} characters (STRICTLY enforced — count carefully)
- {hook_instruction}
- Add 1-2 relevant hashtags at the end (e.g. #JapanStocks #Nikkei #USDJPY #BOJ #JapanEconomy)
- Do NOT include a URL (will be added manually)
- Do NOT use em-dashes or exotic punctuation
- Output the tweet text ONLY — no explanation, no quotes

News headline: {article['title']}
Summary: {article['summary']}
Source: {article['source']}

Tweet:"""


def generate_tweet(client: genai.Client, article: dict) -> str | None:
    try:
        resp = client.models.generate_content(
            model    = MODEL,
            contents = build_tweet_prompt(article),
        )
        tweet = resp.text.strip().strip('"').strip("'")
        # safety truncate if model overshoots
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        return tweet
    except Exception as e:
        print(f"  ⚠️  Gemini error: {e}")
        return None

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")

    print(f"Model     : {MODEL}")
    print(f"Output    : {OUTPUT_FILE}")
    print(f"Target    : {POSTS_PER_RUN} posts")
    print()

    # load seen article IDs (deduplication)
    seen_ids, seen_dict = load_seen()
    print(f"[Step 1/3] Fetching articles (seen cache: {len(seen_ids)} entries)...")
    articles = fetch_articles()

    # filter already-seen
    new_articles = [a for a in articles if a["id"] not in seen_ids]
    print(f"           Total found : {len(articles)}")
    print(f"           New (unseen): {len(new_articles)}")

    if not new_articles:
        print("No new articles found. Try again later or increase LOOKBACK_HOURS.")
        return

    # sort by weight (higher = preferred source) then by pub date descending
    new_articles.sort(key=lambda x: (x["weight"], x["pub"]), reverse=True)
    # pick top N candidates (slightly more than needed for fallback)
    candidates = new_articles[:POSTS_PER_RUN + 5]

    print(f"\n[Step 2/3] Generating tweets with Gemini...")
    client = genai.Client(api_key=api_key)

    posts  = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, article in enumerate(candidates):
        if len(posts) >= POSTS_PER_RUN:
            break
        print(f"  [{i+1}/{len(candidates)}] {article['title'][:70]}...")
        tweet = generate_tweet(client, article)
        if tweet:
            posts.append({
                "n":      len(posts) + 1,
                "tweet":  tweet,
                "chars":  len(tweet),
                "source": article["source"],
                "title":  article["title"],
                "url":    article["url"],
            })
            # mark as seen
            seen_dict[article["id"]] = now_iso
        time.sleep(2)  # rate limit buffer

    # save seen
    save_seen(seen_dict)

    # write output file
    print(f"\n[Step 3/3] Writing output...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Japan Finance Weekly — Daily X Posts\n")
        f.write(f"Generated : {today}\n")
        f.write(f"Posts     : {len(posts)}/{POSTS_PER_RUN}\n")
        f.write("=" * 65 + "\n\n")

        for p in posts:
            f.write(f"── Post {p['n']} ({p['chars']} chars) [{p['source']}] ──\n")
            f.write(f"{p['tweet']}\n")
            f.write(f"📎 Add URL: {p['url']}\n\n")

        f.write("=" * 65 + "\n")
        f.write("Posting tips:\n")
        f.write("- Space posts 1-2 hours apart for best reach\n")
        f.write("- Add the article URL to each post before sending\n")
        f.write("- Edit freely — these are drafts\n")

    print(f"\n✅ Done! {len(posts)} posts saved to {OUTPUT_FILE.name}")
    print(f"   Open: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
