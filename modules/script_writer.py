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

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY, NICHES


# ── Niche-Specific Style Guides ────────────────────────────────

NICHE_STYLE_GUIDES = {
    "ai_money": """STYLE: Practical AI money-making educator.
Share REAL, tested methods to earn with AI tools. No fake income claims.
Give step-by-step instructions someone can follow today.
Mention specific free tools by name (ChatGPT, Claude, Canva, Notion).
Tone: Helpful friend sharing what actually works — honest about effort required.""",

    "tech_news": """STYLE: Frontline WAR-NEWS analyst for Tech Pulse Africa.
FOCUS: the CURRENT major world conflict or geopolitical story that is trending right now
(whatever it is — a war, an escalation, a diplomatic crisis, a coup, sanctions, a chokepoint
or resource standoff). Cover strikes, retaliation, proxies, nuclear/ceasefire moves, and the
global/oil/food fallout of THAT story. Keep a neutral, factual war-correspondent tone and,
where relevant, spell out the impact on Africa / South Africa. Do NOT hard-lock to any one
country or conflict — follow the biggest breaking story of the moment.
Explain what is REALLY happening on the ground and how it affects ordinary people.
Report it like breaking war news — urgent, factual, balanced (both sides), verified.
Tone: Bold frontline war correspondent — direct, gripping, no fear-mongering, no sugarcoating.

VISUALS — CRITICAL: every visual_description must SHOW WHAT THAT SCENE'S NARRATION IS ABOUT
— pull the EXACT subject from that line of the story, don't default to a generic war montage.
Match the picture to the words, and make every scene a DIFFERENT, specific shot:
  • sea / Red Sea / blockade / navy → warships, a naval vessel or carrier, patrol boats at sea
  • strikes / retaliation / air raid → a missile launching, drones in the sky, a jet, an airstrike hitting a target
  • oil / economy / shipping fallout → oil tankers, a burning refinery, a busy port, fuel depots
  • nuclear standoff → a nuclear facility, reactor domes, a centrifuge hall
  • a bombed city / civilians → damaged buildings, smoking rubble, people fleeing, rescue workers digging
  • ground fighting → soldiers running and firing through smoke, tanks or a convoy speeding through dust
When it fits the story, INCLUDE the relevant NATIONAL FLAGS of the countries actually involved in
this story on a ship, vehicle, or building, or a clearly identifiable real setting — this anchors it
to the real news.
Keep it dynamic and moving (motion, smoke, speed), but ONE clear, readable subject per shot —
NOT a chaotic jumble of everything at once (that produces malformed AI images).
Figures are GENERIC anonymous soldiers/civilians — NEVER depict a real politician or leader in the
image (fabricating a real leader in combat is misinformation and gets flagged); the narration may
name them, the picture stays anonymous. Never take a side; show the human cost without glorifying.
Every frame should feel like real breaking-news footage of THIS specific story.""",

    "sa_pulse": """STYLE: Trusted South African current-affairs explainer for "Genesis News".
FOCUS: What is happening in South Africa right now and why it matters to ordinary people —
national news and civic events, new laws and government decisions, the job market and real
opportunities, tourism, border/migration policy, cost of living, and social cohesion.
Explain it like a calm, credible SA news explainer — clear, factual, balanced, verified.
Help citizens UNDERSTAND and feel hopeful, not panic.

STRICT SAFETY (non-negotiable — this is sensitive civic content):
- NEUTRAL & NON-PARTISAN: never endorse or attack any political party, leader or group
  (ANC, DA, EFF, MK, IFP, etc.). Report what happened and give balanced context; let the
  viewer decide. No campaigning, no partisan spin.
- NO INCITEMENT: never call for, encourage or glorify protest, violence, looting, or any
  action against anyone. Report civic events calmly and factually; show the human side.
- REAL PEOPLE: only state established, verifiable facts about named people. NEVER invent
  quotes, actions or scandals. When unsure, keep it general and say what is known.
- IMMIGRATION / BORDERS / XENOPHOBIA: frame ONLY around ROOT CAUSES (unemployment,
  inequality, scarce resources, service-delivery and migration-management failures) and
  CONSTRUCTIVE SOLUTIONS (jobs, skills, regional integration, community dialogue, fair and
  efficient policy). NEVER blame, mock or dehumanise any nationality or group; NEVER stoke
  us-vs-them. Keep an empathetic, unifying, pan-African "we rise together" tone.
- NO misinformation, no fear-mongering, no fake statistics. This is general information,
  NOT legal or financial advice.
Tone: Calm, credible, empowering Mzansi voice — a trusted friend who explains the news
honestly and always points toward understanding and solutions.

VISUALS — MUST look unmistakably South African and MATCH each line:
- Show the SOUTH AFRICAN FLAG and instantly-recognisable SA landmarks when they fit —
  Table Mountain, the Union Buildings, Sandton/Joburg skyline, Durban beachfront, Cape Town,
  Parliament, township streets, spaza shops, minibus taxi ranks, robots (traffic lights).
- Every visual_description shows the ACTUAL subject of that line: jobs → people at work /
  interviews / construction; laws → parliament / documents / a courtroom; cost of living →
  shops, groceries, fuel pumps; tourism → landmarks; migration → a border post; grid →
  pylons / substations. If SA money is mentioned, show the RAND.
- Real, everyday South Africans of ALL backgrounds; GENERIC anonymous people only — NEVER
  depict a real politician or leader in the image. One clear, specific, DIFFERENT subject per shot.
- CINEMATIC & DRAMATIC: striking angles, golden-hour light, energy, motion and emotional
  stakes — eye-catching, scroll-stopping footage. But the drama comes from great
  cinematography and real human emotion, NEVER from violence, chaos or degrading imagery.
  Peaceful and dignified, yet gripping.""",

    "motivation": """STYLE: Practical life coach.
Share specific techniques for discipline, habits, and mindset.
Give concrete steps: "Do this for 5 minutes each morning."
Use real psychology and research, not empty hype.
Tone: Supportive mentor who gives straight advice — warm but direct.""",

    "health_wellness": """STYLE: Friendly organic-living & healthy-habits guide for "Herbal Organic Life".
COMPLIANCE: Never claim any food/herb cures, treats, heals, reverses or prevents disease — always use "traditionally used for" / "may support" framing instead.
Share simple, practical everyday tips: organic food, cooking with fresh herbs & spices,
home/herb gardening, whole-food meals, hydration, gentle movement, rest, and calm routines.
Give easy, doable steps a beginner can follow today.
STRICT SAFETY: This is general lifestyle content, NOT medical advice. NEVER claim any food,
herb, or habit treats, cures, prevents, or reverses a disease or condition. No "kills
inflammation", "melts fat", "reverses damage", "doctors are stunned" — no fear-mongering,
no clickbait medical claims, no dosing as medicine. Keep claims modest and honest
("may help you feel more energised", "a simple way to enjoy more veg"). When wellness comes
up, gently remind viewers this is general info and to see a professional for personal advice.
Tone: warm, encouraging friend who loves fresh food and simple living — calm, genuine, helpful.""",

    "blissful_moments": """STYLE: Fun, wholesome baby and kids content for Mzansi Baby Stars.
Share parenting tips, baby milestones, cute moments, and family joy.
Content should celebrate South African family life and culture.
Include practical tips for new parents — feeding, sleep, development.
Tone: Warm, loving parent sharing joy — fun, relatable, proudly South African.""",

    "daily_breakdown": """STYLE: Proudly South African voice for Mzansi Daily.
Share the best of South Africa — news, culture, food, nature, people, innovation.
Cover both the good AND the challenges honestly, but always with love for the country.
Celebrate SA achievements, highlight local heroes, share practical tips for SA life.
Use South African English naturally — lekker, braai, mzansi, eish, ubuntu.
Tone: Proud South African sharing their country with the world — warm, patriotic, honest, real.""",

    "limitless_you": """STYLE: Africa's future — innovation, progress, and opportunity for Africa 2050.
Share stories of African innovation, startups, and progress.
Highlight African tech, entrepreneurs, infrastructure, and youth empowerment.
Focus on solutions and opportunities across the continent.
Tone: Proud, forward-looking African voice — optimistic, informed, inspiring.""",
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
      "visual_description": "Specific Pexels stock footage query, 3-5 concrete words (e.g. 'person analyzing data computer', 'city traffic aerial view'). Must be filmable — NEVER use abstract words like 'unknown', 'concept', 'symbols'.",
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
      "visual_description": "Specific Pexels stock footage query, 3-5 concrete words (e.g. 'stock trading screen green profits', 'person typing laptop office', 'city skyline night lights'). NEVER use abstract words like 'unknown', 'concept', 'abstract', 'symbols'. Must be a real thing a camera can film.",
      "duration_seconds": 5,
      "lower_third_text": "Punchy overlay text (max 6 words, uses numbers when possible)",
      "sfx_hint": "One of: whoosh, impact, money, data, notification, rise, success, reveal, glitch, typing, none"
    }}
  ],
  "thumbnail_text": "Bold 2-4 word hook text"
}}

