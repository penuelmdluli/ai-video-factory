"""
Affiliate Links & Monetization Manager for AI Video Factory.

Centralized management of affiliate links, digital products, trading signals,
and lead magnets across all niches. Used by uploaders and script writers to
append monetization CTAs to video descriptions.
"""

import random
from typing import Optional

# ---------------------------------------------------------------------------
# Affiliate links per niche (sorted by priority, 1 = highest)
# ---------------------------------------------------------------------------
NICHE_AFFILIATES = {
    "ai_trading": [
        {"name": "Binance", "url": "https://www.binance.com/en/activity/referral-entry/CPA?ref=CPA_00DZ0RGQX0", "commission_info": "Up to 50% lifetime trading fee commission", "priority": 1},
        {"name": "Vantage Markets", "url": "https://www.vantagemarkets.com/?cxd=51578_661448", "commission_info": "Up to $1,200 CPA per funded account", "priority": 2},
        {"name": "TradingView", "url": "https://www.tradingview.com/pricing/?share_your_love=traderadar", "commission_info": "Up to $15 per premium signup", "priority": 3},
        {"name": "Bybit", "url": "https://www.bybit.com/invite?ref=TRADERADAR", "commission_info": "30% trading fee commission", "priority": 4},
    ],
    "ai_money": [
        {"name": "Jasper AI", "url": "https://www.jasper.ai?fpr=traderadar", "commission_info": "30% recurring lifetime commission", "priority": 1},
        {"name": "Copy.ai", "url": "https://www.copy.ai?via=traderadar", "commission_info": "45% first-year commission", "priority": 2},
        {"name": "Hostinger", "url": "https://www.hostinger.com/special/traderadar", "commission_info": "Up to 60% per sale", "priority": 3},
        {"name": "Fiverr", "url": "https://go.fiverr.com/visit/?bta=XXXXX&brand=fiverrcpa", "commission_info": "Up to $150 CPA per first-time buyer", "priority": 4},
    ],
    "tech_news": [
        {"name": "NordVPN", "url": "https://go.nordvpn.net/aff_c?offer_id=15&aff_id=XXXXX", "commission_info": "$40-100 per sale, 30% recurring", "priority": 1},
        {"name": "Surfshark", "url": "https://surfshark.com/deal?coupon=TRADERADAR", "commission_info": "40% recurring commission", "priority": 2},
        {"name": "Amazon Tech", "url": "https://www.amazon.com/?tag=traderadar-20", "commission_info": "1-10% on all products, 24hr cookie", "priority": 3},
        {"name": "Udemy", "url": "https://click.linksynergy.com/fs-bin/click?id=XXXXX&offerid=507388", "commission_info": "15% per course sale", "priority": 4},
    ],
    "motivation": [
        {"name": "Audible", "url": "https://www.amazon.com/hz/audible/mlp?tag=traderadar-20", "commission_info": "$5 per free trial signup", "priority": 1},
        {"name": "Headspace", "url": "https://www.headspace.com/referral/TRADERADAR", "commission_info": "25% per subscription", "priority": 2},
        {"name": "Skillshare", "url": "https://skl.sh/traderadar", "commission_info": "$7 per free trial signup", "priority": 3},
        {"name": "Blinkist", "url": "https://www.blinkist.com/nc/partners/traderadar", "commission_info": "25% per subscription", "priority": 4},
    ],
    "health_wellness": [
        {"name": "iHerb", "url": "https://www.iherb.com/?rcode=TRADERADAR", "commission_info": "5-10% per order, 7-day cookie", "priority": 1},
        {"name": "Thrive Market", "url": "https://thrivemarket.com/share/traderadar", "commission_info": "$40 per membership signup", "priority": 2},
        {"name": "Athletic Greens", "url": "https://athleticgreens.com/en/partner/traderadar", "commission_info": "$20-50 per sale", "priority": 3},
        {"name": "Onnit", "url": "https://www.onnit.com/?a_aid=traderadar", "commission_info": "15% per sale", "priority": 4},
    ],
    "blissful_moments": [
        {"name": "Calm", "url": "https://www.calm.com/partner/traderadar", "commission_info": "30% per subscription", "priority": 1},
        {"name": "BetterHelp", "url": "https://www.betterhelp.com/traderadar", "commission_info": "$200+ per referral", "priority": 2},
        {"name": "Amazon Wellness", "url": "https://www.amazon.com/?tag=traderadar-20", "commission_info": "1-10% on all products, 24hr cookie", "priority": 3},
        {"name": "Yoga International", "url": "https://yogainternational.com/partner/traderadar", "commission_info": "30% per subscription", "priority": 4},
    ],
    "limitless_you": [
        {"name": "Mindvalley", "url": "https://www.mindvalley.com/partnerships?ref=traderadar", "commission_info": "30% per membership", "priority": 1},
        {"name": "Coursera", "url": "https://imp.i384100.net/traderadar", "commission_info": "15-45% per course/subscription", "priority": 2},
        {"name": "Tony Robbins Programs", "url": "https://www.tonyrobbins.com/?aff=traderadar", "commission_info": "15% per program sale", "priority": 3},
        {"name": "Skillshare", "url": "https://skl.sh/traderadar", "commission_info": "$7 per free trial signup", "priority": 4},
    ],
    "daily_breakdown": [
        {"name": "NordVPN", "url": "https://go.nordvpn.net/aff_c?offer_id=15&aff_id=XXXXX", "commission_info": "$40-100 per sale, 30% recurring", "priority": 1},
        {"name": "ExpressVPN", "url": "https://www.expressvpn.com/refer-a-friend/traderadar", "commission_info": "$13-36 per sale", "priority": 2},
        {"name": "Morning Brew", "url": "https://www.morningbrew.com/daily/r/?kid=TRADERADAR", "commission_info": "Reward tiers per referral", "priority": 3},
        {"name": "The Hustle", "url": "https://thehustle.co/?ambassador=traderadar", "commission_info": "Reward tiers per referral", "priority": 4},
    ],
    "shopmo_products": [
        {"name": "Amazon Associates", "url": "https://www.amazon.com/?tag=traderadar-20", "commission_info": "1-10% on all products, 24hr cookie", "priority": 1},
        {"name": "AliExpress", "url": "https://s.click.aliexpress.com/e/_TRADERADAR", "commission_info": "3-9% per sale", "priority": 2},
        {"name": "Shopify", "url": "https://shopify.pxf.io/traderadar", "commission_info": "$150 per paid merchant referral", "priority": 3},
        {"name": "Printful", "url": "https://www.printful.com/a/traderadar", "commission_info": "10% recurring commission", "priority": 4},
    ],
}

