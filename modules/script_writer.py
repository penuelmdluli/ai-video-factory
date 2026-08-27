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

    "sa_pulse": """STYLE: High-energy South African PSL football news for "Genesis News" —
the page Mzansi checks for Kaizer Chiefs, Orlando Pirates and Mamelodi Sundowns.
You sound like a clued-up Mzansi football show host: fast, passionate, opinionated about
the FOOTBALL, but never loose with the facts. Speak to fans, not at them.

PRIORITY — KAIZER CHIEFS FIRST: Amakhosi drive the most engagement in SA football. Lead
with Chiefs whenever there is a Chiefs angle, and when covering Pirates or Sundowns, tell
it through what it MEANS for the title race and for Chiefs' rivals.

REEL STRUCTURE (follow this beat map for every short):
- HOOK (0:00-0:05): a bold question or claim that starts an argument.
  e.g. "Are Chiefs FINALLY ready for Sundowns?" / "Is this the signing Amakhosi needed?"
  Name the clubs in the first sentence so the algorithm and the fan both know instantly.
- THE NEWS (0:05-0:25): the actual story — who, what, when, and the result or quote that
  was really reported. Include a real detail: a scoreline that was played, a named player,
  a coach's actual words, a fixture and venue.
- THE KEY BATTLE (0:25-0:45): the football insight — the matchup, the tactical question,
  the form line, the player under pressure. This is what makes it worth watching.
- CALL TO ACTION (0:45-0:60): GIVE THE VIEWER A JOB.
  Our own numbers: a news reel did 46,225 views and got 5 comments, while a
  "who starts" post did 33,747 and got 138, and the matchday post got 345.
  Views without replies leave nothing behind — replies are what keep the page
  in front of the same people. So the closing question must be SPECIFIC and
  ANSWERABLE IN THREE WORDS, about a choice only a fan can make:
    "Who starts on Saturday - Phili or Baartman?"
    "Name the one player you would drop."
    "Your score: comment it now."
  BANNED: "what do you think", "let us know", "thoughts?", "comment below"
  on their own - nobody answers a question with no answer in it.
  Then the closing ask.
  THE CLOSING LINE IS MANDATORY and must use the word "subscribe" out loud, with a
  REASON to come back — not a bare "follow us". The same audio runs on YouTube,
  Facebook and TikTok, and on YouTube "subscribe" is the action that counts.
  Vary the wording every time, and name what they get:
    "Subscribe to Genesis News — we call every Chiefs game before kick-off."
    "Subscribe. We break the team news before the whistle."
    "Hit subscribe — the log race, every Friday, on Genesis News."
  Never end on the debate question alone.

TITLE RULES (the title decides whether anyone presses play — treat it as the
single most important line you write):
- 55 characters or fewer. Front-load the club or the derby: "Chiefs vs Sundowns:",
  "Pirates' ", "Sundowns Just...".
- Open an information gap around a REAL fact from the headlines — make them need
  the answer: "The One Battle That Decides Chiefs vs Sundowns",
  "Why Sundowns Fear This Chiefs Change", "'We Fear No One' — Inside Chiefs' Plan".
- A named player + a stake beats anything generic: "Shabalala's Biggest Test Yet"
  beats "Chiefs Team News".
- Numbers work: "3 Battles", "2 Changes", "The 89th-Minute Problem".
- NEVER promise what the video doesn't deliver, never invent a fact or score for
  the title, no ALL-CAPS words (club initials excepted), no emoji in the title.

STRICT FACTUALITY (non-negotiable — football fans fact-check instantly):
- Use ONLY facts supplied in the live headlines / topic brief. NEVER invent a scoreline,
  a goalscorer, a transfer, a signing, an injury, a log position or a quote.
- Anything reported as a rumour stays a rumour: say "reports claim", "reports suggest",
  "is being linked with" — NEVER state it as done.
- NEVER name an outlet in the narration or on screen ("Goal.com", "Soccer Laduma",
  "iDiski Times" must not be SPOKEN). Attribute to the person only: "Miguel said",
  "reports claim". Credit the outlets in the DESCRIPTION instead — end the description
  with a line like "Sources: Soccer Laduma, Goal.com".
- If a detail is not in the brief, leave it out. A shorter true script beats a fuller fake
  one. Never guess a fixture date, a final score or a squad list.
- NO betting tips, odds, or "guaranteed" predictions. Fan opinion is fine; gambling advice
  is not.
- RESPECT: criticise performance, tactics and decisions — NEVER insult a player, coach,
  referee or fan base personally, and never mock a club's supporters. No claims about
  anyone's private life. Passionate rivalry banter only, the kind that keeps comments fun.

Tone: Loud, warm, proudly South African — but the narration is READ BY A VOICE
that struggles with Nguni words, so in NARRATION always use the pronounceable
names: "Kaizer Chiefs" (never "Amakhosi"), "Sundowns" (never "Masandawana"),
"Pirates" or "the Buccaneers" (fine), "FNB Stadium" or "the Calabash", "the
Soweto Derby". Local flavour words (Amakhosi, Masandawana, eS'Godini, shibobo)
may ONLY appear in the description/hashtags, never in a scene's narration.

VISUALS — matchday energy, and legally/ethically safe:
- Every visual_description is football: packed stands under floodlights, fans mid-roar with
  vuvuzelas and makarapas, a keeper flying across goal, a tackle in midfield, boots and ball
  on grass, a coach pacing the touchline, an empty stadium at golden hour, Soweto streets in
  club colours.
- ANONYMOUS people and GENERIC unbranded kit ONLY. NEVER describe a real, recognisable
  footballer, coach or official, and NEVER a club badge, logo, sponsor or replica shirt —
  generated images of real players are misinformation and club marks are trademarked.
  The narration names real people; the picture stays generic.
- Use plain COLOUR to signal a club instead of a badge: gold and black for Chiefs, black and
  white for Pirates, yellow for Sundowns.
- Match the shot to the line: transfer talk → a lone player walking out of a tunnel; injury
  → a physio and a strapped ankle; a big fixture → a heaving crowd; the log → floodlights
  over a full stadium.
- CINEMATIC SPORTS PHOTOGRAPHY: long-lens compression, motion blur, grass spray, sweat,
  flares of stand colour, night floodlight haze. Drama from atmosphere and emotion —
  never from crowd trouble, violence or anything degrading.""",

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


