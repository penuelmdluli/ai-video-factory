"""
Trend Detector — Real-time trend discovery from multiple sources.

Sources:
1. Google Trends (pytrends) — real search volume data
2. Reddit hot posts — community pulse
3. YouTube trending — video topic validation (Data API v3)
4. Twitter/X — social pulse (API v2, bearer token)
5. TikTok — viral content signals (unofficial/Google fallback)

Includes:
- SourceHealthTracker for reliability monitoring + exponential backoff
- Result caching with configurable TTL
- Graceful degradation: if all sources fail, serves stale cache

Feeds trending data to Gemini for grounded topic generation.
"""
import asyncio
import json
import random
import base64
import hashlib
import hmac
import time as _time
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    NICHES, OUTPUT_DIR, YOUTUBE_API_KEY,
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TREND_CACHE_TTL_HOURS, TREND_SOURCE_STALE_HOURS,
)


# ── Niche-to-search mappings for trend APIs ──────────────
NICHE_TREND_QUERIES = {
    "ai_trading": {
        "pytrends": ["AI trading", "stock market AI", "crypto AI", "algorithmic trading", "trading bot"],
        "reddit": ["algotrading", "wallstreetbets", "stocks", "cryptocurrency", "daytrading"],
        "youtube_query": "AI trading stocks crypto",
        "twitter": ["AI trading", "stock market", "crypto AI", "#algotrading", "#AIstocks"],
    },
    "ai_money": {
        "pytrends": ["make money AI", "AI side hustle", "passive income AI", "ChatGPT money", "AI business"],
        "reddit": ["sidehustle", "beermoney", "WorkOnline", "Entrepreneur", "passive_income"],
        "youtube_query": "make money AI side hustle",
        "twitter": ["AI side hustle", "make money AI", "passive income", "#AIsidehustle", "#onlineincome"],
    },
    "tech_news": {
        "pytrends": ["AI news", "artificial intelligence", "tech news", "AI breakthrough", "new AI model"],
        "reddit": ["technology", "artificial", "MachineLearning", "singularity", "tech"],
        "youtube_query": "AI news technology breakthrough",
        "twitter": ["AI news", "tech news", "artificial intelligence", "#AInews", "#techbreakthrough"],
    },
    "motivation": {
        "pytrends": ["motivation", "self improvement", "morning routine", "discipline mindset", "success habits"],
        "reddit": ["GetMotivated", "selfimprovement", "productivity", "DecidingToBeBetter", "getdisciplined"],
        "youtube_query": "motivation success mindset discipline",
        "twitter": ["motivation", "self improvement", "morning routine", "#motivation", "#mindset"],
    },
    "health_wellness": {
        "pytrends": ["health tips", "natural remedies", "nutrition science", "gut health", "longevity"],
        "reddit": ["health", "nutrition", "HealthyFood", "naturalmedicine", "longevity"],
        "youtube_query": "health wellness natural remedies nutrition",
        "twitter": ["health tips", "natural remedies", "nutrition", "#healthyliving", "#wellness"],
    },
    "blissful_moments": {
        "pytrends": ["mindfulness", "gratitude", "inner peace", "happiness tips", "positivity"],
        "reddit": ["Mindfulness", "happy", "MadeMeSmile", "wholesome", "UpliftingNews"],
        "youtube_query": "mindfulness gratitude positivity inspiration",
        "twitter": ["mindfulness", "gratitude", "positivity", "#mindfulness", "#gratitude"],
    },
}


