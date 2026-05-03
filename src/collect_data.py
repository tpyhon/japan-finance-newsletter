"""
collect_data.py
Yahoo Finance / RSS からデータを収集して data/weekly_data.json に保存する
"""

import json
import os
import requests
import feedparser
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────
# 1. 株価・為替データ（Yahoo Finance）
# ──────────────────────────────────────────
def collect_equities() -> dict:
    """日経225・TOPIX・USD/JPY・EUR/JPY・EWJ ETFを取得"""
    tickers = {
        "nikkei": "^N225",
        "topix":  "1306.T",   # TOPIX連動ETF（東証上場）
        "usdjpy": "JPY=X",
        "eurjpy": "EURJPY=X",
        "ej_etf": "EWJ",      # iShares MSCI Japan ETF
    }

    results = {}
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist   = ticker.history(period="5d")
            if hist.empty:
                results[name] = {"error": "no data"}
                continue
            latest    = float(hist["Close"].iloc[-1])
            prev      = float(hist["Close"].iloc[0])
            change    = round(latest - prev, 2)
            change_pct = round((latest - prev) / prev * 100, 2)
            results[name] = {
                "latest":            round(latest, 2),
                "weekly_change":     change,
                "weekly_change_pct": change_pct,
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    return results


# ──────────────────────────────────────────
# 2. 日本銀行 政策金利（公式サイトから取得）
# ──────────────────────────────────────────
def collect_boj_rate() -> dict:
    """日銀のUncollateralized Overnight Call Rate（無担保コール翌日物）を取得"""
    try:
        # 日銀 時系列統計データ検索サイト API
        url = "https://www.stat-search.boj.or.jp/ssi/mtsvi/exportCSV.do"
        params = {
            "smp":  "1",
            "co":   "a",
            "mp":   "1",
            "d":    "m",          # 月次データ
            "s[0]": "FM02'IRTI'IRTCBOR",
            "e[0]": "b",
            "ys":   str(datetime.now().year),
            "ms":   "01",
            "ye":   str(datetime.now().year),
            "me":   str(datetime.now().month).zfill(2),
            "nm":   "call_rate",
        }
        resp  = requests.get(url, params=params, timeout=10)
        lines = resp.text.strip().split("\n")
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    rate = float(parts[-1].strip().strip('"'))
                    return {
                        "policy_rate_pct": rate,
                        "description": "BOJ Uncollateralized Overnight Call Rate (%)"
                    }
                except ValueError:
                    continue

        # フォールバック：直近の公表値をハードコード（2024年3月利上げ後）
        return {
            "policy_rate_pct": 0.5,
            "description": "BOJ policy rate (manually updated Mar 2024)",
            "note": "API unavailable - using last known value"
        }

    except Exception as e:
        return {
            "policy_rate_pct": 0.5,
            "description": "BOJ policy rate (fallback)",
            "error": str(e)
        }


# ──────────────────────────────────────────
# 3. 日本経済ニュース（RSS）
# ──────────────────────────────────────────
def collect_news() -> list:
    """複数RSSソースから日本経済関連ニュースを取得"""
    feeds = [
        {
            "url":  "https://japantoday.com/feed",
            "name": "Japan Today"
        },
        {
            "url":  "https://www.reuters.com/rssFeed/businessNews",
            "name": "Reuters Business"
        },
        {
            "url":  "https://feeds.bloomberg.com/markets/news.rss",
            "name": "Bloomberg Markets"
        },
    ]

    # Japan関連キーワード（緩めに設定）
    japan_keywords = [
        "japan", "yen", "jpy", "boj", "nikkei",
        "tokyo", "japanese", "abenomics", "kishida",
        "softbank", "toyota", "sony", "nintendo",
        "BoJ", "Bank of Japan"
    ]

    headlines = []
    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:10]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")[:300]
                combined = (title + " " + summary).lower()

                if any(kw.lower() in combined for kw in japan_keywords):
                    headlines.append({
                        "title":   title,
                        "summary": summary,
                        "source":  feed_info["name"],
                    })
                    if len(headlines) >= 8:
                        break
        except Exception as e:
            print(f"  ⚠️  RSS error ({feed_info['name']}): {e}")

        if len(headlines) >= 8:
            break

    # ニュースが0件の場合のフォールバック
    if not headlines:
        headlines = [{
            "title":   "Japan markets data collected - no RSS headlines available",
            "summary": "Market data successfully retrieved via Yahoo Finance.",
            "source":  "system"
        }]

    return headlines


# ──────────────────────────────────────────
# 4. 全データをまとめてJSONに保存
# ──────────────────────────────────────────
def collect_all() -> dict:
    print("📡 Collecting equity & FX data...")
    equities = collect_equities()

    print("🏦 Collecting BOJ policy rate...")
    boj = collect_boj_rate()

    print("📰 Collecting news headlines...")
    news = collect_news()

    data = {
        "collected_at": datetime.now().isoformat(),
        "week_label":   datetime.now().strftime("%Y-W%V"),
        "equities":     equities,
        "boj":          boj,
        "news":         news,
    }

    os.makedirs("data", exist_ok=True)
    path = "data/weekly_data.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Data saved to {path}")
    return data


if __name__ == "__main__":
    result = collect_all()
    print("\n── Summary ──")
    print(f"Nikkei  : {result['equities'].get('nikkei', {})}")
    print(f"TOPIX   : {result['equities'].get('topix', {})}")
    print(f"USD/JPY : {result['equities'].get('usdjpy', {})}")
    print(f"BOJ rate: {result['boj']}")
    print(f"News    : {len(result['news'])} headlines collected")
