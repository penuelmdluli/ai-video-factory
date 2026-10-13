"""TradeRadar is the ONLY product the owner's videos and comments promote (owner, 2026-10-12: "to all our video from
now on we fully market TradeRadar nothing else"). iVideo Studio is retired from end cards, captions, CTA comments,
seed comments and community replies.

Self-contained (no traderadar-ai imports) so the cloud reels kit can run it too. Mirrors
traderadar-ai/content/pages/tr_promo.py.

Compliance (FAIS): no profit / pips / win-rate claims, no trade calls, "Analysis, not advice" wherever markets are
mentioned, never "passive income". Reply lines avoid buy/sell/long/short/entry/stop/target/profit/signal words.
"""
from __future__ import annotations

import re

SITE = "gettraderadar.com"
BASE = f"https://{SITE}"
DISCLAIMER = "Analysis, not advice."

# niche (ai-video-factory FB_PAGE_TOKEN_<niche>) -> topic
NICHE_TOPIC = {
    "sa_pulse": "sport", "genesis": "sport",
    "tech_news": "news", "blissful_moments": "news",
    "mzansi_baby": "parents", "health_wellness": "herbal", "motivation": "news", "limitless_you": "news",
    "ai_money": "money", "profile": "general", "repost": "general",
}

HOOKS = {
    "sport": "📈 Off the pitch, the rand never rests. See gold, USD/ZAR and the markets read by AI, free to start",
    "news": "📈 Rand moving on this news? See gold, USD/ZAR and the markets read by AI, free to start",
    "parents": "📈 Fees, groceries, petrol: it all follows the rand. Track USD/ZAR and gold free with TradeRadar",
    "herbal": "📈 Shelf prices follow the rand. Track USD/ZAR and gold free with TradeRadar",
    "money": "📊 Market Lens: an AI that reads the market for you. Free account, R49 for your first week of full access",
    "general": "📈 Track gold, the rand and the markets free with TradeRadar, read by AI every day",
}


def topic(niche: str | None) -> str:
    return NICHE_TOPIC.get(niche or "", "general")


# utm_source per page (matches traderadar-ai pages.json utm_source so GA groups both pipelines per page)
NICHE_SOURCE = {"sa_pulse": "genesis_news", "genesis": "genesis_news", "tech_news": "tech_pulse_africa"}


def url(niche: str | None, medium: str, campaign: str, source: str | None = None) -> str:
    source = source or NICHE_SOURCE.get(niche or "", "facebook")
    path = "/lens" if topic(niche) == "money" else "/"
    return (f"{BASE}{path}?utm_source={source}&utm_medium={medium}&utm_campaign={campaign[:60]}"
            f"&utm_content={niche or 'page'}")


def cta_comment(niche: str | None, medium: str = "comment", campaign: str | None = None) -> str:
    """First comment under a video: hook + benefit + one UTM link + the compliance line."""
    return (f"{HOOKS.get(topic(niche), HOOKS['general'])} 👉 {url(niche, medium, campaign or niche or 'video')}\n"
            f"({DISCLAIMER} Trading involves risk.)")


def caption_cta(niche: str | None, medium: str = "profile", campaign: str = "brand") -> str:
    """The line appended to a caption (personal profile / reposts)."""
    return (f"📈 Track gold, the rand and the markets free with TradeRadar 👉 {url(niche, medium, campaign)}\n"
            f"({DISCLAIMER})\n#TradeRadar #Mzansi")


SEED_COMMENTS = [  # first comment on reels (profile / dance / reposts)
    "📈 Between reels: TradeRadar tracks gold, the rand and the markets free 👉 {url} (Analysis, not advice.)",
    "Rand check 👀 TradeRadar reads gold and USD/ZAR every day, free 👉 {url} (Analysis, not advice.)",
    "📊 Free daily market read on gold and the rand, made in Mzansi 👉 {url} (Analysis, not advice.)",
    "Keeping an eye on the rand? TradeRadar does it free 👉 {url} (Analysis, not advice.)",
]

REPLY_POOL = {
    "sport": ["Between games we keep an eye on the rand on TradeRadar, free to try.",
              "Off the field, TradeRadar shows how the rand and gold are moving, free.",
              "Fun fact: our admin checks gold and the rand on TradeRadar at half-time.",
              "When the match is done, TradeRadar has the rand and gold read by AI, free.",
              "Big games move moods, the rand moves prices: TradeRadar tracks it free."],
    "news": ["News like this can move the rand. TradeRadar tracks it free.",
             "If you watch how news hits the rand and gold, TradeRadar reads it daily, free.",
             "We follow the rand on TradeRadar when stories like this break, free to try.",
             "Curious how this lands on the rand? TradeRadar shows it, free to start.",
             "TradeRadar puts gold, USD/ZAR and the markets in one free daily read."],
    "money": ["TradeRadar's free Market Lens shows what moved the market today.",
              "For the daily market read, Market Lens on TradeRadar is free to start.",
              "If you like the bigger picture, TradeRadar's Market Lens lays it out daily, free.",
              "TradeRadar shows gold, USD/ZAR and the majors in one free daily read."],
    "parents": ["Household costs follow the rand: TradeRadar tracks it free.",
                "Fees and petrol follow the rand, and TradeRadar shows it daily, free.",
                "TradeRadar keeps an eye on the rand for you, free to start."],
    "herbal": ["Shelf prices follow the rand: TradeRadar tracks it free.",
               "Curious why imported goods cost more? TradeRadar shows the rand daily, free.",
               "TradeRadar puts the rand and gold in one free daily read."],
}
REPLY_GENERAL = [
    "By the way, TradeRadar tracks gold, the rand and the markets free.",
    "Psst: TradeRadar reads gold and USD/ZAR for you every day, free to start.",
    "Side note: our team uses TradeRadar to keep an eye on the rand. Free to try.",
    "Also worth a look: TradeRadar, a free daily read on gold and the rand.",
    "TradeRadar shows what the rand and gold are doing today, free.",
    "If you follow the rand, TradeRadar has it read by AI, free to start.",
    "Quick tip: TradeRadar puts gold, the rand and the markets in one place, free.",
    "One more thing: TradeRadar's free daily market read is made right here in Mzansi.",
    "Keeping an eye on the rand? TradeRadar does it free.",
    "TradeRadar is our free AI read on gold, USD/ZAR and the markets.",
    "Our sister app TradeRadar tracks the rand and gold daily, free to try.",
    "TradeRadar: gold, the rand and the markets, read by AI every day, free.",
    "Fun fact: the rand moves every day, and TradeRadar shows you how, free.",
    "Curious where gold is today? TradeRadar has the free daily read.",
    "Made in Mzansi: TradeRadar's free AI read on the rand and gold.",
]


def reply_pool(niche: str | None) -> list[str]:
    return REPLY_POOL.get(topic(niche), []) + REPLY_GENERAL


def reply_mention(niche: str | None, n: int) -> str:
    pool = reply_pool(niche)
    return f"{pool[(n * 7) % len(pool)]} {url(niche, 'fan_reply', 'community_reply')} ({DISCLAIMER})"


def mention_due(reply_count: int) -> bool:
    """Every 2nd-3rd reply, never every reply: replies 0, 2, 5, 7, 10, 12 ... (gaps 2, 3, 2, 3)."""
    return reply_count % 5 in (0, 2)


BANNED_COPY = re.compile(r"passive income|guarantee|profit|win[\s-]?rate|\bpips?\b|\bsignals?\b|ivideo", re.I)
