"""
Engagement Booster — Post-upload engagement strategies for all platforms.

Features:
1. First-comment posting (seeds engagement, adds hashtags, boosts algorithm)
2. Pinned comment strategy (CTA + additional hashtags)
3. Platform-specific engagement optimization
4. Comment reply templates (for future automation)

First-comment strategy is used by every major creator to:
- Add extra hashtags without cluttering the caption
- Seed the comment section (posts with comments get more distribution)
- Include a strong CTA to drive engagement
"""
import os
import random
import asyncio
import requests

from config import NICHES


# ── First Comment Templates per Niche ────────────────────
FIRST_COMMENT_TEMPLATES = {
    "ai_trading": [
        "🔥 What trading pair should AI analyze next? Drop it below! 👇\n\n🤖 Try TradeRadar AI for FREE stock analysis → gettraderadar.com",
        "💰 Are you using AI to trade? I want to hear your results!\n\n📊 FREE AI analysis tool → gettraderadar.com",
        "📈 Save this video — these strategies are changing the game!\n\n⚡ Get AI-powered insights FREE → gettraderadar.com",
        "🤖 I've been using TradeRadar AI for stock analysis — it explains everything in plain English! Try it FREE → gettraderadar.com",
        "⚡ The data doesn't lie. Want AI to analyze any stock for you?\n\n👉 TradeRadar AI is FREE → gettraderadar.com",
    ],
    "ai_money": [
        "💡 What's your favorite AI tool for making money? Comment below!\n\n📊 For stock analysis try TradeRadar AI FREE → gettraderadar.com",
        "🚀 Who's trying this today? Drop a 🔥 if you're in!",
        "💰 I've been testing this for 30 days — ask me anything!\n\n🤖 Also check out TradeRadar AI for FREE market insights → gettraderadar.com",
        "📌 Save this for later — you'll want to come back to it!",
        "🧠 What other AI money methods should I cover next?",
    ],
    "tech_news": [
        "🤔 What do you think — is this the future or just hype?",
        "🔔 Turn on notifications — I post tech updates daily!",
        "💭 This changes everything. What's your take on this?",
        "🌐 Tag someone in tech who needs to see this!",
        "⚡ What tech topic should I cover next? Tell me below!",
    ],
    "motivation": [
        "💪 Type 'I'M READY' if this hit different!",
        "🔥 Save this for the days when you need that extra push!",
        "🏆 What's YOUR morning routine? Share below!",
        "⭐ Tag someone who needs this motivation right now!",
        "🧠 Which habit changed your life the most? Comment!",
    ],
    "health_wellness": [
        "🌿 Have you tried this? Share your experience below!",
        "💚 Save this for your wellness routine!",
        "🍃 What natural remedy works best for you? Comment!",
        "📌 Bookmark this — your future self will thank you!",
        "🧘 What health topic should I cover next? Let me know!",
    ],
    "blissful_moments": [
        "✨ What brings YOU peace? Share in the comments!",
        "🙏 Type 'GRATEFUL' if this made you smile!",
        "💫 Save this for a moment when you need calm!",
        "🌸 Tag someone who needs this positivity today!",
        "☀️ What's ONE thing you're thankful for right now?",
    ],
}


