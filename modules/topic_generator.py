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

from config import NICHES, GEMINI_API_KEY, ANTHROPIC_API_KEY, OUTPUT_DIR, VIRAL_SCORE_THRESHOLD, VIRAL_SCORE_MAX_RETRIES

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
    """Get topic hashes used in the last N days for a niche."""
    history = _load_history()
    niche_history = history.get(niche, {})
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    return {
        h for h, info in niche_history.items()
        if (info if isinstance(info, str) else info.get("date", "")) > cutoff
    }


def _get_recent_topic_titles(niche: str, days: int = 14) -> list[str]:
    """Get full topic titles used in the last N days for dedup + AI prompt."""
    history = _load_history()
    niche_history = history.get(niche, {})
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    titles = []
    for h, info in niche_history.items():
        if isinstance(info, dict):
            date = info.get("date", "")
            title = info.get("title", "")
            if date > cutoff and title:
                titles.append(title)
        # Legacy format (hash -> date string) has no title, skip
    return titles


def _is_too_similar(new_topic: str, recent_titles: list[str], threshold: int = 3,
                    ignore_words: set | None = None) -> bool:
    """
    Check if a new topic is too similar to recent ones using keyword overlap.

    ignore_words: terms to exclude from the comparison (e.g. a focused page's
    recurring core subject words — such as the current conflict's country/leader
    names or a niche's theme words — which recur in every title and would
    otherwise cause every on-theme topic to look like a duplicate).
    """
    stop = {"the", "a", "an", "is", "are", "to", "for", "in", "of", "and", "or",
            "how", "why", "what", "your", "you", "this", "that", "with", "from",
            "it", "its", "not", "can", "do", "does", "will", "be", "on", "at"}
    stop = stop | {w.lower() for w in (ignore_words or set())}

    def _words(s: str) -> set:
        ws = {w.lower().strip(".,!?:;'\"()") for w in s.split()} - stop
        return {w for w in ws if len(w) > 2}

    new_words = _words(new_topic)
    for title in recent_titles:
        if len(new_words & _words(title)) >= threshold:
            return True
    return False


