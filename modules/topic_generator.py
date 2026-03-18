"""
Topic Generator — Picks trending topics for video creation.

Uses a combination of:
1. Real trend data (Google Trends via pytrends, Reddit hot posts)
2. AI generation (Gemini) grounded in real trend data
3. Performance feedback loop (top-performing past keywords)
4. A/B tested hook styles
5. Rotating topic bank as fallback
"""
import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, GEMINI_API_KEY, OUTPUT_DIR, VIRAL_SCORE_THRESHOLD, VIRAL_SCORE_MAX_RETRIES

# Track recently used topics to avoid repeats
HISTORY_FILE = OUTPUT_DIR / "topic_history.json"


def _load_history() -> dict:
    """Load topic history from file."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_history(history: dict):
    """Save topic history to file."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def _topic_hash(topic: str) -> str:
    """Create a short hash for a topic to track usage."""
    return hashlib.md5(topic.lower().strip().encode()).hexdigest()[:8]


def _get_recent_topics(niche: str, days: int = 7) -> set:
    """Get topics used in the last N days for a niche."""
    history = _load_history()
    niche_history = history.get(niche, {})
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    return {
        h for h, date in niche_history.items()
        if date > cutoff
    }


def _record_topic(niche: str, topic: str):
    """Record that a topic was used."""
    history = _load_history()
    if niche not in history:
        history[niche] = {}
    history[niche][_topic_hash(topic)] = datetime.now().isoformat()
    # Prune entries older than 30 days
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    history[niche] = {
        h: d for h, d in history[niche].items() if d > cutoff
    }
    _save_history(history)


async def _fetch_trending_context(niche: str) -> str:
    """
    Fetch real trending data from multiple sources.

    Uses the new trend_detector module instead of broken Google scraping.
    Falls back to lightweight Google search if trend_detector fails.
    """
    # Primary: Use the real trend detector (YouTube + Google Trends + Reddit + Twitter + TikTok)
    try:
        from modules.trend_detector import get_trending_topics
        trend_data = await get_trending_topics(niche)
        if trend_data["context_string"]:
            sources = ", ".join(trend_data.get("active_sources", []))
            return f"[Live data from: {sources}]\n{trend_data['context_string']}"
    except Exception as e:
        print(f"[TopicGen] Trend detector failed (non-critical): {e}")

    # Fallback: lightweight Google search (original method, still as backup)
    try:
        import httpx

        niche_config = NICHES[niche]
        query = f"{niche_config['search_keywords'][0]} trending today {datetime.now().strftime('%B %Y')}"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.google.com/search",
                params={"q": query, "num": 5},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                import re
                titles = re.findall(r'<h3[^>]*>(.*?)</h3>', resp.text)
                headlines = []
                for t in titles[:5]:
                    clean = re.sub(r'<[^>]+>', '', t).strip()
                    if clean and len(clean) > 10:
                        headlines.append(clean)
                if headlines:
                    return "Current headlines:\n" + "\n".join(f"- {h}" for h in headlines)
    except Exception:
        pass

    return ""