# ── Source Health Tracker ────────────────────────────────
class SourceHealthTracker:
    """Track health/freshness of each trend source with exponential backoff."""

    HEALTH_FILE = OUTPUT_DIR / "trend_source_health.json"

    def __init__(self):
        self._status = self._load()

    def _load(self) -> dict:
        try:
            if self.HEALTH_FILE.exists():
                return json.loads(self.HEALTH_FILE.read_text())
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            self.HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.HEALTH_FILE.write_text(json.dumps(self._status, indent=2))
        except Exception:
            pass

    def record_success(self, source: str, result_count: int):
        self._status[source] = {
            "last_success": datetime.now().isoformat(),
            "last_result_count": result_count,
            "consecutive_failures": 0,
            "last_error": None,
            "backoff_until": None,
        }
        self._save()

    def record_failure(self, source: str, error: str):
        entry = self._status.get(source, {})
        failures = entry.get("consecutive_failures", 0) + 1
        # Exponential backoff: 2^failures minutes, max 60 min
        backoff_minutes = min(2 ** failures, 60)
        self._status[source] = {
            **entry,
            "last_failure": datetime.now().isoformat(),
            "last_error": str(error)[:200],
            "consecutive_failures": failures,
            "backoff_until": (datetime.now() + timedelta(minutes=backoff_minutes)).isoformat(),
        }
        self._save()

    def should_backoff(self, source: str) -> bool:
        entry = self._status.get(source, {})
        backoff_until = entry.get("backoff_until")
        if backoff_until:
            try:
                return datetime.now() < datetime.fromisoformat(backoff_until)
            except Exception:
                pass
        return False

    def is_healthy(self, source: str) -> bool:
        entry = self._status.get(source, {})
        last_success = entry.get("last_success")
        if not last_success:
            return True  # Never ran = assume healthy (let it try)
        try:
            age = datetime.now() - datetime.fromisoformat(last_success)
            return age < timedelta(hours=TREND_SOURCE_STALE_HOURS)
        except Exception:
            return True

    def get_stale_sources(self) -> list[str]:
        all_sources = ["google_trends", "reddit", "youtube", "twitter", "tiktok"]
        return [s for s in all_sources if not self.is_healthy(s)]

    def get_status_summary(self) -> dict:
        return {
            source: {
                "healthy": self.is_healthy(source),
                "backed_off": self.should_backoff(source),
                "consecutive_failures": self._status.get(source, {}).get("consecutive_failures", 0),
                "last_success": self._status.get(source, {}).get("last_success"),
                "last_error": self._status.get(source, {}).get("last_error"),
                "last_result_count": self._status.get(source, {}).get("last_result_count", 0),
            }
            for source in ["google_trends", "reddit", "youtube", "twitter", "tiktok"]
        }


# Module-level health tracker
_health_tracker = SourceHealthTracker()


# ── Trend Cache ──────────────────────────────────────────
CACHE_FILE = OUTPUT_DIR / "trend_cache.json"


def _load_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(cache: dict):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass


def _get_cached_trends(niche: str) -> dict | None:
    cache = _load_cache()
    entry = cache.get(niche)
    if entry:
        try:
            cached_at = datetime.fromisoformat(entry["timestamp"])
            if datetime.now() - cached_at < timedelta(hours=TREND_CACHE_TTL_HOURS):
                return entry
        except Exception:
            pass
    return None


def _cache_trends(niche: str, data: dict):
    cache = _load_cache()
    cache[niche] = data
    _save_cache(cache)


# ── Source 1: Google Trends (pytrends) ───────────────────

async def get_google_trends(niche: str, max_results: int = 10) -> list[dict]:
    """Fetch real trending queries from Google Trends via pytrends."""
    queries = NICHE_TREND_QUERIES.get(niche, {}).get("pytrends", [])
    if not queries:
        return []

    trending = []
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360)

        for query in queries[:3]:
            try:
                pytrends.build_payload([query], timeframe="now 7-d")
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
                await asyncio.sleep(3)  # Increased from 1s to avoid rate limits
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(15)
                continue
    except ImportError:
        print("[TrendDetector] pytrends not installed. Run: pip install pytrends")
    except Exception as e:
        print(f"[TrendDetector] Google Trends failed: {e}")

    return trending[:max_results]


# ── Source 2: Reddit Hot Posts ───────────────────────────