async def _live_facts_block(niche: str) -> str:
    """
    Real, sourced headlines appended to the script prompt for fact-bound niches.

    The topic generator already picks the topic from live headlines, but the
    script writer only received the topic STRING — leaving the model free to
    invent the scoreline, the signing and the quote that fill the 60 seconds.
    For football that is instantly falsifiable, so the same sourced headlines
    are handed to the script writer as the only permitted facts.

    Returns "" for every other niche (and on any failure) — behaviour unchanged.
    """
    try:
        if not NICHES.get(niche, {}).get("use_live_headlines"):
            return ""
        from modules.psl_news import headlines_for_prompt
        live = await headlines_for_prompt()
        if not live:
            print(f"[ScriptWriter] {niche}: no live headlines — keeping script general")
            return ""
        return (
            f"\n\n## LIVE SOURCED HEADLINES — THE ONLY FACTS YOU MAY STATE\n{live}\n\n"
            f"HARD RULES:\n"
            f"- Every specific claim in the narration (score, goalscorer, signing, injury, "
            f"quote, fixture, log position) MUST come from the list above, word for word in "
            f"substance. If it is not there, do NOT say it.\n"
            f"- NEVER speak an outlet name in the narration ('Goal.com', 'Soccer Laduma', "
            f"'iDiski Times' etc. must not appear in any scene). Attribute to the person "
            f"only ('Miguel said', 'reports claim'). CREDIT every outlet you used in the "
            f"description field instead — end the description with 'Sources: <outlets>'.\n"
            f"- Items flagged REPORT/RUMOUR must be voiced as reports, never as done deals.\n"
            f"- If the headlines are thin, write a shorter, opinion-and-preview script rather "
            f"than inventing detail. A true short beats a fake full one.\n"
            f"- DO NOT INFER: if a headline does not say a player was signed, transferred, "
            f"injured, dropped or made his debut, do not say it.\n"
            f"- QUOTES ARE SACRED: only quote words that appear inside quote marks in the "
            f"headlines above, verbatim and attributed to the SAME person (the outlet that "
            f"published it goes in the description Sources line, never the narration). "
            f"Never merge two headlines into one quote, never trim a quote into a fragment, and "
            f"never attach a quote to a different person. If you cannot quote it exactly, "
            f"paraphrase without quote marks.\n"
            f"- NO STALE KNOWLEDGE: do not reference a trophy drought, a trophyless run, a "
            f"last-trophy date, a league position, a head-to-head record or a manager's tenure "
            f"unless it appears above. Kaizer Chiefs ENDED their 10-year drought by winning the "
            f"2025 Nedbank Cup — 'can Chiefs finally win a trophy' is wrong and fans will say so.\n"
            f"- NAME ONLY, NO LABELS: say 'Sphelele Mkhulise', never 'Sundowns striker Sphelele "
            f"Mkhulise'. Do not attach a position (striker/midfielder/defender/keeper), age, "
            f"nationality or club history to any player unless those exact words appear in the "
            f"headlines above. Getting a player's position wrong is the fastest way to lose fans.\n"
            f"- Lead with Kaizer Chiefs whenever the list has a Chiefs angle."
        )
    except Exception as e:
        print(f"[ScriptWriter] live facts unavailable for {niche}: {e}")
        return ""


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
    prompt += await _live_facts_block(niche)

    # ── Strategy: Claude FIRST (reliable), Gemini fallback (free but rate-limited) ──
    response = None

    # 0. Claude via the local Claude Code CLI — uses the subscription already paid
    # for, so it costs nothing per call and does not depend on API credits. This is
    # PRIMARY; the API key below is now only a fallback.
    if not response:
        try:
            from modules.claude_cli import claude_cli_complete, cli_enabled
            if cli_enabled():
                text = await claude_cli_complete(
                    prompt + "\n\nReturn ONLY valid JSON, no markdown, no commentary."
                )
                if text:
                    response = type("R", (), {"text": text})()
                    print("[ScriptWriter] Claude CLI (subscription) generated script")
        except Exception as e:
            print(f"[ScriptWriter] Claude CLI failed: {e}")

    # 1. Try Claude API (fallback — needs credits on ANTHROPIC_API_KEY)
    if not response and ANTHROPIC_API_KEY:
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
        models = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]
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
    """Extract the JSON object from an AI response.

    Models often append a sentence after the JSON ("Here is the script...",
    a note, a second fenced block). json.loads then dies with "Extra data",
    which failed a whole build. Take the FIRST balanced {...} object and
    ignore whatever follows.
    """
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    start = text.find("{")
    if start == -1:
        return text
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


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
    prompt += await _live_facts_block(niche)

    # Aggressive retry: cycle models with escalating waits (Gemini free tier resets per-minute)
    models = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]  # Refreshed 2026-08-14: 2.0-flash + 2.0-flash-lite are retired (404)
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
        prompt += await _live_facts_block(niche)

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


