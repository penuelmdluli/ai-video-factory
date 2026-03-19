"""
News Scraper — Fetches trending news headlines for Daily Breakdown videos.

Sources (all free, no API keys):
1. Google News RSS — real-time headlines by region/topic
2. Reddit — community-curated news from relevant subreddits

Uses Gemini to rank stories by visual potential (Pexels-searchable).
"""
import asyncio
import random
import re
from datetime import datetime
from typing import Optional

import feedparser
import httpx

from config import GEMINI_API_KEY


# ── Google News RSS Feeds ──────────────────────────────────────
GOOGLE_NEWS_FEEDS = {
    "iran": "https://news.google.com/rss/search?q=Iran&hl=en-US&gl=US&ceid=US:en",
    "south_africa": "https://news.google.com/rss/search?q=South+Africa&hl=en-US&gl=US&ceid=US:en",
    "world": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "africa": "https://news.google.com/rss/search?q=Africa+news&hl=en-US&gl=US&ceid=US:en",
    "breaking": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "politics": "https://news.google.com/rss/search?q=world+politics&hl=en-US&gl=US&ceid=US:en",
    "conflict": "https://news.google.com/rss/search?q=war+conflict+crisis&hl=en-US&gl=US&ceid=US:en",
}

# ── Reddit News Subreddits ─────────────────────────────────────
REDDIT_SUBREDDITS = [
    "worldnews",
    "news",
    "africa",
    "southafrica",
    "geopolitics",
]

