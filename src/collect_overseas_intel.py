"""
collect_overseas_intel.py
日本人がアクセスしていない海外一次情報を収集して
data/overseas_intel.json に保存する
"""

import json
import os
import re as _re
import requests
import feedparser
from datetime import datetime, timedelta, timezone
import email.utils
from dotenv import load_dotenv

load_dotenv()


# ── 1. FRB公式RSS ─────────────────────────────────────────────
def collect_fed_news() -> list:
    sources = [
        {"name": "Federal Reserve Press Releases",
         "url":  "https://www.federalreserve.gov/feeds/press_all.xml"},
        {"name": "Fed FEDS Notes",
         "url":  "https://www.federalreserve.gov/feeds/feds_notes.xml"},
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


# ── 2. SEC EDGAR ──────────────────────────────────────────────
def collect_sec_filings() -> list:
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=10&output=atom"
    results = []
    try:
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


# ── 3. Alpha Vantage ──────────────────────────────────────────
def collect_alpha_vantage_news() -> list:
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
                "source":          item.get("source", ""),
                "title":           item.get("title", ""),
                "summary":         item.get("summary", "")[:300],
                "link":            item.get("url", ""),
                "date":            item.get("time_published", ""),
                "sentiment":       item.get("overall_sentiment_label", ""),
                "sentiment_score": item.get("overall_sentiment_score", 0),
            })
    except Exception as e:
        print(f"⚠️ Alpha Vantage error: {e}")
    return results


