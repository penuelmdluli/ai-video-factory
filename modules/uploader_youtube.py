"""
YouTube Uploader — Uploads videos via YouTube Data API v3.

Handles:
- OAuth2 authentication with token refresh
- Video upload with metadata (title, description, tags, thumbnail)
- SRT caption upload for SEO
- Long-form and Shorts detection
- Per-niche channel support (separate tokens)
- AI content disclosure
"""
import json
import os
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from config import (
    YOUTUBE_SCOPES,
    YOUTUBE_API_VERSION,
    NICHE_YOUTUBE_CATEGORY,
    TOKENS_DIR,
)
try:
    from config import SET_CUSTOM_THUMBNAIL
except Exception:
    SET_CUSTOM_THUMBNAIL = False

TOKEN_PATH = TOKENS_DIR / "youtube_token.json"
CLIENT_SECRET_PATH = TOKENS_DIR / "youtube_client_secret.json"

# Secondary channel: Deep Chill (@DeepFocusBeats-w2f) — all niches cross-post here
DEEP_CHILL_TOKEN_PATH = TOKENS_DIR / "youtube_token_deep_chill.json"


def _get_token_path(niche: str = "") -> Path:
    """Get YouTube token path, preferring niche-specific tokens for separate channels."""
    if niche:
        niche_token = TOKENS_DIR / f"youtube_token_{niche}.json"
        if niche_token.exists():
            return niche_token
    return TOKEN_PATH


def _get_credentials(niche: str = "") -> Credentials:
    """Get valid YouTube API credentials, refreshing if needed."""
    creds = None
    token_path = _get_token_path(niche)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    if not creds or not creds.valid:
        if not CLIENT_SECRET_PATH.exists():
            raise FileNotFoundError(
                f"YouTube client secret not found at {CLIENT_SECRET_PATH}. "
                "Download it from Google Cloud Console > APIs > Credentials > OAuth 2.0."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), YOUTUBE_SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def _get_youtube_service(niche: str = ""):
    """Build YouTube API service client."""
    creds = _get_credentials(niche)
    return build("youtube", YOUTUBE_API_VERSION, credentials=creds)


async def upload_srt_captions(
    youtube,
    video_id: str,
    srt_path: str,
    language: str = "en",
) -> bool:
    """
    Upload SRT captions to a YouTube video for SEO.

    YouTube indexes caption text for search — uploading accurate SRT
    significantly improves discoverability vs auto-generated captions.

    Args:
        youtube: Authenticated YouTube API service
        video_id: YouTube video ID
        srt_path: Path to the SRT/VTT subtitle file
        language: Caption language code

    Returns:
        True if upload succeeded
    """
    srt_file = Path(srt_path)
    if not srt_file.exists():
        return False

    try:
        # Determine mime type
        mime_type = "application/x-subrip"
        if srt_path.endswith(".vtt"):
            mime_type = "text/vtt"

        body = {
            "snippet": {
                "videoId": video_id,
                "language": language,
                "name": "English",
                "isDraft": False,
            },
        }

        media = MediaFileUpload(
            srt_path,
            mimetype=mime_type,
            resumable=True,
        )

        youtube.captions().insert(
            part="snippet",
            body=body,
            media_body=media,
        ).execute()

        print(f"[YouTube] SRT captions uploaded for {video_id}")
        return True

    except Exception as e:
        print(f"[YouTube] Caption upload failed: {e}")
        return False


async def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    niche: str = "ai_trading",
    thumbnail_path: str | None = None,
    is_short: bool = False,
    privacy: str = "public",
    srt_path: str | None = None,
    made_for_kids: bool | None = None,
) -> dict:
    """
    Upload a video to YouTube.

    Args:
        video_path: Path to the video file
        title: Video title (max 100 chars)
        description: Video description
        tags: List of tags
        niche: Niche key for category selection and channel routing
        thumbnail_path: Path to custom thumbnail
        is_short: Whether this is a YouTube Short
        privacy: "public", "private", or "unlisted"
        srt_path: Path to SRT subtitle file for caption upload

    Returns:
        dict with video_id, url, status
    """
    try:
        youtube = _get_youtube_service(niche)

        # Add #Shorts tag if it's a short
        if is_short and "#Shorts" not in title:
            title = title[:90] + " #Shorts" if len(title) > 90 else title + " #Shorts"

        # Truncate title to YouTube limit
        title = title[:100]

        # Build SEO-optimized description
        # Target keyword in first line, then content, then links
        seo_description = _build_seo_description(description, title, niche, tags)

        category = NICHE_YOUTUBE_CATEGORY.get(niche, "28")

        # COPPA: kids-content channels MUST self-declare "made for kids".
        # Auto-detect for kids niches unless the caller overrides explicitly.
        KIDS_NICHES = {"kids_songs"}
        if made_for_kids is None:
            made_for_kids = niche in KIDS_NICHES

        body = {
            "snippet": {
                "title": title,
                "description": seo_description,
                "tags": tags[:30],  # YouTube allows max ~500 chars of tags
                "categoryId": category,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": bool(made_for_kids),
            },
        }

        media = MediaFileUpload(
            video_path,
            chunksize=256 * 1024,  # 256KB chunks
            resumable=True,
            mimetype="video/mp4",
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YouTube] Upload progress: {int(status.progress() * 100)}%")

        video_id = response["id"]
        video_url = f"https://youtube.com/watch?v={video_id}"

        # Set custom thumbnail
        if SET_CUSTOM_THUMBNAIL and thumbnail_path and Path(thumbnail_path).exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
                ).execute()
                print(f"[YouTube] Thumbnail set for {video_id}")
            except Exception as e:
                print(f"[YouTube] Thumbnail upload failed: {e}")

        # Upload SRT captions for SEO boost. Skippable: caption inserts cost
        # ~400 quota units each and our shorts carry burned-in subtitles —
        # on tight-quota days this burned the daily budget for nothing.
        if srt_path and os.getenv("SKIP_YT_CAPTIONS", "").lower() not in ("true", "1"):
            await upload_srt_captions(youtube, video_id, srt_path, language="en")

            # Multi-language caption tracks → international reach
            try:
                from config import SUBTITLE_TRANSLATE, SUBTITLE_LANGUAGES
                if SUBTITLE_TRANSLATE:
                    from modules.caption_generator import translate_srt
                    for code, name in SUBTITLE_LANGUAGES.items():
                        tpath = translate_srt(srt_path, code, name)
                        if tpath:
                            await upload_srt_captions(youtube, video_id, tpath, language=code)
            except Exception as e:
                print(f"[YouTube] Multi-language captions skipped: {e}")

        print(f"[YouTube] Uploaded: {video_url}")

        return {
            "platform": "youtube",
            "video_id": video_id,
            "url": video_url,
            "title": title,
            "status": "uploaded",
            "is_short": is_short,
        }

    except Exception as e:
        print(f"[YouTube] Upload failed: {e}")
        return {
            "platform": "youtube",
            "status": "failed",
            "error": str(e),
        }


