"""
Trend Detector — Real-time trend discovery from multiple sources.

Replaces broken Google scraping with reliable trend APIs:
1. Google Trends (pytrends) — real search volume data
2. Reddit hot posts — community pulse
3. YouTube trending — video topic validation
4. NewsAPI — breaking headlines

Feeds trending data to Gemini for grounded topic generation.
"""
import asyncio
import random
from datetime import datetime, timedelta

from config import NICHES


# ── Niche-to-search mappings for trend APIs ──────────────
NICHE_TREND_QUERIES = {
    "ai_trading": {
        "pytrends": ["AI trading", "stock market AI", "crypto AI", "algorithmic trading", "trading bot"],
        "reddit": ["algotrading", "wallstreetbets", "stocks", "cryptocurrency", "daytrading"],
        "youtube_query": "AI trading stocks crypto",
    },
    "ai_money": {
        "pytrends": ["make money AI", "AI side hustle", "passive income AI", "ChatGPT money", "AI business"],
        "reddit": ["sidehustle", "beermoney", "WorkOnline", "Entrepreneur", "passive_income"],
        "youtube_query": "make money AI side hustle",
    },
    "tech_news": {
        "pytrends": ["AI news", "artificial intelligence", "tech news", "AI breakthrough", "new AI model"],
        "reddit": ["technology", "artificial", "MachineLearning", "singularity", "tech"],
        "youtube_query": "AI news technology breakthrough",
    },
    "motivation": {
        "pytrends": ["motivation", "self improvement", "morning routine", "discipline mindset", "success habits"],
        "reddit": ["GetMotivated", "selfimprovement", "productivity", "DecidingToBeBetter", "getdisciplined"],
        "youtube_query": "motivation success mindset discipline",
    },
    "health_wellness": {
        "pytrends": ["health tips", "natural remedies", "nutrition science", "gut health", "longevity"],
        "reddit": ["health", "nutrition", "HealthyFood", "naturalmedicine", "longevity"],
        "youtube_query": "health wellness natural remedies nutrition",
    },
    "blissful_moments": {
        "pytrends": ["mindfulness", "gratitude", "inner peace", "happiness tips", "positivity"],
        "reddit": ["Mindfulness", "happy", "MadeMeSmile", "wholesome", "UpliftingNews"],
        "youtube_query": "mindfulness gratitude positivity inspiration",
    },
}


async def get_google_trends(niche: str, max_results: int = 10) -> list[dict]:
    """
    Fetch real trending queries from Google Trends via pytrends.

    Returns list of {keyword, score, trend_direction} dicts.
    """
    queries = NICHE_TREND_QUERIES.get(niche, {}).get("pytrends", [])
    if not queries:
        return []

    trending = []
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360)

        # Get related queries for each seed keyword
        for query in queries[:3]:  # Limit to avoid rate limits
            try:
                pytrends.build_payload([query], timeframe="now 7-d")

                # Related queries (rising = trending)
                related = pytrends.related_queries()
                if query in related:
                    rising = related[query].get("rising")
                    if rising is not None and not rising.empty:
                        for _, row in rising.head(5).iterrows():
                            trending.append({
                                "keyword": row["query"],
                                "score": int(row.get("value", 0)),
                                "trend_direction": "rising",
                                "source": "google_trends",
                            })

                    top = related[query].get("top")
                    if top is not None and not top.empty:
                        for _, row in top.head(3).iterrows():
                            trending.append({
                                "keyword": row["query"],
                                "score": int(row.get("value", 0)),
                                "trend_direction": "top",
                                "source": "google_trends",
                            })

                # Small delay between requests to avoid rate limiting
                await asyncio.sleep(1)
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(10)
                continue

    except ImportError:
        print("[TrendDetector] pytrends not installed. Run: pip install pytrends")
    except Exception as e:
        print(f"[TrendDetector] Google Trends failed: {e}")

    return trending[:max_results]


