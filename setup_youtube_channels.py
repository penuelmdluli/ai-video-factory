"""
YouTube Channel Setup Utility — Updates channel descriptions & branding via API.

Usage:
    python setup_youtube_channels.py              # Set up all 6 niche channels
    python setup_youtube_channels.py --auth-only  # Just authenticate and save tokens
    python setup_youtube_channels.py --niche ai_trading  # Set up one specific niche

Requires:
    - tokens/youtube_client_secret.json (OAuth 2.0 Desktop credentials)
    - Google account with access to all brand channels
"""
import argparse
import json
import sys
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# ── Paths ─────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
TOKENS_DIR = ROOT_DIR / "tokens"
CLIENT_SECRET_PATH = TOKENS_DIR / "youtube_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",  # Full access for channel updates
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# ── Channel IDs (from channel creation) ───────────────────────
NICHE_CHANNELS = {
    "ai_trading": {
        "channel_id": "UC4Y4udaLeLc6E4BhoepK5XA",
        "name": "Beast Mode Academy",
        "handle": "@BeastModeAcademyZA",
        "keywords": "AI trading,trading bots,cryptocurrency,bitcoin,forex,stock market,technical analysis,passive income,algorithmic trading,automated trading,crypto trading,AI investing",
        "description": (
            "Master AI-Powered Trading Strategies That Actually Work\n"
            "\n"
            "Beast Mode Academy breaks down complex trading concepts into "
            "actionable strategies using artificial intelligence and automation. "
            "From crypto to forex to stocks \u2014 we show you how smart traders "
            "use AI bots, technical analysis, and data-driven systems to build wealth.\n"
            "\n"
            "New videos every week:\n"
            "\u2022 AI Trading Bots and Automation\n"
            "\u2022 Cryptocurrency and Bitcoin Analysis\n"
            "\u2022 Stock Market Strategies for Beginners\n"
            "\u2022 Technical Analysis Made Simple\n"
            "\u2022 Passive Income Through Smart Investing\n"
            "\n"
            "Whether you're just starting or levelling up your portfolio, "
            "Beast Mode Academy gives you the edge. No hype, just results.\n"
            "\n"
            "Subscribe and turn on notifications so you never miss a profitable insight."
        ),
    },
    "ai_money": {
        "channel_id": "UCOfKMxPVvraa6q1XEolvedg",
        "name": "Smart Money AI",
        "handle": "@SmartMoneyAIZA",
        "keywords": "AI money making,make money with AI,AI side hustle,ChatGPT,AI tools,passive income AI,online income,AI business,AI automation,ElevenLabs,Midjourney",
        "description": (
            "Turn AI Tools Into Real Income Streams\n"
            "\n"
            "Smart Money AI shows you exactly how to use artificial intelligence "
            "to build income streams, automate your business, and work smarter. "
            "From ChatGPT to AI automation \u2014 we break down the tools, strategies, "
            "and step-by-step methods that actually make money.\n"
            "\n"
            "What you'll learn:\n"
            "\u2022 AI Side Hustles That Pay\n"
            "\u2022 ChatGPT and AI Tool Tutorials\n"
            "\u2022 Automating Your Online Business\n"
            "\u2022 Passive Income with AI\n"
            "\u2022 AI Freelancing and Content Creation\n"
            "\n"
            "No fluff, no fake promises \u2014 just proven AI strategies "
            "to build real wealth in the age of automation.\n"
            "\n"
            "Subscribe for weekly AI money-making tutorials."
        ),
    },
    "tech_news": {
        "channel_id": "UCN56RIHQ5UNCI-o5OtHNAYw",
        "name": "Tech Pulse Africa",
        "handle": "@TechPulseAfricaZA",
        "keywords": "tech news,AI news,technology,artificial intelligence,tech Africa,gadgets,startups,innovation,science,future tech,robotics,machine learning",
        "description": (
            "Africa's Pulse on Technology and AI Innovation\n"
            "\n"
            "Tech Pulse Africa delivers the latest technology news, "
            "AI breakthroughs, and innovation stories that matter. "
            "From cutting-edge gadgets to groundbreaking AI research \u2014 "
            "we keep you informed about the tech shaping our future.\n"
            "\n"
            "We cover:\n"
            "\u2022 AI and Machine Learning Breakthroughs\n"
            "\u2022 Tech Industry News and Analysis\n"
            "\u2022 Gadget Reviews and First Looks\n"
            "\u2022 African Tech Startups and Innovation\n"
            "\u2022 Science and Future Technology\n"
            "\n"
            "Stay ahead of the curve with daily tech updates "
            "delivered in plain English.\n"
            "\n"
            "Subscribe and hit the bell for your daily tech briefing."
        ),
    },
    "motivation": {
        "channel_id": "UCb6vhwP8oKjcqUBri0Zd_Ew",
        "name": "Elevate You",
        "handle": "@ElevateYouZA",
        "keywords": "motivation,inspirational,self improvement,mindset,success,personal growth,motivational speech,discipline,hustle,entrepreneur,confidence,goals",
        "description": (
            "Elevate Your Mindset. Elevate Your Life.\n"
            "\n"
            "Elevate You delivers powerful motivational content designed "
            "to ignite your drive, sharpen your mindset, and push you "
            "toward your greatest potential. Every video is crafted to "
            "help you build discipline, crush your goals, and become "
            "the best version of yourself.\n"
            "\n"
            "Content that transforms:\n"
            "\u2022 Motivational Speeches and Compilations\n"
            "\u2022 Success Mindset and Discipline\n"
            "\u2022 Entrepreneur and Hustle Motivation\n"
            "\u2022 Confidence and Self-Improvement\n"
            "\u2022 Goal Setting and Achievement\n"
            "\n"
            "Your next level starts with the right mindset. "
            "Let's get there together.\n"
            "\n"
            "Subscribe and turn on notifications for your daily dose of motivation."
        ),
    },
    "health_wellness": {
        "channel_id": "UCs3Y2sZ0ImXQ9QEwR5gFHfw",
        "name": "Herbal Organic Life",
        "handle": "@HerbalOrganicLifeZA",
        "keywords": "herbal remedies,natural health,wellness,organic living,holistic health,nutrition,healthy lifestyle,herbal medicine,superfoods,detox,immunity,self care",
        "description": (
            "Your Guide to Natural Health and Herbal Wellness\n"
            "\n"
            "Herbal Organic Life explores the power of natural remedies, "
            "herbal medicine, and holistic wellness. We bring you evidence-based "
            "content on herbs, superfoods, and organic living that can transform "
            "your health from the inside out.\n"
            "\n"
            "Topics we cover:\n"
            "\u2022 Herbal Remedies and Natural Cures\n"
            "\u2022 Nutrition and Superfoods\n"
            "\u2022 Holistic Health and Detox\n"
            "\u2022 Immunity Boosting Naturally\n"
            "\u2022 Organic Living Tips\n"
            "\n"
            "Nature has the answers \u2014 we help you find them. "
            "Take control of your health the natural way.\n"
            "\n"
            "Subscribe for weekly wellness wisdom and herbal knowledge."
        ),
    },
    "blissful_moments": {
        "channel_id": "UCPNgMBuOOUQ5-lvdm5miruQ",
        "name": "Blissful Moments",
        "handle": "@BlissfulMomentsZA",
        "keywords": "relaxation,satisfying videos,ASMR,calming,soothing,oddly satisfying,peaceful,meditation,stress relief,ambient,nature sounds,sleep",
        "description": (
            "Find Your Peace in Every Moment\n"
            "\n"
            "Blissful Moments is your escape from the noise. "
            "We create soothing, satisfying, and calming visual experiences "
            "that help you relax, de-stress, and find inner peace. "
            "Perfect for unwinding after a long day or setting a calm atmosphere.\n"
            "\n"
            "What we offer:\n"
            "\u2022 Oddly Satisfying Compilations\n"
            "\u2022 Calming Nature and Ambient Videos\n"
            "\u2022 Relaxation and Stress Relief\n"
            "\u2022 Soothing ASMR Content\n"
            "\u2022 Peaceful Sleep and Meditation Aids\n"
            "\n"
            "Take a breath. Press play. Let the calm wash over you.\n"
            "\n"
            "Subscribe for daily moments of bliss."
        ),
    },
}