Requirements:
- Total duration: 25-35 seconds (SWEET SPOT for completion rate)
- 6-10 scenes (cuts every 2-3 seconds — FAST pacing)
- Include hashtags: {hashtags}
- Make the viewer feel something — curiosity, shock, FOMO, or inspiration
- ZERO filler words — every sentence earns its place

Today's date: {today}
Topic: "{topic}"
"""


# ── VIRAL SHORTS Script Prompt (10-30 sec, AI-generated visuals) ──────

VIRAL_SHORTS_PROMPT = """You are creating a {duration_target}-second educational short video that genuinely HELPS people.

Topic: "{topic}"
Niche: {niche_name}

{niche_style_guide}

YOUR MISSION: Give viewers ONE practical, actionable takeaway they can use TODAY.
No clickbait. No fake shock. No hype. Just real value delivered clearly.

STRUCTURE FOR {duration_target}s VIDEO:

1. HOOK (0-3 seconds):
   - Open with a relatable problem or question the viewer actually faces
   - Be direct: "Here's how to..." / "Most people don't know..." / "The simple fix for..."
   - Speak like a knowledgeable friend, not a salesperson

2. TEACH (3-{mid_point} seconds):
   - Share the practical tip, method, or insight
   - Use specific examples, numbers, or steps people can follow
   - Each scene builds understanding — don't repeat, progress
   - Speak naturally — conversational, warm, clear

