"""
Content Optimizer — Data-driven content strategy for Facebook page growth.

Analyzes performance data to recommend:
- Best content types per niche
- Optimal posting frequency
- Topic suggestions based on what's working
- Weekly content strategies
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, ROOT_DIR, ANTHROPIC_API_KEY, GEMINI_API_KEY, OUTPUT_DIR


# ── Constants ────────────────────────────────────────────────

ACTIVE_NICHES = [
    "ai_money", "tech_news", "motivation",
    "health_wellness", "blissful_moments", "limitless_you",
]

NICHE_PAGE_NAMES = {
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Blissful Moments",
    "limitless_you": "Limitless You",
}


# ── Performance Analysis ─────────────────────────────────────

async def analyze_content_performance(niche: str) -> dict:
    """
    Analyze what's working for a niche by pulling from multiple data sources.

    Returns comprehensive analysis with recommendations.
    """
    analysis = {
        "niche": niche,
        "page_name": NICHE_PAGE_NAMES.get(niche, niche),
        "analyzed_at": datetime.now().isoformat(),
        "best_content_types": [],
        "best_topics": [],
        "best_posting_hours": [],
        "engagement_trend": "stable",
        "recommendations": [],
    }

    # Pull from facebook_insights
    try:
        from modules.facebook_insights import get_best_content_types, get_top_posts, get_growth_rate
        analysis["best_content_types"] = get_best_content_types(niche)
        analysis["top_posts"] = get_top_posts(niche, 5)

        weekly_growth = get_growth_rate(niche, "weekly")
        if weekly_growth["growth_percent"] > 2:
            analysis["engagement_trend"] = "growing"
        elif weekly_growth["growth_percent"] < -2:
            analysis["engagement_trend"] = "declining"
        analysis["weekly_growth"] = weekly_growth
    except Exception as e:
        print(f"[Optimizer] Could not load insights data for {niche}: {e}")

    # Pull from performance_tracker
    try:
        from modules.performance_tracker import get_best_posting_hours, get_best_performing_keywords
        analysis["best_posting_hours"] = get_best_posting_hours(niche)
        analysis["best_topics"] = get_best_performing_keywords(niche)
    except Exception as e:
        print(f"[Optimizer] Could not load performance data for {niche}: {e}")

    # Pull from A/B testing
    try:
        from modules.ab_testing import get_winning_variants
        analysis["winning_variants"] = get_winning_variants(niche)
    except Exception as e:
        pass

    # Generate recommendations
    analysis["recommendations"] = _generate_recommendations(analysis)

    return analysis


def _generate_recommendations(analysis: dict) -> list[str]:
    """Generate actionable recommendations from analysis data."""
    recs = []
    niche = analysis["niche"]
    trend = analysis.get("engagement_trend", "stable")

    if trend == "declining":
        recs.append("Engagement is declining — try more polls and questions to boost comments")
        recs.append("Consider posting at different times based on when your audience is most active")
    elif trend == "growing":
        recs.append("Growth is strong — maintain current strategy and increase posting frequency")

    # Content type recommendations
    best_types = analysis.get("best_content_types", [])
    if best_types:
        top_type = best_types[0].get("content_type", "video")
        recs.append(f"Top performing content type: {top_type} — create more of this")

    # Topic recommendations
    best_topics = analysis.get("best_topics", [])
    if best_topics:
        recs.append(f"Top keywords: {', '.join(best_topics[:5])} — lean into these topics")

    # Posting time recommendations
    best_hours = analysis.get("best_posting_hours", [])
    if best_hours:
        hours_str = ", ".join(f"{h}:00" for h in best_hours[:3])
        recs.append(f"Best posting hours: {hours_str}")

    # Growth-based recommendations
    weekly = analysis.get("weekly_growth", {})
    if weekly.get("current", 0) < 1000:
        recs.append("Under 1K followers — focus on engagement posts and community replies to build loyalty")
    elif weekly.get("current", 0) < 5000:
        recs.append("Growing page — mix engagement posts with viral content for discovery")

    return recs


# ── Schedule Recommendations ─────────────────────────────────

def get_recommended_schedule(niche: str) -> dict:
    """
    Recommend optimal posting schedule based on page performance.

    Returns: {viral_shorts: N, engagement_posts: N, content_mix: {...}}
    """
    # Get current follower count
    followers = 0
    engagement_rate = 0.0
    try:
        from modules.facebook_insights import get_growth_rate
        data = get_growth_rate(niche, "weekly")
        followers = data.get("current", 0)
    except Exception:
        pass

    try:
        from modules.facebook_insights import get_page_benchmarks
        benchmarks = get_page_benchmarks()
        for b in benchmarks:
            if b["niche"] == niche:
                engagement_rate = b.get("engagement_rate", 0)
                break
    except Exception:
        pass

    # Base schedule by tier
    if followers >= 10000:  # Large page
        schedule = {
            "viral_shorts": 5,
            "engagement_posts": 5,
            "content_mix": {"video": 0.6, "image_post": 0.25, "text_poll": 0.15},
        }
    elif followers >= 1000:  # Medium page
        schedule = {
            "viral_shorts": 3,
            "engagement_posts": 4,
            "content_mix": {"video": 0.5, "image_post": 0.30, "text_poll": 0.20},
        }
    else:  # Small page
        schedule = {
            "viral_shorts": 2,
            "engagement_posts": 3,
            "content_mix": {"video": 0.4, "image_post": 0.30, "text_poll": 0.30},
        }

    # Adjust based on engagement rate
    if engagement_rate > 5:
        schedule["viral_shorts"] += 1  # High engagement = post more
    elif engagement_rate < 1 and engagement_rate > 0:
        schedule["engagement_posts"] += 1  # Low engagement = more interaction posts

    schedule["niche"] = niche
    schedule["followers"] = followers
    schedule["engagement_rate"] = engagement_rate

    return schedule


# ── AI-Powered Topic Suggestions ─────────────────────────────

async def get_content_recommendations(niche: str) -> list[str]:
    """
    Use Claude AI to suggest new content topics based on what's working.

    Feeds in: top performing topics, current trends, niche context.
    Returns: 5 new topic suggestions.
    """
    # Gather context
    best_topics = []
    try:
        from modules.performance_tracker import get_best_performing_keywords
        best_topics = get_best_performing_keywords(niche)
    except Exception:
        pass

    top_posts = []
    try:
        from modules.facebook_insights import get_top_posts
        raw_posts = get_top_posts(niche, 5)
        top_posts = [p.get("message", "")[:100] for p in raw_posts if p.get("message")]
    except Exception:
        pass

    niche_info = NICHES.get(niche, {})
    niche_name = niche_info.get("name", niche)
    niche_topics = niche_info.get("topics_bank", [])[:5]

    prompt = f"""You are a social media content strategist for the Facebook page "{NICHE_PAGE_NAMES.get(niche, niche)}" in the {niche_name} niche.