async def post_first_comment_facebook(
    post_id: str,
    niche: str,
    extra_hashtags: list[str] | None = None,
    page_id: str = "",
) -> dict:
    """
    Post a first comment on a Facebook video/reel to seed engagement.

    Args:
        post_id: The Facebook post/reel ID
        niche: Content niche for comment template selection
        extra_hashtags: Additional hashtags to include in the comment
        page_id: The Facebook Page ID (for scoped-ID comment format)

    Returns:
        dict with status and comment_id
    """
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
    if not page_token or not post_id:
        return {"status": "skipped", "reason": "No token or post_id"}

    # Build comment text
    templates = FIRST_COMMENT_TEMPLATES.get(niche, FIRST_COMMENT_TEMPLATES["motivation"])
    comment_text = random.choice(templates)

    if extra_hashtags:
        tags = " ".join(h if h.startswith("#") else f"#{h}" for h in extra_hashtags[:10])
        comment_text = f"{comment_text}\n\n{tags}"

    # Resolve page_id: prefer passed param, fallback to env var
    if not page_id:
        page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")

    try:
        # For Reels, the post_id from upload is a video_id. We need the
        # actual feed post ID to comment. Try multiple strategies:
        # 1. Look up the video's feed post via Graph API
        # 2. Try {page_id}_{video_id} scoped format
        # 3. Try raw post_id

        resp = None
        api_base = "https://graph.facebook.com/v21.0"  # Use v21.0 (v24.0 has comment bugs)

        # Strategy 0: Look up the video's associated feed post (most reliable for Reels)
        if page_id:
            try:
                lookup_resp = requests.get(
                    f"{api_base}/{post_id}",
                    params={
                        "fields": "id,post_id",
                        "access_token": page_token,
                    },
                    timeout=10,
                )
                if lookup_resp.status_code == 200:
                    lookup_data = lookup_resp.json()
                    feed_post_id = lookup_data.get("post_id") or lookup_data.get("id")
                    if feed_post_id and feed_post_id != post_id:
                        print(f"[Engagement] Found feed post ID: {feed_post_id}")
                        resp = requests.post(
                            f"{api_base}/{feed_post_id}/comments",
                            data={"message": comment_text, "access_token": page_token},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            comment_id = resp.json().get("id")
                            print(f"[Engagement] First comment posted on FB: {comment_id}")
                            return {"status": "posted", "comment_id": comment_id, "platform": "facebook"}
            except Exception:
                pass

        # Strategy 1: Try {page_id}_{post_id} scoped format (works for most Reels)
        if page_id and not post_id.startswith(page_id):
            scoped_id = f"{page_id}_{post_id}"
            print(f"[Engagement] Trying comment with scoped ID: {scoped_id}")
            resp = requests.post(
                f"{api_base}/{scoped_id}/comments",
                data={"message": comment_text, "access_token": page_token},
                timeout=15,
            )
            if resp.status_code == 200:
                comment_id = resp.json().get("id")
                print(f"[Engagement] First comment posted on FB: {comment_id}")
                return {"status": "posted", "comment_id": comment_id, "platform": "facebook"}
            else:
                print(f"[Engagement] Scoped ID failed ({resp.status_code}), trying raw ID...")

        # Strategy 2: Try raw post_id directly
        resp = requests.post(
            f"{api_base}/{post_id}/comments",
            data={"message": comment_text, "access_token": page_token},
            timeout=15,
        )
        if resp.status_code == 200:
            comment_id = resp.json().get("id")
            print(f"[Engagement] First comment posted on FB: {comment_id}")
            return {"status": "posted", "comment_id": comment_id, "platform": "facebook"}

        # Strategy 3: Query Page's recent videos to find the matching feed post
        if page_id:
            try:
                vids_resp = requests.get(
                    f"{api_base}/{page_id}/videos",
                    params={
                        "fields": "id,post_id",
                        "limit": 5,
                        "access_token": page_token,
                    },
                    timeout=10,
                )
                if vids_resp.status_code == 200:
                    for vid in vids_resp.json().get("data", []):
                        if vid.get("id") == post_id or post_id in str(vid.get("id", "")):
                            feed_id = vid.get("post_id") or f"{page_id}_{vid['id']}"
                            resp = requests.post(
                                f"{api_base}/{feed_id}/comments",
                                data={"message": comment_text, "access_token": page_token},
                                timeout=15,
                            )
                            if resp.status_code == 200:
                                comment_id = resp.json().get("id")
                                print(f"[Engagement] First comment posted on FB (via video lookup): {comment_id}")
                                return {"status": "posted", "comment_id": comment_id, "platform": "facebook"}
                            break
            except Exception:
                pass

        error_text = resp.text[:300] if resp else "no response"
        print(f"[Engagement] FB comment failed: {resp.status_code if resp else 'N/A'} {error_text}")
        return {"status": "failed", "error": error_text}

    except Exception as e:
        print(f"[Engagement] FB first comment failed: {e}")
        return {"status": "failed", "error": str(e)}


async def post_first_comment_youtube(
    video_id: str,
    niche: str,
    extra_hashtags: list[str] | None = None,
) -> dict:
    """
    Post a first comment on a YouTube video to seed engagement.

    Uses the YouTube Data API v3 commentThreads.insert endpoint.
    """
    try:
        from modules.uploader_youtube import _get_youtube_service

        youtube = _get_youtube_service()

        templates = FIRST_COMMENT_TEMPLATES.get(niche, FIRST_COMMENT_TEMPLATES["motivation"])
        comment_text = random.choice(templates)

        if extra_hashtags:
            tags = " ".join(h if h.startswith("#") else f"#{h}" for h in extra_hashtags[:8])
            comment_text = f"{comment_text}\n\n{tags}"

        body = {
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {
                        "textOriginal": comment_text,
                    }
                },
            }
        }

        response = youtube.commentThreads().insert(
            part="snippet",
            body=body,
        ).execute()

        comment_id = response.get("id")
        print(f"[Engagement] First comment posted on YT: {comment_id}")
        return {"status": "posted", "comment_id": comment_id, "platform": "youtube"}

    except Exception as e:
        print(f"[Engagement] YT first comment failed: {e}")
        return {"status": "failed", "error": str(e)}