# ---------------------------------------------------------------------------
# Digital products per niche
# ---------------------------------------------------------------------------
NICHE_PRODUCTS = {
    "ai_trading": {
        "name": "AI Trading Starter Kit",
        "price": "$27",
        "url": "https://gettraderadar.com/products/trading-kit",
    },
    "ai_money": {
        "name": "100 AI Side Hustle Prompts",
        "price": "$17",
        "url": "https://gettraderadar.com/products/ai-prompts",
    },
    "tech_news": {
        "name": "Tech Career Pivot Guide",
        "price": "$37",
        "url": "https://gettraderadar.com/products/tech-guide",
    },
    "motivation": {
        "name": "90-Day Transformation Journal",
        "price": "$12",
        "url": "https://gettraderadar.com/products/journal",
    },
    "health_wellness": {
        "name": "Herbal Remedies Quick Guide",
        "price": "$17",
        "url": "https://gettraderadar.com/products/herbal-guide",
    },
    "blissful_moments": {
        "name": "Mindfulness Meditation Pack",
        "price": "$12",
        "url": "https://gettraderadar.com/products/meditation",
    },
    "limitless_you": {
        "name": "Limitless Mind Mastery Course",
        "price": "$97",
        "url": "https://gettraderadar.com/products/mind-mastery",
    },
    "daily_breakdown": {
        "name": "Daily Productivity System",
        "price": "$27",
        "url": "https://gettraderadar.com/products/productivity",
    },
    "shopmo_products": {
        "name": "Dropshipping Blueprint",
        "price": "$47",
        "url": "https://gettraderadar.com/products/dropship",
    },
}

# ---------------------------------------------------------------------------
# Trading signals config
# ---------------------------------------------------------------------------
TRADING_SIGNALS = {
    "url": "https://gettraderadar.com/signals",
    "price": "$47/month",
    "vip_price": "$97/month",
    "telegram": "https://t.me/beastmodetrading",
}