WHAT'S WORKING (top performing keywords): {', '.join(best_topics[:10]) if best_topics else 'No data yet'}
TOP POSTS: {json.dumps(top_posts[:3]) if top_posts else 'No data yet'}
EXISTING TOPICS: {', '.join(niche_topics)}

Generate 5 NEW viral topic ideas that:
1. Build on what's already working
2. Are timely and relevant for July 2026
3. Would drive high engagement (comments, shares)
4. Are unique enough to stand out

Return ONLY a JSON array of 5 topic strings. Example:
["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]"""

    # Try Claude
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            print(f"[Optimizer] Claude topic gen failed: {e}")

    # Fallback to Gemini
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"[Optimizer] Gemini topic gen failed: {e}")

    return []


# ── Weekly Strategy ──────────────────────────────────────────

async def generate_weekly_strategy(niche: str) -> dict:
    """
    Generate a full week content plan for a niche.

    Returns: {
        niche, week_of, daily_plan: [{day, videos, engagement_posts, topics, focus}],
        summary
    }
    """
    schedule = get_recommended_schedule(niche)
    topics = await get_content_recommendations(niche)
    analysis = await analyze_content_performance(niche)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Weight towards weekends (higher engagement)
    day_weights = {
        "Monday": 0.8, "Tuesday": 0.8, "Wednesday": 0.9,
        "Thursday": 1.0, "Friday": 1.1, "Saturday": 1.2, "Sunday": 1.1,
    }

    daily_plan = []
    topic_idx = 0

    for day in days:
        weight = day_weights[day]
        videos = max(1, round(schedule["viral_shorts"] * weight))
        eng_posts = max(1, round(schedule["engagement_posts"] * weight * 0.6))

        # Assign topics
        day_topics = []
        for _ in range(videos):
            if topics and topic_idx < len(topics):
                day_topics.append(topics[topic_idx % len(topics)])
                topic_idx += 1

        # Content focus by day
        focus_map = {
            "Monday": "motivation_start",
            "Tuesday": "educational",
            "Wednesday": "tips_tricks",
            "Thursday": "trending",
            "Friday": "fun_engagement",
            "Saturday": "viral_content",
            "Sunday": "reflection_gratitude",
        }

        daily_plan.append({
            "day": day,
            "videos": videos,
            "engagement_posts": eng_posts,
            "topics": day_topics,
            "focus": focus_map.get(day, "mixed"),
        })

    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())

    return {
        "niche": niche,
        "page_name": NICHE_PAGE_NAMES.get(niche, niche),
        "week_of": week_start.strftime("%Y-%m-%d"),
        "daily_plan": daily_plan,
        "total_videos": sum(d["videos"] for d in daily_plan),
        "total_engagement": sum(d["engagement_posts"] for d in daily_plan),
        "recommendations": analysis.get("recommendations", []),
        "generated_at": datetime.now().isoformat(),
    }