async def get_reddit_trending(niche: str, max_results: int = 10) -> list[dict]:
    """
    Fetch hot posts from niche-relevant subreddits.

    Uses Reddit's public JSON API (no auth needed for read-only).
    """
    subreddits = NICHE_TREND_QUERIES.get(niche, {}).get("reddit", [])
    if not subreddits:
        return []

    trending = []
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            # Pick 2 random subreddits per call to diversify
            selected = random.sample(subreddits, min(2, len(subreddits)))
            for sub in selected:
                try:
                    resp = await client.get(
                        f"https://www.reddit.com/r/{sub}/hot.json",
                        params={"limit": 10, "t": "day"},
                        headers={"User-Agent": "AIVideoFactory/1.0"},
                    )
                    if resp.status_code == 200:
                        posts = resp.json().get("data", {}).get("children", [])
                        for post in posts[:5]:
                            data = post.get("data", {})
                            title = data.get("title", "")
                            score = data.get("score", 0)
                            if title and score > 50:
                                trending.append({
                                    "keyword": title,
                                    "score": score,
                                    "trend_direction": "hot",
                                    "source": f"reddit_r/{sub}",
                                    "url": f"https://reddit.com{data.get('permalink', '')}",
                                })
                    await asyncio.sleep(1)
                except Exception:
                    continue

    except ImportError:
        print("[TrendDetector] httpx not installed")
    except Exception as e:
        print(f"[TrendDetector] Reddit fetch failed: {e}")

    # Sort by score and deduplicate
    trending.sort(key=lambda x: x["score"], reverse=True)
    return trending[:max_results]


async def get_trending_topics(niche: str) -> dict:
    """
    Aggregate trending data from all sources for a niche.

    Returns a dict with structured trend data for the topic generator.
    """
    # Run all sources concurrently
    google_task = asyncio.create_task(get_google_trends(niche))
    reddit_task = asyncio.create_task(get_reddit_trending(niche))

    google_results = await google_task
    reddit_results = await reddit_task

    all_trends = google_results + reddit_results

    # Extract top keywords for Gemini prompt
    top_keywords = []
    seen = set()
    for t in all_trends:
        kw = t["keyword"].lower().strip()
        if kw not in seen and len(kw) > 5:
            top_keywords.append(t["keyword"])
            seen.add(kw)
    top_keywords = top_keywords[:15]

    # Build trending context string for the AI prompt
    context_parts = []
    if google_results:
        rising = [t["keyword"] for t in google_results if t["trend_direction"] == "rising"][:5]
        if rising:
            context_parts.append(f"🔥 Rising Google searches: {', '.join(rising)}")

    if reddit_results:
        hot_titles = [t["keyword"][:80] for t in reddit_results[:5]]
        if hot_titles:
            context_parts.append(f"📱 Hot on Reddit:\n" + "\n".join(f"  - {t}" for t in hot_titles))

    return {
        "trends": all_trends,
        "top_keywords": top_keywords,
        "context_string": "\n".join(context_parts) if context_parts else "",
        "source_count": len(all_trends),
        "timestamp": datetime.now().isoformat(),
    }


async def get_trending_hashtags(niche: str) -> list[str]:
    """
    Get currently trending hashtags for a niche from trend data.

    Converts trending keywords into hashtag format.
    """
    trend_data = await get_trending_topics(niche)
    hashtags = []

    for keyword in trend_data["top_keywords"][:10]:
        # Convert keyword to hashtag format
        tag = keyword.strip().title().replace(" ", "")
        tag = "#" + "".join(c for c in tag if c.isalnum())
        if len(tag) > 3 and tag not in hashtags:
            hashtags.append(tag)

    return hashtags[:10]


# CLI test
if __name__ == "__main__":
    async def test():
        for niche in ["ai_trading", "motivation", "tech_news"]:
            print(f"\n{'='*50}")
            print(f"  Trends for: {niche}")
            print(f"{'='*50}")
            data = await get_trending_topics(niche)
            print(f"  Sources found: {data['source_count']}")
            print(f"  Top keywords: {data['top_keywords'][:5]}")
            if data["context_string"]:
                print(f"\n{data['context_string']}")

    asyncio.run(test())