# Role/position words that are claims about a real person. Stating one the sources
# never gave is the fastest credibility kill on a football page — a fan knows
# instantly that Luke Baartman is a winger, not a "midfield engine".
_ROLE_WORDS = re.compile(
    r"\b(striker|strikers|winger|wingers|midfielder|midfielders|midfield|defender|"
    r"defenders|goalkeeper|goalkeepers|keeper|keepers|forward|forwards|captain|"
    r"skipper|left-back|right-back|centre-back|center-back|fullback|full-back)\b",
    re.IGNORECASE,
)

# "Sundowns striker Sphelele Mkhulise" → "Sphelele Mkhulise". Strips the label but
# keeps the person, so the sentence still reads naturally.
# The case-insensitive flag is scoped to the words that need it. Applying it to
# the whole pattern makes [A-Z] match lowercase, so "striker does in the ninety
# seconds" parsed as "<role> <Name>" and the scrub produced "watch what the does".
_LABEL_BEFORE_NAME = re.compile(
    r"\b(?:(?i:chiefs|kaizer chiefs|amakhosi|pirates|orlando pirates|buccaneers|bucs|"
    r"sundowns|mamelodi sundowns|masandawana)\s+)?"
    r"(?i:striker|winger|midfielder|defender|goalkeeper|keeper|forward|skipper|"
    r"left-back|right-back|centre-back|center-back|fullback|full-back)\s+"
    r"(?=[A-Z][a-z]+\s+[A-Z])"
)