# ── Reporting ────────────────────────────────────────────────

def print_optimization_report():
    """Print content optimization recommendations for all niches."""
    print("\n" + "=" * 70)
    print("  CONTENT OPTIMIZATION REPORT")
    print("=" * 70)

    for niche in ACTIVE_NICHES:
        schedule = get_recommended_schedule(niche)
        print(f"\n  {NICHE_PAGE_NAMES.get(niche, niche)}")
        print(f"  {'─' * 40}")
        print(f"  Followers: {schedule['followers']:,}  |  Engagement: {schedule['engagement_rate']:.1f}%")
        print(f"  Recommended: {schedule['viral_shorts']} videos/day + {schedule['engagement_posts']} engagement posts/day")

        mix = schedule["content_mix"]
        print(f"  Content mix: Video {mix['video']:.0%} | Image {mix['image_post']:.0%} | Poll {mix['text_poll']:.0%}")

    print("\n" + "=" * 70 + "\n")


# ── CLI Entry Point ──────────────────────────────────────────

async def main():
    import sys

    if "--strategy" in sys.argv:
        # Generate weekly strategy for all niches
        for niche in ACTIVE_NICHES:
            strategy = await generate_weekly_strategy(niche)
            print(f"\n=== {strategy['page_name']} — Week of {strategy['week_of']} ===")
            for day in strategy["daily_plan"]:
                topics_str = ", ".join(day["topics"][:2]) if day["topics"] else "auto-generated"
                print(f"  {day['day']:<10} {day['videos']} videos, {day['engagement_posts']} eng posts | {topics_str}")
            print(f"  Total: {strategy['total_videos']} videos, {strategy['total_engagement']} engagement posts")
    else:
        # Show optimization report
        print_optimization_report()

        # Show AI recommendations for each niche
        for niche in ACTIVE_NICHES:
            analysis = await analyze_content_performance(niche)
            if analysis["recommendations"]:
                print(f"\n  {NICHE_PAGE_NAMES.get(niche, niche)} Recommendations:")
                for rec in analysis["recommendations"]:
                    print(f"    - {rec}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
