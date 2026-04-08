"""
Genesis Content Engine — Trend Fetcher

Fetches top trending topic per brand from multiple sources.
Scores by recency, engagement, and keyword strength.
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta

from genesis.genesis_config import BRANDS, NEWS_API_KEY, YOUTUBE_API_KEY
from genesis.db import save_trend, get_today_trends, log_pipeline


# ── Keyword Scoring Bonuses ───────────────────────────────
BONUS_KEYWORDS = {
    "news": ["breaking", "crisis", "war", "attack", "killed", "shocking", "emergency", "alert", "explosion", "collapse"],
    "finance": ["crash", "surge", "record", "billion", "plunge", "rally", "bubble", "recession", "bitcoin", "crypto"],
    "motivation": ["secret", "powerful", "changed my life", "mistake", "regret", "transform", "unstoppable", "truth"],
    "viral": ["shocking", "insane", "caught on camera", "nobody expected", "drama", "exposed", "cancelled", "viral"],
}


def _keyword_score(text: str, brand: str) -> float:
    text_lower = text.lower()
    keywords = BONUS_KEYWORDS.get(brand, [])
    return sum(5.0 for kw in keywords if kw in text_lower)


def _recency_score(published_at: str) -> float:
    """Score 0-10 based on how recent. Last 2 hours = 10, last 12 hours = 5, older = 1."""
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(pub.tzinfo) - pub).total_seconds() / 3600
        if age_hours < 2:
            return 10.0
        elif age_hours < 6:
            return 7.0
        elif age_hours < 12:
            return 5.0
        elif age_hours < 24:
            return 3.0
        return 1.0
    except Exception:
        return 3.0


async def fetch_newsapi(session: aiohttp.ClientSession, category: str, brand: str) -> list:
    """Fetch from NewsAPI.org."""
    if not NEWS_API_KEY:
        return []

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "category": category,
        "language": "en",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY,
    }

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            results = []
            for article in data.get("articles", [])[:10]:
                title = article.get("title", "")
                if not title or title == "[Removed]":
                    continue
                recency = _recency_score(article.get("publishedAt", ""))
                kw_bonus = _keyword_score(title, brand)
                score = recency + kw_bonus
                results.append({
                    "topic": article.get("source", {}).get("name", "News"),
                    "headline": title,
                    "score": score,
                    "source": "newsapi",
                    "source_url": article.get("url", ""),
                })
            return results
    except Exception as e:
        print(f"  [NewsAPI] Error for {brand}: {e}")
        return []


async def fetch_reddit(session: aiohttp.ClientSession, subreddits: list, brand: str) -> list:
    """Fetch hot posts from Reddit (no API key needed)."""
    results = []
    headers = {"User-Agent": "GenesisStudioBot/1.0"}

    for sub in subreddits[:3]:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for post in data.get("data", {}).get("children", []):
                    pd = post.get("data", {})
                    title = pd.get("title", "")
                    if not title:
                        continue
                    ups = pd.get("ups", 0)
                    comments = pd.get("num_comments", 0)
                    engagement = min(10, (ups + comments * 2) / 500)
                    kw_bonus = _keyword_score(title, brand)
                    score = engagement + kw_bonus + 3  # Reddit baseline
                    results.append({
                        "topic": f"r/{sub}",
                        "headline": title,
                        "score": score,
                        "source": "reddit",
                        "source_url": f"https://reddit.com{pd.get('permalink', '')}",
                    })
        except Exception as e:
            print(f"  [Reddit] Error for r/{sub}: {e}")

    return results


async def fetch_coingecko(session: aiohttp.ClientSession, brand: str) -> list:
    """Fetch trending coins from CoinGecko (free, no API key)."""
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            results = []
            for coin in data.get("coins", [])[:5]:
                item = coin.get("item", {})
                name = item.get("name", "")
                symbol = item.get("symbol", "")
                rank = item.get("score", 5)
                score = max(1, 10 - rank) + _keyword_score(name, brand)
                results.append({
                    "topic": f"{name} ({symbol})",
                    "headline": f"{name} is trending on crypto markets — #{symbol} surging",
                    "score": score,
                    "source": "coingecko",
                    "source_url": f"https://www.coingecko.com/en/coins/{item.get('id', '')}",
                })
            return results
    except Exception as e:
        print(f"  [CoinGecko] Error: {e}")
        return []


async def fetch_youtube_trending(session: aiohttp.ClientSession, query: str, brand: str) -> list:
    """Fetch trending YouTube videos for a query."""
    if not YOUTUBE_API_KEY:
        return []

    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z",
            "maxResults": 5,
            "key": YOUTUBE_API_KEY,
        }
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            results = []
            for item in data.get("items", []):
                title = item.get("snippet", {}).get("title", "")
                if not title:
                    continue
                kw_bonus = _keyword_score(title, brand)
                score = 6 + kw_bonus  # YouTube trending baseline
                results.append({
                    "topic": item.get("snippet", {}).get("channelTitle", "YouTube"),
                    "headline": title,
                    "score": score,
                    "source": "youtube",
                    "source_url": f"https://youtube.com/watch?v={item.get('id', {}).get('videoId', '')}",
                })
            return results
    except Exception as e:
        print(f"  [YouTube] Error: {e}")
        return []


async def fetch_trends_for_brand(brand: str) -> dict | None:
    """Fetch and score all trends for a single brand, return the top one."""
    config = BRANDS[brand]
    sources = config["trend_sources"]
    all_results = []

    start = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = []

        # NewsAPI
        if "newsapi_category" in sources:
            tasks.append(fetch_newsapi(session, sources["newsapi_category"], brand))

        # Reddit
        if "reddit_subs" in sources:
            tasks.append(fetch_reddit(session, sources["reddit_subs"], brand))

        # CoinGecko (finance only)
        if sources.get("coingecko"):
            tasks.append(fetch_coingecko(session, brand))

        # YouTube trending
        if "youtube_query" in sources:
            tasks.append(fetch_youtube_trending(session, sources["youtube_query"], brand))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, list):
                all_results.extend(r)

    # ── Real-time sources (Google Trends, Twitter, TikTok) ──
    try:
        from genesis.intelligence import fetch_google_trends, fetch_twitter_trending, fetch_tiktok_trending, cross_platform_boost
        realtime_tasks = [
            fetch_google_trends(brand),
            fetch_twitter_trending(),
            fetch_tiktok_trending(),
        ]
        realtime_results = await asyncio.gather(*realtime_tasks, return_exceptions=True)
        for r in realtime_results:
            if isinstance(r, list):
                all_results.extend(r)

        # Cross-platform boost: topics on 2+ platforms get score multiplied
        all_results = cross_platform_boost(all_results)
    except Exception as e:
        print(f"  [Intelligence] Real-time sources failed: {e}")

    duration = time.time() - start

    if not all_results:
        log_pipeline("trend_fetch", brand, "failed", "No trends found from any source", duration)
        return None

    # Sort by score, pick top
    all_results.sort(key=lambda x: x["score"], reverse=True)
    top = all_results[0]

    # Save all top 5 to DB for tracking, capture the top trend's DB id
    top_trend_id = None
    for i, trend in enumerate(all_results[:5]):
        tid = save_trend(brand, trend["topic"], trend["headline"], trend["score"], trend["source"], trend.get("source_url", ""))
        if i == 0:
            top_trend_id = tid

    top["id"] = top_trend_id
    log_pipeline("trend_fetch", brand, "success", f"Top: {top['headline'][:80]} (score: {top['score']:.1f})", duration)

    return top


async def fetch_all_trends() -> dict:
    """Fetch trending topics for all 4 brands in parallel."""
    print("\n🔍 PHASE 1: Fetching Trends...")

    tasks = {brand: fetch_trends_for_brand(brand) for brand in BRANDS}
    results = {}

    for brand, task in tasks.items():
        result = await task
        results[brand] = result
        if result:
            print(f"  ✅ {BRANDS[brand]['name']}: {result['headline'][:70]}")
        else:
            print(f"  ❌ {BRANDS[brand]['name']}: No trend found")

    return results


if __name__ == "__main__":
    results = asyncio.run(fetch_all_trends())
    print(f"\nFetched {sum(1 for v in results.values() if v)} / {len(BRANDS)} trends")
