"""
Genesis Studio Content Engine — Central Configuration

Maps 4 Genesis brands to existing Facebook pages and YouTube channels.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

ROOT_DIR = Path(__file__).parent
FACTORY_DIR = ROOT_DIR.parent
TOKENS_DIR = FACTORY_DIR / "tokens"
OUTPUT_DIR = ROOT_DIR / "output"
LOGS_DIR = ROOT_DIR / "logs"
DB_PATH = ROOT_DIR / "genesis.db"

OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ── API Keys ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
FAL_KEY = os.getenv("FAL_KEY", "")
TIKTOK_SESSION_ID = os.getenv("TIKTOK_SESSION_ID", "")

# Genesis Studio API (for Brain Studio video generation)
GENESIS_STUDIO_URL = os.getenv("GENESIS_STUDIO_URL", "https://genesis-studio-hazel.vercel.app")
GENESIS_STUDIO_API_KEY = os.getenv("GENESIS_STUDIO_API_KEY", "")

# ── The 4 Genesis Brands ─────────────────────────────────
BRANDS = {
    "news": {
        "name": "Genesis News AI",
        "color": "#FF3131",
        "niche_key": "tech_news",  # maps to existing FB page + YT channel
        "facebook": {
            "page_id": os.getenv("FB_PAGE_ID_tech_news", "100919755007786"),
            "access_token": os.getenv("FB_PAGE_TOKEN_tech_news", ""),
        },
        "youtube": {
            "token_file": TOKENS_DIR / "youtube_token_tech_news.json",
        },
        "tiktok": {
            "session_id": TIKTOK_SESSION_ID,
            "cookies_file": TOKENS_DIR / "tiktok_cookies.json",
        },
        "hashtags": ["#BreakingNews", "#WorldNews", "#AINews", "#GenesisNews", "#NewsAlert"],
        "trend_sources": {
            "newsapi_category": "general",
            "reddit_subs": ["worldnews", "news", "geopolitics"],
            "youtube_query": "breaking news today",
        },
    },
    "finance": {
        "name": "Genesis Wealth AI",
        "color": "#F5C518",
        "niche_key": "ai_money",
        "facebook": {
            "page_id": os.getenv("FB_PAGE_ID_ai_money", "107465491085378"),
            "access_token": os.getenv("FB_PAGE_TOKEN_ai_money", ""),
        },
        "youtube": {
            "token_file": TOKENS_DIR / "youtube_token_ai_money.json",
        },
        "tiktok": {
            "session_id": TIKTOK_SESSION_ID,
            "cookies_file": TOKENS_DIR / "tiktok_cookies.json",
        },
        "hashtags": ["#Finance", "#Crypto", "#StockMarket", "#WealthAI", "#MoneyTips"],
        "trend_sources": {
            "newsapi_category": "business",
            "reddit_subs": ["CryptoCurrency", "stocks", "wallstreetbets"],
            "coingecko": True,
            "youtube_query": "finance crypto market news today",
        },
    },
    "motivation": {
        "name": "Genesis Inspire AI",
        "color": "#A855F7",
        "niche_key": "motivation",
        "facebook": {
            "page_id": os.getenv("FB_PAGE_ID_motivation", "102206758210905"),
            "access_token": os.getenv("FB_PAGE_TOKEN_motivation", ""),
        },
        "youtube": {
            "token_file": TOKENS_DIR / "youtube_token_motivation.json",
        },
        "tiktok": {
            "session_id": TIKTOK_SESSION_ID,
            "cookies_file": TOKENS_DIR / "tiktok_cookies.json",
        },
        "hashtags": ["#Motivation", "#Inspire", "#Mindset", "#Success", "#Growth"],
        "trend_sources": {
            "reddit_subs": ["GetMotivated", "LifeProTips", "selfimprovement"],
            "youtube_query": "motivation success mindset",
        },
    },
    "viral": {
        "name": "Genesis Viral AI",
        "color": "#00D4AA",
        "niche_key": "blissful_moments",  # largest page, 58K followers
        "facebook": {
            "page_id": os.getenv("FB_PAGE_ID_blissful_moments", "112465853843545"),
            "access_token": os.getenv("FB_PAGE_TOKEN_blissful_moments", ""),
        },
        "youtube": {
            "token_file": TOKENS_DIR / "youtube_token_blissful_moments.json",
        },
        "tiktok": {
            "session_id": TIKTOK_SESSION_ID,
            "cookies_file": TOKENS_DIR / "tiktok_cookies.json",
        },
        "hashtags": ["#Viral", "#Trending", "#Entertainment", "#Drama", "#OMG"],
        "trend_sources": {
            "reddit_subs": ["popular", "entertainment", "Drama"],
            "youtube_trending": True,
            "youtube_query": "viral trending entertainment today",
        },
    },
}

# ── Posting Schedule (SAST = UTC+2) ──────────────────────
# Two batches per day: morning (9 AM) and evening (6 PM)
# Each batch: trends → scripts → videos → watermark → post all 4 brands
# Cron format: minute hour * * *
SCHEDULE = {
    # ── MORNING BATCH ──
    "morning_trends":     "0 5 * * *",    # 07:00 SAST — fetch morning trends
    "morning_videos":     "15 5 * * *",   # 07:15 SAST — generate videos (Brain Studio)
    "morning_watermark":  "45 5 * * *",   # 07:45 SAST — apply watermarks
    "morning_post":       "0 7 * * *",    # 09:00 SAST — post all 4 brands

    # ── EVENING BATCH ──
    "evening_trends":     "0 12 * * *",   # 14:00 SAST — fetch evening trends
    "evening_videos":     "15 12 * * *",  # 14:15 SAST — generate videos (Brain Studio)
    "evening_watermark":  "45 12 * * *",  # 14:45 SAST — apply watermarks
    "evening_post":       "0 16 * * *",   # 18:00 SAST — post all 4 brands (prime time)

    # ── ANALYTICS ──
    "analytics":          "0 22 * * *",   # 00:00 SAST — pull daily analytics
}

# ── Watermark Settings ────────────────────────────────────
WATERMARK = {
    "text": "Genesis Studio",
    "position": "bottom-center",
    "font_size": 28,
    "font": "Arial",
}

# ── Script Prompts (Claude) ──────────────────────────────
SCRIPT_PROMPTS = {
    "news": {
        "system": "Write a 40-second breaking news video script. Start with BREAKING or JUST IN. Short punchy sentences. Present tense. Build tension. End on a cliffhanger question. Never mention any brand, website or app. Pure news journalism tone.",
        "caption_prefix": "BREAKING",
    },
    "finance": {
        "system": "Write a 40-second financial insight video script. Open with a shocking stat or contrarian take. Use 'The market just...' or 'What nobody is telling you...'. Create urgency. Smart, confident tone. Never mention any brand or website.",
        "caption_prefix": "MARKET ALERT",
    },
    "motivation": {
        "system": "Write a 40-second motivational video script. Start with a relatable struggle. Build to a turning point. End with power. Short sentences. Use 'you' language. Real, raw, no fluff. Never mention any brand or website.",
        "caption_prefix": "",
    },
    "viral": {
        "system": "Write a 40-second entertainment commentary script. Lead with the most shocking element. Conversational and punchy. Light humor where appropriate. End with a question that drives comments. Never mention any brand or website.",
        "caption_prefix": "NO WAY",
    },
}