async def get_reddit_trending(niche: str, max_results: int = 10) -> list[dict]:
    """Fetch hot posts from niche-relevant subreddits (public JSON API)."""
    subreddits = NICHE_TREND_QUERIES.get(niche, {}).get("reddit", [])
    if not subreddits:
        return []

    trending = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            selected = random.sample(subreddits, min(2, len(subreddits)))
            for sub in selected:
                try:
                    resp = await client.get(
                        f"https://www.reddit.com/r/{sub}/hot.json",
                        params={"limit": 10, "t": "day"},
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                            "Accept": "application/json",
                        },
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

    trending.sort(key=lambda x: x["score"], reverse=True)
    return trending[:max_results]


# ── Source 3: YouTube Trending (Data API v3) ─────────────

async def get_youtube_trending(niche: str, max_results: int = 10) -> list[dict]:
    """Fetch trending/popular YouTube videos for a niche via Data API v3."""
    if not YOUTUBE_API_KEY:
        return []

    query = NICHE_TREND_QUERIES.get(niche, {}).get("youtube_query", "")
    if not query:
        return []

    trending = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            # Search for recent popular videos in this niche
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": seven_days_ago,
                    "maxResults": min(max_results, 15),
                    "key": YOUTUBE_API_KEY,
                },
            )
            if resp.status_code != 200:
                print(f"[TrendDetector] YouTube search failed: {resp.status_code}")
                return []

            items = resp.json().get("items", [])
            if not items:
                return []

            # Get video statistics for view velocity calculation
            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
            if not video_ids:
                return []

            stats_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics,snippet",
                    "id": ",".join(video_ids[:10]),
                    "key": YOUTUBE_API_KEY,
                },
            )
            if stats_resp.status_code != 200:
                return []

            for video in stats_resp.json().get("items", []):
                try:
                    title = video["snippet"]["title"]
                    views = int(video["statistics"].get("viewCount", 0))
                    published = video["snippet"]["publishedAt"]
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    hours_since = max((datetime.now().astimezone() - pub_dt).total_seconds() / 3600, 1)
                    velocity = views / hours_since

                    trending.append({
                        "keyword": title,
                        "score": int(velocity),
                        "trend_direction": "viral" if velocity > 1000 else "rising",
                        "source": "youtube",
                        "views": views,
                        "velocity": round(velocity, 1),
                    })
                except Exception:
                    continue

    except ImportError:
        print("[TrendDetector] httpx not installed")
    except Exception as e:
        print(f"[TrendDetector] YouTube trending failed: {e}")

    trending.sort(key=lambda x: x["score"], reverse=True)
    return trending[:max_results]


# ── Source 4: Twitter/X Trending (API v2, bearer token) ──

async def _get_twitter_bearer_token() -> str | None:
    """Get a bearer token using app-only auth (client credentials)."""
    if not TWITTER_API_KEY or not TWITTER_API_SECRET:
        return None

    try:
        import httpx
        credentials = base64.b64encode(f"{TWITTER_API_KEY}:{TWITTER_API_SECRET}".encode()).decode()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.twitter.com/oauth2/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                },
                data="grant_type=client_credentials",
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
    except Exception as e:
        print(f"[TrendDetector] Twitter bearer token failed: {e}")
    return None


async def get_twitter_trending(niche: str, max_results: int = 10) -> list[dict]:
    """Fetch trending tweets for a niche via Twitter API v2."""
    keywords = NICHE_TREND_QUERIES.get(niche, {}).get("twitter", [])
    if not keywords:
        return []

    bearer_token = await _get_twitter_bearer_token()
    if not bearer_token:
        return []

    trending = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            # Search recent tweets with niche keywords (pick 2 to conserve rate limits)
            selected_kws = random.sample(keywords, min(2, len(keywords)))
            query = " OR ".join(selected_kws) + " -is:retweet lang:en"

            resp = await client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": query,
                    "max_results": 10,
                    "tweet.fields": "public_metrics,created_at",
                },
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            if resp.status_code != 200:
                print(f"[TrendDetector] Twitter search failed: {resp.status_code}")
                return []

            tweets = resp.json().get("data", [])
            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                engagement = (
                    metrics.get("like_count", 0)
                    + metrics.get("retweet_count", 0) * 2
                    + metrics.get("reply_count", 0)
                )
                text = tweet.get("text", "")
                if text and engagement > 5:
                    # Clean up tweet text for use as a keyword
                    clean = text.split("http")[0].strip()  # Remove URLs
                    if len(clean) > 15:
                        trending.append({
                            "keyword": clean[:120],
                            "score": engagement,
                            "trend_direction": "trending",
                            "source": "twitter",
                        })

    except ImportError:
        print("[TrendDetector] httpx not installed")
    except Exception as e:
        print(f"[TrendDetector] Twitter trending failed: {e}")

    trending.sort(key=lambda x: x["score"], reverse=True)
    return trending[:max_results]