3. APPLY ({mid_point}-{end_point} seconds):
   - Show how to put it into action right now
   - End with encouragement or a clear next step
   - "Try this today" / "Start with just..." / "Save this for later"

VISUAL DESCRIPTIONS (these search for real stock footage):
- Describe real-world scenes a camera could film
- People doing things, real environments, practical demonstrations
- Use natural settings: offices, kitchens, gyms, nature, streets
- Examples of GOOD descriptions:
  * "Person writing in a journal at a wooden desk, morning light through window"
  * "Close-up of hands preparing a healthy smoothie with fresh fruits"
  * "Person jogging on a trail through autumn trees, early morning"
  * "Overhead view of laptop and notebook on a clean desk"
- Examples of BAD descriptions (NEVER use):
  * "abstract concept of success" (not filmable)
  * "glowing holographic AI interface" (not real footage)
  * "explosive dramatic reveal" (overdramatic)

OUTPUT FORMAT — Return valid JSON:
{{
  "title": "Clear, helpful title under 60 chars — tell people what they'll learn",
  "caption": "Brief description of the tip + relevant hashtags",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Natural spoken words — like talking to a friend. Max 2 sentences.",
      "visual_description": "Real-world scene description for stock footage search. 10-20 words.",
      "duration_seconds": 5,
      "text_overlay": "",
      "sfx_hint": "none"
    }}
  ],
  "thumbnail_text": "2-4 word summary of the tip"
}}

REQUIREMENTS:
- Total duration: EXACTLY {duration_target} seconds (±2 seconds)
- {scene_count} scenes (each 4-6 seconds)
- Be GENUINELY helpful — teach something real
- NO fake numbers, NO manufactured urgency, NO "shocking" claims
- NO text_overlay on scenes — keep visuals clean (captions handle the text)
- sfx_hint should be "none" for most scenes — only use sparingly for transitions
- Include hashtags: {hashtags}
- Make the viewer feel smarter after watching