async def generate_trending_topic_ai(
    niche: str,
    perf_keywords: list[str] | None = None,
    hook_style: str = "",
    title_style: str = "",
) -> str | None:
    """
    Use Gemini to generate a fresh trending topic for the niche.

    Enhanced with:
    - Real trending data from multiple sources (not just broken Google scraping)
    - Performance feedback keywords from top-performing past content
    - A/B tested hook and title style instructions
    - Negative filter to avoid repetitive/sensitive content
    """
    if not GEMINI_API_KEY:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        niche_config = NICHES[niche]
        today = datetime.now().strftime("%B %d, %Y")

        # Fetch real trending data
        trending_context = ""
        try:
            trending_context = await _fetch_trending_context(niche)
            if trending_context:
                trending_context = (
                    f"\n\nCURRENT TRENDING DATA (REAL, live from YouTube + Google Trends + Reddit):\n"
                    f"{trending_context}\n\n"
                    f"IMPORTANT: Use these REAL trending topics as your foundation. Pick one that's HOT right now "
                    f"and create a video angle on it that will get MORE views than the existing content."
                )
        except Exception:
            pass

        # Performance feedback keywords
        perf_context = ""
        if perf_keywords:
            perf_context = f"\n\nOur TOP PERFORMING past topics included these themes: {', '.join(perf_keywords)}"
            perf_context += "\nThese themes get the MOST engagement from our audience. Lean into them."

        # A/B test modifiers
        hook_instruction = ""
        if hook_style:
            try:
                from modules.ab_testing import get_hook_prompt_modifier
                hook_instruction = f"\n\nHOOK STYLE: {get_hook_prompt_modifier(hook_style)}"
            except Exception:
                pass

        title_instruction = ""
        if title_style:
            try:
                from modules.ab_testing import get_title_prompt_modifier
                title_instruction = f"\n\nTITLE STYLE: {get_title_prompt_modifier(title_style)}"
            except Exception:
                pass

        prompt = f"""You are an elite YouTube strategist who has studied every viral video formula. Your job: generate ONE video topic for the "{niche_config['name']}" niche that will MAXIMIZE views and subscriber growth.

Today's date: {today}
{trending_context}
{perf_context}
{hook_instruction}
{title_instruction}

## VIRAL VIDEO FORMULAS THAT WORK (use one):

1. **"I Tested X So You Don't Have To"** — Personal experiment with surprising results
   "I gave AI $1000 to trade stocks for 30 days — here's what happened"

2. **"The Hidden Truth About X"** — Expose or reveal something the audience doesn't know
   "The stock your broker doesn't want you to know about just got flagged by AI"

3. **"X Just Changed Everything"** — Breaking news angle with real impact
   "OpenAI just released a tool that replaces $50K analysts — and it's free"

4. **"Why X Is Doing Y (And What It Means For You)"** — Connect trending news to viewer's life
   "Why Goldman Sachs just went all-in on AI trading — and what it means for your portfolio"

5. **"I Found X And It Actually Works"** — Discovery/proof format
   "I found an AI that predicts stock breakouts 3 days early — here's the proof"

6. **"Stop Doing X, Do This Instead"** — Contrarian advice with authority
   "Stop using ChatGPT for trading — this AI tool actually understands markets"

7. **"X vs Y — The Results Shocked Me"** — Comparison with surprising outcome
   "AI trading bot vs my own picks for 7 days — the results will shock you"

## RULES:

1. MUST be based on something ACTUALLY trending or newsworthy right now ({today})
2. Use SPECIFIC names, numbers, tools, or events — never generic
3. The first 5 words must create an IRRESISTIBLE curiosity gap
4. Must provide real VALUE — not empty clickbait (the viewer should learn something)
5. Keep it under 15 words — punchy, not wordy
6. Must feel URGENT — like they'll miss out if they don't watch NOW

## AVOID (instant skip for viewers):

- Generic "AI is amazing" or "AI changes everything" (too vague)
- "Top 5/10 things" lists (overplayed)
- Unverifiable claims or fake statistics
- Topics with no trending news hook (stale content)
- Anything that sounds like every other channel

## NICHE KEYWORDS: {', '.join(niche_config['search_keywords'])}

Return ONLY the topic as a single line. No quotes. No explanation. No numbering."""

        # Try multiple models for rate limit resilience
        for model_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                topic = response.text.strip().strip('"').strip("'")
                if topic and len(topic) > 10:
                    return topic
            except Exception as model_err:
                if "429" in str(model_err) or "RESOURCE_EXHAUSTED" in str(model_err):
                    import asyncio
                    await asyncio.sleep(2)
                    continue
                raise
    except Exception as e:
        print(f"[TopicGen] Gemini topic generation failed: {e}")

    return None


