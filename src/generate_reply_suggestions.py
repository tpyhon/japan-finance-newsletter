# generate_reply_suggestions.py
# Monitors finance-related tweets and generates English reply suggestions
# using Gemma-4. No X API key required (uses Nitter via ntscraper).
# Output: data/reply_suggestions.txt (human reviews and manually replies)

import os
import json
import time
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "reply_suggestions.txt"

# Search queries targeting English-speaking finance/Japan market audience
SEARCH_QUERIES = [
    "Japan stocks",
    "Nikkei 225",
    "Bank of Japan BOJ",
    "USD JPY yen",
    "invest in Japan",
    "Japanese equities",
    "Japan economy",
    "Nikkei investing",
]

# Filters: only engage with tweets that meet these criteria
MIN_LIKES = 3        # avoid zero-engagement posts
MAX_TWEETS_PER_QUERY = 5
MAX_TOTAL_TWEETS = 20

# ---------------------------------------------------------------------------
# System prompt for Gemma-4
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a knowledgeable financial commentator who runs 
"Japan Finance Weekly" — a free English newsletter covering Japanese markets 
for global investors. You write thoughtful, expert replies to tweets about 
Japan's financial markets, BOJ policy, USD/JPY, and related topics.

Your reply style:
- Add genuine insight the original poster may not have considered
- Reference Japan-specific context (BOJ policy, TSE reforms, yen dynamics)
- Sound like a knowledgeable peer, not a salesperson
- Maximum 2-3 sentences (fits in a tweet reply)
- NEVER say "Great tweet!" or "Interesting point!" — get straight to the insight
- End naturally — do NOT add "Follow me" or promotional text
  (the human will decide whether to add that manually)
- Write in English only"""

def build_reply_prompt(tweet: dict) -> str:
    return f"""Generate a high-quality reply to this tweet about Japanese markets/finance.

TWEET AUTHOR: @{tweet.get('username', 'unknown')}
TWEET TEXT: {tweet.get('text', '')}
LIKES: {tweet.get('likes', 0)}
DATE: {tweet.get('date', '')}

Requirements:
- 2-3 sentences maximum
- Add a specific data point or insight about Japan markets
- Sound like a knowledgeable peer, not promotional
- End with a natural conversation-starter question (optional but preferred)

