# generate_medium_articles.py
# Generates 5 Medium articles for Japan Finance Weekly
# Target audience: English-speaking global investors
# No historical data required - theme-based AI generation
# Place this file in src/ alongside other scripts

import os
import json
import time
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Output directory (relative to project root, not src/)
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "medium_articles"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Article themes - 5 evergreen topics for Japan Finance Weekly
# Ordered by SEO priority / shareability
# ---------------------------------------------------------------------------
ARTICLE_THEMES = [
    {
        "id": 1,
        "title_hint": "Why Global Investors Are Watching Japan's Stock Market Right Now",
        "focus": (
            "Nikkei 225 breaking 30-year highs, Warren Buffett's Japan trading house bets, "
            "TSE governance reform pressure on low-PBR companies, weak yen tailwind for exporters"
        ),
        "angle": (
            "Beginner-friendly explainer for Western investors discovering Japan equities. "
            "Emphasize the 'why now' urgency."
        ),
        "seo_keywords": "Japan stocks, Nikkei 225, Japanese equities, invest in Japan"
    },
    {
        "id": 2,
        "title_hint": "The Bank of Japan's Historic Policy Shift: What Every Investor Needs to Know",
        "focus": (
            "BOJ ending negative interest rates, yield curve control phase-out, "
            "yen carry trade unwind risks, impact on global bond markets and USD/JPY"
        ),
        "angle": (
            "Macro analysis for intermediate investors. "
            "Explain the carry trade in plain English - this is the most misunderstood risk."
        ),
        "seo_keywords": "Bank of Japan, BOJ rate hike, yen carry trade, Japanese yen"
    },
    {
        "id": 3,
        "title_hint": "Japan's Corporate Governance Revolution: The Quiet Bull Case Most Investors Are Missing",
        "focus": (
            "TSE's campaign against PBR below 1x, record share buybacks, "
            "activist investors rising (Elliott, ValueAct), cross-shareholding unwinding, "
            "GPIF influence as world's largest pension fund"
        ),
        "angle": (
            "Deep-dive structural change story. "
            "Most shareable among finance Twitter/LinkedIn crowd. "
            "Position this as a contrarian long-term thesis."
        ),
        "seo_keywords": "Japan corporate governance, TSE reform, Japan value stocks, PBR"
    },
    {
        "id": 4,
        "title_hint": "USD/JPY Explained: The Currency Pair That Moves Global Markets",
        "focus": (
            "Interest rate differential as primary driver, BOJ vs Fed divergence, "
            "Japanese government intervention history and thresholds, "
            "safe-haven yen flows during crises, practical impact on Japan stock returns for foreign investors"
        ),
        "angle": (
            "Currency education for equity investors who ignore FX at their peril. "
            "Include a practical section on currency-hedged ETFs vs unhedged."
        ),
        "seo_keywords": "USD JPY, dollar yen, Japanese yen, currency hedging Japan"
    },
    {
        "id": 5,
        "title_hint": "How to Invest in Japan: ETFs, ADRs, and Direct Stocks Compared",
        "focus": (
            "EWJ vs DXJ vs DBJP ETF comparison, top Japan ADRs (Toyota, Sony, SoftBank), "
            "opening a Japan brokerage account as a foreigner, "
            "withholding tax on dividends, NISA account overview"
        ),
        "angle": (
            "Practical how-to guide. Highest conversion potential - readers ready to act. "
            "This should feel like a helpful friend explaining the options, not a product pitch."
        ),
        "seo_keywords": "how to invest in Japan, Japan ETF, EWJ, Japan ADR, Nikkei ETF"
    }
]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a senior financial journalist at a respected English-language publication. "
    "Your beat is Asian markets, with deep expertise in Japanese equities, macro policy, and FX. "
    "Your readers are English-speaking retail and semi-professional investors in the US, UK, Europe, and Australia. "
    "They want actionable insight delivered with authority, clarity, and occasional wit. "
    "You never use jargon without a brief explanation. "
    "You write in flowing paragraphs - not bullet-point dumps. "
    "Your pieces are respected enough to be shared on finance Twitter and cited in investment club discussions."
)

