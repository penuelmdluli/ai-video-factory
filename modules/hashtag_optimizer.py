"""
Hashtag Optimizer — Dynamic hashtag research and selection per platform.

Replaces static hashtag lists with a smart mix:
1. Mega hashtags (>1M posts) — for broad discovery
2. Mid-tier hashtags (100K-1M) — sweet spot for reach + competition
3. Niche hashtags (<100K) — high engagement, low competition
4. Trending hashtags — real-time from trend detector
5. Evergreen hashtags — proven performers from past videos

Strategy: 30% mega, 40% mid-tier, 20% niche, 10% trending
"""
import os
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, OUTPUT_DIR


# ── Curated hashtag pools per niche (categorized by reach tier) ──
HASHTAG_POOLS = {
    "ai_trading": {
        "mega": ["#AI", "#Trading", "#StockMarket", "#Crypto", "#Investing", "#Finance", "#Money", "#Bitcoin"],
        "mid": ["#AITrading", "#DayTrading", "#AlgoTrading", "#TradingBot", "#CryptoTrading", "#SwingTrading",
                "#StockPicks", "#ForexTrading", "#TradingStrategy", "#MarketAnalysis", "#CryptoSignals",
                "#TechnicalAnalysis", "#InvestingSmart", "#TradingLife", "#OptionsTrading"],
        "niche": ["#AITradingBot", "#AlgorithmTrading", "#CryptoAI", "#SmartTrading", "#AutoTrading",
                  "#TradingAlgorithm", "#AIStocks", "#QuantTrading", "#RoboTrader", "#AIInvesting"],
    },
    "ai_money": {
        "mega": ["#AI", "#Money", "#SideHustle", "#PassiveIncome", "#Entrepreneur", "#Business", "#MakeMoneyOnline"],
        "mid": ["#AITools", "#OnlineBusiness", "#DigitalBusiness", "#AIAutomation", "#ChatGPT", "#AISideHustle",
                "#IncomeStream", "#FreelanceAI", "#OnlineIncome", "#MoneyMaking", "#AIBusiness",
                "#RemoteWork", "#TechBusiness", "#DigitalNomad", "#StartupLife"],
        "niche": ["#AIMoneyMaker", "#AIFreelance", "#AIContentCreation", "#AIProductivity", "#MakeMoneyWithAI",
                  "#AIEntrepreneur", "#AIIncome", "#ChatGPTMoney", "#AIHustle", "#AIAutomationBusiness"],
    },
    # Tech Pulse Africa is a WAR-NEWS / geopolitics page — NOT locked to any single
    # conflict. Pools stay conflict-agnostic; story-specific tags (e.g. #Iran, #Ukraine)
    # are injected dynamically from topic_keywords when a given story mentions them.
    "tech_news": {
        "mega": ["#BreakingNews", "#WorldNews", "#War", "#Geopolitics", "#GlobalNews", "#Conflict", "#Politics"],
        "mid": ["#WorldOrder", "#WarNews", "#GlobalCrisis", "#WorldAffairs", "#GlobalConflict",
                "#OilPrices", "#Sanctions", "#Military", "#Airstrike", "#Ceasefire",
                "#Diplomacy", "#Superpowers", "#Escalation", "#GlobalSecurity", "#PowerStruggle"],
        "niche": ["#TechPulseAfrica", "#BRICS", "#NewWorldOrder", "#AfricaImpact", "#FrontlineNews",
                  "#WarUpdate", "#GeopoliticalTensions", "#GlobalPolitics", "#ConflictZone", "#WorldStage"],
    },
    "motivation": {
        "mega": ["#Motivation", "#Success", "#Mindset", "#Goals", "#Hustle", "#Discipline", "#Inspiration"],
        "mid": ["#DailyMotivation", "#SuccessMindset", "#GrindMode", "#NeverGiveUp", "#SelfImprovement",
                "#MorningRoutine", "#Ambition", "#GrowthMindset", "#MotivationalQuotes", "#KeepGoing",
                "#DreamBig", "#LevelUp", "#WorkHard", "#PositiveMindset", "#StayFocused"],
        "niche": ["#StoicMindset", "#EliteMinds", "#MillionaireMorning", "#UnstoppableMindset",
                  "#MentalToughness", "#WinnerMentality", "#DailyDiscipline", "#SuccessHabits",
                  "#MindsetCoach", "#BeastMode"],
    },
    "health_wellness": {
        "mega": ["#Health", "#Wellness", "#Fitness", "#Healthy", "#Nutrition", "#SelfCare", "#MentalHealth"],
        "mid": ["#HealthyLiving", "#NaturalRemedies", "#HealthTips", "#GutHealth", "#Organic",
                "#HolisticHealth", "#HealthyFood", "#Superfoods", "#AntiAging", "#Detox",
                "#MindBodySoul", "#HealthyLifestyle", "#NaturalHealing", "#WellnessJourney", "#CleanEating"],
        "niche": ["#HerbalRemedies", "#FunctionalMedicine", "#NutritionScience", "#BiohackingLife",
                  "#GutHealthMatters", "#NaturalMedicine", "#PlantBased", "#LongevityTips",
                  "#HealthHacks", "#WellnessWarrior"],
    },
    "blissful_moments": {
        "mega": ["#Peace", "#Love", "#Gratitude", "#Happiness", "#Mindfulness", "#Positive", "#Beautiful"],
        "mid": ["#InnerPeace", "#BlissfulMoments", "#FeelGood", "#Positivity", "#GratefulHeart",
                "#MindfulLiving", "#DailyGratitude", "#PeaceOfMind", "#SelfLove", "#HappyLife",
                "#BePresent", "#JoyfulLiving", "#SoulFood", "#Serenity", "#BeautifulLife"],
        "niche": ["#BlissfulLife", "#MomentOfPeace", "#GratitudeJournal", "#InnerCalm",
                  "#SoulfulMoments", "#PeacefulMind", "#DailyBliss", "#HealingSoul",
                  "#JoyInSimpleThings", "#BlissAndPeace"],
    },
}

