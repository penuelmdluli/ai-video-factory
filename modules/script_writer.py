"""
Script Writer — Generates viral video scripts using AI.

Supports:
- Long-form (8-10 min YouTube)
- Short-form (30-60 sec Shorts/TikTok/Reels)

Uses Gemini (free) as primary, Claude as premium fallback.
"""
import json
import re
import random
from datetime import datetime

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY, NICHES, AFFILIATE_LINKS


# ── Niche-Specific Style Guides ────────────────────────────────

NICHE_STYLE_GUIDES = {
    "ai_trading": """NICHE STYLE — AI Trading & Markets:
- Lead with SPECIFIC dollar amounts and percentages ("This AI bot returned 47% in February")
- Create urgency: markets move fast, viewers need to act NOW
- Use trading language naturally: "positions", "entries", "signals", "breakout"
- Include one counterintuitive insight ("The WORST time to use AI trading is actually...")
- Naturally mention AI-powered tools for stock analysis when relevant
- Reference how AI can analyze stocks in plain English — making markets accessible to everyone
- Tone: Confident insider sharing alpha, NOT a financial advisor lecturing""",

    "ai_money": """NICHE STYLE — Make Money With AI:
- Lead with a SPECIFIC income number and timeframe ("$3,200 in my first week")
- Tell a mini transformation story: "I was [before state] until I discovered [tool/method]"
- Make it feel accessible: "You don't need coding skills or a big budget"
- Include the specific AI tool names (ChatGPT, Midjourney, Claude, etc.)
- Tone: Excited friend who just discovered a goldmine and is sharing it""",

    "tech_news": """NICHE STYLE — AI & Tech News:
- Lead with the IMPACT, not the announcement ("This changes everything about how we...")
- Connect tech news to the viewer's daily life ("Here's why this affects YOUR job")
- Include the company/researcher name for credibility
- Add a "what this means for the future" angle
- Tone: Smart tech-savvy friend breaking down complex news simply""",

    "motivation": """NICHE STYLE — Daily Motivation & Mindset:
- Lead with a RELATABLE struggle ("You've been waking up hitting snooze, feeling behind...")
- Use the hero's journey: struggle → discovery → transformation
- Include one specific habit or action (not just "believe in yourself")
- Reference a real successful person or study for credibility
- Create an emotional crescendo — start low, end on a powerful high note
- Tone: Tough love mentor who genuinely cares, NOT a motivational poster""",

    "health_wellness": """NICHE STYLE — Health & Wellness:
- Lead with a SURPRISING health fact ("Your body does THIS while you sleep and nobody talks about it")
- Include specific foods, herbs, or practices (not vague "eat healthy")
- Reference a study or doctor for credibility ("Harvard researchers found...")
- Add a practical tip viewers can try TODAY
- Tone: Knowledgeable wellness friend sharing discoveries, warm and caring""",

    "blissful_moments": """NICHE STYLE — Blissful Moments & Positivity:
- Lead with a VIVID sensory moment ("Imagine standing on a quiet beach as the sun rises...")
- Use poetic, flowing language — paint pictures with words
- Include a simple mindfulness exercise or gratitude prompt
- Create a feeling of calm and wonder — slow the viewer's racing mind
- End with an affirmation or gentle call to appreciate the present moment
- Tone: Gentle, wise friend sharing a beautiful perspective on life""",
}


# ── Script Structure Templates ─────────────────────────────────

LONG_FORM_PROMPT = """You are a viral YouTube scriptwriter specializing in {niche_name} content.

Write a complete video script for this topic: "{topic}"

{niche_style_guide}

CRITICAL RULES:
1. HOOK (first 5 seconds): Start with a bold, specific claim or surprising fact that creates curiosity. Use a number or dollar amount if possible.
2. CONTEXT (next 15 seconds): Explain why this matters RIGHT NOW.
3. BODY (main content, 6-8 minutes): Break into 4-6 clear sections. Each section should have a mini-hook transition. Include specific data, examples, and actionable insights.
4. PAYOFF (last 30 seconds): Deliver the most surprising or valuable insight.
5. CTA (final 10 seconds): "Subscribe and turn on notifications for daily [niche] updates."

STYLE RULES:
- Write conversationally, as if talking to a friend
- Use short, punchy sentences
- Include "pattern interrupts" every 30-60 seconds (rhetorical questions, surprising facts, "but here's the thing...")
- Never use filler phrases like "in today's video" or "without further ado"
- Be specific with numbers and data (even approximate is better than vague)
- Create curiosity loops: hint at what's coming to keep viewers watching

OUTPUT FORMAT — Return valid JSON:
{{
  "title": "Viral YouTube title (under 70 chars, include a number or $ amount)",
  "description": "YouTube description (150-200 words, include keywords naturally)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "The exact words to speak for this scene",
      "visual_description": "Brief description of what should be shown on screen",
      "duration_seconds": 15,
      "lower_third_text": "Short topic label for this scene (5-8 words, e.g. 'AI Trading Profits Up 340%')",
      "sfx_hint": "One of: whoosh, impact, money, data, notification, rise, success, reveal, glitch, typing, none"
    }}
  ],
  "thumbnail_text": "Bold 3-5 word text for the thumbnail"
}}

Requirements:
- Total duration: 7-10 minutes of narration
- 15-25 scenes
- Each scene: 15-40 seconds of narration
- Visual descriptions should be searchable stock footage keywords
- Tags should include: {hashtags}

Today's date: {today}
Topic: "{topic}"
"""

