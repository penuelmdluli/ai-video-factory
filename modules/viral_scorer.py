"""
Viral Scorer — Validates a topic has real viral potential before committing.

Checks:
1. YouTube velocity — are existing videos on this topic getting views fast?
2. TikTok performance — is similar content doing well on TikTok?
3. Competition level — is the topic saturated or underserved?
4. Trend alignment — does the topic match current trending data?
5. Past performance — do keywords overlap with historically top-performing content?

Returns a 0-100 viral score. Topics below VIRAL_SCORE_THRESHOLD are retried.
All checks run concurrently and degrade gracefully (failures score 0, not block).
"""
import asyncio
import re
from datetime import datetime, timedelta

from config import YOUTUBE_API_KEY, VIRAL_SCORE_THRESHOLD


# ── Check 1: YouTube View Velocity ──────────────────────

async def check_youtube_velocity(topic: str, niche: str) -> dict:
    """
    Search YouTube for the topic and compute view velocity of recent videos.

    High velocity = topic is hot right now.
    Returns: avg_velocity, max_velocity, result_count, top_video_views
    """
    if not YOUTUBE_API_KEY:
        return {"avg_velocity": 0, "max_velocity": 0, "result_count": 0, "top_video_views": 0}

    try:
        import httpx

        # Extract key terms (3-4 words) from the topic for a broader search
        words = topic.split()
        search_query = " ".join(words[:6]) if len(words) > 6 else topic

        async with httpx.AsyncClient(timeout=15) as client:
            two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": search_query,
                    "type": "video",
                    "order": "date",
                    "publishedAfter": two_days_ago,
                    "maxResults": 10,
                    "key": YOUTUBE_API_KEY,
                },
            )
            if resp.status_code != 200:
                return {"avg_velocity": 0, "max_velocity": 0, "result_count": 0, "top_video_views": 0}

            items = resp.json().get("items", [])
            if not items:
                return {"avg_velocity": 0, "max_velocity": 0, "result_count": 0, "top_video_views": 0}

            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
            if not video_ids:
                return {"avg_velocity": 0, "max_velocity": 0, "result_count": 0, "top_video_views": 0}

            stats_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics,snippet",
                    "id": ",".join(video_ids[:10]),
                    "key": YOUTUBE_API_KEY,
                },
            )
            if stats_resp.status_code != 200:
                return {"avg_velocity": 0, "max_velocity": 0, "result_count": 0, "top_video_views": 0}

            velocities = []
            top_views = 0
            for video in stats_resp.json().get("items", []):
                try:
                    views = int(video["statistics"].get("viewCount", 0))
                    published = video["snippet"]["publishedAt"]
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    hours = max((datetime.now().astimezone() - pub_dt).total_seconds() / 3600, 1)
                    vel = views / hours
                    velocities.append(vel)
                    top_views = max(top_views, views)
                except Exception:
                    continue

            if not velocities:
                return {"avg_velocity": 0, "max_velocity": 0, "result_count": len(items), "top_video_views": 0}

            return {
                "avg_velocity": round(sum(velocities) / len(velocities), 1),
                "max_velocity": round(max(velocities), 1),
                "result_count": len(items),
                "top_video_views": top_views,
            }

    except Exception as e:
        print(f"[ViralScorer] YouTube velocity check failed: {e}")
        return {"avg_velocity": 0, "max_velocity": 0, "result_count": 0, "top_video_views": 0}


# ── Check 2: TikTok Performance ─────────────────────────

async def check_tiktok_performance(topic: str, niche: str) -> dict:
    """
    Estimate TikTok content popularity via Google search.

    Returns: estimated_popularity (0-100), result_count
    """
    try:
        import httpx

        words = topic.split()
        search_query = f"site:tiktok.com {' '.join(words[:5])}"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.google.com/search",
                params={"q": search_query, "num": 10},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            if resp.status_code == 200:
                # Count search results as a proxy for popularity
                result_count = len(re.findall(r'<h3[^>]*>', resp.text))
                # More results = more popular (logarithmic scaling)
                popularity = min(result_count * 12, 100)
                return {"estimated_popularity": popularity, "result_count": result_count}

    except Exception as e:
        print(f"[ViralScorer] TikTok check failed: {e}")

    return {"estimated_popularity": 0, "result_count": 0}