Today's date: {today}
Topic: "{topic}"
"""


async def generate_viral_short_script(
    topic: str,
    niche: str,
    duration_target: int = 30,
) -> dict | None:
    """
    Generate a viral short-form script (25-35 seconds).

    Optimized for AI-generated visuals and maximum engagement.
    Uses the Hook → Escalation → Payoff structure.
    """
    if not GEMINI_API_KEY:
        return None

    from google import genai
    import asyncio

    client = genai.Client(api_key=GEMINI_API_KEY)
    niche_config = NICHES[niche]
    today = datetime.now().strftime("%B %d, %Y")
    niche_style = NICHE_STYLE_GUIDES.get(niche, "Write in an engaging, viewer-focused style.")

    # Calculate structure based on duration
    mid_point = max(duration_target - 8, duration_target // 2 + 2)
    end_point = duration_target - 2
    scene_count = max(3, duration_target // 5)

    prompt = VIRAL_SHORTS_PROMPT.format(
        topic=topic,
        niche_name=niche_config["name"],
        niche_style_guide=niche_style,
        hashtags=", ".join(niche_config["hashtags"]),
        today=today,
        duration_target=duration_target,
        mid_point=mid_point,
        end_point=end_point,
        scene_count=scene_count,
    )

    # ── Strategy: Claude FIRST (reliable), Gemini fallback (free but rate-limited) ──
    response = None

    # 1. Try Claude first (always available, no rate limits)
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt + "\n\nReturn ONLY valid JSON, no markdown."}],
            )
            if msg.content and msg.content[0].text:
                response = type("R", (), {"text": msg.content[0].text})()
                print(f"[ScriptWriter] Claude generated script successfully")
        except Exception as e:
            print(f"[ScriptWriter] Claude failed: {e}")

    # 2. Gemini fallback (if Claude fails)
    if not response or not response.text:
        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        for model_name in models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    print(f"[ScriptWriter] {model_name} generated script successfully")
                    break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"[ScriptWriter] {model_name} rate limited, trying next...")
                    continue
                print(f"[ScriptWriter] {model_name} failed: {e}")
                continue

    if not response or not response.text:
        return None

    try:
        raw = _clean_json_response(response.text)
        script = json.loads(raw)

        # Add metadata
        script["niche"] = niche
        script["format"] = "viral_short"
        script["duration_target"] = duration_target
        script["generated_at"] = datetime.now().isoformat()
        script["ai_model"] = "gemini"

        # Compliance guardrails (health cure-claims / finance disclaimer)
        script = _sanitize_script(script, niche)

        # Validate total duration
        total = sum(s.get("duration_seconds", 3) for s in script.get("scenes", []))
        if total > duration_target + 5:
            # Scale down scene durations proportionally
            scale = duration_target / total
            for scene in script["scenes"]:
                scene["duration_seconds"] = max(2, round(scene["duration_seconds"] * scale))

        print(f"[ScriptWriter] Viral short ({duration_target}s): {script.get('title', topic)[:60]}")
        return script

    except json.JSONDecodeError as e:
        print(f"[ScriptWriter] JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"[ScriptWriter] Viral short script failed: {e}")
        return None


def _clean_json_response(text: str) -> str:
    """Extract JSON from AI response, handling markdown code blocks."""
    # Remove markdown code blocks
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    return text


def _add_affiliate_links(description: str, niche: str) -> str:
    """Pure content — no affiliate links, no website URLs, no disclaimers.
    Just the description as-is. Clean content only.
    """
    return description


# ── Compliance Guardrails (monetization + legal safety) ────────────
#
# 2026 platform-policy + legal requirement:
#   • Meta throttles / demonetizes disease-cure claims — health content must
#     never claim to cure, treat, heal or reverse a disease.
#   • SA FSCA regulates financial advice — money content must carry a clear
#     "not financial advice" note.
#
# The sanitizer below is niche-aware and applied to the FINAL generated script
# (scene narration + caption/description) as a belt-and-suspenders safety net on
# top of the prompt-level instructions in NICHE_STYLE_GUIDES.

# Health disclaimer appended once to health_wellness scripts.
HEALTH_DISCLAIMER = "Educational only — not medical advice. Consult a healthcare professional."

# Finance disclaimer appended once to ai_money scripts.
FINANCE_DISCLAIMER = "Not financial advice — for education only."

# Case-insensitive disease-cure verbs → safe wellness framing.
# Order matters: longer / inflected forms first so "cures" is matched before "cure".
# Kept conservative and readable — targeted phrase swaps, never blunt deletion.
HEALTH_CLAIM_REPLACEMENTS = [
    (r"\bcuring\b", "supporting"),
    (r"\bcures\b", "may support"),
    (r"\bcure\b", "may support"),
    (r"\btreats\b", "may help with"),
    (r"\btreat\b", "may help with"),
    (r"\bheals\b", "may soothe"),
    (r"\bheal\b", "may soothe"),
    (r"\beliminates\b", "may reduce"),
    (r"\beliminate\b", "may reduce"),
    (r"\breverses\b", "may improve"),
    (r"\breverse\b", "may improve"),
    (r"\bprevents\b", "may help maintain"),
    (r"\bprevent\b", "may help maintain"),
]

# Serious medical conditions — a benefit claim tied to any of these is downgraded
# wholesale to a modest "traditionally used" statement (stronger than the generic
# verb swap above, because naming a disease + a benefit is the highest-risk pattern).
SERIOUS_CONDITIONS = (
    r"cancer|tumou?rs?|diabetes|diabetic|hiv|aids|hypertension|"
    r"high blood pressure|blood pressure|heart disease|stroke|"
    r"alzheimer'?s|arthritis|asthma|depression|covid(?:-?19)?"
)

# Verbs that, when paired with a serious condition, constitute a medical claim.
_CLAIM_VERBS = (
    r"cure[sd]?|curing|treat[s]?|heal[s]?|healing|eliminate[s]?|"
    r"reverse[s]?|reversing|prevent[s]?|fight[s]?|fighting|beat[s]?|"
    r"kill[s]?|cures?|remed(?:y|ies)|may support|may help with|may soothe|"
    r"may reduce|may improve|may help maintain"
)

# Matches "<verb> ... <condition>" OR "<condition> ... <verb>" within a short window.
_SERIOUS_CLAIM_PATTERNS = [
    re.compile(
        rf"\b(?:{_CLAIM_VERBS})\b(?:\s+\w+){{0,3}}?\s+(?:{SERIOUS_CONDITIONS})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:{SERIOUS_CONDITIONS})\b(?:\s+\w+){{0,3}}?\s+(?:{_CLAIM_VERBS})\b",
        re.IGNORECASE,
    ),
]

_SAFE_CONDITION_PHRASE = "traditionally used in herbal traditions for wellness"


def _apply_compliance_guardrails(text: str, niche: str, append_disclaimer: bool = True) -> str:
    """Sanitize a generated script/caption for legal + monetization safety.

    Niche-aware:
      • health_wellness — soften disease-cure language into modest wellness
        framing, downgrade serious-condition benefit claims, and (when
        ``append_disclaimer``) append a persistent medical disclaimer once.
      • ai_money — (when ``append_disclaimer``) append a "not financial advice"
        note once. Text is otherwise left untouched.
      • all other niches — returned unchanged.

    Args:
        text: The script/caption/narration text to sanitize.
        niche: The content niche key (e.g. "health_wellness", "ai_money").
        append_disclaimer: Whether to append the niche disclaimer. Set False when
            sanitizing individual scene narrations (so the spoken disclaimer is not
            repeated per scene) and True for the single caption/description field.

    Returns:
        The sanitized text (conservative, readable phrase-level edits only).
    """
    if not text or not isinstance(text, str):
        return text

    if niche == "health_wellness":
        # 1. Downgrade the highest-risk pattern first: a benefit claim tied to a
        #    named serious condition → a single modest "traditionally used" phrase.
        for pattern in _SERIOUS_CLAIM_PATTERNS:
            text = pattern.sub(_SAFE_CONDITION_PHRASE, text)

        # 2. Soften remaining generic disease-cure verbs into wellness framing.
        for pattern, replacement in HEALTH_CLAIM_REPLACEMENTS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # 3. Append the persistent disclaimer once (never duplicate).
        if append_disclaimer and HEALTH_DISCLAIMER not in text:
            text = f"{text.rstrip()} {HEALTH_DISCLAIMER}"
        return text

    if niche == "ai_money":
        # Finance: ensure the "not financial advice" note is present once.
        if append_disclaimer and FINANCE_DISCLAIMER not in text:
            text = f"{text.rstrip()} {FINANCE_DISCLAIMER}"
        return text

    # All other niches: unchanged.
    return text


def _sanitize_script(script: dict, niche: str) -> dict:
    """Apply compliance guardrails across a full script dict in place.

    Sanitizes every scene's narration (without repeating the disclaimer) and
    appends the disclaimer once to the caption/description field. No-op for
    niches other than health_wellness and ai_money.
    """
    if niche not in ("health_wellness", "ai_money") or not isinstance(script, dict):
        return script

    # Scene narration — sanitize wording, but do NOT append the disclaimer per scene.
    for scene in script.get("scenes", []):
        if isinstance(scene, dict) and scene.get("narration"):
            scene["narration"] = _apply_compliance_guardrails(
                scene["narration"], niche, append_disclaimer=False
            )

    # Caption / description — sanitize AND append the disclaimer once.
    for field in ("caption", "description"):
        if script.get(field):
            script[field] = _apply_compliance_guardrails(
                script[field], niche, append_disclaimer=True
            )

    return script


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

    prompt_template = SHORT_FORM_PROMPT  # Shorts only — no long-form
    niche_style = NICHE_STYLE_GUIDES.get(niche, "Write in an engaging, viewer-focused style.")
    prompt = prompt_template.format(
        topic=topic,
        niche_name=niche_config["name"],
        niche_style_guide=niche_style,
        hashtags=", ".join(niche_config["hashtags"]),
        today=today,
    )

    # Aggressive retry: cycle models with escalating waits (Gemini free tier resets per-minute)
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]  # Current models (July 2026)
    response = None
    max_rounds = 3

    for round_num in range(max_rounds):
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
                    wait = 5 * (round_num + 1)
                    print(f"[ScriptWriter] {model_name} rate limited (round {round_num+1}), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                print(f"[ScriptWriter] {model_name} failed: {e}")
                continue
        if response and response.text:
            break
        if round_num < max_rounds - 1:
            wait = 30 * (round_num + 1)
            print(f"[ScriptWriter] All models rate limited. Waiting {wait}s before round {round_num+2}...")
            await asyncio.sleep(wait)

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

        # Compliance guardrails (health cure-claims / finance disclaimer)
        script = _sanitize_script(script, niche)

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

        prompt_template = SHORT_FORM_PROMPT  # Shorts only — no long-form
        niche_style = NICHE_STYLE_GUIDES.get(niche, "Write in an engaging, viewer-focused style.")
        prompt = prompt_template.format(
            topic=topic,
            niche_name=niche_config["name"],
            niche_style_guide=niche_style,
            hashtags=", ".join(niche_config["hashtags"]),
            today=today,
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
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

        # Compliance guardrails (health cure-claims / finance disclaimer)
        script = _sanitize_script(script, niche)

        return script

    except Exception as e:
        print(f"[ScriptWriter] Claude script generation failed: {e}")
        return None


async def generate_script(
    topic: str,
    niche: str,
    format_type: str = "short",
) -> dict:
    """
    Generate a video script. SHORTS ONLY pipeline.

    For shorts: uses generate_viral_short_script (optimized 30s format)
    Falls back to Claude direct if viral script fails.
    """
    # Shorts use the viral shorts pipeline (Claude primary, Gemini fallback)
    if format_type in ("short", "viral_short"):
        script = await generate_viral_short_script(topic, niche, duration_target=30)
        if script:
            print(f"[ScriptWriter] Generated viral short: {script.get('title', topic)[:60]}")
            return script

    # Direct Claude fallback for any format
    script = await generate_script_claude(topic, niche, format_type)
    if script:
        print(f"[ScriptWriter] Generated {format_type} script via Claude: {script.get('title', topic)[:60]}")
        return script

    raise RuntimeError(f"Failed to generate script for topic: {topic}")


# ── News Anchor Script Prompt (Daily Breakdown) ──────────────────

NEWS_ANCHOR_SCRIPT_PROMPT = """You are a WORLD-CLASS news analyst creating viral short-form content. Think Tucker Carlson's confidence meets Vice News's edge meets CNN's authority. You don't just report — you ANALYZE with fire.

