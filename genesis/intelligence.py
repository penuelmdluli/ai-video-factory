"""
Genesis Content Engine — Intelligence Layer

Self-learning system that makes the pipeline smarter over time:

1. PERFORMANCE SCORER — Tracks what works per brand
   - Engagement rate (views, shares, comments)
   - Best posting times
   - Top-performing topic categories
   - Script style effectiveness

2. TREND BOOSTER — Amplifies trending-right-now signals
   - Google Trends real-time (pytrends)
   - Cross-platform correlation scoring
   - Viral velocity detection (acceleration, not just volume)

3. ADAPTIVE PROMPTS — Auto-tunes Claude script prompts
   - Learns from top 10% performing posts
   - Adjusts tone, structure, CTA style per brand
   - A/B tests prompt variations
"""
import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from genesis.genesis_config import BRANDS, DB_PATH, ANTHROPIC_API_KEY
from genesis.db import get_db


# ═══════════════════════════════════════════════════════
# 1. PERFORMANCE SCORER
# ═══════════════════════════════════════════════════════

def calculate_engagement_score(views: int, reactions: int, shares: int, comments: int) -> float:
    """
    Weighted engagement score.
    Comments > Shares > Reactions > Views
    (Comments signal deep engagement, shares signal virality)
    """
    if views == 0:
        return 0.0
    engagement_rate = (
        (comments * 4.0) +
        (shares * 3.0) +
        (reactions * 1.5) +
        (views * 0.1)
    ) / max(views, 1)
    return round(engagement_rate * 100, 2)


def get_brand_performance(brand: str, days: int = 30) -> dict:
    """Get performance analytics for a brand over N days."""
    conn = get_db()
    since = (datetime.now() - timedelta(days=days)).isoformat()

    rows = conn.execute("""
        SELECT p.*, v.brand, s.script, s.hook_line, s.caption,
               t.headline, t.source
        FROM genesis_posts p
        JOIN genesis_videos v ON p.video_id = v.id
        JOIN genesis_scripts s ON v.script_id = s.id
        LEFT JOIN genesis_trends t ON s.trend_id = t.id
        WHERE v.brand = ? AND p.status = 'posted' AND p.created_at > ?
        ORDER BY p.performance_score DESC
    """, (brand, since)).fetchall()
    conn.close()

    if not rows:
        return {"brand": brand, "total_posts": 0, "avg_score": 0, "top_posts": [], "insights": []}

    posts = [dict(r) for r in rows]
    scores = [p["performance_score"] for p in posts if p["performance_score"]]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Top performing posts
    top_posts = posts[:5]

    # Extract patterns from top performers
    insights = _extract_performance_insights(posts)

    return {
        "brand": brand,
        "total_posts": len(posts),
        "avg_score": round(avg_score, 2),
        "top_posts": top_posts,
        "insights": insights,
    }