# ── Pexels Visual Mapping ──────────────────────────────────────
# Common news topics → Pexels search queries
VISUAL_KEYWORD_MAP = {
    # ── WAR & CONFLICT — hard-hitting real footage queries ──
    "war": ["war zone destruction", "military combat", "soldiers battlefield", "air strike aftermath", "war refugees fleeing", "armored vehicles convoy"],
    "strike": ["air strike explosion", "missile launch military", "bombing destruction", "military attack", "fighter jet bombing"],
    "ceasefire": ["ceasefire negotiations", "peace talks diplomats", "military standoff", "war destruction aftermath"],
    "invasion": ["military invasion tanks", "war destruction buildings", "soldiers urban combat", "refugees border crossing"],
    "bomb": ["explosion aftermath", "bombing destruction", "missile launch", "military air strike"],
    "attack": ["military attack footage", "explosion aftermath", "emergency response", "destruction aftermath"],
    "troops": ["soldiers marching", "military troops deployment", "armed forces training", "military convoy"],
    "missile": ["missile launch military", "rocket attack", "air defense system", "military weapons"],

    # ── IRAN SPECIFIC — real regional footage ──
    "iran": ["Tehran Iran city", "Iran military parade", "Persian Gulf warships", "Iran protest crowd", "Middle East conflict", "Iranian people street"],
    "tehran": ["Tehran Iran skyline", "Tehran streets crowds", "Iran capital city"],
    "persian": ["Iran landscape mountains", "Persian Gulf ships", "Middle East architecture"],

    # ── ISRAEL / MIDDLE EAST ──
    "israel": ["Israel military IDF", "Tel Aviv Israel city", "Israel iron dome missile", "Middle East conflict", "Jerusalem old city"],
    "gaza": ["Gaza destruction buildings", "humanitarian crisis refugees", "Middle East conflict zone", "emergency rescue rubble"],
    "hamas": ["Middle East conflict", "military operation urban", "destruction aftermath war"],
    "hezbollah": ["Lebanon military", "Middle East conflict", "Beirut city", "military forces"],
    "middle east": ["Middle East city aerial", "desert military operation", "Middle East crowd protest", "Arabian architecture"],

    # ── SOUTH AFRICA SPECIFIC ──
    "south africa": ["Johannesburg South Africa", "Cape Town Table Mountain", "South Africa parliament", "Pretoria government", "African people protest", "Soweto township"],
    "ambassador": ["diplomat press conference", "embassy building", "diplomatic meeting", "government officials"],
    "anc": ["South Africa politics", "African parliament debate", "political rally Africa"],

    # ── GLOBAL POLITICS ──
    "trump": ["White House Washington DC", "US president press conference", "American politics", "United States Congress"],
    "biden": ["White House government", "US politics Washington", "American president"],
    "putin": ["Kremlin Russia Moscow", "Russian military parade", "Russia politics"],
    "nato": ["NATO military alliance", "NATO headquarters Brussels", "military forces Europe"],
    "united nations": ["United Nations assembly", "UN headquarters", "international diplomacy", "world leaders summit"],
    "sanctions": ["economic sanctions", "shipping containers port", "international trade embargo", "customs inspection"],

    # ── GENERAL CATEGORIES ──
    "nuclear": ["nuclear facility reactor", "radiation hazard warning", "nuclear weapons test", "atomic energy plant"],
    "protest": ["massive protest crowd", "demonstration march streets", "police riot protest", "people angry protest signs"],
    "election": ["election voting ballot", "election results crowd", "political campaign rally", "parliament debate"],
    "economy": ["stock market crash", "economic crisis", "currency exchange", "Wall Street traders"],
    "climate": ["climate change drought", "flooding disaster city", "wildfire destruction", "extreme weather storm"],
    "technology": ["artificial intelligence robot", "cyber security hacking", "data center servers", "drone technology military"],
    "health": ["hospital emergency room", "pandemic virus", "medical surgery doctors", "health crisis"],
    "crime": ["police crime scene", "security surveillance", "courthouse judge trial", "prison inmates"],
    "diplomacy": ["diplomatic handshake leaders", "press conference podium", "summit meeting leaders", "peace negotiations table"],
    "oil": ["oil refinery fire", "oil tanker ship", "petroleum industry pipeline", "gas price crisis"],
    "military": ["military tanks battle", "army soldiers training", "naval warship ocean", "fighter jet takeoff", "military helicopter", "armed forces operation"],
    "refugee": ["refugee camp tents", "refugees fleeing border", "humanitarian aid distribution", "displaced families children"],
    "earthquake": ["earthquake destruction buildings", "rescue workers rubble", "seismic damage city"],
    "flood": ["flooding city streets", "flood rescue helicopter", "flood devastation homes"],
    "fire": ["massive wildfire forest", "city building fire", "firefighters action", "fire destruction aftermath"],
    "corruption": ["courthouse corruption trial", "prison bars", "political scandal"],
    "education": ["school children classroom", "university campus students", "graduation ceremony"],
    "infrastructure": ["bridge construction", "highway traffic city", "power grid electrical"],
    "poverty": ["poverty slum conditions", "food aid distribution", "homeless people street"],
    "sports": ["stadium crowd cheering", "athletes competition", "sports celebration victory"],
    "terrorism": ["security checkpoint", "emergency response", "police special forces", "counter terrorism operation"],
    "coup": ["military coup tanks street", "soldiers government building", "political unrest armed"],
}


