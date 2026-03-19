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
VIRAL_SCORE_THRESHOLD = float(os.getenv("VIRAL_SCORE_THRESHOLD", "35"))
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
FB_PAGE_ID_AI_TRADING = os.getenv("FB_PAGE_ID_ai_trading", "")
FB_PAGE_TOKEN_AI_TRADING = os.getenv("FB_PAGE_TOKEN_ai_trading", "")
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
    "ai_trading": {
        "user_id": os.getenv("IG_USER_ID_ai_trading", os.getenv("INSTAGRAM_USER_ID", "")),
        "access_token": os.getenv("IG_TOKEN_ai_trading", os.getenv("INSTAGRAM_ACCESS_TOKEN", "")),
    },
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
VOICE_YOUTUBE_LONG = os.getenv("DEFAULT_VOICE_YOUTUBE", "elevenlabs")
VOICE_SHORTS = os.getenv("DEFAULT_VOICE_SHORTS", "edge-tts")

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

# ── Video Settings ─────────────────────────────────────────────
VIDEO_SETTINGS = {
    "youtube_long": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "duration_target": 480,  # ~8 minutes target
        "aspect": "16:9",
    },
    "youtube_shorts": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 55,  # under 60 seconds
        "aspect": "9:16",
    },
    "tiktok": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 45,  # sweet spot 30-60 sec
        "aspect": "9:16",
    },
    "instagram_reels": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 30,  # 15-45 sec sweet spot
        "aspect": "9:16",
    },
    # ── News Anchor Format (Daily Breakdown) ──
    "news_anchor_short": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 60,   # 45-75 sec sweet spot for news clips
        "aspect": "9:16",
    },
    # ── Podcast Split-Screen Format ──
    "podcast_short": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_target": 90,   # 60-120 sec debates
        "aspect": "9:16",
    },
    "podcast_long": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "duration_target": 300,  # 3-5 min longer debates
        "aspect": "16:9",
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
CAPTION_FONT_SIZE = 64  # Large karaoke-style
CAPTION_MAX_WORDS = 4   # Short punchy phrases (4 words for readability)
CAPTION_FONT_COLOR = "white"
CAPTION_STROKE_COLOR = "black"
CAPTION_STROKE_WIDTH = 3
CAPTION_BG_OPACITY = 0.65
CAPTION_POSITION = ("center", "bottom")

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
# SFX decoupled from voice — can use cached SFX even without ElevenLabs
ENABLE_SFX = True  # Always try SFX; will use cached files or skip gracefully
TRANSITION_DURATION = 0.4
KEN_BURNS_ZOOM_RANGE = (1.0, 1.50)  # Cinematic zoom (was 1.20, now 1.50 for stronger effect)

# ── Talking Head Avatar APIs ─────────────────────────────────
# D-ID (primary) — Lite plan: 400 credits/month
DID_API_KEY = os.getenv("DID_API_KEY", "")
DID_AVATAR_IMAGE_URL = os.getenv("DID_AVATAR_IMAGE_URL", "")
# HeyGen (fallback) — alternative talking head API
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
# Local avatar (FREE — Wav2Lip + audio-reactive, no API needed)
LOCAL_AVATAR_ENABLED = os.getenv("LOCAL_AVATAR_ENABLED", "true").lower() in ("true", "1", "yes")
LOCAL_AVATAR_PREFER_GPU = os.getenv("LOCAL_AVATAR_PREFER_GPU", "true").lower() in ("true", "1", "yes")
ENABLE_AVATAR = bool(DID_API_KEY) or bool(HEYGEN_API_KEY) or LOCAL_AVATAR_ENABLED
# Viseme sprite library (D-ID quality, zero ongoing cost after initial generation)
VISEME_SPRITES_DIR = Path(__file__).parent / "assets" / "viseme_sprites"
VISEME_SPRITES_ENABLED = os.getenv("VISEME_SPRITES_ENABLED", "false").lower() in ("true", "1", "yes")
SFX_CACHE_DIR = ASSETS_DIR / "sfx_cache"