{niche_style_guide}

TODAY'S NEWS STORIES:
{news_stories}

AVAILABLE VIDEO CLIPS & IMAGES (visual assets we have):
{available_clips}

YOUR TASK: Write a punchy 50-65 second news analysis script that DEMANDS attention.

HOOK FORMULA (First 3 seconds — viewer decides to stay or scroll):
- Open with a SHOCKING statement, question, or revelation
- Examples: "This changes EVERYTHING." / "Nobody's talking about this." / "You need to see this."
- Make it personal — "Here's what they're NOT telling you about..."
- NEVER start generic ("Today we're looking at..."). That's boring.

STORY ANALYSIS RULES:
- Cover 2-3 stories, ~15 seconds each
- ALWAYS reference the visuals: "Look at this footage...", "As you can see right here..."
- Don't just state facts — give YOUR take: "Here's what this REALLY means..."
- Use contrast and tension: "While the world watches X, nobody noticed Y"
- Include NUMBERS and specifics — "42% increase", "3 countries", "since March 2026"
- Use power phrases: "Make no mistake", "Let that sink in", "Here's the truth"
- Short punchy sentences. Not academic. Conversational but authoritative.

TRANSITIONS (keep momentum):
- "But here's where it gets interesting..."
- "Now, meanwhile on the other side of the world..."
- "And it gets worse."
- "But wait — there's more to this story."
- NEVER: "Moving on to our next story..."

