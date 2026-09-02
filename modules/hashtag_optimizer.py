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
    # Tech Pulse Africa is a SOUTH AFRICAN NEWS page (repointed 2026-08-28).
    #
    # This pool was missed by that repoint - it changed config.py, script_writer,
    # ai_images and community_manager, but the tags kept going out as
    # #Superpowers, #WorldOrder, #Geopolitics and #FrontlineNews on stories about
    # SASSA payment dates. Tags are the discovery surface: war-news tags put an
    # Eskom reel in front of an audience that came for Ukraine, which is worse
    # than no tags, because it teaches the algorithm the wrong audience.
    #
    # Story-specific tags (#PhalaPhala, #Eskom) are injected from topic_keywords.
    "tech_news": {
        "mega": ["#SouthAfrica", "#Mzansi", "#SANews", "#BreakingNews",
                 "#SouthAfricaNews", "#News", "#Nuus"],
        "mid": ["#LoadShedding", "#Eskom", "#SASSA", "#Gauteng", "#CapeTown",
                "#Johannesburg", "#Durban", "#Pretoria", "#RandNews",
                "#PetrolPrice", "#SAPolitics", "#SAEconomy", "#Jobs",
                "#ServiceDelivery", "#Parliament"],
        "niche": ["#TechPulseAfrica", "#MzansiNews", "#SouthAfricans",
                  "#SAToday", "#KnowYourCountry", "#Joburg", "#Soweto",
                  "#SATaxpayers", "#MzansiMatters", "#ProudlySouthAfrican"],
    },
    # Genesis News — PSL & Mzansi Football. This niche had NO pool, so it fell
    # through the silent `HASHTAG_POOLS.get(niche, ...["motivation"])` default
    # and every Chiefs post went out tagged #UnstoppableMindset, #GrindMode and
    # #KeepGoing. On the one page that is actually growing.
    #
    # Chiefs-weighted on purpose (owner call 2026-08-26): Amakhosi is the
    # SUBJECT of this page, and the numbers back it — a median 1,066 views
    # against 90 for everything else.
    #
    # Rival clubs are deliberately ABSENT from the standing pool. Under the same
    # rule they are context, never the story, so #OrlandoPirates belongs on a
    # derby post and nowhere else — which is exactly what topic_keywords
    # injection already does. Putting them in the pool would tag every routine
    # Chiefs post for a rival's fans, which is how a page teaches the algorithm
    # it is about somebody else.
    "sa_pulse": {
        "mega": ["#KaizerChiefs", "#Amakhosi", "#PSL", "#BetwayPremiership",
                 "#SouthAfricanFootball", "#Mzansi", "#Football"],
        "mid": ["#KhosiNation", "#Naturena", "#SowetoDerby", "#MTN8",
                "#NedbankCup", "#CarlingKnockout", "#MatchDay", "#PSLFootball",
                "#ChiefsNation", "#StartingXI", "#MzansiFootball",
                "#FootballSA", "#TeamNews", "#PSLTransfers", "#Soweto"],
        "niche": ["#GenesisNewsPSL", "#Amakhosi4Life", "#ChiefsFamily",
                  "#LoveAndPeace", "#KhosiForLife", "#AmakhosiFaithful",
                  "#ChiefsFC", "#PSLMatchday", "#MzansiSoccer", "#KhosiPride"],
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


def _pool_for(niche: str) -> dict:
    """The niche's pool, saying so out loud when it has to fall back.

    The fallback was silent, and sa_pulse - Genesis News - quietly inherited
    the MOTIVATION pool for as long as it has existed, tagging Kaizer Chiefs
    reels #GrindMode and #UnstoppableMindset. Nothing failed, nothing logged,
    and the wrong audience was being addressed on the page that grows fastest.
    A missing pool is now visible the first time it is used.
    """
    pool = HASHTAG_POOLS.get(niche)
    if pool is None:
        print(f"[Hashtags] WARNING: no pool for '{niche}' - falling back to "
              f"motivation tags, which are almost certainly wrong for it. "
              f"Add a '{niche}' entry to HASHTAG_POOLS.")
        pool = HASHTAG_POOLS["motivation"]
    return pool


def _clean_tag(raw: str, from_keyword: bool = False) -> str:
    """Normalise one candidate tag, or return '' if it is not usable.

    The bar is what a human would plausibly type into a search box. A scraped
    feed will happily hand over a whole publication title with the spaces
    removed; nobody has ever searched that, so it buys no reach and reads as
    automated - which is the one impression a page recovering from a dead
    fortnight cannot afford.

    from_keyword=True means the input is prose ("Eskom profit") and needs to be
    reduced to one capitalised word. An already-formed tag keeps its own casing:
    title-casing #LoadShedding gives #Loadshedding, which is not a fix but a
    SECOND tag competing with the real one, and both landed in the same set.
    """
    if not raw:
        return ""
    body = raw.strip().lstrip("#")
    if from_keyword:
        # Keep a multi-word PROPER NOUN together. Taking only the first word
        # turned "Orlando Pirates derby" into #Orlando - a city in Florida -
        # and would do the same to Phala Phala, Cape Town and Kaizer Chiefs.
        # So consume the leading run of capitalised words (up to three) and
        # fall back to one title-cased word when the phrase is lowercase.
        words = body.split()
        if not words:
            return ""
        lead = []
        for w in words[:3]:
            if w[:1].isupper():
                lead.append(w)
            else:
                break
        # A lowercase phrase gets the same two-word treatment rather than one
        # word: "load shedding stage 4" as #Load is nearly as useless as the
        # 44-character monster this function was written to stop.
        body = "".join(lead) if lead else "".join(w.title() for w in words[:2])
    body = "".join(c for c in body.replace("-", "") if c.isalnum())
    # 3-20 characters: shorter is noise ("#SA" aside, which the pools own),
    # longer is a scrape artefact. Pure digits are a year or a count, not a tag.
    if not (3 <= len(body) <= 20) or body.isdigit():
        return ""
    return f"#{body}"


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
    pool = _pool_for(niche)
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
        # These arrive UNVETTED from scraped feeds and went straight out: a real
        # post on 31 Aug carried #BasketballEvolutionNationMagazineForNbaNews,
        # a 44-character scrape artefact, on a South African news reel. The
        # length guard that catches exactly this already existed one branch
        # below, applied only to topic keywords - so the sanitiser is now shared
        # and every source goes through it.
        chosen = {t.lower() for t in selected}
        available_trending = []
        for t in (_clean_tag(t) for t in trending_hashtags):
            if t and t.lower() not in chosen:
                chosen.add(t.lower())
                available_trending.append(t)
        selected.extend(available_trending[:n_trending])

    # 5. Topic-specific hashtags (if space remains)
    remaining = limit - len(selected)
    if topic_keywords and remaining > 0:
        for kw in topic_keywords[:remaining]:
            # Only use single words as topic hashtags (avoid concatenated monsters)
            tag = _clean_tag(kw, from_keyword=True)
            if tag and tag.lower() not in {s.lower() for s in selected}:
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
    pool = _pool_for(niche)
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
