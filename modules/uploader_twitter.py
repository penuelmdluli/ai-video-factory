"""
Twitter/X Uploader — Posts videos via Tweepy (Twitter API v2).

Requirements:
- Twitter Developer account with Elevated access
- API keys and tokens configured in .env
"""
import tweepy

from config import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
)


def _get_twitter_client() -> tuple:
    """Get authenticated Tweepy client and API (v1.1 for media upload)."""
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)

    # v1.1 API needed for media upload
    api_v1 = tweepy.API(auth)

    # v2 client for posting tweets
    client_v2 = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
    )

    return client_v2, api_v1


async def upload_to_twitter(
    video_path: str,
    text: str,
    hashtags: list[str] | None = None,
) -> dict:
    """
    Upload a video to Twitter/X.

    Args:
        video_path: Path to video file (max 512MB, max 2:20 for video)
        text: Tweet text
        hashtags: List of hashtags to append

    Returns:
        dict with platform, status, tweet_id, url
    """
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return {
            "platform": "twitter",
            "status": "skipped",
            "error": "Twitter credentials not configured",
        }

    try:
        client_v2, api_v1 = _get_twitter_client()

        # Build tweet text with hashtags
        full_text = text
        if hashtags:
            tags = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags[:5])
            full_text = f"{text}\n\n{tags}"
        full_text = full_text[:280]  # Twitter character limit

        # Upload media via v1.1 API (required for video)
        print(f"[Twitter] Uploading video...")
        media = api_v1.media_upload(
            filename=video_path,
            media_category="tweet_video",
        )

        # Post tweet with media via v2 API
        response = client_v2.create_tweet(
            text=full_text,
            media_ids=[media.media_id],
        )

        tweet_id = response.data["id"]
        tweet_url = f"https://twitter.com/i/status/{tweet_id}"

        print(f"[Twitter] Posted: {tweet_url}")

        return {
            "platform": "twitter",
            "status": "uploaded",
            "tweet_id": tweet_id,
            "url": tweet_url,
        }

    except Exception as e:
        print(f"[Twitter] Upload failed: {e}")
        return {
            "platform": "twitter",
            "status": "failed",
            "error": str(e),
        }
