"""
Genesis Content Engine — Analytics Puller

Fetches performance data from Facebook and YouTube for posted videos.
Updates post records with views, reactions, shares, comments.
"""
import asyncio
import aiohttp
import json
import time
from pathlib import Path

from genesis.genesis_config import BRANDS
from genesis.db import get_posts_needing_analytics, update_post, log_pipeline

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


GRAPH_API_VERSION = "v19.0"


async def pull_facebook_analytics(post: dict) -> dict | None:
    """Pull analytics for a Facebook post."""
    brand = post["brand"]
    fb_post_id = post["platform_post_id"]
    config = BRANDS.get(brand, {})
    access_token = config.get("facebook", {}).get("access_token", "")

    if not access_token or not fb_post_id:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            # Get video insights
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{fb_post_id}"
            params = {
                "fields": "views,likes.summary(true),comments.summary(true),shares",
                "access_token": access_token,
            }

            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

            views = data.get("views", 0)
            reactions = data.get("likes", {}).get("summary", {}).get("total_count", 0)
            comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
            shares = data.get("shares", {}).get("count", 0)

            # Performance score: weighted combo
            score = views * 0.1 + reactions * 2 + comments * 5 + shares * 10

            return {
                "views": views,
                "reactions": reactions,
                "comments": comments,
                "shares": shares,
                "performance_score": round(score, 2),
            }
    except Exception as e:
        print(f"  ⚠️  Facebook analytics error for post {post['id']}: {e}")
        return None


def pull_youtube_analytics(post: dict) -> dict | None:
    """Pull analytics for a YouTube video."""
    brand = post["brand"]
    yt_video_id = post["platform_post_id"]
    config = BRANDS.get(brand, {})
    token_file = config.get("youtube", {}).get("token_file")

    if not token_file or not Path(token_file).exists() or not yt_video_id:
        return None

    try:
        creds = Credentials.from_authorized_user_file(
            str(token_file),
            ["https://www.googleapis.com/auth/youtube.force-ssl"]
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        response = youtube.videos().list(
            part="statistics",
            id=yt_video_id,
        ).execute()

        items = response.get("items", [])
        if not items:
            return None

        stats = items[0].get("statistics", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))

        score = views * 0.1 + likes * 2 + comments * 5

        return {
            "views": views,
            "reactions": likes,
            "comments": comments,
            "shares": 0,  # YouTube doesn't expose share count
            "performance_score": round(score, 2),
        }
    except Exception as e:
        print(f"  ⚠️  YouTube analytics error for post {post['id']}: {e}")
        return None


async def pull_all_analytics():
    """Pull analytics for all posted content."""
    print("\n📊 PHASE 8: Pulling Analytics...")

    posts = get_posts_needing_analytics()

    if not posts:
        print("  ℹ️  No posts to analyze")
        return

    updated = 0

    for post in posts:
        metrics = None

        if post["platform"] == "facebook":
            metrics = await pull_facebook_analytics(post)
        elif post["platform"] == "youtube":
            metrics = pull_youtube_analytics(post)

        if metrics:
            update_post(post["id"], **metrics)
            updated += 1
            brand_name = BRANDS.get(post["brand"], {}).get("name", post["brand"])
            print(f"  📈 {brand_name} ({post['platform']}): {metrics['views']} views, score: {metrics['performance_score']}")

    log_pipeline("analytics", "all", "success", f"Updated {updated}/{len(posts)} posts")
    print(f"\n  Updated {updated} / {len(posts)} posts")


if __name__ == "__main__":
    asyncio.run(pull_all_analytics())