def _record_topic(niche: str, topic: str):
    """Record that a topic was used (stores full title for dedup)."""
    history = _load_history()
    if niche not in history:
        history[niche] = {}
    history[niche][_topic_hash(topic)] = {
        "date": datetime.now().isoformat(),
        "title": topic,
    }
    # Prune entries older than 30 days
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    history[niche] = {
        h: info for h, info in history[niche].items()
        if (info if isinstance(info, str) else info.get("date", "")) > cutoff
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

        # Rotate the trend seed: the trend cache has a 2h TTL, so back-to-back
        # runs would otherwise see the SAME #1 trend and produce the same topic.
        # Shuffle the trend pool so a DIFFERENT signal leads each run → variety.
        trends = trend_data.get("trends") or []
        keywords = [t.get("keyword", "").strip() for t in trends if t.get("keyword")]
        keywords = list(dict.fromkeys(keywords))  # de-dup, preserve first-seen
        if keywords:
            random.shuffle(keywords)
            picked = keywords[:6]
            sources = ", ".join(trend_data.get("active_sources", []))
            lines = "\n".join(f"- {k}" for k in picked)
            return (
                f"[Live data from: {sources}]\n"
                f"Trending signals right now (a rotating sample — pick a FRESH angle "
                f"and vary the subject from previous runs):\n{lines}"
            )
        if trend_data.get("context_string"):
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



def _pin_ok(topic: str, niche_config: dict) -> bool:
    """True if a generated topic actually honours the pin.

    Prompt instructions alone have not held in this pipeline — the model produced
    real-but-off-fixture topics repeatedly — so the pin is validated, not trusted.
    """
    if not niche_config.get("topic_pin"):
        return True
    terms = [t.lower() for t in niche_config.get("topic_pin_terms", [])]
    if not terms:
        return True
    low = (topic or "").lower()
    return any(t in low for t in terms)


async def generate_trending_topic_ai(
    niche: str,
    perf_keywords: list[str] | None = None,
    hook_style: str = "",
    title_style: str = "",
    recent_titles: list[str] | None = None,
    angle: str = "",
) -> str | None:
    """
    Use Gemini to generate a fresh trending topic for the niche.

    Enhanced with:
    - Real trending data from multiple sources (not just broken Google scraping)
    - Performance feedback keywords from top-performing past content
    - A/B tested hook and title style instructions
    - Negative filter to avoid repetitive/sensitive content
    """
    if not GEMINI_API_KEY and not ANTHROPIC_API_KEY:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
        niche_config = NICHES[niche]
        today = datetime.now().strftime("%B %d, %Y")

        # Hard subject lock for pages that only perform on one theme.
        focus = niche_config.get("topic_focus", "")

        # Fetch real trending data
        trending_context = ""
        try:
            if focus:
                # Focused page: DON'T inject the rotating multi-topic trend feed —
                # it would pull the topic off-subject. Stay strictly on-theme and
                # vary the angle within it instead.
                trending_context = (
                    f"\n\n## MANDATORY TOPIC FOCUS (do not deviate):\n{focus}\n\n"
                    f"Every topic MUST be about the subject above. Today is {today} — "
                    f"pick a FRESH angle within this focus (a different event, figure, "
                    f"consequence, or question) that differs from the ALREADY COVERED list."
                )

                # LIVE HEADLINES for focused-but-factual pages (e.g. PSL football).
                # A focus lock alone leaves the model free to invent the *specifics*
                # — a scoreline, a signing, a quote. For sport that is instantly
                # falsifiable, so pull the real headlines and make them the ONLY
                # permitted source of facts.
                # HARD PIN — every topic must be about this fixture/story.
                pin = niche_config.get("topic_pin", "")
                if pin:
                    trending_context += (
                        f"\n\n## PINNED STORY — NON-NEGOTIABLE\n"
                        f"Every topic MUST be about: {pin}\n"
                        f"Angle it differently each time (the key battle, a player, "
                        f"form, tactics, what a rival's news means for it), but the "
                        f"topic must clearly be about {pin}. Do NOT write about any "
                        f"other fixture, club or competition, even if the headlines "
                        f"below mention one."
                    )

                if niche_config.get("use_live_headlines"):
                    try:
                        from modules.psl_news import headlines_for_prompt
                        live = await headlines_for_prompt()
                        if live:
                            trending_context += (
                                f"\n\n## LIVE HEADLINES — THE ONLY FACTS YOU MAY USE\n{live}\n\n"
                                f"RULES: build the topic from ONE of the headlines above. "
                                f"NEVER invent a scoreline, transfer, signing, injury or quote "
                                f"that is not in that list. Anything flagged REPORT/RUMOUR must "
                                f"be phrased as a report ('reports claim...'), never as fact."
                            )
                        else:
                            print(f"[TopicGen] {niche}: no live headlines — using evergreen angles only")
                    except Exception as e:
                        print(f"[TopicGen] live headline fetch failed for {niche}: {e}")
            else:
                trending_context = await _fetch_trending_context(niche)
                if trending_context:
                    trending_context = (
                        f"\n\nCURRENT TRENDING DATA (REAL, live from YouTube + Google Trends + Reddit):\n"
                        f"{trending_context}\n\n"
                        f"IMPORTANT: Use these as inspiration, but pick a DIFFERENT signal/subject than "
                        f"recent videos (see ALREADY COVERED below). Explore a fresh angle — a different "
                        f"entity, region, or question — rather than the most obvious headline. Variety across "
                        f"videos matters more than chasing the single hottest keyword."
                    )
        except Exception:
            pass

        # Performance feedback keywords
        perf_context = ""
        if perf_keywords:
            perf_context = f"\n\nOur TOP PERFORMING past topics included these themes: {', '.join(perf_keywords)}"
            perf_context += "\nThese themes get the MOST engagement from our audience. Lean into them."

        # The slot's required angle. Without this the rotation was decorative:
        # it was logged, then only used if generation failed outright.
        if angle:
            perf_context += (
                "\n\nREQUIRED ANGLE FOR THIS POST: " + angle
                + "\nThe topic MUST take this angle. Our own "
                "numbers say posts built on a disagreement out-perform "
                "straight information by a wide margin, so name who "
                "disagrees with whom.")

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

        prompt = f"""Generate ONE helpful video topic for the "{niche_config['name']}" channel.

Today's date: {today}
{trending_context}
{perf_context}

## GOOD TOPIC FORMATS:

1. "How to [solve a real problem]" — practical, actionable
2. "The truth about [common misconception]" — educational, honest
3. "[Current event]: what it means for you" — timely, relevant
4. "Why [thing people do] doesn't work (and what to do instead)" — contrarian but helpful
5. "[Number] ways to [achieve something specific]" — concrete value

## RULES:

1. Must be genuinely HELPFUL — teach something real
2. Be SPECIFIC — use real names, places, numbers, current events
3. Keep it under 15 words — clear and direct
4. Must be relevant to TODAY ({today}) — not generic evergreen
5. No fake claims, no manufactured urgency, no clickbait
6. The viewer should feel SMARTER after watching

## NICHE KEYWORDS: {', '.join(niche_config['search_keywords'])}

## ALREADY COVERED (DO NOT repeat these topics or anything similar):
{chr(10).join('- ' + t for t in (recent_titles or [])[-15:]) or '(none yet)'}

Return ONLY the topic as a single line. No quotes. No explanation. Must be a COMPLETELY DIFFERENT subject from the list above."""

        # Strategy: Claude FIRST (reliable), Gemini fallback (free but rate-limited)

        # 0. Claude via the local Claude Code CLI (subscription — no API credits)
        try:
            from modules.claude_cli import claude_cli_complete, cli_enabled
            if cli_enabled():
                text = await claude_cli_complete(prompt, timeout=120)
                if text:
                    topic = text.strip().splitlines()[-1].strip().strip('"').strip("'")
                    if topic and len(topic) > 10 and _pin_ok(topic, niche_config):
                        return topic
                    if topic and not _pin_ok(topic, niche_config):
                        print(f"[TopicGen] PIN reject (CLI): {topic[:70]}")
        except Exception as e:
            print(f"[TopicGen] Claude CLI failed: {e}")

        # 1. Try Claude API (fallback — needs credits)
        if ANTHROPIC_API_KEY:
            try:
                import anthropic
                claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                msg = claude_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=100,
                    messages=[{"role": "user", "content": prompt}],
                )
                if msg.content:
                    topic = msg.content[0].text.strip().strip('"').strip("'")
                    if topic and len(topic) > 10 and _pin_ok(topic, niche_config):
                        return topic
                    if topic and not _pin_ok(topic, niche_config):
                        print(f"[TopicGen] PIN reject (API): {topic[:70]}")
            except Exception as e:
                print(f"[TopicGen] Claude failed: {e}")

        # 2. Try Gemini models (if client available)
        if not client:
            return None
        models = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]
        for model_name in models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                topic = response.text.strip().strip('"').strip("'")
                if topic and len(topic) > 10 and _pin_ok(topic, niche_config):
                    return topic
                if topic and not _pin_ok(topic, niche_config):
                    print(f"[TopicGen] PIN reject ({model_name}): {topic[:70]}")
            except Exception as model_err:
                if "429" in str(model_err) or "RESOURCE_EXHAUSTED" in str(model_err):
                    print(f"[TopicGen] {model_name} rate limited, trying next...")
                    continue
                print(f"[TopicGen] {model_name} failed: {model_err}")
                continue
    except Exception as e:
        print(f"[TopicGen] Topic generation failed: {e}")

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
    recent_titles = _get_recent_topic_titles(niche, days=14)

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

    # For a focused page, the core subject words recur in every title, so exclude
    # them from the dedup comparison and require more overlap before rejecting —
    # otherwise every on-theme angle looks like a duplicate.
    focus = niche_config.get("topic_focus", "")
    if focus:
        focus_ignore = {w.lower().strip(".,!?:;'\"()") for w in
                        (focus + " " + " ".join(niche_config.get("search_keywords", []))).split()}
        sim_threshold = 4
    else:
        focus_ignore = None
        sim_threshold = 3

    if use_ai:
        for attempt in range(VIRAL_SCORE_MAX_RETRIES):
            ai_topic = await generate_trending_topic_ai(
                niche,
                perf_keywords=perf_keywords,
                hook_style=hook_style,
                title_style=title_style,
                recent_titles=recent_titles,
            )
            if not ai_topic or _topic_hash(ai_topic) in recent:
                continue
            # Reject topics too similar to recent ones (keyword overlap)
            if _is_too_similar(ai_topic, recent_titles, threshold=sim_threshold, ignore_words=focus_ignore):
                print(f"[TopicGen] Rejected similar topic: {ai_topic[:60]}")
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