SHORT_FORM_PROMPT = """You are an elite short-form video scriptwriter who creates VIRAL content for TikTok, YouTube Shorts, and Instagram Reels. You study what makes the top 1% of creators go viral.

Write a script for: "{topic}" in the {niche_name} niche.

{niche_style_guide}

VIRAL STRUCTURE (every second counts):
1. HOOK (0-3 seconds): This decides EVERYTHING. The viewer will scroll past in 0.5 seconds if you bore them.
   - Lead with the most shocking/specific claim (numbers, dollar amounts, timeframes)
   - Or ask a question that creates an "open loop" the viewer MUST close
   - NEVER start with "Did you know" or "In this video" — those are instant scroll-past
   - Examples of killer hooks: "I made $8,000 in 3 days using this one AI tool", "Scientists just discovered something terrifying about your morning coffee", "This 5-second habit made me a millionaire"

2. TENSION BUILD (3-15 seconds): Create a curiosity gap — hint at the payoff without revealing it.
   - "And the reason why will change how you think about everything..."
   - "But what happened next shocked even the experts..."
   - Give just enough context to make the viewer NEED to keep watching

3. VALUE DELIVERY (15-40 seconds): Rapid-fire insights with mini-hooks between each point.
   - Each point should make the viewer think "wait, WHAT?"
   - Use the "But here's what nobody tells you..." pattern between points
   - Include specific numbers, names, and timeframes (not vague claims)
   - Every 8-10 seconds, drop a new revelation to maintain dopamine

4. PLOT TWIST / PAYOFF (40-48 seconds): The biggest revelation saved for last.
   - This should reframe everything they just learned
   - "But the REAL reason this works is..."
   - Make them want to watch again or share with friends

5. CTA (48-55 seconds): Quick, natural, and value-added.
   - "Follow for more [niche] secrets" or "Save this before it's gone"
   - Never beg — make it sound like they'd be missing out

WRITING RULES:
- Write like you're texting your smartest friend — casual but packed with insight
- EVERY sentence must earn its place. If it doesn't hook, inform, or surprise — cut it
- Use power words: "secretly", "actually", "just discovered", "nobody talks about"
- Vary sentence length: short punchy hits mixed with one slightly longer explanatory sentence
- Create at least 2 "curiosity loops" (open a question, answer it later)
- Address the viewer directly: "You", "Your", "Look..."
- Include ONE moment of genuine surprise or counterintuitive insight

OUTPUT FORMAT — Return valid JSON:
{{
  "title": "Short punchy title (under 60 chars, include a number or specific claim)",
  "caption": "Engaging caption that adds context + hashtags. Start with a hook question or bold claim, NOT just hashtags.",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Exact words to speak — write these as if performing, not reading",
      "visual_description": "Specific, searchable visual (e.g. 'close-up of stock trading screen with green profits' not just 'trading')",
      "duration_seconds": 5,
      "lower_third_text": "Punchy overlay text (max 6 words, uses numbers when possible)",
      "sfx_hint": "One of: whoosh, impact, money, data, notification, rise, success, reveal, glitch, typing, none"
    }}
  ],
  "thumbnail_text": "Bold 2-4 word hook text"
}}

Requirements:
- Total duration: 45-55 seconds
- 5-8 scenes
- Include hashtags: {hashtags}
- Make the viewer feel something — curiosity, shock, FOMO, or inspiration

Today's date: {today}
Topic: "{topic}"
"""


def _clean_json_response(text: str) -> str:
    """Extract JSON from AI response, handling markdown code blocks."""
    # Remove markdown code blocks
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    return text


def _add_affiliate_links(description: str, niche: str) -> str:
    """Add our product CTAs + relevant affiliate links to video description."""
    from config import PRODUCT_CTA_TEMPLATES

    # ── OUR PRODUCT CTA (always first, above the fold) ──────────
    product_section = ""
    product_ctas = PRODUCT_CTA_TEMPLATES.get(niche, [])
    if product_ctas:
        product_section = f"\n\n{'─' * 40}\n{random.choice(product_ctas)}\n{'─' * 40}"

    # ── Affiliate tools section ─────────────────────────────────
    niche_links = {
        "ai_trading": ["traderadar", "tradingview", "binance"],
        "ai_money": ["traderadar", "chatgpt", "elevenlabs", "midjourney"],
        "tech_news": ["chatgpt", "midjourney"],
    }

    links_section = "\n\n--- Tools & Resources ---\n"
    for link_key in niche_links.get(niche, []):
        if link_key in AFFILIATE_LINKS:
            name = link_key.replace("_", " ").title()
            if link_key == "traderadar":
                name = "⭐ TradeRadar AI (FREE)"
            links_section += f"- {name}: {AFFILIATE_LINKS[link_key]}\n"

    links_section += "\n--- Disclaimer ---\n"
    links_section += "This video was created with AI assistance. "
    links_section += "This is not financial advice. Trading involves risk. "
    links_section += "Some links above are affiliate links.\n"

    return description + product_section + links_section