# ── Niche Configurations ──────────────────────────────────────
NICHES = {
    "ai_trading": {
        "name": "AI Trading & Markets",
        "topics_bank": [
            "AI trading bot results today",
            "stock market AI prediction",
            "crypto AI analysis today",
            "best AI trading strategies",
            "AI vs human traders",
            "automated trading results",
            "AI market analysis daily",
            "top stocks AI recommends",
            "crypto market AI signals",
            "forex AI trading bot",
            "AI portfolio management",
            "day trading with AI bots",
            "swing trading AI strategy",
            "AI predicts market crash",
            "AI identifies breakout stocks",
            "I let AI analyze 50 stocks and found these hidden gems",
            "This FREE AI tool explains any stock in plain English",
            "AI stock analysis that actually makes sense for beginners",
            "How AI reads the market better than most traders",
            "Stop guessing — let AI analyze your stocks for free",
            "AI just flagged these 3 stocks as breakout candidates",
            "The AI stock analyzer Wall Street doesn't want you to know about",
        ],
        "search_keywords": ["AI trading", "stock market", "crypto", "trading bot", "algorithm trading", "AI stock analysis"],
        "pexels_queries": ["stock market", "trading", "cryptocurrency", "finance chart", "stock exchange", "money growth", "business graph", "data analysis"],
        "hashtags": ["#AITrading", "#StockMarket", "#Crypto", "#Trading", "#DayTrading", "#AI", "#Finance", "#Investing", "#TradingBot", "#Stocks", "#TradeRadarAI", "#AIStockAnalysis"],
        "cpm_estimate": 22,
        "generate_charts": True,
        "chart_symbols": ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "BTC-USD", "ETH-USD"],
        "edge_voice": "en-US-JennyNeural",  # Female — matches D-ID Alice avatar
    },
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
        "name": "AI & Tech News",
        "topics_bank": [
            "biggest AI news today",
            "new AI tool just launched",
            "AI breakthrough this week",
            "tech company AI announcement",
            "AI regulation update",
            "AI replaces jobs update",
            "new robot AI technology",
            "AI in healthcare breakthrough",
            "AI startup raised millions",
            "AI vs AI competition results",
            "new AI model released",
            "AI safety research update",
            "tech layoffs AI impact",
            "AI in education changes",
            "future of AI prediction",
        ],
        "search_keywords": ["AI news", "tech news", "artificial intelligence", "AI update", "technology breakthrough"],
        "pexels_queries": ["technology", "artificial intelligence", "robot", "computer", "futuristic", "innovation", "circuit board", "coding", "server room", "data center"],
        "hashtags": ["#AI", "#TechNews", "#ArtificialIntelligence", "#Technology", "#AINews", "#Innovation", "#FutureTech", "#MachineLearning", "#Tech", "#AIUpdate"],
        "cpm_estimate": 12,
        "generate_charts": False,
        "edge_voice": "en-GB-SoniaNeural",
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
        "name": "Health & Wellness AI",
        "topics_bank": [
            "AI discovers new health benefit",
            "foods that boost brain power",
            "morning routine for longevity",
            "natural remedies backed by science",
            "AI analyzes best diet for health",
            "sleep optimization tips science",
            "gut health impacts everything",
            "anti aging foods you should eat",
            "herbs that heal naturally",
            "water fasting health benefits",
            "AI reveals exercise secrets",
            "stress relief techniques that work",
            "superfoods to eat every day",
            "how to detox your body naturally",
            "mental health daily practices",
        ],
        "search_keywords": ["health tips", "wellness", "natural remedies", "healthy living", "nutrition science"],
        "pexels_queries": ["healthy food", "yoga", "meditation", "herbs", "nature", "wellness", "green smoothie", "exercise", "organic", "peaceful", "fruits vegetables"],
        "hashtags": ["#Health", "#Wellness", "#HealthyLiving", "#NaturalRemedies", "#Nutrition", "#Fitness", "#MentalHealth", "#Organic", "#HealthTips", "#SelfCare"],
        "cpm_estimate": 14,
        "generate_charts": False,
        "edge_voice": "en-US-AriaNeural",  # Warm female voice — soothing for health content
    },
    "blissful_moments": {
        "name": "Blissful Moments - Positivity & Inspiration",
        "topics_bank": [
            "beautiful moments that restore your faith in humanity",
            "simple joys that make life worth living",
            "heartwarming stories that will make your day",
            "finding peace in everyday moments",
            "gratitude practice that changes everything",
            "small acts of kindness with big impact",
            "mindfulness moments for inner peace",
            "positive affirmations for a beautiful day",
            "life lessons from nature and animals",
            "feel good stories from around the world",
            "how to find happiness in simple things",
            "calming moments for stress relief",
            "inspiring stories of human kindness",
            "creating joy in your daily routine",
            "blissful moments that heal the soul",
        ],
        "search_keywords": ["positivity", "inspiration", "happiness", "mindfulness", "gratitude", "feel good"],
        "pexels_queries": ["sunset", "nature beauty", "happy people", "flowers", "peaceful", "ocean waves", "butterfly", "golden hour", "smiling", "waterfall", "forest", "calm"],
        "hashtags": ["#BlissfulMoments", "#Positivity", "#Inspiration", "#Happiness", "#Gratitude", "#Mindfulness", "#PeaceOfMind", "#FeelGood", "#InnerPeace", "#BeautifulLife"],
        "cpm_estimate": 8,
        "generate_charts": False,
        "edge_voice": "en-US-AriaNeural",  # Warm female voice — soothing for positivity content
    },
    "daily_breakdown": {
        "name": "The Daily Breakdown - News Analysis",
        "topics_bank": [
            "Iran nuclear tensions latest developments",
            "South Africa political crisis update",
            "global economic outlook this week",
            "Middle East conflict analysis",
            "Africa rising: economic growth stories",
            "world leaders meeting at summit",
            "sanctions impact on global trade",
            "refugee crisis update worldwide",
            "climate change affecting developing nations",
            "technology in modern warfare",
            "South Africa energy crisis and solutions",
            "Iran diplomatic negotiations breakdown",
            "global food security concerns",
            "Africa infrastructure development boom",
            "world news that mainstream media ignores",
            "geopolitical shifts reshaping the world order",
            "breaking news analysis and what it means for you",
            "South Africa crime and safety update",
            "Iran Israel tensions escalating",
            "what is really happening in the world right now",
        ],
        "search_keywords": ["world news", "Iran news", "South Africa news", "breaking news", "geopolitics", "Africa news"],
        "pexels_queries": ["news broadcast", "world map", "political meeting", "press conference", "city skyline", "protest crowd", "parliament building", "military", "diplomacy", "african city"],
        "hashtags": ["#DailyBreakdown", "#NewsAnalysis", "#WorldNews", "#BreakingNews", "#Iran", "#SouthAfrica", "#Africa", "#Geopolitics", "#NewsUpdate", "#CurrentEvents"],
        "cpm_estimate": 15,
        "generate_charts": False,
        "edge_voice": "en-US-GuyNeural",  # Deep male voice — authoritative for news
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
        "name": "Limitless You - AI-Powered Self Improvement",
        "topics_bank": [
            "AI analyzed 10000 morning routines and found this one habit matters most",
            "AI scanned every productivity study from the last decade here is what actually works",
            "we fed 5000 success stories into AI and found the one pattern they all share",
            "AI reveals the exact minute your willpower dies each day and how to fix it",
            "the neuroscience of habit formation what AI found in 300 brain studies",
            "AI tracked 1000 people who quit social media for 30 days here is what happened",
            "why AI says your goals are failing and the scientific fix nobody talks about",
            "AI analyzed every self help book ever written these 3 rules actually work",
            "the 2 minute brain hack AI found in cognitive behavioral therapy research",
            "AI discovered why some people bounce back from failure and others don't",
            "we asked AI to design the perfect morning routine based on sleep science",
            "AI reveals the hidden cost of saying yes to everything backed by data",
            "the compound effect AI calculated exactly how small habits create massive results",
            "AI found the optimal learning technique that 95 percent of people ignore",
            "how AI coaches are replacing therapists for daily mindset training",
            "AI analyzed stoic philosophy and modern psychology here is where they agree",
            "the focus formula AI extracted from studying elite performers",
            "AI predicts your biggest obstacle to success based on behavioral patterns",
            "cold exposure vs meditation AI compared 200 studies to find the better habit",
            "AI decoded emotional intelligence into 5 trainable micro skills",
        ],
        "search_keywords": ["AI self improvement", "personal development science", "habit formation research", "mindset growth AI", "discipline neuroscience", "productivity data"],
        "pexels_queries": ["personal growth", "reading book", "meditation", "sunrise", "journal writing", "mountain climbing", "fitness", "focused person", "nature peace", "running athlete", "brain science", "data analysis", "AI technology"],
        "hashtags": ["#LimitlessYou", "#AICoach", "#SelfImprovement", "#PersonalGrowth", "#MindsetScience", "#Discipline", "#HabitScience", "#Productivity", "#GrowthMindset", "#AIWisdom", "#LevelUp", "#BecomeUnstoppable"],
        "cpm_estimate": 11,
        "generate_charts": False,
        "edge_voice": "en-US-ChristopherNeural",  # Deep male voice — authoritative for self-improvement
    },
}