# A bare role word with no name after it (e.g. "watch what the striker does").
# Deleting it breaks the sentence, so swap in a neutral noun instead — the claim
# disappears, the grammar survives.
_BARE_ROLE = re.compile(
    r"\b(?i:striker|strikers|winger|wingers|midfielder|midfielders|defender|defenders|"
    r"goalkeeper|goalkeepers|keeper|keepers|forward|forwards)\b"
)


# Claims the model reaches for from stale training knowledge rather than from the
# feed. The trophy-drought line is the live example: Chiefs ended a 10-year drought
# by winning the 2025 Nedbank Cup, so "can Chiefs finally end their drought?" is both
# wrong and the kind of thing Amakhosi fans pile on. Anything here must be earned
# from a source headline or it does not go out.
_STALE_CLAIMS = re.compile(
    r"(trophy drought|trophyless|silverware drought|without a trophy|"
    r"haven'?t won (?:a|any) (?:trophy|silverware)|has not won (?:a|any) (?:trophy|silverware)|"
    r"last (?:won a )?trophy|end(?:ing)? (?:their|the) (?:long )?wait for silverware)",
    re.IGNORECASE,
)

# Safe closers used when a scene's only content was an unsourced claim.
_SAFE_CTA = "Drop your score prediction in the comments and follow Genesis News for every PSL update."


def _unsourced_claims(script: dict, sources_text: str) -> list[str]:
    """Stale-knowledge claims that no source headline supports."""
    src = (sources_text or "").lower()
    found = set()
    for scene in script.get("scenes", []) or []:
        for m in _STALE_CLAIMS.findall(scene.get("narration", "") or ""):
            phrase = m if isinstance(m, str) else m[0]
            if phrase.lower() not in src:
                found.add(phrase.lower())
    return sorted(found)


def _strip_claim_sentences(script: dict) -> dict:
    """Drop whole sentences carrying a stale claim; keep the scene speakable."""
    for scene in script.get("scenes", []) or []:
        n = scene.get("narration") or ""
        if not n or not _STALE_CLAIMS.search(n):
            continue
        kept = [s for s in re.split(r"(?<=[.!?])\s+", n) if not _STALE_CLAIMS.search(s)]
        scene["narration"] = " ".join(kept).strip() or _SAFE_CTA
    return script


# Quoted speech only. The apostrophe in "here's" / "it's" is NOT an opening quote —
# an earlier version treated it as one and shredded whole scripts, so a single-quoted
# span must start at a word boundary and close before punctuation/whitespace.
_QUOTE_SPAN = re.compile(
    r"[\"“]([^\"”\n]{8,})[\"”]"
    r"|(?:^|(?<=[\s:,—–-]))['‘]([^'’\n]{8,})['’](?=[\s.,!?;:]|$)"
)


def _quotes_in(text: str) -> list[str]:
    return [a or b for a, b in _QUOTE_SPAN.findall(text or "") if (a or b)]


def _norm_words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split())


def _unsourced_quotes(script: dict, sources_text: str) -> list[str]:
    """
    Quoted speech in the narration that no source headline actually contains.

    Putting words in a named person's mouth — and crediting a named outlet for
    them — is the most damaging thing this page can do. Observed failure: the
    model merged two headlines into "Goal.com reports Monyane said 'We look to
    keep up that'", which nobody said. A quote must appear in the sources
    verbatim (first six words) or it does not air.
    """
    src = _norm_words(sources_text)
    if not src:
        return []
    bad = []
    for scene in script.get("scenes", []) or []:
        for raw in _quotes_in(scene.get("narration", "")):
            q = _norm_words(raw)
            if not q:
                continue
            head = " ".join(q.split()[:6])
            if head and head not in src:
                bad.append(raw.strip())
    return bad