Return ONLY the reply text. No quotes, no explanation, just the reply."""

# ---------------------------------------------------------------------------
# Tweet fetching via ntscraper
# ---------------------------------------------------------------------------
def fetch_tweets(queries: list) -> list:
    try:
        from ntscraper import Nitter
    except ImportError:
        print("  ERROR: ntscraper not installed.")
        print("  Run: .venv\\Scripts\\python.exe -m pip install ntscraper")
        return []

    print(f"  Initializing Nitter scraper...")
    scraper = Nitter(log_level=0, skip_instance_check=False)

    all_tweets = []
    seen_ids = set()

    for query in queries:
        print(f"  Searching: '{query}'...")
        try:
            results = scraper.get_tweets(
                query,
                mode="term",
                number=MAX_TWEETS_PER_QUERY,
                language="en"
            )

            tweets = results.get("tweets", [])
            for tweet in tweets:
                tweet_id = tweet.get("link", "")

                # Deduplication
                if tweet_id in seen_ids:
                    continue
                seen_ids.add(tweet_id)

                # Filter: minimum engagement
                likes = tweet.get("stats", {}).get("likes", 0)
                if likes < MIN_LIKES:
                    continue

                # Filter: skip retweets
                text = tweet.get("text", "")
                if text.startswith("RT @"):
                    continue

                # Filter: skip if too short (low value)
                if len(text) < 60:
                    continue

                all_tweets.append({
                    "username": tweet.get("user", {}).get("username", "unknown"),
                    "text": text,
                    "likes": likes,
                    "date": tweet.get("date", ""),
                    "link": tweet_id,
                    "query": query
                })

            # Rate limiting - be gentle with Nitter instances
            time.sleep(3)

        except Exception as e:
            print(f"    WARNING: Query '{query}' failed: {e}")
            continue

    # Sort by likes descending (prioritize high-engagement tweets)
    all_tweets.sort(key=lambda x: x.get("likes", 0), reverse=True)

    # Limit total
    return all_tweets[:MAX_TOTAL_TWEETS]

# ---------------------------------------------------------------------------
# Reply generation via Gemma-4
# ---------------------------------------------------------------------------
def generate_replies(client: genai.Client, tweets: list) -> list:
    results = []

    for i, tweet in enumerate(tweets, 1):
        print(f"  [{i}/{len(tweets)}] Generating reply for @{tweet['username']}...")

        try:
            prompt = build_reply_prompt(tweet)

            response = client.models.generate_content(
                model="gemma-4-26b-a4b-it",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.75,
                    max_output_tokens=200,
                )
            )

            reply_text = response.text.strip()

            results.append({
                "tweet": tweet,
                "reply": reply_text
            })

            # Small delay between API calls
            time.sleep(2)

        except Exception as e:
            print(f"    WARNING: Reply generation failed: {e}")
            continue

    return results

# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def save_output(results: list):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "=" * 70,
        f"REPLY SUGGESTIONS - Japan Finance Weekly",
        f"Generated: {now}",
        f"Total suggestions: {len(results)}",
        "=" * 70,
        "",
        "HOW TO USE:",
        "  1. Review each suggestion below",
        "  2. Edit if needed (add your own flair)",
        "  3. Open X and manually reply to the tweet",
        "  4. Optional: add 'More in Japan Finance Weekly (link in bio)'",
        "",
        "=" * 70,
    ]

    for i, item in enumerate(results, 1):
        tweet = item["tweet"]
        reply = item["reply"]

        lines += [
            "",
            f"[{i:02d}] {'=' * 60}",
            f"QUERY     : {tweet.get('query', '')}",
            f"AUTHOR    : @{tweet.get('username', '')}",
            f"LIKES     : {tweet.get('likes', 0)}",
            f"DATE      : {tweet.get('date', '')}",
            f"TWEET URL : {tweet.get('link', '')}",
            "",
            "ORIGINAL TWEET:",
            f"  {tweet.get('text', '')}",
            "",
            "SUGGESTED REPLY:",
            f"  {reply}",
            "",
            "MANUAL REPLY STEPS:",
            f"  1. Open: {tweet.get('link', 'URL not available')}",
            f"  2. Click Reply",
            f"  3. Paste the suggested reply above",
            f"  4. Edit as needed → Post",
            "-" * 70,
        ]

    lines += [
        "",
        "=" * 70,
        "END OF SUGGESTIONS",
        "=" * 70,
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Saved: {OUTPUT_FILE}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("=" * 60)
    print(" Reply Suggestion Generator - Japan Finance Weekly")
    print(" Target: English-speaking finance/Japan market Twitter")
    print("=" * 60)

    # Load API key
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env file")

    client = genai.Client(api_key=api_key)
    print(f" Model  : gemma-4-26b-a4b-it")
    print(f" Output : {OUTPUT_FILE}")
    print()

    # Step 1: Fetch tweets
    print("[Step 1/2] Fetching tweets via Nitter...")
    tweets = fetch_tweets(SEARCH_QUERIES)

    if not tweets:
        print()
        print("  No tweets found.")
        print("  Possible reasons:")
        print("  - Nitter instances may be down (try again later)")
        print("  - ntscraper not installed (run pip install ntscraper)")
        return

    print(f"  Found {len(tweets)} qualifying tweets")
    print()

    # Step 2: Generate replies
    print("[Step 2/2] Generating reply suggestions with Gemma-4...")
    results = generate_replies(client, tweets)
    print()

    # Save output
    save_output(results)

    # Summary
    print()
    print("=" * 60)
    print(f" COMPLETE: {len(results)} reply suggestions generated")
    print()
    print(" NEXT STEPS:")
    print(f"  1. Open: data/reply_suggestions.txt")
    print(f"  2. Review each suggestion")
    print(f"  3. Manually reply on X (takes ~10 min for all)")
    print("=" * 60)
    print()

if __name__ == "__main__":
    main()