# ── Schedule (videos per day per niche) ────────────────────────
SCHEDULE = {
    "ai_trading": {"long_form": 1, "shorts": 1, "podcast": 1},    # 3 videos/day
    "ai_money": {"long_form": 1, "shorts": 1, "podcast": 1},       # 3 videos/day
    "tech_news": {"long_form": 1, "shorts": 1, "podcast": 1},      # 3 videos/day
    "motivation": {"long_form": 1, "shorts": 1, "podcast": 1},     # 3 videos/day
    "health_wellness": {"long_form": 1, "shorts": 1, "podcast": 1}, # 3 videos/day
    "blissful_moments": {"long_form": 1, "shorts": 1, "podcast": 1}, # 3 videos/day — 58K followers!
    "daily_breakdown": {"shorts": 2},  # 2 news analysis clips/day
    "shopmo_products": {"long_form": 1, "shorts": 2},  # 1 product review + 2 shorts/day — pure sales machine
    "limitless_you": {"long_form": 1, "shorts": 1, "podcast": 1},  # 3 videos/day — self improvement
}

# ── Facebook Engagement Posts (images + text between videos) ──
ENABLE_ENGAGEMENT_POSTS = os.getenv("ENABLE_ENGAGEMENT_POSTS", "true").lower() in ("true", "1", "yes")
ENGAGEMENT_POSTS_PER_DAY = int(os.getenv("ENGAGEMENT_POSTS_PER_DAY", "5"))
ENGAGEMENT_HOURS = [9, 12, 15, 18, 21]  # 5 slots spread across the day
ENGAGEMENT_CONTENT_TYPES = ["quote", "tip", "fact", "poll", "mixed"]

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
        "niches": ["ai_trading", "ai_money"],  # Which niches promote this
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
    "ai_trading": [
        "🚀 Try TradeRadar AI — FREE AI stock analysis in plain English!\n👉 https://www.gettraderadar.com",
        "📊 Get AI-powered stock analysis FREE at TradeRadar AI\n👉 https://www.gettraderadar.com",
        "🤖 Want AI to analyze ANY stock for you? Try TradeRadar FREE!\n👉 https://www.gettraderadar.com",
        "💡 Stop guessing. Let AI analyze the market for you — FREE\n👉 https://www.gettraderadar.com",
        "⚡ TradeRadar AI: Your free AI trading analyst. No jargon, just insights.\n👉 https://www.gettraderadar.com",
    ],
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
    "ai_trading": YOUTUBE_CATEGORY_EDUCATION,
    "ai_money": YOUTUBE_CATEGORY_HOWTO,
    "tech_news": YOUTUBE_CATEGORY_SCIENCE_TECH,
    "motivation": YOUTUBE_CATEGORY_EDUCATION,
    "health_wellness": YOUTUBE_CATEGORY_HOWTO,
    "blissful_moments": YOUTUBE_CATEGORY_ENTERTAINMENT,
    "daily_breakdown": YOUTUBE_CATEGORY_NEWS,
    "shopmo_products": YOUTUBE_CATEGORY_HOWTO,  # Product reviews = How-to
}