def build_article_prompt(theme: dict) -> str:
    return f"""Write a complete, publication-ready Medium article based on the brief below.

TITLE HINT      : {theme['title_hint']}
KEY FOCUS AREAS : {theme['focus']}
READER ANGLE    : {theme['angle']}
SEO KEYWORDS    : naturally weave in: {theme['seo_keywords']}

STRUCTURE REQUIREMENTS:
1. Hook (2-3 sentences) - open with a surprising fact, bold claim, or vivid scenario
2. Context section (H2) - why this topic matters right now
3. Main analysis - 3 sections with H2 headers, each 150-200 words
4. "Key Takeaways" section (H2) - 3 concise bullets (the ONLY bullets allowed)
5. Closing paragraph + CTA inviting readers to follow "Japan Finance Weekly" for weekly updates

STYLE RULES:
- Length: 950-1100 words total
- Tone: Bloomberg Opinion meets personal finance blog - authoritative but human
- Prefer paragraphs over bullets (except the Key Takeaways section)
- Include 4-6 specific data points or facts for credibility
- No clickbait but strong headline that would perform on Google and Medium search
- Naturally include the SEO keywords without stuffing

OUTPUT FORMAT - return ONLY a valid JSON object, no markdown fences, no extra text:
{{
  "title": "Final article title (compelling, SEO-optimized, 50-70 characters)",
  "subtitle": "One-sentence subtitle that expands on the title (100-140 characters)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "estimated_read_minutes": <integer between 4 and 6>,
  "body_markdown": "Full article body in Markdown. Use ## for H2 headers. Escape any internal double quotes with backslash."
}}"""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def generate_article(client: genai.Client, theme: dict, article_num: int) -> dict:
    print(f"  [{article_num}/5] Generating: {theme['title_hint'][:55]}...")

    prompt = build_article_prompt(theme)

    response = client.models.generate_content(
        model="gemma-4-26b-a4b-it",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.78,
            max_output_tokens=2500,
        )
    )

    raw_text = response.text.strip()

    # Strip markdown code fences if the model wraps output anyway
    if raw_text.startswith("```"):
        parts = raw_text.split("```")
        # parts[1] is the content between first pair of fences
        inner = parts[1]
        if inner.lower().startswith("json"):
            inner = inner[4:]
        raw_text = inner.strip()

    article_data = json.loads(raw_text)
    article_data["theme_id"] = theme["id"]

    word_count = len(article_data.get("body_markdown", "").split())
    print(f"         Title : {article_data.get('title', 'N/A')}")
    print(f"         Words : ~{word_count}  |  Read: ~{article_data.get('estimated_read_minutes', '?')} min")
    return article_data


def save_article_files(article: dict, theme_id: int) -> Path:
    # --- Raw JSON (for debugging / re-processing) ---
    json_path = OUTPUT_DIR / f"article_{theme_id:02d}_raw.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)

    # --- Medium-ready Markdown (copy-paste this into Medium) ---
    md_content = (
        f"# {article['title']}\n\n"
        f"### {article['subtitle']}\n\n"
        f"---\n\n"
        f"{article['body_markdown']}\n\n"
        f"---\n\n"
        f"*Follow **Japan Finance Weekly** for weekly updates on Japanese markets, "
        f"BOJ policy, and investment opportunities across Asia.*\n\n"
        f"*Tags: {', '.join(article['tags'])}*  \n"
        f"*Estimated read: {article['estimated_read_minutes']} min*\n"
    )
    md_path = OUTPUT_DIR / f"article_{theme_id:02d}_medium_ready.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"         Saved : {md_path.name}  +  {json_path.name}")
    return md_path


def save_summary(articles: list, failed: list):
    summary = {
        "total_generated": len(articles),
        "failed_ids": failed,
        "partner_program_ready": len(articles) >= 5,
        "articles": [
            {
                "id": a.get("theme_id"),
                "title": a.get("title"),
                "subtitle": a.get("subtitle"),
                "tags": a.get("tags"),
                "read_minutes": a.get("estimated_read_minutes")
            }
            for a in articles
        ]
    }
    summary_path = OUTPUT_DIR / "articles_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary_path