def _split_sentences(text: str) -> list[str]:
    """Split on sentence ends, allowing a closing quote mark after the stop."""
    return [s for s in re.split(r"(?<=[.!?])['\"’”]?\s+", text) if s.strip()]


def _strip_quote_sentences(script: dict, sources_text: str) -> dict:
    """
    Drop only the sentences whose quote is unverifiable — a correctly sourced
    quote is the most valuable line in the script and must survive.
    """
    src = _norm_words(sources_text)
    scenes = script.get("scenes", []) or []
    for scene in scenes:
        n = scene.get("narration") or ""
        if not n or not _quotes_in(n):
            continue
        kept = []
        for s in _split_sentences(n):
            unsourced = any(
                " ".join(_norm_words(q).split()[:6]) not in src
                for q in _quotes_in(s) if _norm_words(q)
            )
            if not unsourced:
                kept.append(s)
        scene["narration"] = " ".join(kept).strip()
    # An emptied scene is DROPPED, never back-filled with the CTA — a stray
    # "drop your prediction" as scene 1 wrecked a build.
    script["scenes"] = [s for s in scenes if (s.get("narration") or "").strip()]
    return script


# "defender Inacio Miguel" — the role must be sourced FOR THIS PLAYER. A global
# allow-list let "defender" through because a different headline called a Pirates
# player a defender, which is how Inacio Miguel got the wrong position.
# NOTE: the case-insensitive flag is scoped to the role words only. Applying it to
# the whole pattern makes [A-Z] match lowercase, so "defender Inacio Miguel says"
# captured the name as "Inacio Miguel says".
_ROLE_THEN_NAME = re.compile(
    r"\b((?i:striker|winger|midfielder|defender|goalkeeper|keeper|forward|skipper|captain))\s+"
    r"((?:[A-Z][\w'’-]+\s+){0,2}[A-Z][\w'’-]+)"
)


def _unsourced_roles(script: dict, sources_text: str) -> list[str]:
    """
    Role words the sources do not support — checked per player, not globally.

    A role is allowed only if some single source line contains BOTH the role word
    and that player's surname. A bare role word with no name attached is allowed
    only if the sources use it somewhere.
    """
    src_lines = [_norm_words(l) for l in (sources_text or "").splitlines() if l.strip()]
    loose_ok = {w.lower() for w in _ROLE_WORDS.findall(sources_text or "")}
    found = set()
    for scene in script.get("scenes", []) or []:
        text = scene.get("narration", "") or ""
        paired = {}
        for role, name in _ROLE_THEN_NAME.findall(text):
            surname = _norm_words(name).split()[-1] if _norm_words(name) else ""
            paired[role.lower()] = surname
            if not any(role.lower() in l and surname and surname in l for l in src_lines):
                found.add(f"{role.lower()} {surname}".strip())
        for w in _ROLE_WORDS.findall(text):
            if w.lower() not in paired and w.lower() not in loose_ok:
                found.add(w.lower())
    return sorted(found)


# Outlet domains read badly aloud. Kokoro turned "Goal.com" into "Goal dot com
# dot com" in a shipped voiceover. Say the masthead the way a presenter would.
_SPEAKABLE_SOURCES = [
    (re.compile(r"\bGoal\.com(?:\.com)*\b", re.IGNORECASE), "Goal dot com"),
    (re.compile(r"\biol\.co\.za\b", re.IGNORECASE), "IOL"),
    (re.compile(r"\bsupersport\.com\b", re.IGNORECASE), "SuperSport"),
    (re.compile(r"\bflashscore\.co\.za\b", re.IGNORECASE), "Flashscore"),
    (re.compile(r"\bkickoff\.com\b", re.IGNORECASE), "KickOff"),
    (re.compile(r"\bsoccerladuma\.co\.za\b", re.IGNORECASE), "Soccer Laduma"),
    (re.compile(r"\bidiskitimes\.co\.za\b", re.IGNORECASE), "iDiski Times"),
    (re.compile(r"\btimeslive\.co\.za\b", re.IGNORECASE), "TimesLIVE"),
]


