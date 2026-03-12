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

from config import NICHES, GEMINI_API_KEY, OUTPUT_DIR

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
    # Primary: Use the real trend detector
    try:
        from modules.trend_detector import get_trending_topics
        trend_data = await get_trending_topics(niche)
        if trend_data["context_string"]:
            return trend_data["context_string"]
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
                    f"\n\nCurrent trending data (REAL, from Google Trends and Reddit):\n"
                    f"{trending_context}\n\n"
                    f"Use these as inspiration but create an ORIGINAL topic that's MORE specific and viral."
                )
        except Exception:
            pass

        # Performance feedback keywords
        perf_context = ""
        if perf_keywords:
            perf_context = f"\n\nOur TOP PERFORMING past topics included these themes: {', '.join(perf_keywords)}"
            perf_context += "\nConsider incorporating similar themes since our audience responds well to them."

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

        prompt = f"""You are a viral content strategist. Generate ONE specific, trending video topic for the "{niche_config['name']}" niche.

Today's date: {today}
{trending_context}
{perf_context}
{hook_instruction}
{title_instruction}

Requirements:
- Must be about something currently relevant or trending RIGHT NOW in {today}
- Must be SPECIFIC (include numbers, names, or specific tools — not generic like "AI is changing the world")
- Must have viral potential (curiosity gap, surprising data, controversy, or practical value)
- The FIRST 3 SECONDS when spoken must hook the viewer — make the opening words irresistible
- Return ONLY the topic as a single sentence, nothing else
- Make it sound like a viral video title hook that compels clicks

AVOID these patterns (too generic, overused):
- "X things you didn't know about..."
- Generic predictions with no specific data
- Topics we've likely covered in the past week
- Unverifiable health claims or dangerous financial advice
- Clickbait with no real substance

Keywords to consider: {', '.join(niche_config['search_keywords'])}

Examples of good specific topics:
- "This new AI tool just replaced 5 freelancer jobs overnight"
- "AI trading bot made 47% returns in February — here's the strategy"
- "Why every tech company is firing engineers and hiring AI trainers"
- "Scientists just discovered this herb reverses aging by 10 years"
- "I let AI analyze 50 stocks and found 3 hidden gems nobody's talking about"
- "This FREE AI tool explains any stock in plain English — no jargon needed"
- "AI just predicted this stock will breakout — here's what the data shows"

Return ONLY the topic, no quotes, no explanation."""

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
    Pick a topic for a given niche.

    Args:
        niche: Content niche key
        use_ai: Whether to use AI generation
        ab_variants: A/B test variants (hook_style, title_style)

    Returns:
        dict with keys: topic, niche, source, timestamp
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

    # Try AI-generated trending topic first
    if use_ai:
        ai_topic = await generate_trending_topic_ai(
            niche,
            perf_keywords=perf_keywords,
            hook_style=hook_style,
            title_style=title_style,
        )
        if ai_topic and _topic_hash(ai_topic) not in recent:
            _record_topic(niche, ai_topic)
            return {
                "topic": ai_topic,
                "niche": niche,
                "source": "gemini_ai",
                "timestamp": datetime.now().isoformat(),
            }

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