async def generate_script_gemini(
    topic: str,
    niche: str,
    format_type: str = "long",
) -> dict | None:
    """Generate a script using Gemini (free tier). Tries multiple models."""
    if not GEMINI_API_KEY:
        return None

    from google import genai
    import asyncio

    client = genai.Client(api_key=GEMINI_API_KEY)
    niche_config = NICHES[niche]
    today = datetime.now().strftime("%B %d, %Y")

    prompt_template = LONG_FORM_PROMPT if format_type == "long" else SHORT_FORM_PROMPT
    niche_style = NICHE_STYLE_GUIDES.get(niche, "Write in an engaging, viewer-focused style.")
    prompt = prompt_template.format(
        topic=topic,
        niche_name=niche_config["name"],
        niche_style_guide=niche_style,
        hashtags=", ".join(niche_config["hashtags"]),
        today=today,
    )

    # Try multiple models in case one is rate-limited
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    response = None

    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print(f"[ScriptWriter] {model_name} rate limited, trying next model...")
                await asyncio.sleep(2)
                continue
            print(f"[ScriptWriter] {model_name} failed: {e}")
            continue

    if not response or not response.text:
        return None

    try:

        raw = _clean_json_response(response.text)
        script = json.loads(raw)

        # Add affiliate links to description
        if "description" in script:
            script["description"] = _add_affiliate_links(script["description"], niche)

        script["niche"] = niche
        script["format"] = format_type
        script["generated_at"] = datetime.now().isoformat()
        script["ai_model"] = "gemini-2.5-flash"

        return script

    except json.JSONDecodeError as e:
        print(f"[ScriptWriter] JSON parse error: {e}")
        print(f"[ScriptWriter] Raw response: {raw[:500]}")
        return None
    except Exception as e:
        print(f"[ScriptWriter] Gemini script generation failed: {e}")
        return None


async def generate_script_claude(
    topic: str,
    niche: str,
    format_type: str = "long",
) -> dict | None:
    """Generate a script using Claude (premium fallback)."""
    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        niche_config = NICHES[niche]
        today = datetime.now().strftime("%B %d, %Y")

        prompt_template = LONG_FORM_PROMPT if format_type == "long" else SHORT_FORM_PROMPT
        niche_style = NICHE_STYLE_GUIDES.get(niche, "Write in an engaging, viewer-focused style.")
        prompt = prompt_template.format(
            topic=topic,
            niche_name=niche_config["name"],
            niche_style_guide=niche_style,
            hashtags=", ".join(niche_config["hashtags"]),
            today=today,
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = _clean_json_response(message.content[0].text)
        script = json.loads(raw)

        if "description" in script:
            script["description"] = _add_affiliate_links(script["description"], niche)

        script["niche"] = niche
        script["format"] = format_type
        script["generated_at"] = datetime.now().isoformat()
        script["ai_model"] = "claude-sonnet"

        return script

    except Exception as e:
        print(f"[ScriptWriter] Claude script generation failed: {e}")
        return None


async def generate_script(
    topic: str,
    niche: str,
    format_type: str = "long",
) -> dict:
    """
    Generate a video script. Tries Gemini first, falls back to Claude.

    Args:
        topic: The video topic
        niche: Niche key from config (ai_trading, ai_money, tech_news)
        format_type: "long" for YouTube, "short" for Shorts/TikTok/Reels

    Returns:
        Script dict with title, scenes, description, tags, etc.
    """
    # Try Gemini first (free)
    script = await generate_script_gemini(topic, niche, format_type)
    if script:
        print(f"[ScriptWriter] Generated {format_type} script via Gemini: {script.get('title', topic)[:60]}")
        return script

    # Fallback to Claude
    script = await generate_script_claude(topic, niche, format_type)
    if script:
        print(f"[ScriptWriter] Generated {format_type} script via Claude: {script.get('title', topic)[:60]}")
        return script

    raise RuntimeError(f"Failed to generate script for topic: {topic}")


def get_full_narration(script: dict) -> str:
    """Extract the full narration text from a script."""
    return " ".join(scene["narration"] for scene in script["scenes"])


def get_scene_visuals(script: dict) -> list[dict]:
    """Extract visual descriptions with timing and narration from a script."""
    return [
        {
            "visual": scene["visual_description"],
            "narration": scene.get("narration", ""),
            "duration": scene["duration_seconds"],
            "scene_number": scene["scene_number"],
        }
        for scene in script["scenes"]
    ]


# CLI test
if __name__ == "__main__":
    import asyncio

    async def test():
        script = await generate_script(
            topic="AI trading bots just outperformed hedge funds in February 2026",
            niche="ai_trading",
            format_type="short",
        )
        print(json.dumps(script, indent=2)[:2000])

    asyncio.run(test())