def _build_seo_description(
    description: str,
    title: str,
    niche: str,
    tags: list[str],
) -> str:
    """
    Build an SEO-optimized YouTube description.

    Structure:
    1. Target keyword in first line (YouTube uses first 2-3 lines for search)
    2. Main description body
    3. Timestamp chapters (if available)
    4. Related hashtags
    5. Affiliate links
    """
    from config import NICHES, AFFILIATE_LINKS

    niche_config = NICHES.get(niche, {})
    lines = []

    # First line: keyword-rich summary (critical for YT SEO)
    # YouTube indexes the first 200 chars heavily
    lines.append(description.split("\n")[0] if description else title)
    lines.append("")

    # Full description
    lines.append(description)
    lines.append("")

    # Hashtags (YouTube shows top 3 above title)
    if tags:
        top_tags = [t if t.startswith("#") else f"#{t}" for t in tags[:5]]
        lines.append(" ".join(top_tags))
        lines.append("")

    # Pure content — no affiliate links

    return "\n".join(lines)[:5000]  # YT description limit


async def upload_to_deep_chill(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    niche: str = "ai_trading",
    thumbnail_path: str | None = None,
    is_short: bool = False,
    srt_path: str | None = None,
) -> dict:
    """
    DISABLED. Deep Chill (@DeepFocusBeats-w2f) is now the dedicated AlphaZone
    Sounds MUSIC channel — only make_music.py posts there. War/news/other niches
    must NOT cross-post here (mixed content confuses the algorithm + brand).
    """
    return {"platform": "youtube_deep_chill", "status": "disabled",
            "error": "deep_chill is now the dedicated music channel — no cross-posting"}

    if not DEEP_CHILL_TOKEN_PATH.exists():
        print("[YouTube/DeepChill] Token not found — skipping (run: python auth_one_channel.py deep_chill)")
        return {"platform": "youtube_deep_chill", "status": "skipped", "error": "no token"}

    try:
        creds = Credentials.from_authorized_user_file(str(DEEP_CHILL_TOKEN_PATH), YOUTUBE_SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(DEEP_CHILL_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

        if not creds or not creds.valid:
            print("[YouTube/DeepChill] Token expired and cannot refresh — skipping")
            return {"platform": "youtube_deep_chill", "status": "skipped", "error": "token expired"}

        youtube = build("youtube", YOUTUBE_API_VERSION, credentials=creds)

        # Prefix title for Deep Chill branding
        dc_title = title[:100]

        if is_short and "#Shorts" not in dc_title:
            dc_title = dc_title[:90] + " #Shorts" if len(dc_title) > 90 else dc_title + " #Shorts"

        dc_title = dc_title[:100]

        seo_description = _build_seo_description(description, dc_title, niche, tags)
        category = NICHE_YOUTUBE_CATEGORY.get(niche, "28")

        body = {
            "snippet": {
                "title": dc_title,
                "description": seo_description,
                "tags": tags[:30],
                "categoryId": category,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path,
            chunksize=256 * 1024,
            resumable=True,
            mimetype="video/mp4",
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YouTube/DeepChill] Upload progress: {int(status.progress() * 100)}%")

        video_id = response["id"]
        video_url = f"https://youtube.com/watch?v={video_id}"

        if SET_CUSTOM_THUMBNAIL and thumbnail_path and Path(thumbnail_path).exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
                ).execute()
            except Exception:
                pass

        if srt_path:
            await upload_srt_captions(youtube, video_id, srt_path)

        print(f"[YouTube/DeepChill] Uploaded: {video_url}")

        return {
            "platform": "youtube_deep_chill",
            "video_id": video_id,
            "url": video_url,
            "title": dc_title,
            "status": "uploaded",
            "is_short": is_short,
        }

    except Exception as e:
        print(f"[YouTube/DeepChill] Upload failed: {e}")
        return {"platform": "youtube_deep_chill", "status": "failed", "error": str(e)}


def check_youtube_quota() -> dict:
    """Check remaining YouTube API quota (approximate)."""
    try:
        youtube = _get_youtube_service()
        youtube.channels().list(part="id", mine=True).execute()
        return {"status": "ok", "message": "YouTube API accessible"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