async def post_first_comments(
    uploads: list[dict],
    niche: str,
    extra_hashtags: list[str] | None = None,
) -> list[dict]:
    """
    Post first comments on all successfully uploaded platforms.

    Args:
        uploads: List of upload result dicts from main pipeline
        extra_hashtags: Hashtags from hashtag_optimizer for the comment

    Returns:
        List of comment result dicts
    """
    results = []

    for upload in uploads:
        if upload.get("status") != "uploaded":
            continue

        platform = upload.get("platform")

        try:
            if platform == "facebook" and upload.get("post_id"):
                # Longer delay for Reels — FB needs time to process
                wait_time = 20 if upload.get("type") == "reel" else 10
                print(f"[Engagement] Waiting {wait_time}s for FB to process {upload.get('type', 'post')}...")
                await asyncio.sleep(wait_time)
                result = await post_first_comment_facebook(
                    post_id=upload["post_id"],
                    niche=niche,
                    extra_hashtags=extra_hashtags,
                    page_id=upload.get("page_id", ""),
                )
                # If first attempt failed for Reels, retry after more delay
                if result.get("status") == "failed" and upload.get("type") == "reel":
                    print(f"[Engagement] Comment failed, retrying in 30s (Reel processing delay)...")
                    await asyncio.sleep(30)
                    result = await post_first_comment_facebook(
                        post_id=upload["post_id"],
                        niche=niche,
                        extra_hashtags=extra_hashtags,
                        page_id=upload.get("page_id", ""),
                    )
                results.append(result)

            elif platform == "youtube" and upload.get("video_id"):
                await asyncio.sleep(5)
                result = await post_first_comment_youtube(
                    video_id=upload["video_id"],
                    niche=niche,
                    extra_hashtags=extra_hashtags,
                )
                results.append(result)

        except Exception as e:
            print(f"[Engagement] First comment failed for {platform}: {e}")
            results.append({"status": "failed", "platform": platform, "error": str(e)})

    return results


# ── Engagement Score Calculator ─────────────────────────
def calculate_engagement_rate(metrics: dict) -> float:
    """
    Calculate engagement rate from platform metrics.

    Weighted formula:
    - Likes: 1x
    - Comments: 3x (strongest algorithm signal)
    - Shares: 5x (most valuable for reach)
    - Saves: 4x (strong intent signal)
    - Watch time: 2x bonus per minute
    """
    likes = metrics.get("likes", 0)
    comments = metrics.get("comments", 0)
    shares = metrics.get("shares", 0)
    saves = metrics.get("saves", 0)
    views = max(metrics.get("views", 1), 1)  # Avoid division by zero
    avg_watch_time = metrics.get("avg_watch_time", 0)

    weighted_engagement = (
        likes * 1
        + comments * 3
        + shares * 5
        + saves * 4
    )

    # Watch time bonus (per minute)
    watch_bonus = avg_watch_time * 2 if avg_watch_time > 0 else 0

    # Engagement rate as percentage
    rate = ((weighted_engagement + watch_bonus) / views) * 100

    return round(rate, 2)