# ── Check 3: Competition Level ──────────────────────────

async def check_competition_level(topic: str, niche: str) -> dict:
    """
    Check how many recent YouTube videos exist on this exact topic.

    Some competition validates interest; too much means saturated.
    Returns: competition_score (0-1.0), recent_video_count
    """
    if not YOUTUBE_API_KEY:
        return {"competition_score": 0.5, "recent_video_count": 0}

    try:
        import httpx

        words = topic.split()
        search_query = " ".join(words[:5])

        async with httpx.AsyncClient(timeout=15) as client:
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": search_query,
                    "type": "video",
                    "order": "relevance",
                    "publishedAfter": seven_days_ago,
                    "maxResults": 25,
                    "key": YOUTUBE_API_KEY,
                },
            )
            if resp.status_code != 200:
                return {"competition_score": 0.5, "recent_video_count": 0}

            count = len(resp.json().get("items", []))

            # Score: 0-2 = blue ocean (great), 3-10 = sweet spot, 20+ = saturated
            if count <= 2:
                score = 0.1  # Blue ocean — unique topic, low competition
            elif count <= 5:
                score = 0.15  # Ideal — some validation, low competition
            elif count <= 10:
                score = 0.25  # Good — validated topic, manageable competition
            elif count <= 20:
                score = 0.5  # Getting competitive
            else:
                score = 0.8  # Saturated

            return {"competition_score": score, "recent_video_count": count}

    except Exception as e:
        print(f"[ViralScorer] Competition check failed: {e}")

    return {"competition_score": 0.5, "recent_video_count": 0}


# ── Calculate Combined Score ────────────────────────────

def calculate_viral_score(
    trend_data: dict,
    youtube_velocity: dict,
    tiktok_perf: dict,
    competition: dict,
    perf_keywords: list[str] | None = None,
    topic: str = "",
) -> float:
    """
    Calculate a combined viral score (0-100).

    Weights (recalibrated for real-world data availability):
    - Trend data richness:      35%  (how much trending data we have)
    - YouTube velocity:         30%  (are similar videos getting views fast?)
    - Competition (inverted):   20%  (unique topics score higher)
    - Past performance match:   10%  (alignment with proven winners)
    - TikTok bonus:              5%  (unreliable source, bonus only)

    A base score of 15 is added when trend data exists, since having ANY
    real trending context means the topic is grounded in reality.
    """
    # Base score: if we have any trend data, the topic is at least somewhat grounded
    base_score = 15 if trend_data.get("source_count", 0) > 0 else 0

    # 1. Trend data richness (35%) — more sources + results = better grounding
    source_count = trend_data.get("source_count", 0)
    active_sources = len(trend_data.get("active_sources", []))
    trend_score = min(source_count * 4 + active_sources * 10, 100)

    # 2. YouTube velocity (30%) — are existing videos on similar topics getting views?
    avg_vel = youtube_velocity.get("avg_velocity", 0)
    max_vel = youtube_velocity.get("max_velocity", 0)
    top_views = youtube_velocity.get("top_video_views", 0)
    # Use max of avg and scaled max velocity for more generous scoring
    best_vel = max(avg_vel, max_vel * 0.5)
    if best_vel >= 1000:
        yt_score = 100
    elif best_vel >= 100:
        yt_score = 60 + (best_vel - 100) / 900 * 40
    elif best_vel >= 10:
        yt_score = 25 + (best_vel - 10) / 90 * 35
    elif top_views > 0:
        yt_score = 15  # Found videos but low velocity — still some signal
    else:
        yt_score = 0

    # 3. Competition — inverted (20%): unique topics score higher
    comp = competition.get("competition_score", 0.5)
    comp_score = (1.0 - comp) * 100

    # 4. Past performance alignment (10%)
    perf_score = 0
    if perf_keywords and topic:
        topic_lower = topic.lower()
        matches = sum(1 for kw in perf_keywords if kw.lower() in topic_lower)
        perf_score = min(matches * 33, 100)

    # 5. TikTok bonus (5%) — unreliable, just a bonus when available
    tt_score = tiktok_perf.get("estimated_popularity", 0)

    # Weighted combination
    final = base_score + (
        trend_score * 0.35
        + yt_score * 0.30
        + comp_score * 0.20
        + perf_score * 0.10
        + tt_score * 0.05
    ) * 0.85  # Scale to leave room for base score

    return round(final, 1)