# Platform-specific hashtag limits
PLATFORM_HASHTAG_LIMITS = {
    "youtube": 15,         # Tags, not really hashtags
    "tiktok": 5,           # 3-5 is optimal, more looks spammy
    "instagram": 20,       # IG allows 30 but 20 is optimal
    "facebook": 10,        # FB hashtags have lower impact
    "twitter": 3,          # Twitter max effective
}

# Track which hashtags perform well (updated by performance tracker)
HASHTAG_PERF_FILE = OUTPUT_DIR / "hashtag_performance.json"


def _load_hashtag_perf() -> dict:
    """Load hashtag performance data."""
    if HASHTAG_PERF_FILE.exists():
        try:
            return json.loads(HASHTAG_PERF_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_hashtag_perf(data: dict):
    """Save hashtag performance data."""
    HASHTAG_PERF_FILE.parent.mkdir(parents=True, exist_ok=True)
    HASHTAG_PERF_FILE.write_text(json.dumps(data, indent=2))


def get_optimized_hashtags(
    niche: str,
    platform: str = "tiktok",
    trending_hashtags: list[str] | None = None,
    topic_keywords: list[str] | None = None,
) -> list[str]:
    """
    Generate an optimized hashtag set for a specific platform and niche.

    Strategy:
    - 30% mega (broad discovery)
    - 40% mid-tier (sweet spot)
    - 20% niche (high engagement)
    - 10% trending (real-time relevance)

    Args:
        niche: Content niche
        platform: Target platform
        trending_hashtags: Real-time trending hashtags from trend_detector
        topic_keywords: Keywords from the video topic for relevant hashtags

    Returns:
        Optimized list of hashtags for the platform
    """
    pool = HASHTAG_POOLS.get(niche, HASHTAG_POOLS["motivation"])
    limit = PLATFORM_HASHTAG_LIMITS.get(platform, 10)

    # Calculate counts per tier
    n_mega = max(1, int(limit * 0.3))
    n_mid = max(1, int(limit * 0.4))
    n_niche = max(1, int(limit * 0.2))
    n_trending = max(0, limit - n_mega - n_mid - n_niche)

    selected = []

    # 1. Mega hashtags
    mega = random.sample(pool["mega"], min(n_mega, len(pool["mega"])))
    selected.extend(mega)

    # 2. Mid-tier hashtags
    mid = random.sample(pool["mid"], min(n_mid, len(pool["mid"])))
    selected.extend(mid)

    # 3. Niche hashtags
    niche_tags = random.sample(pool["niche"], min(n_niche, len(pool["niche"])))
    selected.extend(niche_tags)

    # 4. Trending hashtags (from trend detector)
    if trending_hashtags and n_trending > 0:
        # Filter to ones not already selected
        available_trending = [t for t in trending_hashtags if t not in selected]
        selected.extend(available_trending[:n_trending])

    # 5. Topic-specific hashtags (if space remains)
    remaining = limit - len(selected)
    if topic_keywords and remaining > 0:
        for kw in topic_keywords[:remaining]:
            # Only use single words as topic hashtags (avoid concatenated monsters)
            word = kw.strip().split()[0] if kw.strip() else ""
            tag = "#" + word.title().replace("-", "")
            tag = "".join(c for c in tag if c.isalnum() or c == "#")
            if tag not in selected and 3 < len(tag) <= 20:
                selected.append(tag)

    # Ensure all start with #
    selected = [t if t.startswith("#") else f"#{t}" for t in selected]

    # Shuffle to avoid pattern detection by algorithms
    random.shuffle(selected)

    return selected[:limit]


def get_first_comment_hashtags(
    niche: str,
    platform: str = "tiktok",
    main_hashtags: list[str] | None = None,
) -> list[str]:
    """
    Generate a second set of hashtags for the first comment.

    These complement the main hashtags without duplicating them.
    """
    pool = HASHTAG_POOLS.get(niche, HASHTAG_POOLS["motivation"])
    all_pool = pool["mega"] + pool["mid"] + pool["niche"]

    # Exclude main hashtags
    excluded = set(main_hashtags or [])
    available = [t for t in all_pool if t not in excluded]

    limit = PLATFORM_HASHTAG_LIMITS.get(platform, 10)
    # First comment gets fewer hashtags
    comment_limit = max(3, limit // 2)

    selected = random.sample(available, min(comment_limit, len(available)))
    return selected


def record_hashtag_performance(hashtags: list[str], niche: str, engagement_score: float):
    """
    Record which hashtags were used and their associated engagement score.
    Over time, builds a model of which hashtags work best per niche.
    """
    data = _load_hashtag_perf()
    if niche not in data:
        data[niche] = {}

    for tag in hashtags:
        tag_lower = tag.lower()
        if tag_lower not in data[niche]:
            data[niche][tag_lower] = {"uses": 0, "total_score": 0, "avg_score": 0}
        data[niche][tag_lower]["uses"] += 1
        data[niche][tag_lower]["total_score"] += engagement_score
        data[niche][tag_lower]["avg_score"] = (
            data[niche][tag_lower]["total_score"] / data[niche][tag_lower]["uses"]
        )

    _save_hashtag_perf(data)


def get_top_performing_hashtags(niche: str, top_n: int = 10) -> list[str]:
    """Get the highest performing hashtags for a niche based on historical data."""
    data = _load_hashtag_perf()
    niche_data = data.get(niche, {})

    if not niche_data:
        return []

    # Sort by average score, require at least 3 uses
    ranked = [
        (tag, info["avg_score"])
        for tag, info in niche_data.items()
        if info["uses"] >= 3
    ]
    ranked.sort(key=lambda x: x[1], reverse=True)

    return [tag for tag, _ in ranked[:top_n]]