async def scrape_google_news(
    regions: list[str] | None = None,
    max_per_region: int = 5,
) -> list[dict]:
    """
    Fetch headlines from Google News RSS feeds.

    Returns list of:
        {"headline", "summary", "source", "region", "published", "url"}
    """
    if regions is None:
        regions = ["iran", "south_africa", "world", "africa"]

    articles = []

    for region in regions:
        feed_url = GOOGLE_NEWS_FEEDS.get(region)
        if not feed_url:
            continue

        try:
            # feedparser can fetch URLs directly but let's use httpx for timeout control
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(feed_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                if resp.status_code != 200:
                    print(f"[NewsScraper] Google News {region}: HTTP {resp.status_code}")
                    continue

                feed = feedparser.parse(resp.text)
        except Exception as e:
            print(f"[NewsScraper] Google News {region} error: {e}")
            continue

        for entry in feed.entries[:max_per_region]:
            # Clean HTML from title and summary
            title = re.sub(r"<[^>]+>", "", entry.get("title", "")).strip()
            summary = re.sub(r"<[^>]+>", "", entry.get("summary", entry.get("description", ""))).strip()

            # Extract source from title (Google News format: "Headline - Source")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip() if len(parts) > 1 else ""

            articles.append({
                "headline": title,
                "summary": summary[:300],  # Truncate long summaries
                "source": source,
                "region": region,
                "published": entry.get("published", ""),
                "url": entry.get("link", ""),
            })

    print(f"[NewsScraper] Google News: {len(articles)} headlines from {len(regions)} regions")
    return articles


async def scrape_reddit_news(
    max_posts: int = 10,
) -> list[dict]:
    """
    Fetch trending news from Reddit public JSON API.

    Returns list of:
        {"headline", "summary", "source", "region", "score", "url"}
    """
    articles = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for sub in REDDIT_SUBREDDITS:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
                resp = await client.get(url, headers={
                    "User-Agent": "AI-Video-Factory/1.0 (news-scraper)"
                })
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for post in data.get("data", {}).get("children", []):
                    pd = post.get("data", {})
                    if pd.get("stickied"):
                        continue

                    title = pd.get("title", "").strip()
                    if not title or len(title) < 20:
                        continue

                    # Determine region from subreddit
                    region_map = {
                        "southafrica": "south_africa",
                        "africa": "africa",
                        "worldnews": "world",
                        "news": "world",
                        "geopolitics": "world",
                    }

                    articles.append({
                        "headline": title,
                        "summary": pd.get("selftext", "")[:200] or title,
                        "source": f"r/{sub}",
                        "region": region_map.get(sub, "world"),
                        "score": pd.get("score", 0),
                        "url": pd.get("url", ""),
                    })

            except Exception as e:
                print(f"[NewsScraper] Reddit r/{sub} error: {e}")
                continue

    # Sort by score (most upvoted first)
    articles.sort(key=lambda x: x.get("score", 0), reverse=True)
    print(f"[NewsScraper] Reddit: {len(articles)} posts from {len(REDDIT_SUBREDDITS)} subreddits")
    return articles[:max_posts]


def _suggest_pexels_queries(headline: str) -> list[str]:
    """
    Map a headline to Pexels search queries using keyword matching.
    Returns 2-4 relevant search queries.
    """
    headline_lower = headline.lower()
    queries = []

    for keyword, pexels_terms in VISUAL_KEYWORD_MAP.items():
        if keyword in headline_lower:
            queries.extend(pexels_terms)

    # Deduplicate and limit
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    # If no matches, use generic news visuals
    if not unique:
        unique = ["news broadcast", "world map", "press conference", "city skyline"]

    return unique[:4]


async def rank_news_by_visual_potential(
    articles: list[dict],
    max_ranked: int = 10,
) -> list[dict]:
    """
    Use Gemini to rank headlines by how well they'd work for a visual news video.
    Adds 'visual_score' (1-10) and 'suggested_pexels_queries' to each article.
    Falls back to keyword-based scoring if Gemini unavailable.
    """
    # First, add keyword-based suggestions to all articles
    for article in articles:
        article["suggested_pexels_queries"] = _suggest_pexels_queries(article["headline"])
        # Base score: more keyword matches = higher visual potential
        article["visual_score"] = min(10, len(article["suggested_pexels_queries"]) * 2 + 3)

    # Try Gemini for smarter ranking
    if GEMINI_API_KEY and articles:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)

            headlines_text = "\n".join(
                f"{i+1}. [{a['region'].upper()}] {a['headline']}"
                for i, a in enumerate(articles[:15])
            )

            prompt = f"""You are a video producer selecting news stories for a short-form news analysis video.

Rate each headline 1-10 based on:
- Visual potential (can we find stock footage for this? Higher = easier to visualize)
- Viewer interest (is this trending/engaging? Higher = more clicks)
- Analysis potential (can we provide unique insight? Higher = better content)

For each, also suggest 2-3 Pexels stock footage search queries.

Headlines:
{headlines_text}

Return JSON array (no markdown):
[{{"index": 1, "score": 8, "queries": ["military vehicles", "middle east city"]}}, ...]"""

            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
            )

            if response and response.text:
                import json
                raw = response.text.strip()
                raw = re.sub(r"```json\s*", "", raw)
                raw = re.sub(r"```\s*", "", raw)
                rankings = json.loads(raw)

                for rank in rankings:
                    idx = rank.get("index", 0) - 1
                    if 0 <= idx < len(articles):
                        articles[idx]["visual_score"] = rank.get("score", 5)
                        if rank.get("queries"):
                            articles[idx]["suggested_pexels_queries"] = rank["queries"]

                print(f"[NewsScraper] Gemini ranked {len(rankings)} headlines by visual potential")

        except Exception as e:
            print(f"[NewsScraper] Gemini ranking failed (using keyword fallback): {e}")

    # Sort by visual score
    articles.sort(key=lambda x: x.get("visual_score", 0), reverse=True)
    return articles[:max_ranked]


