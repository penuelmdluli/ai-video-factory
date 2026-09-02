"""
AI Video Factory — Central Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Paths ──────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT_DIR / "output"))
ASSETS_DIR = ROOT_DIR / "assets"
TEMPLATES_DIR = ROOT_DIR / "templates"
TOKENS_DIR = ROOT_DIR / "tokens"
MUSIC_DIR = TEMPLATES_DIR / "music"

OUTPUT_DIR.mkdir(exist_ok=True)

# ── AI API Keys ────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Voice Keys ─────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# ── AI Image Generation (FREE) ────────────────────────────────
# Cloudflare Workers AI — 100K free images/day (FLUX model)
# Get free account: https://dash.cloudflare.com → AI → Workers AI
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")

# ── Website URL (included in all video descriptions) ─────────
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://www.gettraderadar.com")

# Per-niche website URL override (ShopMO uses its own domain)
NICHE_WEBSITE_URL = {
    "shopmo_products": "https://shopmoo.co.za",
}

def get_website_url(niche: str = "") -> str:
    """Get the website URL for a niche (ShopMO uses shopmoo.co.za)."""
    return NICHE_WEBSITE_URL.get(niche, WEBSITE_URL)

# ── Stock Footage ──────────────────────────────────────────────
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# ── Platform Credentials ──────────────────────────────────────
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")

# ── YouTube Data API (read-only trending/search — simple API key) ──
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ── Viral Score Settings ─────────────────────────────────
VIRAL_SCORE_THRESHOLD = float(os.getenv("VIRAL_SCORE_THRESHOLD", "20"))  # Lower threshold — quality prompt handles the rest
VIRAL_SCORE_MAX_RETRIES = int(os.getenv("VIRAL_SCORE_MAX_RETRIES", "3"))

# ── Niche Prioritization ─────────────────────────────────
ENABLE_NICHE_PRIORITIZATION = os.getenv("ENABLE_NICHE_PRIORITIZATION", "true").lower() in ("true", "1", "yes")
MIN_VIDEOS_PER_NICHE_PER_DAY = int(os.getenv("MIN_VIDEOS_PER_NICHE_PER_DAY", "1"))

# ── Trend Source Settings ─────────────────────────────────
TREND_CACHE_TTL_HOURS = float(os.getenv("TREND_CACHE_TTL_HOURS", "2"))
TREND_SOURCE_STALE_HOURS = float(os.getenv("TREND_SOURCE_STALE_HOURS", "6"))

# ── Facebook Pages (MOTIVATIONS App ID: 591543017174198) ─────
FB_APP_ID = os.getenv("FB_APP_ID", "591543017174198")
# Per-niche page tokens and IDs
FB_PAGE_ID_AI_MONEY = os.getenv("FB_PAGE_ID_ai_money", "")
FB_PAGE_TOKEN_AI_MONEY = os.getenv("FB_PAGE_TOKEN_ai_money", "")
FB_PAGE_ID_TECH_NEWS = os.getenv("FB_PAGE_ID_tech_news", "")
FB_PAGE_TOKEN_TECH_NEWS = os.getenv("FB_PAGE_TOKEN_tech_news", "")
FB_PAGE_ID_MOTIVATION = os.getenv("FB_PAGE_ID_motivation", "")
FB_PAGE_TOKEN_MOTIVATION = os.getenv("FB_PAGE_TOKEN_motivation", "")
FB_PAGE_ID_HEALTH_WELLNESS = os.getenv("FB_PAGE_ID_health_wellness", "")
FB_PAGE_TOKEN_HEALTH_WELLNESS = os.getenv("FB_PAGE_TOKEN_health_wellness", "")
FB_PAGE_ID_BLISSFUL_MOMENTS = os.getenv("FB_PAGE_ID_blissful_moments", "")
FB_PAGE_TOKEN_BLISSFUL_MOMENTS = os.getenv("FB_PAGE_TOKEN_blissful_moments", "")
FB_PAGE_ID_DAILY_BREAKDOWN = os.getenv("FB_PAGE_ID_daily_breakdown", "")
FB_PAGE_TOKEN_DAILY_BREAKDOWN = os.getenv("FB_PAGE_TOKEN_daily_breakdown", "")
FB_PAGE_ID_SHOPMO_PRODUCTS = os.getenv("FB_PAGE_ID_shopmo_products", "61582171693722")
FB_PAGE_TOKEN_SHOPMO_PRODUCTS = os.getenv("FB_PAGE_TOKEN_shopmo_products", "")
FB_PAGE_ID_LIMITLESS_YOU = os.getenv("FB_PAGE_ID_limitless_you", "")
FB_PAGE_TOKEN_LIMITLESS_YOU = os.getenv("FB_PAGE_TOKEN_limitless_you", "")

# ── Cloud Storage (for Instagram Reels upload) ───────────────
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ai-video-factory")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")

# ── Per-Niche Instagram Business Accounts ─────────────────
# Each niche IG Business Account is connected to its FB Page
INSTAGRAM_ACCOUNTS = {
    "ai_money": {
        "user_id": os.getenv("IG_USER_ID_ai_money", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_ai_money", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "tech_news": {
        "user_id": os.getenv("IG_USER_ID_tech_news", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_tech_news", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "motivation": {
        "user_id": os.getenv("IG_USER_ID_motivation", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_motivation", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "health_wellness": {
        "user_id": os.getenv("IG_USER_ID_health_wellness", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_health_wellness", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "blissful_moments": {
        "user_id": os.getenv("IG_USER_ID_blissful_moments", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_blissful_moments", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "daily_breakdown": {
        "user_id": os.getenv("IG_USER_ID_daily_breakdown", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_daily_breakdown", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "shopmo_products": {
        "user_id": os.getenv("IG_USER_ID_shopmo_products", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_shopmo_products", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
    "limitless_you": {
        "user_id": os.getenv("IG_USER_ID_limitless_you", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_limitless_you", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
}

# ── Monitoring & Alerts ──────────────────────────────────────
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")

# ── Voice Routing ──────────────────────────────────────────────
# "elevenlabs" for premium, "edge-tts" for free
VOICE_SHORTS = os.getenv("DEFAULT_VOICE_SHORTS", "elevenlabs")

# ── Edge-TTS Voices (free, natural-sounding) ──────────────────
EDGE_TTS_VOICES = {
    "male_us": "en-US-GuyNeural",
    "female_us": "en-US-JennyNeural",
    "male_uk": "en-GB-RyanNeural",
    "female_uk": "en-GB-SoniaNeural",
    "male_deep": "en-US-ChristopherNeural",
    "female_warm": "en-US-AriaNeural",
}
DEFAULT_EDGE_VOICE = "en-US-JennyNeural"  # Female, warm — matches D-ID Alice avatar

# ── ElevenLabs Voices ─────────────────────────────────────────
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # "Rachel" female — matches D-ID Alice avatar
ELEVENLABS_MODEL = "eleven_multilingual_v2"  # Best quality model — most natural sounding
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_192"   # Premium quality 192kbps (Creator tier)

# ── Video Settings (SHORTS ONLY — no long-form, no podcast) ────
VIDEO_SETTINGS = {
    "youtube_shorts": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,  # 25-35 sec viral sweet spot
        "aspect": "9:16",
    },
    "tiktok": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,  # 25-35 sec viral sweet spot
        "aspect": "9:16",
    },
    "instagram_reels": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,  # 25-35 sec viral sweet spot
        "aspect": "9:16",
    },
    # ── Short format (used by scheduler — all platforms) ──
    "short": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,  # 25-35 sec = highest completion rate
        "aspect": "9:16",
    },
    # Legacy alias
    "viral_short": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,
        "aspect": "9:16",
    },
    "facebook_reels": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,  # 25-35 sec viral sweet spot
        "aspect": "9:16",
    },
}

# ── Thumbnail Settings ─────────────────────────────────────────
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720
THUMBNAIL_FONT_SIZE = 72
THUMBNAIL_BG_COLOR = (15, 15, 25)  # Dark blue-black
THUMBNAIL_TEXT_COLOR = (255, 255, 255)
THUMBNAIL_ACCENT_COLOR = (0, 255, 136)  # Green accent

# ── Caption Settings ───────────────────────────────────────────
# Punchy, high-retention captions for war/news shorts: short bursts, big bold
# text with a heavy outline so it stays readable over busy combat footage.
CAPTION_FONT_SIZE = int(os.getenv("CAPTION_FONT_SIZE", "60"))  # bigger, mobile-readable
CAPTION_MAX_WORDS = int(os.getenv("CAPTION_MAX_WORDS", "3"))   # 3-word bursts = karaoke punch
CAPTION_FONT_COLOR = "white"
CAPTION_STROKE_COLOR = "black"
CAPTION_STROKE_WIDTH = int(os.getenv("CAPTION_STROKE_WIDTH", "6"))  # heavy outline over footage
CAPTION_BG_OPACITY = float(os.getenv("CAPTION_BG_OPACITY", "0.55"))  # lighter bar, text carries
CAPTION_POSITION = ("center", "bottom")

# ── Karaoke word highlight (engagement) ───────────────────────
# Keeps the EXACT caption style; the word being spoken pops yellow + bounces.
KARAOKE_CAPTIONS = os.getenv("KARAOKE_CAPTIONS", "1") not in ("0", "false", "no", "")
# Bright yellow highlight for the active word (R,G,B). Vivid, high-contrast over footage.
KARAOKE_HIGHLIGHT_COLOR = tuple(int(x) for x in os.getenv(
    "KARAOKE_HIGHLIGHT_COLOR", "255,221,51").split(","))
# Active word grows this much (the "bounce" pop). 1.0 = no size change.
KARAOKE_HIGHLIGHT_SCALE = float(os.getenv("KARAOKE_HIGHLIGHT_SCALE", "1.12"))

# ── Background music level (under the voiceover) ──────────────
# 0.18 was almost inaudible under a full-volume voice; 0.35 sits clearly under
# speech without drowning it. Tune via env; ~0.45 = punchy, ~0.25 = subtle.
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.35"))

# ── Platform-Aware Fonts ──────────────────────────────────────
import platform as _platform
if _platform.system() == "Windows":
    CAPTION_FONT = "C:/Windows/Fonts/arialbd.ttf"
    THUMBNAIL_FONT_PATH = "C:/Windows/Fonts/impact.ttf"
else:
    CAPTION_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    THUMBNAIL_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ── Visual Effects ────────────────────────────────────────────
ENABLE_KEN_BURNS = True
ENABLE_TRANSITIONS = True
ENABLE_LOWER_THIRDS = True
# SFX decoupled from voice — can use cached SFX even without ElevenLabs.
# OFF by default: the generated whoosh/impact accents read as artificial noise over
# real footage. Keep clean music + voiceover only. Set ENABLE_SFX=true to bring them back.
ENABLE_SFX = os.getenv("ENABLE_SFX", "false").lower() in ("true", "1", "yes")
TRANSITION_DURATION = 0.4
KEN_BURNS_ZOOM_RANGE = (1.0, 1.50)  # Cinematic zoom (was 1.20, now 1.50 for stronger effect)

# ── AI Image Generation (Local Stable Diffusion XL) ──────────
# Runs on GPU (RTX 2080 Ti 11GB) for unlimited, copyright-free images
ENABLE_LOCAL_SD = os.getenv("ENABLE_LOCAL_SD", "true").lower() in ("true", "1", "yes")
# Prefer LOCAL SDXL for the still images (free/unlimited); the GPU is now free
# because video runs on WaveSpeed's cloud. Cloudflare FLUX is the fallback.
PREFER_LOCAL_IMAGES = os.getenv("PREFER_LOCAL_IMAGES", "true").lower() in ("true", "1", "yes")
SD_STEPS = int(os.getenv("SD_STEPS", "20"))  # 20 = good quality + 33% faster
SD_CFG_SCALE = float(os.getenv("SD_CFG_SCALE", "7.5"))
# Set to false to disable stock footage fallback (100% AI images)
USE_STOCK_FOOTAGE = os.getenv("USE_STOCK_FOOTAGE", "true").lower() in ("true", "1", "yes")

# ── AI Image-to-Video (SVD-XT — LOCAL GPU) ──────────────────
# Converts AI images into CINEMATIC video clips with realistic motion.
# Primary: Stable Video Diffusion XT — runs GPU-direct on RTX 2080 Ti (11GB)
#   at ~2.5 min/clip, fp16-safe on Turing. Loaded once per batch.
# Fallback: Ken Burns zoom (no GPU needed).
# NOTE: CogVideoX-5B and Wan-14B were evaluated and REJECTED for local use —
#   they need bf16 (no Turing HW support) + >11GB VRAM, producing black frames
#   and ~2.7 hr/clip via CPU offload. Use those only via a hosted GPU.
# ── Image-to-video BACKEND ──────────────────────────────────
# "runpod"   = serverless RunPod Wan 2.1 T2V (~$0.02-0.05/clip, endpoint in
#              RUNPOD_ENDPOINT_ID) — cheapest cloud option, replaces WaveSpeed.
# "wavespeed" = serverless cloud GPU (sharp Wan 2.2 / Seedance) — no Turing fight.
# "svd" = local SVD-XT (soft). "none" = stock/Ken Burns only.
# Cloud clip per scene, then STOCK footage as fallback if it fails/over-budget.
I2V_BACKEND = os.getenv("I2V_BACKEND", "wavespeed").lower()
WAVESPEED_MODEL = os.getenv("WAVESPEED_MODEL", "wan22")        # wan22 | seedance
WAVESPEED_RESOLUTION = os.getenv("WAVESPEED_RESOLUTION", "480p")  # 480p | 720p
WAVESPEED_DURATION = int(os.getenv("WAVESPEED_DURATION", "5"))
WAVESPEED_MONTHLY_BUDGET = float(os.getenv("WAVESPEED_MONTHLY_BUDGET", "60"))

# ── Premium "hero clip" tier ──────────────────────────────────────
# Scene 1 (the hook) can use a top-tier cloud model (Seedance 2.0) for a
# cinematic, Hollywood-grade opening with clean human motion. All other scenes
# stay on Wan 2.2 / free Ken Burns. OFF by default = $0 (nothing changes).
# Cost-controlled: master switch + niche allow-list + daily cap + the existing
# WaveSpeed monthly $ budget. Only the FIRST scene ever pays premium (~$0.70/video).
ENABLE_HERO_PREMIUM = os.getenv("ENABLE_HERO_PREMIUM", "false").lower() in ("true", "1", "yes")
HERO_PREMIUM_MODEL = os.getenv("HERO_PREMIUM_MODEL", "seedance")       # WaveSpeed model id
HERO_PREMIUM_RESOLUTION = os.getenv("HERO_PREMIUM_RESOLUTION", "720p")  # 720p | 1080p
# Which niches get the premium hero when enabled (comma-separated). Empty = all.
HERO_PREMIUM_NICHES = [n.strip() for n in os.getenv("HERO_PREMIUM_NICHES", "tech_news").split(",") if n.strip()]
HERO_PREMIUM_DAILY_MAX = int(os.getenv("HERO_PREMIUM_DAILY_MAX", "6"))  # hard cap: premium clips/day

# Custom thumbnails/covers OFF by default — use the platform's auto default frame.
SET_CUSTOM_THUMBNAIL = os.getenv("SET_CUSTOM_THUMBNAIL", "true").lower() in ("true", "1", "yes")

# Multi-language subtitle tracks (YouTube) for international reach.
SUBTITLE_TRANSLATE = os.getenv("SUBTITLE_TRANSLATE", "true").lower() in ("true", "1", "yes")
# code -> language name (translated via Claude, uploaded as YouTube caption tracks)
SUBTITLE_LANGUAGES = {"ar": "Arabic", "fr": "French", "es": "Spanish"}

ENABLE_IMG2VID = os.getenv("ENABLE_IMG2VID", "true").lower() in ("true", "1", "yes")
IMG2VID_FPS = int(os.getenv("IMG2VID_FPS", "16"))   # 16fps = smooth cinematic
IMG2VID_NUM_FRAMES = int(os.getenv("IMG2VID_NUM_FRAMES", "25"))  # SVD-XT native max = 25 (~1.6s clip)
# SVD-XT maxes out at 25 frames (~1.6s). To reach a usable clip length we
# motion-interpolate (ffmpeg minterpolate) and retime each clip to this minimum
# duration — smooth, cinematic, and far cheaper than regenerating more frames.
IMG2VID_MIN_DURATION = float(os.getenv("IMG2VID_MIN_DURATION", "3.0"))  # seconds; 0 = disable
IMG2VID_SMOOTH_FPS = int(os.getenv("IMG2VID_SMOOTH_FPS", "24"))  # output fps after interpolation

# ── AI Music Generation (MusicGen) ───────────────────────────
# Generates copyright-free background music per niche via Meta MusicGen
ENABLE_AI_MUSIC = os.getenv("ENABLE_AI_MUSIC", "false").lower() in ("true", "1", "yes")  # MusicGen too slow on 2080 Ti
AI_MUSIC_CACHE_DIR = ASSETS_DIR / "ai_music_cache"

# ── AI Video Generation ──────────────────────────────────────
# ALL LOCAL — SVD-XT on RTX 2080 Ti for image-to-video conversion
# No paid APIs (fal.ai, Kling, MiniMax) — 100% free local GPU
FAL_KEY = os.getenv("FAL_KEY", "")
ENABLE_AI_VIDEO = False   # No paid video APIs
AI_VIDEO_BUDGET_PER_SESSION = 0  # $0 — all local

# Hero shot disabled — SVD-XT handles all scenes locally for free
ENABLE_HERO_SHOT = False
HERO_SHOT_MAX_COST = 0
CLIP_LIBRARY_DIR = ASSETS_DIR / "clip_library"
MUSIC_CACHE_DIR = ASSETS_DIR / "music_cache"

# ── Suno AI Music API (commercial license, ~$0.11/song) ──────
SUNO_API_KEY = os.getenv("SUNO_API_KEY", "")
SUNO_API_URL = os.getenv("SUNO_API_URL", "")  # Third-party endpoint (EvoLink, etc.)

# ── Viral Shorts Settings ────────────────────────────────────
# Optimized for maximum engagement (July 2026 research):
# - 25-35 seconds = sweet spot (70%+ completion rate)
# - Cuts every 2-3 seconds (fast pacing)
# - First 1-3 seconds = make or break (hook frame)
SHORTS_MAX_DURATION = int(os.getenv("SHORTS_MAX_DURATION", "35"))  # 35s sweet spot
SHORTS_MIN_DURATION = int(os.getenv("SHORTS_MIN_DURATION", "20"))  # minimum for value
SHORTS_VIDEOS_PER_NICHE = int(os.getenv("SHORTS_VIDEOS_PER_NICHE", "3"))  # per run
# Platform-specific rendering: separate files, no cross-posting
SHORTS_PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels", "facebook_reels"]
# Reuse strategy: what % of clips should come from library vs fresh API
CLIP_REUSE_TARGET = float(os.getenv("CLIP_REUSE_TARGET", "0.3"))  # 30% reuse — more fresh content

# ── Talking Head Avatar APIs ─────────────────────────────────
# D-ID (primary) — Lite plan: 400 credits/month
DID_API_KEY = os.getenv("DID_API_KEY", "")
DID_AVATAR_IMAGE_URL = os.getenv("DID_AVATAR_IMAGE_URL", "")
# HeyGen (fallback) — alternative talking head API
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
# Local avatar (FREE — Wav2Lip + audio-reactive, no API needed)
LOCAL_AVATAR_ENABLED = os.getenv("LOCAL_AVATAR_ENABLED", "false").lower() in ("true", "1", "yes")
LOCAL_AVATAR_PREFER_GPU = os.getenv("LOCAL_AVATAR_PREFER_GPU", "true").lower() in ("true", "1", "yes")
ENABLE_AVATAR = bool(DID_API_KEY) or bool(HEYGEN_API_KEY) or LOCAL_AVATAR_ENABLED
# Viseme sprite library (D-ID quality, zero ongoing cost after initial generation)
VISEME_SPRITES_DIR = Path(__file__).parent / "assets" / "viseme_sprites"
VISEME_SPRITES_ENABLED = os.getenv("VISEME_SPRITES_ENABLED", "false").lower() in ("true", "1", "yes")
SFX_CACHE_DIR = ASSETS_DIR / "sfx_cache"

# ── Niche Configurations ──────────────────────────────────────
NICHES = {
    # "ai_trading" removed — Mzansi Baby Stars page repurposed for baby dance content
    "ai_money": {
        "name": "Make Money With AI",
        "topics_bank": [
            "best AI side hustles 2026",
            "AI tools that make money",
            "passive income with AI",
            "AI freelancing opportunities",
            "make money with ChatGPT",
            "AI automation business ideas",
            "AI content creation income",
            "sell AI generated products",
            "AI consulting as side hustle",
            "best AI tools for entrepreneurs",
            "AI print on demand business",
            "make money with AI video",
            "AI copywriting income",
            "AI chatbot business model",
            "how creators use AI to earn",
            "FREE AI tools that help you invest smarter",
            "How to use AI for stock market research for free",
        ],
        "search_keywords": ["make money AI", "AI side hustle", "passive income AI", "AI tools business", "AI automation", "AI investing"],
        "pexels_queries": ["money", "laptop work", "entrepreneur", "technology", "coding", "success", "startup", "freelance", "remote work", "digital nomad"],
        "hashtags": ["#AI", "#MakeMoneyOnline", "#SideHustle", "#PassiveIncome", "#AITools", "#Entrepreneur", "#OnlineBusiness", "#ChatGPT", "#AISideHustle", "#DigitalBusiness"],
        "cpm_estimate": 17,
        "generate_charts": False,
        "edge_voice": "en-US-AriaNeural",
    },
    "tech_news": {
        # SOUTH AFRICA (owner call 2026-08-28: "change it to South African page
        # focus - for South Africa interest"). The page carried world
        # geopolitics - Red Sea shipping, Ghanaian gold, Zambian copper - to
        # 10,442 South African followers, and went quiet on 21 Aug. A page
        # about everywhere is a page about nowhere; the audience is here, so
        # the stories should be too.
        #
        # It must NOT stray into PSL football. Genesis News owns that, and two
        # of the owner's pages competing for the same story helps neither.
        "name": "Tech Pulse Africa - South African News",
        # An EMPTY focus was the whole problem. With no focus the topic path
        # skips the live-headline branch entirely and hands the model a bank of
        # angles - "the big South African story everyone is talking about
        # today" - with no story attached. It answered honestly and evergreenly:
        # Home Affairs queues (29 Aug), a Cape Town water tariff (29 Aug), a
        # Zimbabwean border e-visa (31 Aug). Nothing false, nothing anyone was
        # talking about. The page needs today's argument, not this year's tips.
        "topic_focus": os.getenv(
            "TECH_NEWS_TOPIC_FOCUS",
            "South African news that the country is ACTUALLY arguing about "
            "today - politics, the economy, power, crime, grants, jobs, courts "
            "and the movements and people driving the national conversation. "
            "Name the real story, the real people and the real numbers from "
            "the live headlines. Never PSL football (Genesis News owns that)."
        ),
        # Same contract Genesis runs on: the feed supplies the facts, the model
        # supplies the angle. Without it a news page invents news.
        "use_live_headlines": True,
        "headline_module": "modules.sa_news",
        "headline_rules": (
            "RULES — this page names REAL, LIVING South Africans, so these are hard:\n"
            "1. Build the topic from ONE headline above. The story must be one a "
            "South African would recognise from their feed today.\n"
            "2. Prefer a headline carried by MORE outlets — that number is how many "
            "newsrooms independently stood it up.\n"
            "3. NEVER invent a fact, figure, date, quote or accusation that is not in "
            "the list. No inferred motives, no imagined statements.\n"
            "4. Anything tagged REPORTED CLAIM is an allegation, not a finding — say "
            "'reports say' or 'is accused of', never state it as established.\n"
            "5. Attribute: name the outlet the story comes from.\n"
            "6. REPORT the argument, do not join it. Where a story is contested or a "
            "movement is campaigning, say who is claiming what and who disputes it. "
            "Do not adopt any group's slogans as the page's own voice, and never "
            "target or blame a nationality, race or religion — that is how a 10K page "
            "gets restricted, which ends it far faster than a quiet week does."
        ),
        # Angles, not headlines - the topic generator fills them from real
        # trending SA news. Each is written so the answer affects the viewer's
        # own week: what it costs, what it changes, what to do about it.
        "topics_bank": [
            "the load shedding stage everyone is arguing about and what it means for your week",
            "what the rand doing this is actually costing you at the till",
            "the petrol price change this month and what it does to your budget",
            "the big South African story everyone is talking about today, explained simply",
            "what this government decision actually changes for ordinary people",
            "the crime story South Africans cannot stop talking about",
            "load shedding, Eskom and the plan - what is real and what is talk",
            "the jobs and hiring story that matters if you are looking for work",
            "what is happening with grants, SASSA and the money people depend on",
            "the municipality failing its residents and what is being done",
            "the South African business story behind the headline",
            "what this new law or regulation means for you in plain language",
            "the health story every South African household should know",
            "the school and university story parents are asking about",
            "the world story that actually reaches South Africa, and how",
        ],
        "search_keywords": [
            "South Africa news", "load shedding Eskom", "rand exchange rate",
            "petrol price South Africa", "SASSA grants", "South Africa crime",
            "South Africa politics", "Gauteng", "Cape Town", "Durban",
            "South Africa economy", "municipality service delivery",
        ],
        "pexels_queries": [
            "south africa city", "johannesburg skyline", "cape town",
            "township street", "power lines", "electricity pylon",
            "petrol station", "supermarket shopping", "south african flag",
            "parliament building", "commuter taxi", "queue people",
        ],
        "hashtags": ["#SouthAfrica", "#Mzansi", "#SANews", "#LoadShedding",
                     "#Eskom", "#SouthAfricaNews", "#Gauteng", "#CapeTown",
                     "#TechPulseAfrica"],
        "cpm_estimate": 18,
        "generate_charts": False,
        # A South African page read in a British accent is the first thing an
        # SA viewer notices. Luke is the en-ZA male voice; Genesis already
        # uses the en-ZA female, so the two pages stay distinguishable.
        "edge_voice": "en-ZA-LukeNeural",
    },
    "sa_pulse": {
        "name": "Genesis News - PSL & Mzansi Football",
        # REFOCUSED (2026-08-14): this page is now a dedicated South African
        # football (PSL) news channel built around the BIG THREE — Kaizer Chiefs,
        # Orlando Pirates and Mamelodi Sundowns. Everything below keeps topic
        # generation, trends and the news chyron locked to PSL football.
        #
        # FACTUALITY: football news is check-able — fans will call out a fake
        # score or invented transfer instantly. `use_live_headlines` forces the
        # topic generator to pull REAL headlines from modules/psl_news.py
        # (Google News RSS over Soccer Laduma / KickOff / iDiski Times / SABC /
        # official club sites) instead of letting the model invent a story.
        "use_live_headlines": True,
        # TOPIC PIN (2026-08-14): the generator kept wandering to real-but-wrong
        # stories — Sekhukhune (already played), Pitso Mosimane, Steve Barker —
        # instead of the fixture Mzansi is actually arguing about. This forces
        # every topic onto the pinned fixture until it is cleared.
        # Set SA_PULSE_TOPIC_PIN="" in .env to unpin and follow the feed freely.
        # CLEARED 2026-08-24. The pin was set for the 15 Aug fixture and never
        # lifted, so nine days later every topic still had to be about that one
        # match — eleven straight reels opening "Chiefs vs Sundowns:". A pin is
        # for a live story, not a season. Set SA_PULSE_TOPIC_PIN in .env to pin
        # a genuine breaking story, and CLEAR IT once the story is done.
        "topic_pin": os.getenv("SA_PULSE_TOPIC_PIN", ""),
        # A generated topic must mention at least one of these or it is rejected.
        "topic_pin_terms": ["chiefs", "amakhosi", "sundowns", "masandawana"],
        "topic_focus": (
            "South African PSL football news centred on the BIG THREE: Kaizer Chiefs "
            "(Amakhosi), Orlando Pirates (the Buccaneers) and Mamelodi Sundowns (Masandawana). "
            "Cover the Betway Premiership, MTN8, Nedbank Cup, Carling Knockout, the Toyota Cup "
            "and CAF Champions League: match previews and reactions, the Soweto Derby, "
            "confirmed transfers and signings, injury and squad news, coach press-conference "
            "quotes, standings and title races, and key player battles. ALWAYS report only "
            "what real, named South African football media have actually reported — never "
            "invent a score, a transfer, a signing, an injury or a quote. Use authentic Mzansi "
            "football language (Amakhosi, Buccaneers, Masandawana, the Calabash/FNB Stadium, "
            "Soweto Derby, eS'Godini). South African football only. "
            "PRIORITY: Kaizer Chiefs drive the most engagement in SA football — roughly HALF "
            "of all topics must be Chiefs-led (Chiefs news, or a rival story told through what "
            "it means for Amakhosi). Pirates and Sundowns share the rest."
        ),
        "topics_bank": [
            "Kaizer Chiefs latest team news and what it means for Amakhosi fans",
            "Orlando Pirates squad news and the Buccaneers' next challenge",
            "Mamelodi Sundowns form and why Masandawana keep setting the standard",
            "the Soweto Derby build-up everything at stake for Chiefs and Pirates",
            "Betway Premiership title race where the big three actually stand",
            "the key battle that will decide this weekend's biggest PSL clash",
            "Kaizer Chiefs transfer talk what has actually been confirmed",
            "Orlando Pirates transfer talk separating fact from rumour",
            "Mamelodi Sundowns in the CAF Champions League what to expect",
            "MTN8 fixtures and what the big three need to do to progress",
            "the young PSL players Mzansi should be watching this season",
            "goalkeeper watch who is holding it down for the big three",
            "PSL injury report how the big three squads are shaping up",
            "coach under pressure what the press conference really revealed",
            "Nedbank Cup draw the ties Chiefs Pirates and Sundowns fans want",
            "PSL matchday review the results that shifted the table",
        ],
        "search_keywords": ["Kaizer Chiefs news", "Orlando Pirates news",
                            "Mamelodi Sundowns news", "Betway Premiership",
                            "PSL news South Africa", "Soweto Derby", "MTN8",
                            "Nedbank Cup", "PSL transfers", "PSL log standings"],
        # NOTE: Pexels has no licensed PSL club footage — these are GENERIC football
        # visuals used as b-roll. Real club/player imagery must come from properly
        # credited press photos, never from AI generation of real players.
        "pexels_queries": ["football stadium crowd", "soccer players match action",
                           "soccer stadium floodlights night", "football fans cheering",
                           "soccer ball close up grass", "goalkeeper diving save",
                           "football tackle midfield", "soccer celebration goal",
                           "football coach touchline", "soccer training session",
                           "African football supporters", "vuvuzela stadium crowd",
                           "South African flag", "Johannesburg Soweto streets",
                           "football boots pitch", "packed stadium aerial"],
        "hashtags": ["#PSL", "#BetwayPremiership", "#KaizerChiefs", "#Amakhosi",
                     "#OrlandoPirates", "#Buccaneers", "#MamelodiSundowns",
                     "#Masandawana", "#SowetoDerby", "#Mzansi"],
        "cpm_estimate": 14,
        "generate_charts": False,
        # VOICE: this page uses the SAME female voice as Tech Pulse — Kokoro af_heart
        # (see kokoro_voices in modules/voice_generator.py). The en-ZA voice below is
        # only reached if Kokoro is unavailable, or if SA_PULSE_LOCAL_VOICE=true in
        # .env, which re-locks the page to the South African accent.
        # OWNER PICK (2026-08-14, final): Luke — male SOUTH AFRICAN ENGLISH.
        # zu-ZA-Themba was tried and REJECTED for full scripts: an isiZulu voice
        # applies Zulu phonology to English narration and the result is not
        # intelligible English ("that is not english" — owner). isiZulu voices
        # may only ever be used for single names/phrases, never narration.
        "edge_voice": "en-ZA-LukeNeural",
    },
    "motivation": {
        "name": "Daily Motivation & Mindset",
        "topics_bank": [
            "morning motivation for success",
            "discipline beats motivation",
            "millionaire morning routine secrets",
            "how to stay focused on goals",
            "stoic mindset for success",
            "stop making excuses start winning",
            "mental toughness daily habits",
            "why most people stay broke mindset",
            "power of consistency daily",
            "how successful people think differently",
            "overcome fear of failure today",
            "build unshakeable confidence",
            "daily habits of billionaires",
            "embrace the grind success story",
            "your future self will thank you",
        ],
        "search_keywords": ["motivation", "success mindset", "discipline", "morning routine", "self improvement"],
        "pexels_queries": ["motivation", "success", "mountain top", "sunrise", "running", "fitness", "meditation", "nature landscape", "lion", "determination", "gym workout"],
        "hashtags": ["#Motivation", "#Mindset", "#Success", "#DailyMotivation", "#Discipline", "#GrindMode", "#NeverGiveUp", "#SuccessMindset", "#SelfImprovement", "#Hustle"],
        "cpm_estimate": 10,
        "generate_charts": False,
        "edge_voice": "en-US-ChristopherNeural",  # Deep male voice — powerful for motivation
    },
    "health_wellness": {
        "name": "Herbal Organic Life",
        # SAFE, genuinely-helpful organic-lifestyle content — NO medical/cure/treatment
        # claims (YMYL policy + AdSense/FTC safe). Herbs = culinary; organic = food & garden.
        # Hard subject-lock so the trend-based topic generator can't drift into medical claims:
        "topic_focus": (
            "Simple ORGANIC-LIVING and HEALTHY-HABITS lifestyle tips ONLY: cooking with fresh herbs "
            "and spices, growing a home or herb garden, choosing/storing organic produce, easy whole-food "
            "meals and snacks, hydration, gentle movement, rest, and calm daily routines. "
            "ABSOLUTELY FORBIDDEN: any medical, disease, symptom, 'remedy', 'cure', 'treat', 'heal', "
            "'detox', weight-loss, supplement-dosing, or 'boosts immunity/reverses/kills' claims, and no "
            "fear-mongering or clickbait. Keep every topic practical, food- and garden-focused, modest and honest."
        ),
        "topics_bank": [
            "easy ways to add more vegetables to your meals every day",
            "how to start a simple herb garden on your windowsill",
            "cooking with fresh herbs: simple flavor boosts for everyday meals",
            "how to read organic food labels when you shop",
            "simple whole-food breakfast ideas to start your day",
            "how to build a calming evening routine for better rest",
            "budget-friendly ways to eat more whole foods",
            "easy ways to drink more water through the day",
            "meal-prep basics for busy weeks",
            "seasonal vegetables and simple ways to enjoy them",
            "how to grow your own sprouts at home step by step",
            "easy plant-forward swaps for everyday cooking",
            "how to store fresh herbs so they last longer",
            "simple ways to add more colour to your plate",
            "gentle daily movement habits anyone can start",
            "cosy homemade herbal teas for a relaxing evening",
            "simple ways to reduce food waste in your kitchen",
            "mindful eating habits for calmer, happier mealtimes",
            "starting a small organic vegetable patch at home",
            "wholesome snack ideas made from simple ingredients",
        ],
        "search_keywords": ["healthy eating tips", "organic food", "herb garden", "whole foods",
                            "meal prep", "healthy habits", "cooking with herbs", "organic living"],
        "pexels_queries": ["fresh herbs", "healthy food preparation", "organic garden",
                           "colorful vegetables", "herbal tea", "farmers market", "meal prep", "home kitchen cooking"],
        "hashtags": ["#HealthyEating", "#OrganicLiving", "#HerbGarden", "#WholeFoods",
                     "#HealthyHabits", "#CleanEating", "#EatTheRainbow", "#HealthyLifestyle", "#Wellness", "#HomeCooking"],
        "cpm_estimate": 14,
        "generate_charts": False,
        "edge_voice": "en-US-AriaNeural",  # Warm, calm, friendly female voice
    },
    "blissful_moments": {
        "name": "Mzansi Baby Stars - Parenting & Family Joy",
        "topics_bank": [
            "baby sleep tips that actually work for new parents",
            "fun learning activities for toddlers at home",
            "how to handle toddler tantrums with patience",
            "best first foods for South African babies",
            "affordable baby essentials every SA parent needs",
            "milestones your baby should reach by 12 months",
            "simple homemade baby food recipes",
            "how to create a safe play area at home",
            "signs your baby is ready for solids",
            "bonding activities for dad and baby",
            "how to soothe a colicky baby naturally",
            "fun sensory play ideas for babies under 1",
            "teaching your toddler to share and be kind",
            "best educational toys for South African toddlers",
            "how to make bath time fun and safe",
        ],
        "search_keywords": ["baby tips", "parenting", "toddler", "new parent", "baby milestones", "family", "South African baby"],
        "pexels_queries": ["baby playing", "mother baby", "toddler learning", "family home", "baby sleeping", "parent child", "baby food", "happy family"],
        "hashtags": ["#MzansiBabyStars", "#Parenting", "#BabyTips", "#NewMom", "#NewDad", "#SAParent", "#ToddlerLife", "#BabyMilestones", "#FamilyLove", "#MzansiFamily"],
        "cpm_estimate": 8,
        "generate_charts": False,
        "edge_voice": "en-US-AriaNeural",
    },
    "daily_breakdown": {
        "name": "Proudly South African - Mzansi Daily",
        "topics_bank": [
            "South Africa trending news today what everyone is talking about",
            "top reasons why South Africa is the best country in the world",
            "beautiful places in South Africa you must visit",
            "South African entrepreneurs making the country proud",
            "best South African food recipes the world loves",
            "South Africa sports heroes who inspire the nation",
            "young South Africans doing amazing things right now",
            "South African music taking over the world amapiano",
            "why tourists fall in love with South Africa",
            "South African inventions the world does not know about",
            "Cape Town voted best city again here is why",
            "South Africa wildlife and nature that will blow your mind",
            "Johannesburg the city of gold is rising",
            "South African slang words every mzansi person knows",
            "Durban beaches and culture that make it special",
            "proudly South African brands going global",
            "real South Africa stories of hope and resilience",
            "braai culture why South Africans do it best",
            "South African fashion designers making waves internationally",
            "beauty of South African traditional cultures and heritage",
            "South Africa renewable energy leading Africa",
            "how South Africans solve problems with innovation",
            "Nelson Mandela legacy still inspiring the world",
            "South Africa crime safety tips that actually work",
            "cost of living in South Africa tips to save money",
        ],
        "search_keywords": ["South Africa", "Mzansi", "SA news", "proudly South African", "Cape Town", "Johannesburg", "Durban", "SA trending"],
        "pexels_queries": ["South Africa", "Cape Town", "Johannesburg skyline", "African sunset", "safari animals", "Table Mountain", "beach Durban", "African food", "African dance", "South African flag", "African market", "braai", "African family", "African nature"],
        "hashtags": ["#SouthAfrica", "#Mzansi", "#ProudlySouthAfrican", "#SA", "#CapeTown", "#Johannesburg", "#Durban", "#MzansiDaily", "#SAProud", "#WeAreSouthAfrica"],
        "cpm_estimate": 12,
        "generate_charts": False,
        "edge_voice": "en-US-GuyNeural",
    },
    "shopmo_products": {
        "name": "ShopMO - SA's Smartest Online Store",
        "topics_bank": [
            "best online shopping deals in South Africa today",
            "top 5 gadgets every South African needs in 2026",
            "unboxing the hottest products on ShopMO right now",
            "why South Africans are switching from Takealot to ShopMO",
            "affordable tech gadgets you can buy online in SA",
            "best wireless earbuds under R500 in South Africa",
            "ring light setup for content creators on a budget",
            "air fryer recipes and the best air fryer deals in SA",
            "smart watch vs fitness band which should you buy in SA",
            "home gym essentials you can order online in South Africa",
            "best skincare products available online in SA",
            "fast charger review the one accessory you need",
            "bluetooth speaker showdown best portable speakers SA",
            "yoga mat and resistance bands home workout starter kit",
            "vitamin C serum review best beauty products online SA",
            "car phone mount review best driving accessories",
            "water bottle comparison which one keeps water cold longest",
            "back to school essentials you can buy on ShopMO",
            "gift ideas under R300 from ShopMO South Africa",
            "flash sale alert massive discounts on ShopMO today",
            "how to save money shopping online in South Africa",
            "ShopMO vs Takealot which has better prices in SA",
            "free delivery shopping tips for South Africans",
            "trending products South Africans are buying right now",
            "must have kitchen gadgets under R1000 in South Africa",
            "the ultimate guide to online shopping in South Africa 2026",
            "product review electronics worth buying on ShopMO",
            "beauty and health products every South African woman needs",
            "sports and fitness gear deals you cannot miss",
            "fashion accessories trending in South Africa right now",
        ],
        "search_keywords": ["online shopping South Africa", "best deals SA", "buy online SA", "gadgets South Africa", "affordable tech SA", "ShopMO deals", "South Africa e-commerce"],
        "pexels_queries": ["online shopping", "unboxing", "tech gadgets", "beauty products", "fitness equipment", "kitchen appliances", "smartphone accessories", "happy customer", "delivery package", "south africa city", "shopping bags", "product review"],
        "hashtags": ["#ShopMO", "#OnlineShoppingSA", "#SouthAfrica", "#DealsOfTheDay", "#ShopOnline", "#AffordableGadgets", "#SADeals", "#TrendingProducts", "#FreeDelivery", "#ShopMODeals", "#BuyOnlineSA", "#EcommerceSA"],
        "cpm_estimate": 12,
        "generate_charts": False,
        "edge_voice": "en-US-AriaNeural",  # Warm female voice — engaging for product reviews
    },
    "limitless_you": {
        "name": "Africa 2050 - Innovation & Progress",
        "topics_bank": [
            "African startups solving problems the world ignores",
            "how Kenya became the world leader in mobile money",
            "South Africa solar energy revolution powering millions",
            "young African entrepreneurs building billion dollar companies",
            "how Rwanda became the cleanest country in Africa",
            "African tech hubs creating jobs for the next generation",
            "the African free trade agreement changing the continent",
            "how Nigeria fintech is banking the unbanked millions",
            "African farmers using drones and AI to grow more food",
            "the new African railway connecting countries and creating trade",
            "how African women entrepreneurs are leading innovation",
            "electric vehicles made in Africa for African roads",
            "African universities training the next generation of innovators",
            "how coding bootcamps are creating tech talent across Africa",
            "green energy projects transforming rural African communities",
        ],
        "search_keywords": ["Africa innovation", "African startups", "Africa technology", "African entrepreneurs", "Africa progress", "Africa development"],
        "pexels_queries": ["Africa city", "African entrepreneur", "solar panels Africa", "African technology", "African market", "African youth", "African skyline", "farming Africa", "African innovation"],
        "hashtags": ["#Africa2050", "#AfricanInnovation", "#AfricaRising", "#AfricanStartups", "#ProudlyAfrican", "#AfricaTech", "#AfricanYouth", "#AfricaProgress", "#BuildAfrica", "#AfricanDream"],
        "cpm_estimate": 11,
        "generate_charts": False,
        "edge_voice": "en-US-ChristopherNeural",
    },
}

# ══════════════════════════════════════════════════════════════
# QUALITY OVER QUANTITY — 1 video per niche per day
# ══════════════════════════════════════════════════════════════
# 1 build slot per day. Each video must be genuinely helpful,
# practical, and educational. No clickbait. No flooding.
# ══════════════════════════════════════════════════════════════

# SINGLE-PAGE MODE: only build/post for these niches. Focus is Tech Pulse Africa
# (South African news since 2026-08-28). Set BUILD_NICHES="tech_news,ai_money"
# etc. to add pages back.
BUILD_NICHES = [n.strip() for n in os.getenv("BUILD_NICHES", "tech_news").split(",") if n.strip()]

# ── LOCKED PAGES ──────────────────────────────────────────────
# A locked page belongs to exactly ONE poster script. Every other pipeline
# (main build/upload, engagement posts, blog promo, cross-promo, Zuzu, graphic
# reels) must skip it — no reels, no photos, no feed links.
#   blissful_moments (page 112465853843545) = SAGA OF THE NORTH (Vikings),
#   posted only by post_next_viking.py.
LOCKED_PAGES = {
    "blissful_moments": "post_next_viking.py",
    # Elevate You is now MZANSI CAREERS — verified SA jobs only. Generic
    # motivation/engagement content must never land on a careers page.
    "motivation": "build_careers_post.py",
}


def page_locked(niche: str) -> bool:
    """True if this page is reserved for another poster than the running one.

    The owning script declares itself with PAGE_LOCK_OWNER (see post_next_viking.py);
    everyone else gets True and must skip the page.
    """
    owner = LOCKED_PAGES.get(niche)
    if not owner:
        return False
    running = os.getenv("PAGE_LOCK_OWNER", "")
    # Owner-authorised exception (2026-08-20): a single local-format test on
    # the SAGA page, to measure South African content against its 226-view
    # baseline. Listed explicitly so the lock is never quietly bypassed.
    if niche == "blissful_moments" and running == "build_local_test.py":
        return False
    return running != owner


SCHEDULE = {
    "ai_money": {"short": 1},           # Smart Money AI (4.4K followers)
    "tech_news": {"short": 1},          # Tech Pulse Africa (10.4K followers) — South African news
    # motivation: LOCKED to MZANSI CAREERS — see LOCKED_PAGES / build_careers_post.py
    "health_wellness": {"short": 1},    # Herbal Organic Life (920 followers)
    # blissful_moments: LOCKED to SAGA OF THE NORTH — see LOCKED_PAGES / post_next_viking.py
    "daily_breakdown": {"short": 1},    # Mzansi Daily — Proudly South African (needs FB page)
    "limitless_you": {"short": 1},      # Africa 2050 (209 followers)
    # Genesis News — PSL & Mzansi Football. Without this entry main.py falls back to
    # {"short": 2}, which would fire SIX reels a day at the page across the 3 slots.
    "sa_pulse": {"short": 1},           # Genesis News — PSL (Chiefs/Pirates/Sundowns)
    # shopmo_products: NO FB page — disabled
}

# Active niches for the viral shorts pipeline
VIRAL_SHORTS_NICHES = list(SCHEDULE.keys())

# ── Platform-Specific Rules (from research) ───────────────────
# YouTube Shorts: NO music → keep full 45% creator revenue (music splits with publishers)
# TikTok: USE trending sounds → boosts For You Page placement
# Instagram Reels: Music optional, watch time is #1 factor
# Facebook Reels: Music optional, originality score matters most
PLATFORM_MUSIC_RULES = {
    "youtube_shorts": False,     # NO music — keep full revenue share
    "tiktok": True,              # Music boosts FYP placement
    "instagram_reels": True,     # Music helps engagement
    "facebook_reels": True,      # Music helps but originality matters more
}

# ── EU AI Act Compliance (Aug 2, 2026 deadline) ──────────────
# All AI-generated content must be labeled in machine-readable format
AI_DISCLOSURE_TEXT = "Created with AI assistance"
AI_DISCLOSURE_HASHTAG = "#AIGenerated"
ENABLE_AI_DISCLOSURE = True  # Adds disclosure to captions + video watermark

# ── Facebook Engagement Posts (images + text between videos) ──
ENABLE_ENGAGEMENT_POSTS = os.getenv("ENABLE_ENGAGEMENT_POSTS", "true").lower() in ("true", "1", "yes")
# When true, the engagement slots post a ROTATING BLOG LINK to each page (drives
# traffic to our owned blog = SEO + AdSense) INSTEAD of standalone tip images.
ENABLE_BLOG_PROMO = os.getenv("ENABLE_BLOG_PROMO", "true").lower() in ("true", "1", "yes")
ENGAGEMENT_POSTS_PER_DAY = int(os.getenv("ENGAGEMENT_POSTS_PER_DAY", "2"))
ENGAGEMENT_HOURS = [10, 15]  # 2 slots: morning + afternoon (quality over quantity)
ENGAGEMENT_CONTENT_TYPES = ["tip", "advice"]  # Helpful content only

# ShopMO branding — always show logo and website on ShopMO content
SHOPMO_LOGO_PATH = ASSETS_DIR / "logos" / "shopmo_logo.png"

# ── Affiliate Links (auto-inserted in descriptions) ───────────
AFFILIATE_LINKS = {
    "traderadar": "https://www.gettraderadar.com",
    "shopmo": "https://shopmoo.co.za",
    "tradingview": "https://www.tradingview.com/?aff_id=YOUR_ID",
    "binance": "https://accounts.binance.com/register?ref=YOUR_ID",
    "3commas": "https://3commas.io/?c=YOUR_ID",
    "elevenlabs": "https://elevenlabs.io/?ref=YOUR_ID",
    "midjourney": "https://midjourney.com",
    "chatgpt": "https://chat.openai.com",
}

# ── Our Products (always promoted, not affiliate) ─────────────
OUR_PRODUCTS = {
    "traderadar": {
        "name": "TradeRadar AI",
        "url": "https://www.gettraderadar.com",
        "tagline": "Free AI-powered stock analysis — plain English, no jargon",
        "cta": "Try TradeRadar AI FREE",
        "niches": ["ai_money"],  # Which niches promote this
        "hashtags": ["#TradeRadarAI", "#AITrading", "#StockAnalysis"],
    },
    "shopmo": {
        "name": "ShopMO",
        "url": "https://shopmoo.co.za",
        "tagline": "South Africa's smartest online store — 127+ trending products, free delivery over R500",
        "cta": "Shop now at ShopMO",
        "niches": ["shopmo_products"],
        "hashtags": ["#ShopMO", "#OnlineShoppingSA", "#ShopOnlineSA", "#SADeals"],
    },
}

# ── Product CTA Templates (inserted in video descriptions) ────
PRODUCT_CTA_TEMPLATES = {
    "ai_money": [
        "🤖 FREE AI tool that analyzes stocks for you — TradeRadar AI\n👉 https://www.gettraderadar.com",
        "💰 Want to make smarter investment decisions? Try TradeRadar AI FREE\n👉 https://www.gettraderadar.com",
        "📈 AI-powered market intelligence — completely FREE to start\n👉 https://www.gettraderadar.com",
    ],
    "shopmo_products": [
        "🛒 Shop 127+ trending products at ShopMO — SA's smartest online store!\n🚚 FREE delivery over R500\n👉 https://shopmoo.co.za",
        "🔥 Massive deals on electronics, fashion & more — only at ShopMO!\n💳 Secure Yoco payments | Fast SA delivery\n👉 https://shopmoo.co.za",
        "🇿🇦 South Africa's #1 smart shopping destination — ShopMO\n✅ Free delivery over R500 | Same-day dispatch\n👉 https://shopmoo.co.za",
        "💰 Why pay more? ShopMO has the best prices in SA!\n🛍️ Electronics, beauty, fitness & more\n👉 https://shopmoo.co.za",
        "⚡ Flash deals dropping daily at ShopMO!\n🔥 Don't miss out — shop now before they're gone\n👉 https://shopmoo.co.za/deals",
        "🎁 Looking for the perfect gift? ShopMO has 127+ options!\n🚚 Free delivery over R500 across South Africa\n👉 https://shopmoo.co.za",
        "📱 Best tech gadgets at unbeatable prices — ShopMO\n🇿🇦 Proudly South African | Secure payments\n👉 https://shopmoo.co.za/categories/electronics",
    ],
}

# ── YouTube API ────────────────────────────────────────────────
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",             # Full access (matches existing tokens)
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",   # Captions + comments
]
YOUTUBE_API_VERSION = "v3"
YOUTUBE_CATEGORY_SCIENCE_TECH = "28"
YOUTUBE_CATEGORY_EDUCATION = "27"
YOUTUBE_CATEGORY_HOWTO = "26"
YOUTUBE_CATEGORY_NEWS = "25"

YOUTUBE_CATEGORY_ENTERTAINMENT = "24"

NICHE_YOUTUBE_CATEGORY = {
    "ai_money": YOUTUBE_CATEGORY_HOWTO,
    "tech_news": YOUTUBE_CATEGORY_SCIENCE_TECH,
    "motivation": YOUTUBE_CATEGORY_EDUCATION,
    "health_wellness": YOUTUBE_CATEGORY_HOWTO,
    "blissful_moments": YOUTUBE_CATEGORY_ENTERTAINMENT,
    "daily_breakdown": YOUTUBE_CATEGORY_NEWS,
    "shopmo_products": YOUTUBE_CATEGORY_HOWTO,  # Product reviews = How-to
}

# ── Growth Engine Settings ──────────────────────────────────
ENABLE_GROWTH_ENGINE = os.getenv("ENABLE_GROWTH_ENGINE", "true").lower() in ("true", "1", "yes")
COMMUNITY_REPLY_MAX_PER_HOUR = int(os.getenv("COMMUNITY_REPLY_MAX_PER_HOUR", "10"))
COMMUNITY_CHECK_HOURS = [8, 10, 12, 14, 16, 18, 20]
INSIGHTS_COLLECTION_HOUR = 6
CROSS_PROMO_HOUR = 11
GROWTH_REPORT_HOUR = 22

# Active niches for growth engine (those with FB page ID + token)
GROWTH_NICHES = [
    "ai_money", "tech_news", "motivation",
    "health_wellness", "limitless_you",
    # blissful_moments excluded — locked to SAGA OF THE NORTH (post_next_viking.py)
]

# Page display names (shared across growth modules)
NICHE_PAGE_NAMES = {
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "SAGA OF THE NORTH",
    "daily_breakdown": "The Daily Breakdown",
    "shopmo_products": "ShopMO",
    "limitless_you": "Limitless You",
}