# Outlets we may quote from. Spoken narration must never contain them; the
# description carries the credit ("Sources: ...") instead.
_OUTLET_NAMES = [
    "Soccer Laduma", "Goal.com", "Goal", "iDiski Times", "KickOff", "FARPost",
    "SABC Sport", "TimesLIVE", "SuperSport", "Sowetan", "Daily Sun", "The Citizen",
    "IOL", "News24", "SoccerLaduma",
]
_OUTLET_PHRASE = re.compile(
    r"\s*(?:,?\s*)?(?:according to|as per|per|reports? (?:from|by|in)|via|told|"
    r"speaking to|confirmed (?:to|by)|writes|reports)?\s*"
    r"(?:the\s+)?(" + "|".join(re.escape(o) for o in _OUTLET_NAMES) + r")"
    r"(?:\s+(?:reports?|reported|claims?|writes|said|revealed|confirms?|confirmed))?",
    re.IGNORECASE)


# Words the sa_pulse voice cannot pronounce cleanly -> spoken replacements.
# Owner rule 2026-08-14: narration uses ONLY easy-to-say names; the flavour
# words stay in descriptions/hashtags where nobody has to voice them.
_TTS_FRIENDLY = [
    (re.compile(r"\bAmakhosi\b", re.IGNORECASE), "Kaizer Chiefs"),
    (re.compile(r"\bMasandawana\b", re.IGNORECASE), "Sundowns"),
    (re.compile(r"\beS'?Godini\b", re.IGNORECASE), "Soweto"),
    (re.compile(r"\bshibobo\b", re.IGNORECASE), "a nutmeg"),
    (re.compile(r"\bmakarapa(s)?\b", re.IGNORECASE), r"fan helmet\1"),
    (re.compile(r"\bKe nako\b", re.IGNORECASE), "It's time"),
    (re.compile(r"\bLaduma\b", re.IGNORECASE), "Goal"),
]


def _tts_friendly_narration(script: dict) -> dict:
    """Replace hard-to-pronounce words in every narration (captions follow)."""
    changed = []
    for scene in script.get("scenes", []) or []:
        n = scene.get("narration") or ""
        n2 = n
        for pat, repl in _TTS_FRIENDLY:
            n2 = pat.sub(repl, n2)
        if n2 != n:
            changed.append(True)
        scene["narration"] = re.sub(r"\s{2,}", " ", n2).strip()
    # avoid "Kaizer Chiefs ... Kaizer Chiefs" stutter from a replaced nickname
    for scene in script.get("scenes", []) or []:
        scene["narration"] = re.sub(r"\b(Kaizer Chiefs)(\s*[,—-]?\s*\1)+\b", r"\1",
                                    scene.get("narration") or "")
    if changed:
        print(f"[ScriptWriter] TTS-friendly pass: {len(changed)} narration(s) adjusted")
    return script


def _outlets_to_credits(script: dict) -> dict:
    """Strip outlet names from every narration; credit them in the description."""
    used = []
    for scene in script.get("scenes", []) or []:
        n = scene.get("narration") or ""
        if not n:
            continue

        def _grab(m):
            used.append(m.group(1))
            # keep the sentence grammatical: "Miguel told Goal.com 'X'" ->
            # "Miguel said 'X'"; "according to Soccer Laduma, Chiefs..." -> "Chiefs..."
            return " said" if re.search(r"\btold\b", m.group(0), re.IGNORECASE) else ""

        n2 = _OUTLET_PHRASE.sub(_grab, n)
        n2 = re.sub(r"\s{2,}", " ", n2).replace(" ,", ",").replace(" .", ".").strip(" ,")
        if n2 and n2[0].islower():
            n2 = n2[0].upper() + n2[1:]
        scene["narration"] = n2
    if used:
        # normalise + dedupe, preserving order
        canon = {o.lower(): o for o in _OUTLET_NAMES}
        credits = list(dict.fromkeys(canon.get(u.lower(), u) for u in used))
        desc = (script.get("description") or "").rstrip()
        if "sources:" not in desc.lower():
            script["description"] = f"{desc}\n\nSources: {', '.join(credits)}"
        print(f"[ScriptWriter] outlets moved to credits: {credits}")
    return script