# ── 4. Premium RSS（7日以内のみ） ─────────────────────────────
def collect_premium_rss() -> list:
    sources = [
        {"name": "WSJ Markets",
         "url":  "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"},
        {"name": "MarketWatch Top Stories",
         "url":  "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
        {"name": "Calculated Risk (Macro Blog)",
         "url":  "https://feeds.feedburner.com/calculatedrisk"},
        {"name": "Seeking Alpha Market News",
         "url":  "https://seekingalpha.com/market_currents.xml"},
        {"name": "IMF News",
         "url":  "https://www.imf.org/en/News/rss?language=eng"},
        {"name": "World Bank News",
         "url":  "https://feeds.worldbank.org/news/rss"},
        {"name": "BLS Economic News",
         "url":  "https://www.bls.gov/feed/bls_latest.rss"},
    ]
    keywords = [
        "interest rate", "inflation", "GDP", "recession", "federal reserve",
        "dollar", "yen", "japan", "asia", "bond", "stock market", "earnings",
        "investment", "etf", "oil", "commodity", "trade", "tariff",
    ]

    # ★ 7日以内フィルター
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    results = []
    for src in sources:
        try:
            feed  = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                if count >= 3:
                    break
                title    = entry.get("title", "")
                summary  = entry.get("summary", "")
                combined = (title + " " + summary).lower()

                if not any(kw in combined for kw in keywords):
                    continue

                # ★ 日付チェック（古い記事を除外）
                pub_str = entry.get("published", "")
                if pub_str:
                    try:
                        parsed = email.utils.parsedate_to_datetime(pub_str)
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        if parsed < cutoff:
                            continue  # 7日以上前はスキップ
                    except Exception:
                        pass  # パース失敗は通す

                results.append({
                    "source":  src["name"],
                    "title":   title,
                    "summary": summary[:300],
                    "link":    entry.get("link", ""),
                    "date":    pub_str,
                })
                count += 1
        except Exception as e:
            print(f"⚠️ RSS error ({src['name']}): {e}")
    return results


# ── 5. Reddit（閾値100に緩和） ────────────────────────────────
def collect_reddit_trends() -> list:
    subreddits = ["investing", "personalfinance", "Economics", "financialindependence"]
    results    = []
    headers    = {"User-Agent": "JapanFinanceNewsletter/1.0"}

    for sub in subreddits:
        try:
            url  = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            for post in resp.json()["data"]["children"][:3]:
                d = post["data"]
                if d.get("score", 0) < 100:  # ★ 500 → 100に緩和
                    continue
                results.append({
                    "source":   f"Reddit r/{sub}",
                    "title":    d.get("title", ""),
                    "summary":  d.get("selftext", "")[:200] or "(Link post)",
                    "link":     f"https://reddit.com{d.get('permalink', '')}",
                    "score":    d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                })
        except Exception as e:
            print(f"⚠️ Reddit error (r/{sub}): {e}")
    return results


# ── 6. 決算カレンダー（主要銘柄優先） ────────────────────────
# 注目度の高い主要銘柄リスト
MAJOR_TICKERS = {
    "AAPL","MSFT","GOOGL","GOOG","AMZN","NVDA","META","TSLA",
    "JPM","GS","BAC","MS","BRK.B","V","MA","UNH","JNJ","PFE",
    "XOM","CVX","WMT","COST","HD","MCD","KO","PEP","NFLX",
    "AMD","INTC","QCOM","AVGO","CRM","ORCL","IBM","ADBE",
    "7203","6758","9984","8306","7267","6861",  # 日本主要株
}

def collect_earnings_calendar() -> list:
    api_key = os.getenv("FINNHUB_KEY", "")
    if not api_key:
        return [{"note": "FINNHUB_KEY not set"}]

    today     = datetime.now()
    next_week = today + timedelta(days=7)
    url = (
        f"https://finnhub.io/api/v1/calendar/earnings"
        f"?from={today.strftime('%Y-%m-%d')}"
        f"&to={next_week.strftime('%Y-%m-%d')}"
        f"&token={api_key}"
    )
    results = []
    others  = []
    try:
        resp = requests.get(url, timeout=10)
        for item in resp.json().get("earningsCalendar", []):
            entry = {
                "symbol":       item.get("symbol", ""),
                "date":         item.get("date", ""),
                "eps_estimate": item.get("epsEstimate"),
                "revenue_est":  item.get("revenueEstimate"),
                "is_major":     item.get("symbol", "") in MAJOR_TICKERS,
            }
            # ★ 主要銘柄を先頭に
            if entry["is_major"]:
                results.append(entry)
            else:
                others.append(entry)
    except Exception as e:
        print(f"⚠️ Finnhub error: {e}")

    return (results + others)[:10]


# ── トップ記事選定 ────────────────────────────────────────────
def pick_top_story(intel: dict) -> dict:
    """
    今日フォーカスすべきトップ記事を1本選ぶ
    優先順位:
      1. Alpha Vantage Bullish/Bearish（スコア高い順）
      2. FOMC・利下げ等の重要FEDニュース
      3. premium_rssのインフレ・金利関連
      4. Redditで最もスコアが高い投稿
    """
    # 1. センチメントスコアが高いAlpha Vantageニュース
    av_scored = sorted(
        [i for i in intel.get("alpha_vantage", [])
         if abs(i.get("sentiment_score", 0)) > 0.3],
        key=lambda x: abs(x.get("sentiment_score", 0)),
        reverse=True,
    )
    if av_scored:
        return {"source": "alpha_vantage", "item": av_scored[0]}

    # 2. 重要FEDニュース
    fed_keywords = ["fomc", "interest rate", "inflation", "monetary policy",
                    "rate cut", "rate hike", "powell", "federal reserve"]
    for item in intel.get("fed_news", []):
        if any(kw in item.get("title", "").lower() for kw in fed_keywords):
            return {"source": "fed_news", "item": item}

    # 3. premium_rssの金融系ニュース
    rss_keywords = ["inflation", "fed", "rate", "dollar", "recession",
                    "market", "earnings", "gdp", "tariff"]
    for item in intel.get("premium_rss", []):
        if any(kw in item.get("title", "").lower() for kw in rss_keywords):
            return {"source": "premium_rss", "item": item}

    # 4. Redditトップ
    reddit = sorted(
        intel.get("reddit_trends", []),
        key=lambda x: x.get("score", 0),
        reverse=True,
    )
    if reddit:
        return {"source": "reddit", "item": reddit[0]}

    return {}


# ── メイン ───────────────────────────────────────────────────
def collect_all_intel() -> dict:
    print("🏛️  Collecting FED official news...")
    fed      = collect_fed_news()
    print("📋  Collecting SEC EDGAR filings...")
    sec      = collect_sec_filings()
    print("📡  Collecting Alpha Vantage news sentiment...")
    av       = collect_alpha_vantage_news()
    print("📰  Collecting premium RSS feeds...")
    rss      = collect_premium_rss()
    print("💬  Collecting Reddit investment trends...")
    reddit   = collect_reddit_trends()
    print("📅  Collecting earnings calendar...")
    earnings = collect_earnings_calendar()

    data = {
        "collected_at":      datetime.now().isoformat(),
        "week_label":        datetime.now().strftime("%Y-W%V"),
        "day_label":         datetime.now().strftime("%Y-%m-%d"),  # ★追加
        "fed_news":          fed,
        "sec_filings":       sec,
        "alpha_vantage":     av,
        "premium_rss":       rss,
        "reddit_trends":     reddit,
        "earnings_calendar": earnings,
    }

    # ★ トップ記事を選定して格納
    data["top_story"] = pick_top_story(data)

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
    print(f"   Top story     : {data['top_story'].get('item',{}).get('title','なし')}")

    return data


if __name__ == "__main__":
    collect_all_intel()