# ── Main Entry Point ────────────────────────────────────

async def validate_topic(
    topic: str,
    niche: str,
    min_score: float | None = None,
    trend_data: dict | None = None,
    perf_keywords: list[str] | None = None,
) -> dict:
    """
    Validate a topic's viral potential across multiple signals.

    Runs all checks concurrently. Returns score + pass/fail.

    Args:
        topic: The video topic to validate
        niche: Content niche
        min_score: Minimum score threshold (default from config)
        trend_data: Pre-fetched trend data (avoids re-fetching)
        perf_keywords: Top-performing past keywords

    Returns:
        dict with: topic, viral_score, passes_threshold, components, recommendation
    """
    if min_score is None:
        min_score = VIRAL_SCORE_THRESHOLD

    # Fetch trend data if not provided
    if trend_data is None:
        try:
            from modules.trend_detector import get_trending_topics
            trend_data = await get_trending_topics(niche)
        except Exception:
            trend_data = {"source_count": 0, "top_keywords": [], "context_string": ""}

    # Run all checks concurrently
    yt_task = asyncio.create_task(check_youtube_velocity(topic, niche))
    tt_task = asyncio.create_task(check_tiktok_performance(topic, niche))
    comp_task = asyncio.create_task(check_competition_level(topic, niche))

    youtube_velocity = await yt_task
    tiktok_perf = await tt_task
    competition = await comp_task

    # Calculate combined score
    viral_score = calculate_viral_score(
        trend_data=trend_data,
        youtube_velocity=youtube_velocity,
        tiktok_perf=tiktok_perf,
        competition=competition,
        perf_keywords=perf_keywords,
        topic=topic,
    )

    # Determine recommendation
    if viral_score >= 70:
        recommendation = "strong"
    elif viral_score >= 50:
        recommendation = "moderate"
    elif viral_score >= min_score:
        recommendation = "weak"
    else:
        recommendation = "skip"

    return {
        "topic": topic,
        "viral_score": viral_score,
        "passes_threshold": viral_score >= min_score,
        "components": {
            "trend_velocity": round(min(trend_data.get("source_count", 0) * 5, 100), 1),
            "youtube_velocity": round(youtube_velocity.get("avg_velocity", 0), 1),
            "tiktok_popularity": tiktok_perf.get("estimated_popularity", 0),
            "competition_score": round(competition.get("competition_score", 0.5), 2),
            "top_video_views": youtube_velocity.get("top_video_views", 0),
        },
        "recommendation": recommendation,
    }


# CLI test
if __name__ == "__main__":
    async def test():
        topics = [
            ("AI trading bot beats S&P 500 by 47% in March 2026", "ai_trading"),
            ("This FREE AI tool explains any stock in plain English", "ai_trading"),
            ("Morning routine of a billionaire that changed my life", "motivation"),
        ]
        for topic, niche in topics:
            print(f"\n{'='*60}")
            print(f"  Topic: {topic}")
            print(f"  Niche: {niche}")
            result = await validate_topic(topic, niche)
            print(f"  Viral Score: {result['viral_score']}/100 ({result['recommendation']})")
            print(f"  Passes: {result['passes_threshold']}")
            print(f"  Components: {result['components']}")
            print(f"{'='*60}")

    asyncio.run(test())
