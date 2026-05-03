"""
collect_overseas_intel.py
日本人がアクセスしていない海外一次情報を収集して
data/overseas_intel.json に保存する
"""

import json
import os
import requests
import feedparser
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


# ── 1. FRB（米連邦準備制度）公式RSS ──────────────────────────
def collect_fed_news() -> list:
    """FRBの公式プレスリリース・FEDS Notesを取得"""
    sources = [
        {
            "name": "Federal Reserve Press Releases",
            "url":  "https://www.federalreserve.gov/feeds/press_all.xml",
        },
        {
            "name": "Fed FEDS Notes",
            "url":  "https://www.federalreserve.gov/feeds/feds_notes.xml",
        },
    ]
    results = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:3]:
                results.append({
                    "source":  src["name"],
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link":    entry.get("link", ""),
                    "date":    entry.get("published", ""),
                })
        except Exception as e:
            print(f"⚠️ FED RSS error: {e}")
    return results


# ── 2. SEC EDGAR 最新開示（大手企業の8-K/10-Q） ──────────────
def collect_sec_filings() -> list:
    """SECの最新重要開示（8-K）を取得 - 日本関連企業含む"""
    # SEC公式RSSフィード（最新のForm 8-K）
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=10&output=atom"
    results = []
    try:
        headers = {"User-Agent": "JapanFinanceNewsletter contact@example.com"}
        resp = feedparser.parse(url)
        for entry in resp.entries[:5]:
            results.append({
                "source":  "SEC EDGAR 8-K",
                "title":   entry.get("title", ""),
                "summary": entry.get("summary", "")[:300],
                "link":    entry.get("link", ""),
                "date":    entry.get("published", ""),
            })
    except Exception as e:
        print(f"⚠️ SEC RSS error: {e}")
    return results


# ── 3. Alpha Vantage：注目経済指標ニュース（無料APIキー） ──────
def collect_alpha_vantage_news() -> list:
    """Alpha Vantage News Sentiment API（無料枠25req/日）"""
    api_key = os.getenv("ALPHA_VANTAGE_KEY", "demo")
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT"
        f"&topics=economy_macro,finance,forex"
        f"&sort=LATEST&limit=10"
        f"&apikey={api_key}"
    )
    results = []
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        for item in data.get("feed", [])[:5]:
            results.append({
                "source":        item.get("source", ""),
                "title":         item.get("title", ""),
                "summary":       item.get("summary", "")[:300],
                "link":          item.get("url", ""),
                "date":          item.get("time_published", ""),
                "sentiment":     item.get("overall_sentiment_label", ""),
                "sentiment_score": item.get("overall_sentiment_score", 0),
            })
    except Exception as e:
        print(f"⚠️ Alpha Vantage error: {e}")
    return results