def _extract_performance_insights(posts: list) -> list:
    """Analyze top posts to find what works."""
    insights = []

    if len(posts) < 5:
        return ["Not enough data yet (need 5+ posts)"]

    # Sort by score
    scored = [p for p in posts if p.get("performance_score", 0) > 0]
    if not scored:
        return ["No scored posts yet"]

    scored.sort(key=lambda p: p["performance_score"], reverse=True)
    top_quarter = scored[:max(1, len(scored) // 4)]
    bottom_quarter = scored[-max(1, len(scored) // 4):]

    # Analyze hook line patterns
    top_hooks = [p.get("hook_line", "") for p in top_quarter if p.get("hook_line")]
    bottom_hooks = [p.get("hook_line", "") for p in bottom_quarter if p.get("hook_line")]

    # Check for question endings in top performers
    question_top = sum(1 for h in top_hooks if h.strip().endswith("?"))
    question_bottom = sum(1 for h in bottom_hooks if h.strip().endswith("?"))
    if question_top > question_bottom and len(top_hooks) > 0:
        insights.append("Question-ending hooks perform better")

    # Check hook length
    if top_hooks and bottom_hooks:
        avg_top_len = sum(len(h.split()) for h in top_hooks) / len(top_hooks)
        avg_bottom_len = sum(len(h.split()) for h in bottom_hooks) / len(bottom_hooks)
        if avg_top_len < avg_bottom_len:
            insights.append(f"Shorter hooks work better (avg {avg_top_len:.0f} words vs {avg_bottom_len:.0f})")
        elif avg_top_len > avg_bottom_len * 1.3:
            insights.append(f"Longer detailed hooks work better for this brand")

    # Check for power words
    power_words = ["breaking", "just in", "nobody", "secret", "shocking", "truth", "urgent", "warning"]
    for word in power_words:
        in_top = sum(1 for h in top_hooks if word.lower() in h.lower())
        in_bottom = sum(1 for h in bottom_hooks if word.lower() in h.lower())
        if in_top > in_bottom and in_top > 0:
            insights.append(f'"{word}" in hooks correlates with higher engagement')

    # Analyze posting time
    top_hours = []
    for p in top_quarter:
        if p.get("posted_at"):
            try:
                hour = datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")).hour
                top_hours.append(hour)
            except (ValueError, AttributeError):
                pass

    if top_hours:
        best_hour = max(set(top_hours), key=top_hours.count)
        insights.append(f"Best posting hour: {best_hour}:00 UTC ({best_hour+2}:00 SAST)")

    # Trend source analysis
    top_sources = [p.get("source", "") for p in top_quarter if p.get("source")]
    if top_sources:
        best_source = max(set(top_sources), key=top_sources.count)
        insights.append(f"Best trend source: {best_source}")

    if not insights:
        insights.append("Building pattern database — more data needed")

    return insights


def update_all_performance_scores():
    """Recalculate performance scores for all posts."""
    conn = get_db()
    posts = conn.execute(
        "SELECT id, views, reactions, shares, comments FROM genesis_posts WHERE status = 'posted'"
    ).fetchall()

    updated = 0
    for p in posts:
        score = calculate_engagement_score(p[1] or 0, p[2] or 0, p[3] or 0, p[4] or 0)
        if score > 0:
            conn.execute("UPDATE genesis_posts SET performance_score = ? WHERE id = ?", (score, p[0]))
            updated += 1

    conn.commit()
    conn.close()
    return updated


# ═══════════════════════════════════════════════════════
# 2. TREND BOOSTER — Real-time viral detection
# ═══════════════════════════════════════════════════════

async def fetch_google_trends(brand: str) -> list:
    """
    Fetch real-time trending searches from Google Trends.
    Uses the unofficial pytrends API (no key needed).
    Falls back to RSS feed if pytrends not available.
    """
    import aiohttp

    brand_config = BRANDS[brand]
    trends = []

    # Google Trends RSS — real-time trending searches (no API key needed)
    try:
        rss_url = "https://trends.google.com/trending/rss?geo=US"
        async with aiohttp.ClientSession() as session:
            async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Parse RSS items
                    import re
                    titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", text)
                    traffic_values = re.findall(r"ht:approx_traffic>([\d,+]+)<", text)

                    for i, title in enumerate(titles[1:20]):  # Skip RSS feed title
                        traffic = traffic_values[i].replace(",", "").replace("+", "") if i < len(traffic_values) else "0"
                        trends.append({
                            "headline": title.strip(),
                            "source": "google_trends",
                            "score": int(traffic) / 10000 if traffic.isdigit() else 5.0,
                            "velocity": "rising",
                        })
    except Exception as e:
        print(f"  Google Trends RSS failed: {e}")

    # Google Trends Daily (broader topics)
    try:
        daily_url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        async with aiohttp.ClientSession() as session:
            async with session.get(daily_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    import re
                    titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", text)
                    for title in titles[1:10]:
                        trends.append({
                            "headline": title.strip(),
                            "source": "google_trends_daily",
                            "score": 3.0,
                            "velocity": "sustained",
                        })
    except Exception as e:
        print(f"  Google Trends Daily failed: {e}")

    return trends


async def fetch_twitter_trending() -> list:
    """
    Fetch trending topics from Twitter/X.
    Uses free unofficial endpoint (no API key).
    """
    import aiohttp
    trends = []

    try:
        # Use Nitter or similar public endpoint for trends
        url = "https://trends24.in/united-states/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10),
                                   headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    import re
                    # Extract trending hashtags/topics
                    items = re.findall(r'<a[^>]*class="trend-link"[^>]*>([^<]+)</a>', text)
                    for item in items[:15]:
                        trends.append({
                            "headline": item.strip(),
                            "source": "twitter_trending",
                            "score": 4.0,
                            "velocity": "rising",
                        })
    except Exception as e:
        print(f"  Twitter trends failed: {e}")

    return trends


async def fetch_tiktok_trending() -> list:
    """
    Fetch trending topics from TikTok Creative Center.
    """
    import aiohttp
    trends = []

    try:
        # TikTok Creative Center trending hashtags API
        url = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
        params = {"page": 1, "limit": 20, "country_code": "US", "period": 7}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10),
                                   headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("data", {}).get("list", [])
                    for item in items[:15]:
                        name = item.get("hashtag_name", "")
                        if name:
                            trends.append({
                                "headline": f"#{name} trending on TikTok",
                                "source": "tiktok_creative_center",
                                "score": 3.5,
                                "velocity": "rising",
                            })
    except Exception as e:
        print(f"  TikTok trends failed: {e}")

    return trends


def cross_platform_boost(all_trends: list) -> list:
    """
    Boost topics that appear on multiple platforms simultaneously.
    If a topic is trending on Google + Twitter + Reddit = genuinely viral.
    """
    # Normalize headlines for matching
    from collections import defaultdict
    topic_sources = defaultdict(list)

    for trend in all_trends:
        # Simple normalization: lowercase, strip punctuation
        key = trend["headline"].lower().strip()
        # Remove common prefixes
        for prefix in ["breaking:", "just in:", "#"]:
            if key.startswith(prefix):
                key = key[len(prefix):].strip()
        topic_sources[key].append(trend["source"])

    # Boost trends that appear on 2+ platforms
    boosted = []
    for trend in all_trends:
        key = trend["headline"].lower().strip()
        for prefix in ["breaking:", "just in:", "#"]:
            if key.startswith(prefix):
                key = key[len(prefix):].strip()

        sources = topic_sources.get(key, [])
        unique_sources = set(sources)
        platform_count = len(unique_sources)

        if platform_count >= 3:
            trend["score"] *= 3.0  # Triple boost — cross-platform viral
            trend["cross_platform"] = True
            trend["platforms"] = list(unique_sources)
        elif platform_count >= 2:
            trend["score"] *= 2.0  # Double boost
            trend["cross_platform"] = True
            trend["platforms"] = list(unique_sources)

        boosted.append(trend)

    # Sort by boosted score
    boosted.sort(key=lambda t: t["score"], reverse=True)
    return boosted


# ═══════════════════════════════════════════════════════
# 3. ADAPTIVE PROMPTS — Self-improving script generation
# ═══════════════════════════════════════════════════════

def get_adaptive_prompt(brand: str) -> str:
    """
    Generate an adaptive system prompt for Claude that incorporates
    learnings from past performance data.

    Returns an enhanced system prompt with real insights baked in.
    """
    from genesis.genesis_config import SCRIPT_PROMPTS

    base_prompt = SCRIPT_PROMPTS[brand]["system"]

    # Get performance insights
    perf = get_brand_performance(brand, days=30)

    if perf["total_posts"] < 5:
        # Not enough data — use base prompt
        return base_prompt

    insights = perf.get("insights", [])
    top_posts = perf.get("top_posts", [])

    # Build enhancement section
    enhancements = []

    for insight in insights:
        if "question-ending" in insight.lower():
            enhancements.append("End with a powerful question that drives comments.")
        elif "shorter hooks" in insight.lower():
            enhancements.append("Keep the opening hook under 10 words — punchy and direct.")
        elif "longer detailed" in insight.lower():
            enhancements.append("Use a detailed, intriguing opening that builds curiosity.")
        elif "breaking" in insight.lower() or "just in" in insight.lower():
            enhancements.append(f'Use urgency words like "BREAKING" or "JUST IN" in the opening.')
        elif "nobody" in insight.lower() or "secret" in insight.lower():
            enhancements.append('Use curiosity gap words like "nobody", "secret", "truth" in the opening.')

    # Add top performer hooks as examples
    if top_posts:
        top_hooks = [p.get("hook_line", "") for p in top_posts[:3] if p.get("hook_line")]
        if top_hooks:
            enhancements.append(
                f"These hook styles performed best: " +
                " | ".join(f'"{h[:60]}"' for h in top_hooks)
            )

    if enhancements:
        enhanced_prompt = (
            f"{base_prompt}\n\n"
            f"PERFORMANCE INSIGHTS (from real audience data):\n"
            + "\n".join(f"- {e}" for e in enhancements)
        )
        return enhanced_prompt

    return base_prompt


def generate_performance_report() -> str:
    """Generate a full performance report across all brands."""
    report_lines = [
        "=" * 60,
        "  GENESIS CONTENT ENGINE — Performance Report",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M SAST')}",
        "=" * 60,
    ]

    for brand in BRANDS:
        perf = get_brand_performance(brand, days=30)
        brand_name = BRANDS[brand]["name"]

        report_lines.append(f"\n--- {brand_name} ---")
        report_lines.append(f"  Posts (30d): {perf['total_posts']}")
        report_lines.append(f"  Avg Score: {perf['avg_score']}")

        if perf["insights"]:
            report_lines.append("  Insights:")
            for insight in perf["insights"]:
                report_lines.append(f"    - {insight}")

        if perf["top_posts"]:
            report_lines.append("  Top Performer:")
            top = perf["top_posts"][0]
            report_lines.append(f"    Hook: {top.get('hook_line', 'N/A')[:60]}")
            report_lines.append(f"    Score: {top.get('performance_score', 0)}")
            report_lines.append(f"    Views: {top.get('views', 0)} | Shares: {top.get('shares', 0)}")

    report_lines.append("\n" + "=" * 60)
    return "\n".join(report_lines)


# ═══════════════════════════════════════════════════════
# MAIN — Run intelligence analysis
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    print(generate_performance_report())