# ── Source 5: TikTok Trending (unofficial / Google fallback) ─

async def get_tiktok_trending(niche: str, max_results: int = 10) -> list[dict]:
    """Fetch TikTok trending signals via Google search fallback."""
    niche_config = NICHES.get(niche, {})
    search_kws = niche_config.get("search_keywords", [])
    if not search_kws:
        return []

    trending = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            # Google search for trending TikTok content in this niche
            query = f"site:tiktok.com {search_kws[0]} trending"
            resp = await client.get(
                "https://www.google.com/search",
                params={"q": query, "num": 10},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            if resp.status_code == 200:
                import re
                # Extract titles from search results
                titles = re.findall(r'<h3[^>]*>(.*?)</h3>', resp.text)
                for title in titles[:max_results]:
                    clean = re.sub(r'<[^>]+>', '', title).strip()
                    # Remove "TikTok" prefix and clean up
                    clean = re.sub(r'^TikTok\s*[-·|]\s*', '', clean)
                    if clean and len(clean) > 10:
                        trending.append({
                            "keyword": clean[:120],
                            "score": 50,  # Default score for scraping (no real metric)
                            "trend_direction": "trending",
                            "source": "tiktok",
                        })
    except Exception as e:
        print(f"[TrendDetector] TikTok trending failed: {e}")

    return trending[:max_results]


# ── Aggregator ───────────────────────────────────────────

async def get_trending_topics(niche: str) -> dict:
    """
    Aggregate trending data from all 5 sources for a niche.

    Returns a dict with structured trend data for the topic generator.
    Uses caching and health tracking for reliability.
    """
    # Check cache first
    cached = _get_cached_trends(niche)
    if cached:
        return cached

    # Run all sources concurrently, respecting backoff
    tasks = {}

    if not _health_tracker.should_backoff("google_trends"):
        tasks["google_trends"] = asyncio.create_task(get_google_trends(niche))

    if not _health_tracker.should_backoff("reddit"):
        tasks["reddit"] = asyncio.create_task(get_reddit_trending(niche))

    if not _health_tracker.should_backoff("youtube"):
        tasks["youtube"] = asyncio.create_task(get_youtube_trending(niche))

    if not _health_tracker.should_backoff("twitter"):
        tasks["twitter"] = asyncio.create_task(get_twitter_trending(niche))

    if not _health_tracker.should_backoff("tiktok"):
        tasks["tiktok"] = asyncio.create_task(get_tiktok_trending(niche))

    # Gather results
    results = {}
    for source_name, task in tasks.items():
        try:
            result = await task
            results[source_name] = result
            if result:
                _health_tracker.record_success(source_name, len(result))
            else:
                _health_tracker.record_success(source_name, 0)
        except Exception as e:
            _health_tracker.record_failure(source_name, str(e))
            results[source_name] = []
            print(f"[TrendDetector] {source_name} failed: {e}")

    # Combine all trends
    all_trends = []
    for source_results in results.values():
        all_trends.extend(source_results)

    # If ALL sources returned nothing, try stale cache
    if not all_trends:
        stale = _load_cache().get(niche)
        if stale:
            print(f"[TrendDetector] All sources empty for {niche}, using stale cache")
            return stale

    # Extract top keywords (deduplicated)
    top_keywords = []
    seen = set()
    for t in all_trends:
        kw = t["keyword"].lower().strip()
        if kw not in seen and len(kw) > 5:
            top_keywords.append(t["keyword"])
            seen.add(kw)
    top_keywords = top_keywords[:20]

    # Build trending context string for the AI prompt
    context_parts = []

    google_results = results.get("google_trends", [])
    if google_results:
        rising = [t["keyword"] for t in google_results if t["trend_direction"] == "rising"][:5]
        if rising:
            context_parts.append(f"Rising Google searches: {', '.join(rising)}")

    reddit_results = results.get("reddit", [])
    if reddit_results:
        hot_titles = [t["keyword"][:80] for t in reddit_results[:5]]
        if hot_titles:
            context_parts.append(f"Hot on Reddit:\n" + "\n".join(f"  - {t}" for t in hot_titles))

    youtube_results = results.get("youtube", [])
    if youtube_results:
        yt_titles = [f"{t['keyword'][:70]} ({t.get('views', 0):,} views)" for t in youtube_results[:5]]
        if yt_titles:
            context_parts.append(f"Trending on YouTube:\n" + "\n".join(f"  - {t}" for t in yt_titles))

    twitter_results = results.get("twitter", [])
    if twitter_results:
        tw_posts = [t["keyword"][:80] for t in twitter_results[:5]]
        if tw_posts:
            context_parts.append(f"Trending on Twitter/X:\n" + "\n".join(f"  - {t}" for t in tw_posts))

    tiktok_results = results.get("tiktok", [])
    if tiktok_results:
        tt_titles = [t["keyword"][:80] for t in tiktok_results[:5]]
        if tt_titles:
            context_parts.append(f"Trending on TikTok:\n" + "\n".join(f"  - {t}" for t in tt_titles))

    # Source summary
    active_sources = [name for name, res in results.items() if res]
    source_summary = f"[Sources: {', '.join(active_sources) if active_sources else 'none'}]"

    data = {
        "trends": all_trends,
        "top_keywords": top_keywords,
        "context_string": "\n\n".join(context_parts) if context_parts else "",
        "source_count": len(all_trends),
        "active_sources": active_sources,
        "source_summary": source_summary,
        "timestamp": datetime.now().isoformat(),
    }

    # Only cache if we got actual results (don't cache empty)
    if all_trends:
        _cache_trends(niche, data)

    return data


async def get_trending_hashtags(niche: str) -> list[str]:
    """Get currently trending hashtags for a niche from trend data."""
    trend_data = await get_trending_topics(niche)
    hashtags = []

    for keyword in trend_data["top_keywords"][:10]:
        tag = keyword.strip().title().replace(" ", "")
        tag = "#" + "".join(c for c in tag if c.isalnum())
        if len(tag) > 3 and tag not in hashtags:
            hashtags.append(tag)

    return hashtags[:10]


def get_health_status() -> dict:
    """Get the health status of all trend sources."""
    return _health_tracker.get_status_summary()


# CLI test
if __name__ == "__main__":
    async def test():
        for niche in ["ai_trading", "motivation", "tech_news"]:
            print(f"\n{'='*50}")
            print(f"  Trends for: {niche}")
            print(f"{'='*50}")
            data = await get_trending_topics(niche)
            print(f"  Sources found: {data['source_count']}")
            print(f"  Active sources: {data.get('active_sources', [])}")
            print(f"  Top keywords: {data['top_keywords'][:5]}")
            if data["context_string"]:
                print(f"\n{data['context_string']}")

        print(f"\n{'='*50}")
        print("  Source Health Status")
        print(f"{'='*50}")
        status = get_health_status()
        for source, info in status.items():
            h = "OK" if info["healthy"] else "STALE"
            b = " (BACKOFF)" if info["backed_off"] else ""
            print(f"  {source}: {h}{b} | failures: {info['consecutive_failures']} | last count: {info['last_result_count']}")

    asyncio.run(test())