# ── 4. 高品質英語金融RSSフィード ──────────────────────────────
def collect_premium_rss() -> list:
    """英語圏プロ投資家が読むRSSフィード"""
    sources = [
        # マクロ経済
        {
            "name": "WSJ Markets",
            "url":  "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
        },
        {
            "name": "MarketWatch Top Stories",
            "url":  "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        },
        # FRB・金融政策
        {
            "name": "Calculated Risk (Macro Blog)",
            "url":  "https://feeds.feedburner.com/calculatedrisk",
        },
        # 投資戦略
        {
            "name": "Seeking Alpha Market News",
            "url":  "https://seekingalpha.com/market_currents.xml",
        },
        # 国際経済
        {
            "name": "IMF News",
            "url":  "https://www.imf.org/en/News/rss?language=eng",
        },
        {
            "name": "World Bank News",
            "url":  "https://feeds.worldbank.org/news/rss",
        },
        # 米国経済指標
        {
            "name": "BLS Economic News",
            "url":  "https://www.bls.gov/feed/bls_latest.rss",
        },
    ]

    keywords = [
        "interest rate", "inflation", "GDP", "recession", "federal reserve",
        "dollar", "yen", "japan", "asia", "emerging market", "bond",
        "stock market", "earnings", "investment", "portfolio", "etf",
        "cryptocurrency", "oil", "commodity", "trade war", "tariff",
    ]

    results = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                if count >= 3:
                    break
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                combined = (title + " " + summary).lower()
                if any(kw in combined for kw in keywords):
                    results.append({
                        "source":  src["name"],
                        "title":   title,
                        "summary": summary[:300],
                        "link":    entry.get("link", ""),
                        "date":    entry.get("published", ""),
                    })
                    count += 1
        except Exception as e:
            print(f"⚠️ RSS error ({src['name']}): {e}")

    return results


# ── 5. Reddit r/investing・r/personalfinance トレンド ──────────
def collect_reddit_trends() -> list:
    """Redditの投資系サブレディットのホットトピックを取得（API不要）"""
    subreddits = [
        "investing",
        "personalfinance",
        "Economics",
        "financialindependence",
    ]
    results = []
    headers = {"User-Agent": "JapanFinanceNewsletter/1.0"}

    for sub in subreddits:
        try:
            url  = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            posts = resp.json()["data"]["children"]
            for post in posts[:3]:
                d = post["data"]
                # アップボート数が一定以上のもののみ
                if d.get("score", 0) < 500:
                    continue
                results.append({
                    "source":    f"Reddit r/{sub}",
                    "title":     d.get("title", ""),
                    "summary":   d.get("selftext", "")[:200] or "(Link post)",
                    "link":      f"https://reddit.com{d.get('permalink', '')}",
                    "score":     d.get("score", 0),
                    "comments":  d.get("num_comments", 0),
                })
        except Exception as e:
            print(f"⚠️ Reddit error (r/{sub}): {e}")

    return results


# ── 6. 米国決算カレンダー（Finnhub 無料API） ──────────────────
def collect_earnings_calendar() -> list:
    """今週の主要決算をFinnhub無料APIで取得"""
    api_key = os.getenv("FINNHUB_KEY", "")
    if not api_key:
        return [{"note": "FINNHUB_KEY not set - skipping earnings calendar"}]

    from datetime import timedelta
    today     = datetime.now()
    next_week = today + timedelta(days=7)
    url = (
        f"https://finnhub.io/api/v1/calendar/earnings"
        f"?from={today.strftime('%Y-%m-%d')}"
        f"&to={next_week.strftime('%Y-%m-%d')}"
        f"&token={api_key}"
    )
    results = []
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        for item in data.get("earningsCalendar", [])[:10]:
            results.append({
                "symbol":       item.get("symbol", ""),
                "date":         item.get("date", ""),
                "eps_estimate": item.get("epsEstimate"),
                "revenue_est":  item.get("revenueEstimate"),
            })
    except Exception as e:
        print(f"⚠️ Finnhub error: {e}")
    return results


# ── メイン ──────────────────────────────────────────────────
def collect_all_intel() -> dict:
    print("🏛️  Collecting FED official news...")
    fed   = collect_fed_news()

    print("📋  Collecting SEC EDGAR filings...")
    sec   = collect_sec_filings()

    print("📡  Collecting Alpha Vantage news sentiment...")
    av    = collect_alpha_vantage_news()

    print("📰  Collecting premium RSS feeds...")
    rss   = collect_premium_rss()

    print("💬  Collecting Reddit investment trends...")
    reddit = collect_reddit_trends()

    print("📅  Collecting earnings calendar...")
    earnings = collect_earnings_calendar()

    data = {
        "collected_at":   datetime.now().isoformat(),
        "week_label":     datetime.now().strftime("%Y-W%V"),
        "fed_news":       fed,
        "sec_filings":    sec,
        "alpha_vantage":  av,
        "premium_rss":    rss,
        "reddit_trends":  reddit,
        "earnings_calendar": earnings,
    }

    os.makedirs("data", exist_ok=True)
    path = "data/overseas_intel.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Overseas intel saved to {path}")
    print(f"   FED news      : {len(fed)} items")
    print(f"   SEC filings   : {len(sec)} items")
    print(f"   Alpha Vantage : {len(av)} items")
    print(f"   Premium RSS   : {len(rss)} items")
    print(f"   Reddit trends : {len(reddit)} items")
    print(f"   Earnings cal  : {len(earnings)} items")

    return data


if __name__ == "__main__":
    collect_all_intel()