def save_posting_guide(articles: list):
    lines = [
        "MEDIUM POSTING GUIDE - Japan Finance Weekly",
        "============================================",
        "",
        "Goal: Publish 5 articles to qualify for Medium Partner Program",
        "Schedule: 1 article every 2 days (completes in ~10 days)",
        "After 5 articles + 100 followers: apply at https://medium.com/me/partner/enroll",
        "",
        "POSTING STEPS (per article):",
        "  1. Go to https://medium.com/new-story",
        "  2. Click the title area - paste the title from the .md file",
        "  3. Click below the title - paste everything from body_markdown",
        "  4. Click '...' menu (top right) -> Add tags (use the 5 tags listed below)",
        "  5. Add a featured image (Japan/finance theme - free at https://unsplash.com)",
        "     Search: 'tokyo finance' or 'japan city' or 'stock market'",
        "  6. Click 'Publish' -> 'Public' -> Publish now",
        "  7. Share the URL in your X post (use x_post.txt as template)",
        "",
        "----------------------------------------------",
    ]

    for i, article in enumerate(articles, 1):
        tid = article.get("theme_id", i)
        lines += [
            "",
            f"ARTICLE {i} of 5",
            f"  File    : article_{tid:02d}_medium_ready.md",
            f"  Title   : {article.get('title', 'N/A')}",
            f"  Subtitle: {article.get('subtitle', 'N/A')}",
            f"  Tags    : {', '.join(article.get('tags', []))}",
            f"  Read    : ~{article.get('estimated_read_minutes', '?')} min",
            f"  Post on : Day {i * 2 - 1} (e.g. Mon, Wed, Fri, Sun, Tue)",
        ]

    lines += [
        "",
        "----------------------------------------------",
        "",
        "GROWING TO 100 FOLLOWERS (fastest methods):",
        "  - Post your Medium article link in your weekly X post",
        "  - Add your Medium profile link to your beehiiv newsletter footer",
        "  - Comment thoughtfully on 3-5 popular Japan/finance articles on Medium",
        "  - Follow 20-30 accounts in the Japan/investing tag - many follow back",
        "  - Submit articles to Medium publications: 'The Capital', 'DataDrivenInvestor'",
        "",
        "PARTNER PROGRAM APPLICATION:",
        "  URL  : https://medium.com/me/partner/enroll",
        "  Req  : 5+ published stories AND 100+ followers AND 18+ years old",
        "  Time : Usually approved within 1-3 business days",
        "",
        "EXPECTED EARNINGS (realistic):",
        "  Early stage (100-500 readers/article): $1-5 per article per month",
        "  Growth stage (1K-5K readers/article) : $10-50 per article per month",
        "  Main value: drives beehiiv subscribers via CTA in each article",
        "",
    ]

    guide_path = OUTPUT_DIR / "MEDIUM_POSTING_GUIDE.txt"
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return guide_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("=" * 60)
    print(" Medium Article Generator - Japan Finance Weekly")
    print(" Generating 5 evergreen articles (English)")
    print("=" * 60)

    # Load API key
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found.\n"
            "Local : check your .env file\n"
            "CI    : check GitHub Secrets"
        )

    client = genai.Client(api_key=api_key)
    print(f" Model     : gemma-4-26b-a4b-it")
    print(f" Output    : {OUTPUT_DIR.resolve()}")
    print(f" Articles  : {len(ARTICLE_THEMES)}")
    print()

    articles = []
    failed = []

    for i, theme in enumerate(ARTICLE_THEMES, 1):
        try:
            article = generate_article(client, theme, i)
            save_article_files(article, theme["id"])
            articles.append(article)

            # Small courtesy delay between generations (no rate limit hit but good practice)
            if i < len(ARTICLE_THEMES):
                time.sleep(3)

        except json.JSONDecodeError as e:
            print(f"         ERROR: JSON parse failed for article {i}: {e}")
            print(f"         Tip  : Re-run the script - the model occasionally adds extra text")
            failed.append(i)
        except Exception as e:
            print(f"         ERROR: Article {i} failed: {type(e).__name__}: {e}")
            failed.append(i)

        print()

    # Save summary and guide
    summary_path = save_summary(articles, failed)
    guide_path = save_posting_guide(articles)

    # Final report
    print("=" * 60)
    print(f" RESULTS")
    print(f"   Generated : {len(articles)}/5 articles")
    if failed:
        print(f"   Failed    : article(s) {failed}")
        print(f"   Action    : re-run script - failed articles will overwrite")
    print(f"   Summary   : {summary_path.name}")
    print(f"   Guide     : {guide_path.name}")
    print()
    print(" NEXT STEPS:")
    print("   1. Open data/medium_articles/MEDIUM_POSTING_GUIDE.txt")
    print("   2. Open article_01_medium_ready.md -> paste into Medium")
    print("   3. Post 1 article every 2 days (5 articles = ~10 days)")
    print("   4. At 100 followers -> apply for Partner Program")
    print("      https://medium.com/me/partner/enroll")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