async def pick_topic(
    niche: str,
    use_ai: bool = True,
    ab_variants: dict | None = None,
) -> dict:
    """
    Pick a topic for a given niche with viral validation.

    Generates up to VIRAL_SCORE_MAX_RETRIES topics, validates each against
    the viral score threshold, and picks the best one. Falls back to topic
    bank if AI fails or all topics score too low.

    Args:
        niche: Content niche key
        use_ai: Whether to use AI generation
        ab_variants: A/B test variants (hook_style, title_style)

    Returns:
        dict with keys: topic, niche, source, timestamp, viral_score, viral_components
    """
    niche_config = NICHES[niche]
    recent = _get_recent_topics(niche)

    # Get top-performing keywords for this niche (feedback loop)
    perf_keywords = []
    try:
        from modules.performance_tracker import get_best_performing_keywords
        perf_keywords = get_best_performing_keywords(niche, top_n=3)
    except Exception:
        pass

    # Extract A/B test modifiers
    hook_style = (ab_variants or {}).get("hook_style", "")
    title_style = (ab_variants or {}).get("title_style", "")

    # Pre-fetch trend data once (shared by viral scorer + topic gen)
    trend_data = None
    try:
        from modules.trend_detector import get_trending_topics
        trend_data = await get_trending_topics(niche)
    except Exception:
        pass

    # Viral validation loop: try multiple AI-generated topics
    best_candidate = None
    best_score = -1

    if use_ai:
        for attempt in range(VIRAL_SCORE_MAX_RETRIES):
            ai_topic = await generate_trending_topic_ai(
                niche,
                perf_keywords=perf_keywords,
                hook_style=hook_style,
                title_style=title_style,
            )
            if not ai_topic or _topic_hash(ai_topic) in recent:
                continue

            # Validate viral potential
            try:
                from modules.viral_scorer import validate_topic
                validation = await validate_topic(
                    ai_topic, niche,
                    trend_data=trend_data,
                    perf_keywords=perf_keywords,
                )
                score = validation["viral_score"]

                # Track best candidate regardless of threshold
                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "topic": ai_topic,
                        "niche": niche,
                        "source": "gemini_ai",
                        "timestamp": datetime.now().isoformat(),
                        "viral_score": score,
                        "viral_components": validation["components"],
                        "viral_recommendation": validation["recommendation"],
                    }

                if validation["passes_threshold"]:
                    print(f"[TopicGen] Topic scored {score:.0f}/100 ({validation['recommendation']}) on attempt {attempt+1}")
                    _record_topic(niche, ai_topic)
                    return best_candidate
                else:
                    print(f"[TopicGen] Topic scored {score:.0f}/100 (min: {VIRAL_SCORE_THRESHOLD}) — retrying ({attempt+1}/{VIRAL_SCORE_MAX_RETRIES})")
            except Exception as e:
                # Viral scoring failed — accept the topic anyway (graceful degradation)
                print(f"[TopicGen] Viral scoring failed (non-critical): {e}")
                _record_topic(niche, ai_topic)
                return {
                    "topic": ai_topic,
                    "niche": niche,
                    "source": "gemini_ai",
                    "timestamp": datetime.now().isoformat(),
                    "viral_score": None,
                    "viral_components": None,
                    "viral_recommendation": "unscored",
                }

    # If we have a best candidate (even below threshold), use it rather than topic bank
    if best_candidate:
        print(f"[TopicGen] Using best candidate (score: {best_score:.0f}) after {VIRAL_SCORE_MAX_RETRIES} attempts")
        _record_topic(niche, best_candidate["topic"])
        return best_candidate

    # Fallback to topic bank with randomization
    available = [
        t for t in niche_config["topics_bank"]
        if _topic_hash(t) not in recent
    ]

    # If all topics used recently, reset and allow all
    if not available:
        available = niche_config["topics_bank"]

    topic = random.choice(available)
    _record_topic(niche, topic)

    return {
        "topic": topic,
        "niche": niche,
        "source": "topic_bank",
        "timestamp": datetime.now().isoformat(),
        "viral_score": None,
        "viral_components": None,
        "viral_recommendation": "fallback",
    }


async def pick_topics_for_day(niches: list[str] | None = None) -> list[dict]:
    """Pick topics for all niches for today's video run."""
    if niches is None:
        niches = list(NICHES.keys())

    topics = []
    for niche in niches:
        topic = await pick_topic(niche)
        topics.append(topic)
    return topics


# CLI test
if __name__ == "__main__":
    import asyncio

    async def test():
        for niche in NICHES:
            result = await pick_topic(niche)
            print(f"[{niche}] {result['topic']} (source: {result['source']})")

    asyncio.run(test())