async def select_news_stories(
    regions: list[str] | None = None,
    max_stories: int = 3,
) -> list[dict]:
    """
    Main entry point: scrape → rank → pick top stories with region diversity.

    Returns list of top stories:
        {"headline", "summary", "source", "region", "visual_score", "suggested_pexels_queries"}
    """
    if regions is None:
        regions = ["iran", "south_africa", "world", "africa", "conflict"]

    print(f"\n[NewsScraper] Scraping news for: {', '.join(regions)}")

    # Scrape from multiple sources in parallel
    google_task = scrape_google_news(regions, max_per_region=5)
    reddit_task = scrape_reddit_news(max_posts=10)

    google_articles, reddit_articles = await asyncio.gather(google_task, reddit_task)

    # Combine and deduplicate (by headline similarity)
    all_articles = google_articles + reddit_articles

    # Simple dedup: remove articles with very similar headlines
    seen_headlines = set()
    unique_articles = []
    for article in all_articles:
        # Create a simplified key for dedup
        key = re.sub(r"[^a-z0-9 ]", "", article["headline"].lower())[:50]
        if key not in seen_headlines:
            seen_headlines.add(key)
            unique_articles.append(article)

    print(f"[NewsScraper] Combined: {len(unique_articles)} unique articles (deduped from {len(all_articles)})")

    if not unique_articles:
        print("[NewsScraper] WARNING: No articles found, using fallback topics")
        return _fallback_stories()

    # Rank by visual potential
    ranked = await rank_news_by_visual_potential(unique_articles, max_ranked=10)

    # Select with region diversity (try to get at least one from each region)
    selected = []
    used_regions = set()

    # First pass: pick best from each region
    for article in ranked:
        region = article.get("region", "world")
        if region not in used_regions and len(selected) < max_stories:
            selected.append(article)
            used_regions.add(region)

    # Second pass: fill remaining slots with highest-scored
    for article in ranked:
        if article not in selected and len(selected) < max_stories:
            selected.append(article)

    for i, story in enumerate(selected):
        print(f"[NewsScraper] Story {i+1}: [{story['region'].upper()}] {story['headline'][:70]}... (score: {story.get('visual_score', '?')})")

    return selected


def _fallback_stories() -> list[dict]:
    """Emergency fallback stories when scraping fails."""
    fallbacks = [
        {
            "headline": "Global tensions rise as diplomatic talks stall",
            "summary": "International community seeks peaceful resolution amid growing concerns",
            "source": "fallback",
            "region": "world",
            "visual_score": 7,
            "suggested_pexels_queries": ["united nations", "diplomacy", "world leaders", "press conference"],
        },
        {
            "headline": "South Africa faces economic challenges and opportunity",
            "summary": "Mixed signals from the economy as new policies take effect",
            "source": "fallback",
            "region": "south_africa",
            "visual_score": 7,
            "suggested_pexels_queries": ["johannesburg skyline", "african business", "south africa city"],
        },
        {
            "headline": "Technology reshaping global conflict and diplomacy",
            "summary": "AI and cyber capabilities changing the face of international relations",
            "source": "fallback",
            "region": "world",
            "visual_score": 8,
            "suggested_pexels_queries": ["cyber security", "artificial intelligence", "military technology"],
        },
    ]
    return fallbacks