# ---------------------------------------------------------------------------
# Email lead magnets per niche
# ---------------------------------------------------------------------------
EMAIL_LEAD_MAGNETS = {
    "ai_trading": {
        "title": "Free AI Trading Cheat Sheet",
        "description": "Top 5 AI trading strategies that work in 2026",
        "signup_url": "https://gettraderadar.com/free/ai-trading",
    },
    "ai_money": {
        "title": "Free AI Money-Making Blueprint",
        "description": "7 proven ways to earn with AI tools today",
        "signup_url": "https://gettraderadar.com/free/ai-money",
    },
    "tech_news": {
        "title": "Free Tech Trends Report",
        "description": "The top 10 tech trends shaping the next decade",
        "signup_url": "https://gettraderadar.com/free/tech-news",
    },
    "motivation": {
        "title": "Free Morning Routine Planner",
        "description": "Build an unstoppable morning routine in 7 days",
        "signup_url": "https://gettraderadar.com/free/motivation",
    },
    "health_wellness": {
        "title": "Free Herbal Remedies Starter Guide",
        "description": "10 natural remedies you can start using today",
        "signup_url": "https://gettraderadar.com/free/health-wellness",
    },
    "blissful_moments": {
        "title": "Free 5-Minute Calm Meditation Audio",
        "description": "Instant stress relief guided meditation",
        "signup_url": "https://gettraderadar.com/free/blissful-moments",
    },
    "limitless_you": {
        "title": "Free Peak Performance Playbook",
        "description": "Unlock your full potential with these 5 mental models",
        "signup_url": "https://gettraderadar.com/free/limitless-you",
    },
    "daily_breakdown": {
        "title": "Free Daily News Digest Template",
        "description": "Stay informed in 5 minutes a day with this system",
        "signup_url": "https://gettraderadar.com/free/daily-breakdown",
    },
    "shopmo_products": {
        "title": "Free Product Research Toolkit",
        "description": "Find winning products before they go viral",
        "signup_url": "https://gettraderadar.com/free/shopmo-products",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_affiliate_links(niche: str, max_links: int = 3) -> str:
    """Return a formatted string of top affiliate links for a niche.

    Links are sorted by priority (lowest number first) and capped at
    *max_links*. Returns an empty string if the niche is unknown.

    Args:
        niche: The channel niche key (e.g. ``"ai_trading"``).
        max_links: Maximum number of affiliate links to include.

    Returns:
        Multi-line string with emoji bullet points, ready for a video
        description.
    """
    affiliates = NICHE_AFFILIATES.get(niche, [])
    if not affiliates:
        return ""

    sorted_links = sorted(affiliates, key=lambda a: a["priority"])[:max_links]
    lines = []
    for aff in sorted_links:
        lines.append(f">> {aff['name']}: {aff['url']}")
    return "\n".join(lines)


def get_product_cta(niche: str) -> str:
    """Return a product promotion call-to-action for the given niche.

    Args:
        niche: The channel niche key.

    Returns:
        Formatted CTA string, or empty string if niche has no product.
    """
    product = NICHE_PRODUCTS.get(niche)
    if not product:
        return ""

    return (
        f"GET MY {product['name'].upper()} ({product['price']})\n"
        f"{product['url']}"
    )


def get_signals_cta() -> str:
    """Return a trading-signals promotional CTA.

    Returns:
        Formatted multi-line string advertising the signals service.
    """
    s = TRADING_SIGNALS
    return (
        f"JOIN OUR TRADING SIGNALS\n"
        f"Standard: {s['price']} | VIP: {s['vip_price']}\n"
        f"Sign up: {s['url']}\n"
        f"Telegram: {s['telegram']}"
    )


def get_lead_magnet_cta(niche: str) -> str:
    """Return an email-signup lead-magnet CTA for the given niche.

    Args:
        niche: The channel niche key.

    Returns:
        Formatted CTA string, or empty string if niche is unknown.
    """
    magnet = EMAIL_LEAD_MAGNETS.get(niche)
    if not magnet:
        return ""

    return (
        f"FREE DOWNLOAD: {magnet['title']}\n"
        f"{magnet['description']}\n"
        f"Grab yours: {magnet['signup_url']}"
    )


def get_full_description_footer(niche: str) -> str:
    """Build a complete monetization footer for video descriptions.

    Combines affiliate links, product CTA, lead magnet, and (for
    trading niches) signals CTA into a single formatted block separated
    by dividers.

    Args:
        niche: The channel niche key.

    Returns:
        Ready-to-append description footer string.
    """
    sections = []

    # Affiliate links
    aff_links = get_affiliate_links(niche, max_links=3)
    if aff_links:
        sections.append(f"RECOMMENDED TOOLS & RESOURCES\n{aff_links}")

    # Digital product
    product_cta = get_product_cta(niche)
    if product_cta:
        sections.append(product_cta)

    # Trading signals (only for trading-adjacent niches)
    if niche in ("ai_trading",):
        sections.append(get_signals_cta())

    # Lead magnet
    lead_cta = get_lead_magnet_cta(niche)
    if lead_cta:
        sections.append(lead_cta)

    if not sections:
        return ""

    divider = "\n" + "-" * 40 + "\n"
    return "\n" + divider.join(sections) + "\n"


def get_engagement_cta(niche: str) -> str:
    """Return a short CTA suitable for engagement posts or short-form descriptions.

    Picks the top affiliate link plus the digital product for a concise
    two-liner. Varies phrasing randomly to avoid repetition across uploads.

    Args:
        niche: The channel niche key.

    Returns:
        Short CTA string (2-4 lines).
    """
    openers = [
        "Check this out",
        "You need this",
        "Don't miss this",
        "Highly recommended",
        "Game changer",
    ]

    lines = []

    # Top affiliate
    affiliates = NICHE_AFFILIATES.get(niche, [])
    if affiliates:
        top = sorted(affiliates, key=lambda a: a["priority"])[0]
        lines.append(f"{random.choice(openers)}: {top['url']}")

    # Digital product
    product = NICHE_PRODUCTS.get(niche)
    if product:
        lines.append(f"Grab the {product['name']}: {product['url']}")

    # Lead magnet
    magnet = EMAIL_LEAD_MAGNETS.get(niche)
    if magnet:
        lines.append(f"FREE: {magnet['signup_url']}")

    return "\n".join(lines)