WRAP-UP (last 5-7 seconds):
- Bold prediction OR provocative question
- "The real question is... [thought-provoking question]"
- End with CTA: "Follow for more breakdowns you won't see on mainstream media."

CRITICAL: Each scene MUST use a clip_index matching the available clips above. Distribute clips evenly — use DIFFERENT clips for different scenes. If we have 6 clips, use all 6 across scenes.

OUTPUT FORMAT — Return valid JSON only (no markdown, no ```):
{{
  "title": "Punchy headline (under 60 chars, provocative news-style)",
  "caption": "Engaging caption with context + emojis + hashtags",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Exact words — punchy, direct, conversational authority",
      "visual_description": "The SPECIFIC real subject of THIS line, shot CINEMATICALLY and full of DRAMA — a striking angle, motion, energy or emotional tension that stops the scroll. Name the exact place/person-type/object/flag/landmark the narration mentions (country→its FLAG or landmark, city→its skyline, money→the currency). Dynamic and different every scene, never a static generic stock shot. Think dramatic news-film footage: bold, moving, eye-catching — but always showing THAT exact subject.",
      "clip_index": 0,
      "duration_seconds": 4,
      "lower_third_text": "BREAKING: max 8 words headline",
      "sfx_hint": "One of: whoosh, impact, notification, rise, reveal, suspense_hit, none"
    }}
  ],
  "thumbnail_text": "2-4 word CURIOSITY hook — intriguing, NOT alarmist. Never a fake instruction (no 'EVACUATE NOW', no panic/warning commands, no false claims). Must fit the actual story. Good: 'CAUGHT IN THE MIDDLE', 'THE REAL REASON', 'WHY IT MATTERS'"
}}

Requirements:
- Total duration: 50-65 seconds
- 6-8 scenes (more scenes = more visual variety)
- Scene 1 = HOOK (3-4 seconds, maximum impact)
- Last scene = WRAP-UP + CTA (5-7 seconds)
- Include hashtags: {hashtags}
- Narration must be CONVERSATIONAL — like you're telling a friend the most insane news
- VISUALS MUST MATCH THE WORDS *and* BE DRAMATIC: every scene's visual_description shows the
  EXACT thing that line is about (name a country → its FLAG or landmark, a city → its skyline,
  money → the currency) AND makes it cinematic — motion, energy, striking angles, emotional
  tension. That drama is what stops the scroll and wins views. Never generic B-roll that could
  belong to any video; one clear, specific, DIFFERENT subject per scene. Applies to EVERY channel.
- Use clip_index values from 0 to {max_clip_index} to reference available clips

Today's date: {today}
"""


async def generate_news_anchor_script(
    news_stories: list[dict],
    available_clips: list[dict],
    niche: str = "daily_breakdown",
) -> dict | None:
    """
    Generate a news analysis script based on pre-fetched stories and clips.

    This is the REVERSED flow: clips are fetched first, script references them.

    Args:
        news_stories: List of dicts with headline, summary, region
        available_clips: List of dicts with clip descriptions and paths
        niche: Niche key (default: daily_breakdown)

    Returns:
        Script dict with title, scenes (each with clip_index), caption, etc.
    """
    if not GEMINI_API_KEY:
        return None

    from google import genai

    niche_config = NICHES.get(niche, NICHES["daily_breakdown"])
    today = datetime.now().strftime("%B %d, %Y")
    niche_style = NICHE_STYLE_GUIDES.get(niche, "Speak with authority as a news analyst.")

    # Format stories for the prompt
    stories_text = ""
    for i, story in enumerate(news_stories):
        stories_text += f"\nStory {i+1} [{story.get('region', 'world').upper()}]:\n"
        stories_text += f"  Headline: {story['headline']}\n"
        stories_text += f"  Summary: {story.get('summary', 'No details available')}\n"
        stories_text += f"  Source: {story.get('source', 'unknown')}\n"

    # Format clips for the prompt
    clips_text = ""
    for i, clip in enumerate(available_clips):
        desc = clip.get("visual_description", clip.get("query", f"clip {i}"))
        clips_text += f"  Clip {i}: {desc}\n"

    prompt = NEWS_ANCHOR_SCRIPT_PROMPT.format(
        niche_style_guide=niche_style,
        news_stories=stories_text,
        available_clips=clips_text,
        hashtags=", ".join(niche_config.get("hashtags", [])),
        today=today,
        max_clip_index=max(len(available_clips) - 1, 0),
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]  # Current models (July 2026)
    response = None

    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt,
            )
            if response and response.text:
                print(f"[ScriptWriter] News anchor using {model_name}")
                break
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                import asyncio
                print(f"[ScriptWriter] {model_name} rate-limited, waiting 20s...")
                await asyncio.sleep(20)
                # Retry same model once after wait
                try:
                    response = client.models.generate_content(
                        model=model_name, contents=prompt,
                    )
                    if response and response.text:
                        print(f"[ScriptWriter] News anchor using {model_name} (retry)")
                        break
                except Exception:
                    continue
            else:
                print(f"[ScriptWriter] News anchor {model_name} failed: {e}")
            continue

    # Claude fallback if Gemini is exhausted
    if not response or not response.text:
        try:
            from config import ANTHROPIC_API_KEY as CLAUDE_API_KEY
            if CLAUDE_API_KEY:
                import anthropic
                print("[ScriptWriter] Gemini exhausted — falling back to Claude...")
                claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
                claude_response = claude_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt + "\n\nReturn ONLY valid JSON, no markdown."}],
                )
                if claude_response.content:
                    response = type("Resp", (), {"text": claude_response.content[0].text})()
                    print("[ScriptWriter] News anchor using Claude fallback")
        except Exception as e:
            print(f"[ScriptWriter] Claude fallback failed: {e}")

    if not response or not response.text:
        return None

    try:
        raw = _clean_json_response(response.text)
        script = json.loads(raw)

        # Ensure clip_index exists on each scene
        for scene in script.get("scenes", []):
            if "clip_index" not in scene:
                scene["clip_index"] = min(scene.get("scene_number", 1) - 1, len(available_clips) - 1)

        script["niche"] = niche
        script["format"] = "news_anchor"
        script["generated_at"] = datetime.now().isoformat()
        script["ai_model"] = "gemini"
        script["news_stories"] = news_stories

        # Compliance guardrails (no-op unless health/finance niche)
        script = _sanitize_script(script, niche)

        print(f"[ScriptWriter] News anchor script: {script.get('title', 'untitled')[:60]}")
        return script

    except json.JSONDecodeError as e:
        print(f"[ScriptWriter] News anchor JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"[ScriptWriter] News anchor script failed: {e}")
        return None


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