def authenticate(niche: str) -> Credentials:
    """Authenticate via OAuth and return credentials. Saves token per niche."""
    token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
    creds = None

    # Try loading existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            print(f"  [OK] Token refreshed for {niche}")
            return creds
        except Exception as e:
            print(f"  [!] Token refresh failed: {e}")
            creds = None

    # Need new authentication
    if not creds or not creds.valid:
        if not CLIENT_SECRET_PATH.exists():
            print(f"  [ERROR] Client secret not found at {CLIENT_SECRET_PATH}")
            sys.exit(1)

        channel_info = NICHE_CHANNELS[niche]
        print(f"\n  >>> IMPORTANT: When the browser opens, select the")
        print(f"  >>> '{channel_info['name']}' channel ({channel_info['handle']})")
        print(f"  >>> from the account picker.\n")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_PATH), SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        print(f"  [OK] Token saved to {token_path}")

    return creds


def update_channel_branding(youtube, channel_config: dict) -> bool:
    """Update channel description and keywords via YouTube Data API."""
    channel_id = channel_config["channel_id"]

    try:
        # First, get the current channel data
        response = youtube.channels().list(
            part="brandingSettings,snippet",
            id=channel_id,
        ).execute()

        if not response.get("items"):
            print(f"  [ERROR] Channel {channel_id} not found")
            return False

        channel = response["items"][0]
        current_desc = channel.get("snippet", {}).get("description", "")
        print(f"  Current description: {current_desc[:60]}..." if current_desc else "  Current description: (empty)")

        # Update branding settings
        branding = channel.get("brandingSettings", {})
        branding_channel = branding.get("channel", {})
        branding_channel["description"] = channel_config["description"]
        branding_channel["keywords"] = channel_config["keywords"]
        branding["channel"] = branding_channel

        # Execute update
        youtube.channels().update(
            part="brandingSettings",
            body={
                "id": channel_id,
                "brandingSettings": branding,
            },
        ).execute()

        print(f"  [OK] Description updated ({len(channel_config['description'])} chars)")
        print(f"  [OK] Keywords set: {channel_config['keywords'][:60]}...")
        return True

    except Exception as e:
        print(f"  [ERROR] Failed to update channel: {e}")
        return False