def _speakable_sources(script: dict) -> dict:
    """Make outlet names pronounceable, and collapse repeated domain suffixes."""
    for scene in script.get("scenes", []) or []:
        n = scene.get("narration") or ""
        if not n:
            continue
        for pat, repl in _SPEAKABLE_SOURCES:
            n = pat.sub(repl, n)
        n = re.sub(r"(\bdot com\b)(\s+\1)+", r"\1", n, flags=re.IGNORECASE)
        scene["narration"] = re.sub(r"\s{2,}", " ", n).strip()
    return script


def _scrub_roles(script: dict) -> dict:
    """
    Remove unsourced position claims without wrecking the sentence.

    Two cases:
      "Sundowns striker Sphelele Mkhulise" -> "Sphelele Mkhulise"   (drop label)
      "watch what the striker does"        -> "watch what the player does"
    Plain deletion produced "watch what the does", which shipped into a voiceover.
    """
    for scene in script.get("scenes", []) or []:
        n = scene.get("narration") or ""
        if not n:
            continue
        n = _LABEL_BEFORE_NAME.sub("", n)          # role attached to a name
        n = _BARE_ROLE.sub("player", n)            # role standing alone
        scene["narration"] = re.sub(r"\s{2,}", " ", n).strip()
    return script


async def generate_script(
    topic: str,
    niche: str,
    format_type: str = "short",
) -> dict:
    """
    Generate a video script. SHORTS ONLY pipeline.

    For shorts: uses generate_viral_short_script (optimized 30s format)
    Falls back to Claude direct if viral script fails.

    Fact-bound niches (PSL football) get a hard guard: if the script asserts a
    player's position that no source headline gave, it is regenerated once and
    then scrubbed. Prompt rules alone did not hold — the model twice invented a
    position — so this check is deterministic rather than advisory.
    """
    fact_bound = bool(NICHES.get(niche, {}).get("use_live_headlines"))
    sources_text = await _live_facts_block(niche) if fact_bound else ""

    # Shorts use the viral shorts pipeline (Claude primary, Gemini fallback)
    if format_type in ("short", "viral_short"):
        script = await generate_viral_short_script(topic, niche, duration_target=30)
        if script and fact_bound:
            roles = _unsourced_roles(script, sources_text)
            claims = _unsourced_claims(script, sources_text)
            quotes = _unsourced_quotes(script, sources_text)
            if roles or claims or quotes:
                print(f"[ScriptWriter] GUARD: unsourced roles={roles} claims={claims} "
                      f"quotes={quotes} — regenerating once")
                retry = await generate_viral_short_script(topic, niche, duration_target=30)
                if retry:
                    script = retry
                    roles = _unsourced_roles(script, sources_text)
                    claims = _unsourced_claims(script, sources_text)
                    quotes = _unsourced_quotes(script, sources_text)
                if quotes:
                    print(f"[ScriptWriter] GUARD: still unsourced quotes={quotes} — dropping sentences")
                    script = _strip_quote_sentences(script, sources_text)
                if roles:
                    print(f"[ScriptWriter] GUARD: still unsourced roles={roles} — scrubbing labels")
                    script = _scrub_roles(script)
                if claims:
                    print(f"[ScriptWriter] GUARD: still unsourced claims={claims} — dropping sentences")
                    script = _strip_claim_sentences(script)
        if script and fact_bound:
            # Always run, guard-triggered or not — the source credits are in every
            # script by design, so they always need to be speakable.
            script = _speakable_sources(script)
            # Owner rule (2026-08-14): outlets are CREDITED, never SPOKEN. Move
            # any outlet name the model still put in the narration out of the
            # spoken text; the description keeps/receives the credit line.
            script = _outlets_to_credits(script)
            # Owner rule (2026-08-14): narration only uses words the voice can
            # actually pronounce — "Kaizer Chiefs", never "Amakhosi".
            script = _tts_friendly_narration(script)
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
    models = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]  # Refreshed 2026-08-14: 2.0-flash + 2.0-flash-lite are retired (404)
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
