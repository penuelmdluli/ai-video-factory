"""
Performance Tracker — Multi-platform engagement monitoring and feedback loop.

Tracks: views, likes, comments, shares, watch time, saves across:
- Facebook (Graph API insights)
- YouTube (YouTube Analytics API)
- Instagram (Graph API insights)

Feeds insights back into:
- Topic selection (best-performing keywords)
- Hashtag optimization (which tags drive engagement)
- A/B test scoring (which variants win)
- Posting time optimization (when does each niche peak)
"""
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

from config import OUTPUT_DIR, NICHES, TOKENS_DIR


PERF_FILE = OUTPUT_DIR / "performance_data.json"
GRAPH_API_BASE = "https://graph.facebook.com/v24.0"


def _load_perf_data() -> dict:
    """Load performance data from file."""
    if PERF_FILE.exists():
        with open(PERF_FILE, "r") as f:
            return json.load(f)
    return {"videos": [], "niche_scores": {}, "top_topics": {}, "posting_time_scores": {}}


def _save_perf_data(data: dict):
    """Save performance data to file."""
    PERF_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PERF_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Facebook Insights ────────────────────────────────────

async def fetch_facebook_insights(post_id: str, niche: str) -> dict | None:
    """
    Fetch engagement metrics for a Facebook video/reel post.

    Now includes watch time metrics (avg_watch_time, total_watch_time).
    """
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
    if not page_token or not post_id:
        return None

    try:
        # Request comprehensive video insights including watch time
        fields = (
            "insights.metric("
            "post_video_views,"
            "post_video_avg_time_watched,"
            "post_video_view_time,"
            "post_engaged_users,"
            "post_impressions"
            "),"
            "likes.summary(true),"
            "comments.summary(true),"
            "shares"
        )

        resp = requests.get(
            f"{GRAPH_API_BASE}/{post_id}",
            params={
                "fields": fields,
                "access_token": page_token,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            # Fallback to simpler fields
            resp = requests.get(
                f"{GRAPH_API_BASE}/{post_id}",
                params={
                    "fields": "likes.summary(true),comments.summary(true),shares",
                    "access_token": page_token,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return None

        data = resp.json()
        metrics = {
            "platform": "facebook",
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "avg_watch_time": 0,
            "total_watch_time": 0,
            "engaged_users": 0,
            "impressions": 0,
        }

        # Extract from insights
        insights = data.get("insights", {}).get("data", [])
        for insight in insights:
            name = insight.get("name", "")
            values = insight.get("values", [])
            value = values[0].get("value", 0) if values else 0

            if name == "post_video_views":
                metrics["views"] = value
            elif name == "post_video_avg_time_watched":
                metrics["avg_watch_time"] = value / 1000 if value > 100 else value  # ms -> seconds
            elif name == "post_video_view_time":
                metrics["total_watch_time"] = value
            elif name == "post_engaged_users":
                metrics["engaged_users"] = value
            elif name == "post_impressions":
                metrics["impressions"] = value

        # Extract likes, comments, shares
        metrics["likes"] = data.get("likes", {}).get("summary", {}).get("total_count", 0)
        metrics["comments"] = data.get("comments", {}).get("summary", {}).get("total_count", 0)
        metrics["shares"] = data.get("shares", {}).get("count", 0)

        # Calculate engagement score (weighted)
        metrics["engagement_score"] = (
            metrics["likes"] * 1
            + metrics["comments"] * 3
            + metrics["shares"] * 5
            + (metrics["avg_watch_time"] * 2)  # Watch time bonus
        )

        return metrics

    except Exception as e:
        print(f"[PerfTracker] Facebook insights failed for {post_id}: {e}")
        return None


# ── YouTube Analytics ────────────────────────────────────

async def fetch_youtube_insights(video_id: str) -> dict | None:
    """
    Fetch YouTube video analytics: views, likes, watch time, engagement.

    Uses YouTube Data API v3 (statistics) + YouTube Analytics API (watch time).
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        token_path = TOKENS_DIR / "youtube_token.json"
        if not token_path.exists():
            return None

        creds = Credentials.from_authorized_user_file(
            str(token_path),
            ["https://www.googleapis.com/auth/youtube.readonly",
             "https://www.googleapis.com/auth/youtube.upload"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        # Get video statistics
        resp = youtube.videos().list(
            part="statistics,contentDetails",
            id=video_id,
        ).execute()

        items = resp.get("items", [])
        if not items:
            return None

        stats = items[0].get("statistics", {})

        metrics = {
            "platform": "youtube",
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "shares": 0,  # YT doesn't expose shares via API
            "favorites": int(stats.get("favoriteCount", 0)),
            "avg_watch_time": 0,  # Would need YT Analytics API
        }

        # Try to get watch time from YouTube Analytics API
        try:
            yt_analytics = build("youtubeAnalytics", "v2", credentials=creds)
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            analytics_resp = yt_analytics.reports().query(
                ids="channel==MINE",
                startDate=week_ago,
                endDate=today,
                metrics="estimatedMinutesWatched,averageViewDuration",
                filters=f"video=={video_id}",
            ).execute()

            rows = analytics_resp.get("rows", [])
            if rows:
                metrics["total_watch_minutes"] = rows[0][0]
                metrics["avg_watch_time"] = rows[0][1]  # seconds
        except Exception:
            pass  # YT Analytics API may not be enabled

        metrics["engagement_score"] = (
            metrics["likes"] * 1
            + metrics["comments"] * 3
            + (metrics["avg_watch_time"] * 2)
        )

        return metrics

    except Exception as e:
        print(f"[PerfTracker] YouTube insights failed for {video_id}: {e}")
        return None


# ── Instagram Insights ───────────────────────────────────

async def fetch_instagram_insights(post_id: str) -> dict | None:
    """Fetch Instagram Reels insights: plays, likes, comments, shares, saves."""
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not access_token or not post_id:
        return None

    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/{post_id}/insights",
            params={
                "metric": "plays,likes,comments,shares,saved,reach",
                "access_token": access_token,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return None

        data = resp.json().get("data", [])
        metrics = {
            "platform": "instagram",
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "saves": 0,
            "reach": 0,
        }

        for metric in data:
            name = metric.get("name", "")
            values = metric.get("values", [])
            value = values[0].get("value", 0) if values else 0

            if name == "plays":
                metrics["views"] = value
            elif name == "likes":
                metrics["likes"] = value
            elif name == "comments":
                metrics["comments"] = value
            elif name == "shares":
                metrics["shares"] = value
            elif name == "saved":
                metrics["saves"] = value
            elif name == "reach":
                metrics["reach"] = value

        metrics["engagement_score"] = (
            metrics["likes"] * 1
            + metrics["comments"] * 3
            + metrics["shares"] * 5
            + metrics["saves"] * 4
        )

        return metrics

    except Exception as e:
        print(f"[PerfTracker] Instagram insights failed for {post_id}: {e}")
        return None


# ── Multi-Platform Recording ─────────────────────────────

def record_video_performance(
    niche: str,
    topic: str,
    title: str,
    post_id: str | None = None,
    platform: str = "facebook",
    video_id: str | None = None,
    hashtags: list[str] | None = None,
    ab_experiment_id: str | None = None,
    posted_at: str | None = None,
):
    """
    Record a video for multi-platform performance tracking.

    Now tracks: platform IDs, hashtags used, A/B experiment ID, posting time.
    """
    data = _load_perf_data()
    data["videos"].append({
        "niche": niche,
        "topic": topic,
        "title": title,
        "post_id": post_id,
        "video_id": video_id,
        "platform": platform,
        "hashtags": hashtags or [],
        "ab_experiment_id": ab_experiment_id,
        "created_at": posted_at or datetime.now().isoformat(),
        "posted_hour": datetime.now().hour,
        "posted_weekday": datetime.now().strftime("%A"),
        "metrics": None,
        "last_checked": None,
    })
    _save_perf_data(data)


async def update_all_metrics():
    """
    Update engagement metrics for all tracked videos across all platforms.

    Now fetches from Facebook, YouTube, AND Instagram.
    Extended to 30 days (was 14) for long-tail tracking.
    """
    data = _load_perf_data()
    updated = 0

    for video in data["videos"]:
        post_id = video.get("post_id")
        video_id = video.get("video_id")
        niche = video.get("niche")
        platform = video.get("platform", "facebook")

        if not niche:
            continue

        # Track for 30 days (was 14) to capture long-tail performance
        created = video.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created)
            if datetime.now() - created_dt > timedelta(days=30):
                continue
        except (ValueError, TypeError):
            continue

        metrics = None

        if platform == "facebook" and post_id:
            metrics = await fetch_facebook_insights(post_id, niche)
        elif platform == "youtube" and (video_id or post_id):
            metrics = await fetch_youtube_insights(video_id or post_id)
        elif platform == "instagram" and post_id:
            metrics = await fetch_instagram_insights(post_id)

        if metrics:
            video["metrics"] = metrics
            video["last_checked"] = datetime.now().isoformat()
            updated += 1

            # Update A/B test scoring
            if video.get("ab_experiment_id"):
                try:
                    from modules.ab_testing import update_experiment_score
                    update_experiment_score(
                        video["ab_experiment_id"],
                        metrics.get("engagement_score", 0),
                    )
                except Exception:
                    pass

            # Update hashtag performance
            if video.get("hashtags"):
                try:
                    from modules.hashtag_optimizer import record_hashtag_performance
                    record_hashtag_performance(
                        video["hashtags"],
                        niche,
                        metrics.get("engagement_score", 0),
                    )
                except Exception:
                    pass

    # Recalculate niche scores and posting time analysis
    _recalculate_niche_scores(data)
    _analyze_posting_times(data)

    _save_perf_data(data)
    if updated:
        print(f"[PerfTracker] Updated metrics for {updated} videos across all platforms")

    return data


def _recalculate_niche_scores(data: dict):
    """Recalculate average engagement scores per niche."""
    niche_totals = {}
    niche_counts = {}

    for video in data["videos"]:
        niche = video.get("niche")
        metrics = video.get("metrics")
        if not metrics or not niche:
            continue

        score = metrics.get("engagement_score", 0)
        niche_totals[niche] = niche_totals.get(niche, 0) + score
        niche_counts[niche] = niche_counts.get(niche, 0) + 1

    data["niche_scores"] = {
        niche: round(niche_totals[niche] / niche_counts[niche], 1)
        for niche in niche_totals
        if niche_counts.get(niche, 0) > 0
    }

    # Top-performing topics per niche
    top_topics = {}
    for niche in NICHES:
        niche_videos = [
            v for v in data["videos"]
            if v.get("niche") == niche and v.get("metrics")
        ]
        niche_videos.sort(
            key=lambda v: v["metrics"].get("engagement_score", 0),
            reverse=True,
        )
        top_topics[niche] = [
            {"topic": v["topic"], "score": v["metrics"]["engagement_score"]}
            for v in niche_videos[:5]
        ]
    data["top_topics"] = top_topics


def _analyze_posting_times(data: dict):
    """
    Analyze which posting hours/days get the best engagement per niche.

    Builds a map: {niche: {hour: avg_score, weekday: avg_score}}
    """
    posting_scores = {}

    for video in data["videos"]:
        niche = video.get("niche")
        metrics = video.get("metrics")
        hour = video.get("posted_hour")
        weekday = video.get("posted_weekday")

        if not metrics or not niche or hour is None:
            continue

        score = metrics.get("engagement_score", 0)

        if niche not in posting_scores:
            posting_scores[niche] = {"hours": {}, "weekdays": {}}

        # Aggregate by hour
        h_key = str(hour)
        if h_key not in posting_scores[niche]["hours"]:
            posting_scores[niche]["hours"][h_key] = {"total": 0, "count": 0}
        posting_scores[niche]["hours"][h_key]["total"] += score
        posting_scores[niche]["hours"][h_key]["count"] += 1

        # Aggregate by weekday
        if weekday:
            if weekday not in posting_scores[niche]["weekdays"]:
                posting_scores[niche]["weekdays"][weekday] = {"total": 0, "count": 0}
            posting_scores[niche]["weekdays"][weekday]["total"] += score
            posting_scores[niche]["weekdays"][weekday]["count"] += 1

    # Calculate averages
    for niche in posting_scores:
        for h, d in posting_scores[niche]["hours"].items():
            posting_scores[niche]["hours"][h]["avg"] = round(d["total"] / max(d["count"], 1), 1)
        for w, d in posting_scores[niche]["weekdays"].items():
            posting_scores[niche]["weekdays"][w]["avg"] = round(d["total"] / max(d["count"], 1), 1)

    data["posting_time_scores"] = posting_scores


def get_best_posting_hours(niche: str) -> list[int]:
    """Get the top 3 posting hours for a niche based on performance data."""
    data = _load_perf_data()
    hours = data.get("posting_time_scores", {}).get(niche, {}).get("hours", {})

    if not hours:
        return [9, 14, 19]  # Defaults

    ranked = sorted(hours.items(), key=lambda x: x[1].get("avg", 0), reverse=True)
    return [int(h) for h, _ in ranked[:3]]


def get_performance_summary() -> dict:
    """Get a performance summary for all niches."""
    data = _load_perf_data()

    # Count by platform
    platform_counts = {}
    for v in data["videos"]:
        p = v.get("platform", "unknown")
        platform_counts[p] = platform_counts.get(p, 0) + 1

    return {
        "total_tracked": len(data["videos"]),
        "by_platform": platform_counts,
        "niche_scores": data.get("niche_scores", {}),
        "top_topics": data.get("top_topics", {}),
        "posting_time_scores": data.get("posting_time_scores", {}),
    }


def get_best_performing_keywords(niche: str, top_n: int = 5) -> list[str]:
    """
    Extract keywords from top-performing topics for a niche.

    Used by the topic generator to create similar high-performing content.
    """
    data = _load_perf_data()
    top = data.get("top_topics", {}).get(niche, [])

    keywords = []
    for entry in top[:top_n]:
        topic_words = entry["topic"].lower().split()
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                      "to", "for", "of", "with", "and", "or", "but", "this", "that",
                      "how", "why", "what", "when", "just", "your", "you"}
        meaningful = [w for w in topic_words if w not in stop_words and len(w) > 2]
        keywords.extend(meaningful[:3])

    return list(dict.fromkeys(keywords))[:top_n]


# CLI test
if __name__ == "__main__":
    import asyncio

    async def test():
        print("[PerfTracker] Multi-platform performance tracker loaded")
        summary = get_performance_summary()
        print(f"[PerfTracker] Tracked videos: {summary['total_tracked']}")
        print(f"[PerfTracker] By platform: {summary['by_platform']}")
        print(f"[PerfTracker] Niche scores: {summary['niche_scores']}")

        for niche in NICHES:
            hours = get_best_posting_hours(niche)
            print(f"[PerfTracker] Best hours for {niche}: {hours}")

    asyncio.run(test())
