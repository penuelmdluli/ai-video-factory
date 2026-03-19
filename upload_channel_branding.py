"""Upload banners to all 6 YouTube channels via API.
Note: Profile pictures cannot be set via YouTube API — must be done in YouTube Studio.
"""
import sys
import io
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT_DIR = Path(__file__).parent
TOKENS_DIR = ROOT_DIR / "tokens"
ASSETS_DIR = ROOT_DIR / "assets" / "youtube_branding"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

NICHE_CHANNELS = {
    "ai_trading": ("Beast Mode Academy", "UC4Y4udaLeLc6E4BhoepK5XA"),
    "ai_money": ("Smart Money AI", "UCOfKMxPVvraa6q1XEolvedg"),
    "tech_news": ("Tech Pulse Africa", "UCN56RIHQ5UNCI-o5OtHNAYw"),
    "motivation": ("Elevate You", "UCb6vhwP8oKjcqUBri0Zd_Ew"),
    "health_wellness": ("Herbal Organic Life", "UCs3Y2sZ0ImXQ9QEwR5gFHfw"),
    "blissful_moments": ("Blissful Moments", "UCPNgMBuOOUQ5-lvdm5miruQ"),
}


def get_youtube_service(niche: str):
    token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_banner(niche: str):
    channel_name, channel_id = NICHE_CHANNELS[niche]
    banner_path = ASSETS_DIR / f"banner_{niche}.png"

    if not banner_path.exists():
        print(f"  [SKIP] No banner at {banner_path}")
        return False

    print(f"\n--- {channel_name} ({niche}) ---")
    youtube = get_youtube_service(niche)

    try:
        # Step 1: Upload banner image to YouTube's CDN
        media = MediaFileUpload(str(banner_path), mimetype="image/png")
        banner_resp = youtube.channelBanners().insert(
            media_body=media,
        ).execute()

        banner_url = banner_resp.get("url", "")
        if not banner_url:
            print(f"  [WARN] Banner upload returned no URL")
            return False

        print(f"  [OK] Banner uploaded to CDN: {banner_url[:80]}...")

        # Step 2: Get current channel branding settings
        channel_resp = youtube.channels().list(
            part="brandingSettings",
            mine=True,
        ).execute()

        if not channel_resp.get("items"):
            print(f"  [ERROR] Could not retrieve channel")
            return False

        channel = channel_resp["items"][0]
        branding = channel.get("brandingSettings", {})

        # Update banner URL
        if "image" not in branding:
            branding["image"] = {}
        branding["image"]["bannerExternalUrl"] = banner_url

        # Step 3: Set the banner on the channel
        youtube.channels().update(
            part="brandingSettings",
            body={
                "id": channel["id"],
                "brandingSettings": branding,
            }
        ).execute()

        print(f"  [OK] Banner set on channel!")
        return True

    except Exception as e:
        print(f"  [ERROR] Banner upload failed: {e}")
        return False


if __name__ == "__main__":
    niche_arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    success = 0
    total = 0

    if niche_arg == "all":
        for niche in NICHE_CHANNELS:
            total += 1
            if upload_banner(niche):
                success += 1
    else:
        total = 1
        if upload_banner(niche_arg):
            success += 1

    print(f"\n{'='*50}")
    print(f"Banners: {success}/{total} uploaded successfully")
    print(f"Note: Profile pictures must be set manually in YouTube Studio")
    print(f"{'='*50}")