def verify_channel(youtube, channel_id: str) -> dict:
    """Verify the authenticated channel matches expected channel."""
    try:
        response = youtube.channels().list(
            part="snippet,brandingSettings",
            id=channel_id,
        ).execute()

        if response.get("items"):
            ch = response["items"][0]
            return {
                "id": ch["id"],
                "title": ch["snippet"]["title"],
                "description": ch["snippet"].get("description", "")[:100],
            }
    except Exception as e:
        print(f"  [ERROR] Verification failed: {e}")

    return {}


def setup_niche(niche: str, auth_only: bool = False):
    """Set up a single niche channel."""
    config = NICHE_CHANNELS[niche]
    print(f"\n{'='*60}")
    print(f"  {config['name']} ({config['handle']})")
    print(f"  Channel ID: {config['channel_id']}")
    print(f"{'='*60}")

    # Authenticate
    print(f"\n  [1/3] Authenticating...")
    creds = authenticate(niche)

    # Build YouTube service
    youtube = build("youtube", "v3", credentials=creds)

    # Verify channel access
    print(f"  [2/3] Verifying channel access...")
    info = verify_channel(youtube, config["channel_id"])
    if info:
        print(f"  [OK] Channel verified: {info['title']}")
    else:
        print(f"  [WARN] Could not verify channel - may need different auth")

    if auth_only:
        print(f"  [SKIP] Auth-only mode, skipping branding update")
        return True

    # Update branding
    print(f"  [3/3] Updating channel branding...")
    success = update_channel_branding(youtube, config)

    if success:
        # Final verification
        updated = verify_channel(youtube, config["channel_id"])
        if updated and updated.get("description"):
            print(f"  [VERIFIED] Description starts with: {updated['description'][:60]}...")
        print(f"\n  >>> {config['name']} setup complete!")
    else:
        print(f"\n  >>> {config['name']} setup FAILED")

    return success


def main():
    parser = argparse.ArgumentParser(description="Set up YouTube channels via API")
    parser.add_argument("--niche", type=str, help="Set up a specific niche only")
    parser.add_argument("--auth-only", action="store_true", help="Only authenticate, don't update branding")
    parser.add_argument("--list", action="store_true", help="List all niche channels")
    args = parser.parse_args()

    if args.list:
        print("\nConfigured YouTube Channels:")
        for niche, config in NICHE_CHANNELS.items():
            token_exists = (TOKENS_DIR / f"youtube_token_{niche}.json").exists()
            status = "authenticated" if token_exists else "needs auth"
            print(f"  {niche:20s} | {config['name']:25s} | {config['handle']:25s} | {status}")
        return

    print("\n" + "=" * 60)
    print("  YouTube Channel Setup Utility")
    print("  Using YouTube Data API v3")
    print("=" * 60)

    niches_to_setup = [args.niche] if args.niche else list(NICHE_CHANNELS.keys())
    results = {}

    for niche in niches_to_setup:
        if niche not in NICHE_CHANNELS:
            print(f"\n  [ERROR] Unknown niche: {niche}")
            print(f"  Available: {', '.join(NICHE_CHANNELS.keys())}")
            continue

        success = setup_niche(niche, auth_only=args.auth_only)
        results[niche] = success

    # Summary
    print(f"\n\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for niche, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  [{status}] {NICHE_CHANNELS[niche]['name']}")

    failed = sum(1 for s in results.values() if not s)
    if failed:
        print(f"\n  {failed} channel(s) failed. Run again with --niche to retry.")
    else:
        print(f"\n  All channels set up successfully!")


if __name__ == "__main__":
    main()
