"""
YouTube OAuth Helper — Generates auth URL and exchanges code for tokens.

Usage:
    Step 1: python auth_youtube.py --get-url --niche ai_trading
            (Prints the auth URL to visit in browser)

    Step 2: python auth_youtube.py --exchange-code --niche ai_trading --code "AUTH_CODE_HERE"
            (Exchanges the auth code for tokens and saves them)

    Step 3: python auth_youtube.py --update-branding --niche ai_trading
            (Updates channel description/keywords using saved token)

    All-in-one: python auth_youtube.py --update-branding --niche all
            (Updates all niches that have tokens)
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import requests as http_requests

ROOT_DIR = Path(__file__).parent
TOKENS_DIR = ROOT_DIR / "tokens"
CLIENT_SECRET_PATH = TOKENS_DIR / "youtube_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Load client secret
def load_client_config():
    with open(CLIENT_SECRET_PATH) as f:
        data = json.load(f)
    installed = data["installed"]
    return installed["client_id"], installed["client_secret"]


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
    "kids_songs": {
        "channel_id": "UClg-hsIwpJk1yG3CUI3FMMg",
        "name": "Zuzu & Friends",
        "handle": "@ZuzuAndFriends-u3o",
        "keywords": "nursery rhymes,kids songs,baby songs,lullaby,toddler songs,sing along,ABC song,learning colors,bedtime songs,children music,kids learning,preschool songs,twinkle twinkle,baby elephant",
        "description": (
            "Nursery Rhymes & Kids Songs to Sing, Dance and Learn\n"
            "\n"
            "Zuzu & Friends brings your little ones a magical world of "
            "nursery rhymes, lullabies and sing-along songs — led by Zuzu "
            "the lovable baby elephant. Bright, gentle and full of learning, "
            "every video helps toddlers sing, dance, and drift off to sleep.\n"
            "\n"
            "Sing and learn with us:\n"
            "• Classic Nursery Rhymes\n"
            "• Gentle Bedtime Lullabies\n"
            "• ABC, Numbers and Colors\n"
            "• Fun Sing-Along Kids Songs\n"
            "• Learning Adventures with Zuzu\n"
            "\n"
            "Safe, gentle and made for kids. Subscribe and join Zuzu & Friends "
            "for a new song to sing every day!"
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


def get_auth_url():
    """Generate the OAuth authorization URL."""
    client_id, _ = load_client_config()
    params = {
        "client_id": client_id,
        "redirect_uri": "http://localhost:1",
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)


def exchange_code(code: str, niche: str):
    """Exchange authorization code for tokens."""
    client_id, client_secret = load_client_config()

    response = http_requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:1",
        },
    )

    if response.status_code != 200:
        print(f"[ERROR] Token exchange failed: {response.text}")
        return None

    token_data = response.json()

    # Save token in the format google-auth-library expects
    creds_data = {
        "token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
    }

    token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
    with open(token_path, "w") as f:
        json.dump(creds_data, f, indent=2)

    print(f"[OK] Token saved to {token_path}")
    return creds_data


def update_branding(niche: str):
    """Update channel branding using saved token."""
    token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
    if not token_path.exists():
        print(f"[ERROR] No token for {niche}. Run --exchange-code first.")
        return False

    config = NICHE_CHANNELS[niche]
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh if needed
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    try:
        # Get current channel data
        response = youtube.channels().list(
            part="brandingSettings,snippet",
            id=config["channel_id"],
        ).execute()

        if not response.get("items"):
            print(f"[ERROR] Channel {config['channel_id']} not found. May need different auth.")
            # Try listing the authenticated channel
            mine = youtube.channels().list(part="snippet", mine=True).execute()
            if mine.get("items"):
                print(f"[INFO] Authenticated as: {mine['items'][0]['snippet']['title']} (ID: {mine['items'][0]['id']})")
            return False

        channel = response["items"][0]
        print(f"[INFO] Channel: {channel['snippet']['title']}")

        # Update branding
        branding = channel.get("brandingSettings", {})
        branding_channel = branding.get("channel", {})
        branding_channel["description"] = config["description"]
        branding_channel["keywords"] = config["keywords"]
        branding["channel"] = branding_channel

        youtube.channels().update(
            part="brandingSettings",
            body={
                "id": config["channel_id"],
                "brandingSettings": branding,
            },
        ).execute()

        print(f"[OK] {config['name']} - Description updated ({len(config['description'])} chars)")
        print(f"[OK] {config['name']} - Keywords: {config['keywords'][:60]}...")

        # Verify
        verify = youtube.channels().list(
            part="snippet",
            id=config["channel_id"],
        ).execute()
        if verify.get("items"):
            desc = verify["items"][0]["snippet"].get("description", "")
            print(f"[VERIFIED] Description starts: {desc[:80]}...")

        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--get-url", action="store_true", help="Print OAuth URL")
    parser.add_argument("--exchange-code", action="store_true", help="Exchange auth code for token")
    parser.add_argument("--update-branding", action="store_true", help="Update channel branding")
    parser.add_argument("--niche", type=str, required=True, help="Niche name or 'all'")
    parser.add_argument("--code", type=str, help="Auth code from OAuth redirect")
    args = parser.parse_args()

    if args.get_url:
        url = get_auth_url()
        print(f"\nVisit this URL in your browser:\n{url}\n")
        print("After authorizing, you'll be redirected to a localhost URL that will fail.")
        print("Copy the 'code' parameter from the URL bar.")

    elif args.exchange_code:
        if not args.code:
            print("[ERROR] --code is required with --exchange-code")
            return
        exchange_code(args.code, args.niche)

    elif args.update_branding:
        if args.niche == "all":
            for niche in NICHE_CHANNELS:
                token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
                if token_path.exists():
                    print(f"\n--- {NICHE_CHANNELS[niche]['name']} ---")
                    update_branding(niche)
                else:
                    print(f"\n--- {NICHE_CHANNELS[niche]['name']} --- SKIPPED (no token)")
        else:
            update_branding(args.niche)


if __name__ == "__main__":
    main()
