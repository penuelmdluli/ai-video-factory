"""
Baby Podcast Generator — Two-Character AI Debate Video Format.

Inspired by the viral "Baby Podcast" trend. Creates split-screen debate
videos with two AI characters (SPARKY & NOVA) arguing both sides of
controversial/trending topics.

Features:
- Emotion-tagged dialogue (SHOCKED, ANGRY, LAUGHS, WHISPERING, etc.)
- Structured debate format: HOOK → ROUNDS → TWIST → CLIFFHANGER
- Dual-voice generation (two distinct AI voices per video)
- Split-screen video layout with active-speaker highlighting
- 4 character styles: baby, robot, cartoon, realistic
- Per-niche character visual generation
- Viral optimization: hooks, quotable moments, cliffhangers

Pipeline:
1. Generate emotional debate script (Gemini/Claude)
2. Generate 2 character voices (ElevenLabs / edge-tts)
3. Generate/cache character images (AI or pre-made)
4. Assemble split-screen video with captions + effects
"""
import json
import re
import asyncio
from pathlib import Path
from datetime import datetime

from config import NICHES, GEMINI_API_KEY, ANTHROPIC_API_KEY


# ── Emotion Tags ──────────────────────────────────────────────
EMOTIONS = [
    "SHOCKED", "ANGRY", "LAUGHS", "WHISPERING", "SARCASTIC",
    "DISBELIEF", "EXCITED", "DEAD SERIOUS", "SMIRKING", "CUTS OFF",
    "CONFUSED", "FIRED UP", "CALM", "NERVOUS", "IMPRESSED",
]

# Emotion → edge-tts voice parameters
EMOTION_VOICE_MAP = {
    "SHOCKED":      {"rate": "+15%", "pitch": "+20Hz"},
    "ANGRY":        {"rate": "+10%", "pitch": "-10Hz"},
    "LAUGHS":       {"rate": "+5%",  "pitch": "+15Hz"},
    "WHISPERING":   {"rate": "-15%", "pitch": "-5Hz"},
    "SARCASTIC":    {"rate": "-5%",  "pitch": "+5Hz"},
    "DISBELIEF":    {"rate": "+8%",  "pitch": "+10Hz"},
    "EXCITED":      {"rate": "+18%", "pitch": "+15Hz"},
    "DEAD SERIOUS": {"rate": "-10%", "pitch": "-15Hz"},
    "SMIRKING":     {"rate": "-3%",  "pitch": "+3Hz"},
    "CUTS OFF":     {"rate": "+20%", "pitch": "+5Hz"},
    "CONFUSED":     {"rate": "-5%",  "pitch": "+8Hz"},
    "FIRED UP":     {"rate": "+15%", "pitch": "+10Hz"},
    "CALM":         {"rate": "-8%",  "pitch": "-5Hz"},
    "NERVOUS":      {"rate": "+10%", "pitch": "+12Hz"},
    "IMPRESSED":    {"rate": "+5%",  "pitch": "+8Hz"},
}

# Emotion → D-ID expression parameters for animated avatars.
# Each emotion maps to D-ID expression descriptors that control
# facial movements during lip-synced animation.
# Fields:
#   expression: Primary facial expression category for D-ID
#   intensity: Float 0.0–1.0 controlling how pronounced the expression is
#   params: Fine-grained facial action units (AU) style controls:
#       - brow_raise: Eyebrow lift (0.0–1.0)
#       - brow_furrow: Eyebrow scrunch/frown (0.0–1.0)
#       - eye_wide: Eye openness beyond neutral (0.0–1.0)
#       - smile: Mouth corner lift (0.0–1.0)
#       - mouth_open: Jaw drop / mouth openness (0.0–1.0)
#       - squint: Eye narrowing (0.0–1.0)
EMOTION_DID_EXPRESSION_MAP = {
    "SHOCKED": {
        "expression": "surprise",
        "intensity": 0.9,
        "params": {
            "brow_raise": 0.9,
            "eye_wide": 0.85,
            "mouth_open": 0.7,
            "smile": 0.0,
            "brow_furrow": 0.0,
            "squint": 0.0,
        },
    },
    "ANGRY": {
        "expression": "anger",
        "intensity": 0.75,
        "params": {
            "brow_furrow": 0.85,
            "eye_wide": 0.3,
            "mouth_open": 0.2,
            "smile": 0.0,
            "brow_raise": 0.0,
            "squint": 0.5,
        },
    },
    "LAUGHS": {
        "expression": "happy",
        "intensity": 0.95,
        "params": {
            "smile": 0.95,
            "eye_wide": 0.2,
            "mouth_open": 0.6,
            "brow_raise": 0.3,
            "squint": 0.4,
            "brow_furrow": 0.0,
        },
    },
    "EXCITED": {
        "expression": "happy",
        "intensity": 0.8,
        "params": {
            "smile": 0.7,
            "eye_wide": 0.6,
            "brow_raise": 0.65,
            "mouth_open": 0.4,
            "brow_furrow": 0.0,
            "squint": 0.0,
        },
    },
    "CALM": {
        "expression": "neutral",
        "intensity": 0.3,
        "params": {
            "smile": 0.15,
            "eye_wide": 0.0,
            "brow_raise": 0.0,
            "mouth_open": 0.1,
            "brow_furrow": 0.0,
            "squint": 0.0,
        },
    },
    "WHISPERING": {
        "expression": "neutral",
        "intensity": 0.2,
        "params": {
            "smile": 0.0,
            "eye_wide": 0.15,
            "mouth_open": 0.15,
            "brow_raise": 0.1,
            "brow_furrow": 0.0,
            "squint": 0.15,
        },
    },
    "SARCASTIC": {
        "expression": "contempt",
        "intensity": 0.6,
        "params": {
            "smile": 0.3,
            "brow_raise": 0.5,
            "eye_wide": 0.1,
            "mouth_open": 0.1,
            "squint": 0.3,
            "brow_furrow": 0.2,
        },
    },
    "DISBELIEF": {
        "expression": "surprise",
        "intensity": 0.7,
        "params": {
            "brow_raise": 0.75,
            "eye_wide": 0.65,
            "mouth_open": 0.3,
            "smile": 0.0,
            "brow_furrow": 0.1,
            "squint": 0.0,
        },
    },
    "DEAD SERIOUS": {
        "expression": "neutral",
        "intensity": 0.5,
        "params": {
            "brow_furrow": 0.4,
            "eye_wide": 0.15,
            "mouth_open": 0.1,
            "smile": 0.0,
            "brow_raise": 0.0,
            "squint": 0.25,
        },
    },
    "SMIRKING": {
        "expression": "happy",
        "intensity": 0.4,
        "params": {
            "smile": 0.45,
            "brow_raise": 0.3,
            "eye_wide": 0.0,
            "mouth_open": 0.05,
            "squint": 0.2,
            "brow_furrow": 0.0,
        },
    },
    "CUTS OFF": {
        "expression": "surprise",
        "intensity": 0.6,
        "params": {
            "brow_raise": 0.5,
            "eye_wide": 0.4,
            "mouth_open": 0.5,
            "smile": 0.0,
            "brow_furrow": 0.2,
            "squint": 0.0,
        },
    },
    "CONFUSED": {
        "expression": "puzzled",
        "intensity": 0.65,
        "params": {
            "brow_furrow": 0.5,
            "brow_raise": 0.3,
            "eye_wide": 0.3,
            "mouth_open": 0.15,
            "smile": 0.0,
            "squint": 0.3,
        },
    },
    "FIRED UP": {
        "expression": "anger",
        "intensity": 0.65,
        "params": {
            "brow_furrow": 0.6,
            "eye_wide": 0.5,
            "mouth_open": 0.5,
            "smile": 0.1,
            "brow_raise": 0.2,
            "squint": 0.15,
        },
    },
    "NERVOUS": {
        "expression": "fear",
        "intensity": 0.5,
        "params": {
            "brow_raise": 0.45,
            "eye_wide": 0.5,
            "mouth_open": 0.2,
            "smile": 0.1,
            "brow_furrow": 0.2,
            "squint": 0.0,
        },
    },
    "IMPRESSED": {
        "expression": "surprise",
        "intensity": 0.55,
        "params": {
            "brow_raise": 0.6,
            "eye_wide": 0.45,
            "smile": 0.4,
            "mouth_open": 0.25,
            "brow_furrow": 0.0,
            "squint": 0.0,
        },
    },
}


# ── Character Styles ─────────────────────────────────────────
# Viral baby podcast style: photorealistic babies with BIG headphones,
# professional outfits (suits, blazers), sitting at podcast desks.
# Per-niche variations give each channel a unique look.

# Base prompt components (reusable)
_BABY_BASE = "ultra photorealistic adorable baby, chubby cheeks, big expressive eyes, sitting at a professional podcast desk, large over-ear headphones on head, professional podcast microphone on desk in front, dark moody studio background, cinematic studio lighting, 4K ultra HD, hyper detailed skin texture, shallow depth of field, portrait photography"

# ── Per-Niche Character Names & Identities ───────────────────
# Each niche gets unique character names, genders, and ethnicities
# for diverse, authentic representation across all 6 channels.
NICHE_CHARACTER_NAMES = {
    "ai_trading": {"sparky": "JAYDEN", "nova": "ZOE"},       # Boy + Girl
    "ai_money": {"sparky": "MALIK", "nova": "LUNA"},          # Black boy + Latina girl
    "tech_news": {"sparky": "KAI", "nova": "AMARA"},          # Asian boy + Black girl
    "motivation": {"sparky": "BLAZE", "nova": "SAGE"},        # Boy + Girl
    "health_wellness": {"sparky": "MIA", "nova": "NOAH"},     # Girl + Boy
    "blissful_moments": {"sparky": "ARIA", "nova": "LIAM"},   # Girl + Boy
}

# Niche-specific baby prompt overrides (outfit + studio + ethnicity diversity)
NICHE_BABY_PROMPTS = {
    "ai_trading": {
        "sparky": f"{_BABY_BASE}, adorable mixed-race baby boy with curly dark hair, wearing tiny dark navy suit with red tie, confident bold expression, mouth slightly open as if talking, Wall Street trading screens glowing in background, red and green LED accent lights, financial news studio setting",
        "nova": f"{_BABY_BASE}, adorable baby girl with light brown hair and rosy cheeks, wearing tiny light blue dress with white collar, calm intelligent expression, tiny round glasses, stock market charts on monitor in background, cool blue LED accent lights, modern financial studio setting",
    },
    "ai_money": {
        "sparky": f"{_BABY_BASE}, beautiful Black baby boy with short curly hair and dark brown skin, wearing tiny black turtleneck like Steve Jobs, excited surprised expression, mouth open in shock, gold and green neon lights in background, money and tech themed studio, dark luxurious podcast set",
        "nova": f"{_BABY_BASE}, beautiful Latina baby girl with dark wavy hair and warm caramel skin, wearing tiny grey blazer over white blouse, thoughtful wise expression, slight smile, sleek modern minimalist studio background, soft blue and white LED accents, premium tech podcast studio",
    },
    "tech_news": {
        "sparky": f"{_BABY_BASE}, adorable East Asian baby boy with straight dark hair, wearing tiny tech branded hoodie in dark grey, amazed shocked expression, mouth wide open, multiple screens showing tech news in background, purple and blue neon LED accent lights, futuristic news broadcast studio",
        "nova": f"{_BABY_BASE}, beautiful Black baby girl with short curly natural hair and dark skin, wearing tiny formal blazer and bow tie, calm analytical expression, slight knowing smile, holographic displays in background, cool cyan and blue LED accent lights, high-tech news anchor desk",
    },
    "motivation": {
        "sparky": f"{_BABY_BASE}, adorable baby boy with sandy blonde hair and blue eyes, wearing tiny black leather jacket, fierce determined expression, fist raised slightly, warm amber and gold lighting, motivational quotes on screens in background, dark dramatic podcast studio",
        "nova": f"{_BABY_BASE}, beautiful mixed-race baby girl with curly brown hair and green eyes, wearing tiny cream colored cardigan with flower pin, peaceful wise expression, gentle warm smile, soft golden bokeh lights in background, warm cozy premium podcast studio, earth tone accents",
    },
    "health_wellness": {
        "sparky": f"{_BABY_BASE}, adorable Latina baby girl with dark curly hair and warm brown skin, wearing tiny green scrubs like a doctor, curious excited expression, eyebrows raised, plants and nature elements in background, soft green LED accent lights, natural wellness studio setting",
        "nova": f"{_BABY_BASE}, adorable South Asian baby boy with dark wavy hair, wearing tiny white lab coat, calm knowledgeable expression, reassuring smile, herbal and organic elements on shelves in background, warm natural lighting, health and science podcast studio",
    },
    "blissful_moments": {
        "sparky": f"{_BABY_BASE}, beautiful Black baby girl with adorable afro puffs and dark brown skin, wearing tiny yellow sunflower pattern dress, joyful laughing expression, warm golden hour lighting, fairy lights and soft bokeh in background, cozy aesthetic podcast studio, dreamy atmosphere",
        "nova": f"{_BABY_BASE}, adorable baby boy with red hair and freckles, wearing tiny lavender knit sweater, serene peaceful expression, gentle smile with closed eyes, soft pastel colored lights in background, calming aesthetic studio, crystals and candles on desk",
    },
}

CHARACTER_STYLES = {
    "baby": {
        "label": "Baby Podcast",
        "desc": "Viral photorealistic babies with headphones at a podcast desk — the TikTok trend",
        "sparky_prompt": f"{_BABY_BASE}, baby wearing tiny dark suit with red pocket square, bold confident expression, mouth open as if talking excitedly, red LED accent lighting in background, dark premium podcast studio",
        "nova_prompt": f"{_BABY_BASE}, baby wearing tiny blue blazer and bow tie, calm wise expression with slight smile, tiny round glasses, blue LED accent lighting in background, dark premium podcast studio",
        "did_compatible": True,
    },
    "robot": {
        "label": "Sci-Fi Robots",
        "desc": "Futuristic AI robots in a high-tech broadcast studio",
        "sparky_prompt": "futuristic red humanoid robot character sitting in a dark high-tech podcast studio, large headphones, professional microphone, red LED accent lighting, holographic screens in background, metallic body, glowing red eyes, sci-fi broadcast set, 4K cinematic, dark background",
        "nova_prompt": "futuristic blue humanoid robot character sitting in a dark high-tech podcast studio, large headphones, professional microphone, blue LED accent lighting, holographic screens in background, sleek metallic body, glowing blue visor, sci-fi broadcast set, 4K cinematic, dark background",
        "did_compatible": False,
    },
    "cartoon": {
        "label": "Cartoon Avatars",
        "desc": "Bold animated characters in a colorful podcast studio",
        "sparky_prompt": "bold cartoon character with red hair and leather jacket, large headphones, sitting in a stylish podcast studio, professional microphone on desk, neon red accent lights, dark studio background, Pixar animation style, expressive confident face, high quality 3D render",
        "nova_prompt": "smart cartoon character with blue hair wearing glasses and lab coat, large headphones, sitting in a stylish podcast studio, professional microphone on desk, neon blue accent lights, dark studio background, Pixar animation style, warm confident smile, high quality 3D render",
        "did_compatible": False,
    },
    "realistic": {
        "label": "Realistic AI Hosts",
        "desc": "Photorealistic professional podcast hosts in premium studio",
        "sparky_prompt": "photorealistic portrait of confident young man, large over-ear headphones, in a professional dark podcast studio, wearing red casual shirt, sitting behind sleek desk with podcast microphone, moody studio lighting with warm tones, acoustic panels on wall, 4K cinematic quality, close-up from waist up, natural expression",
        "nova_prompt": "photorealistic portrait of intelligent young woman, large over-ear headphones, in a professional dark podcast studio, wearing blue blazer, sitting behind sleek desk with podcast microphone, moody studio lighting with cool tones, acoustic panels on wall, 4K cinematic quality, close-up from waist up, warm smile",
        "did_compatible": True,
    },
}


# ── Per-Niche Podcast Config ─────────────────────────────────
NICHE_PODCAST_CONFIG = {
    "ai_trading": {
        "default_style": "baby",   # Baby faces work best with D-ID animation
        "topics": [
            "Will AI replace all stock traders by 2030?",
            "Is algorithmic trading a scam or the future?",
            "The truth about how Wall Street uses AI against retail traders",
            "Can a $100 AI bot beat a $10M hedge fund?",
            "The dark side of high-frequency trading nobody talks about",
            "Is crypto dead or about to explode — AI analysis",
            "AI just predicted the next market crash — should you panic?",
        ],
        "tone": "controversial",
    },
    "ai_money": {
        "default_style": "baby",
        "topics": [
            "The truth about how banks steal your money",
            "Will AI replace ALL jobs by 2030?",
            "Gen Z will NEVER own a house — here's why",
            "Is passive income with AI real or a scam?",
            "The hidden cost of your smartphone addiction",
            "Why the rich keep getting richer and you don't",
            "Is crypto the future or the biggest scam ever?",
        ],
        "tone": "controversial",
    },
    "tech_news": {
        "default_style": "baby",   # Baby faces work best with D-ID animation
        "topics": [
            "AI is now smarter than most humans — should we be scared?",
            "The dark truth about social media and your brain",
            "Is Apple actually innovating or just copying?",
            "China vs USA in the AI race — who wins?",
            "Will AI-generated content destroy the internet?",
            "The real reason tech companies are doing mass layoffs",
            "Is your phone secretly listening to you? The truth",
        ],
        "tone": "shocking",
    },
    "motivation": {
        "default_style": "baby",   # Baby podcast is the viral trend
        "topics": [
            "Why discipline beats motivation every single time",
            "The morning routine that millionaires won't tell you about",
            "Stop being positive — toxic positivity is ruining your life",
            "Why your comfort zone is slowly killing your dreams",
            "The harsh truth about why most people stay mediocre",
            "Is hustle culture a scam or the path to success?",
            "Why your 20s are the most important decade of your life",
        ],
        "tone": "controversial",
    },
    "health_wellness": {
        "default_style": "baby",
        "topics": [
            "Is breakfast actually the most important meal? The truth",
            "Your body does THIS while you sleep and nobody talks about it",
            "The supplement industry is lying to you — here's proof",
            "Water fasting — miracle cure or dangerous trend?",
            "Why doctors won't tell you about these natural remedies",
            "The gut-brain connection that changes EVERYTHING",
            "Is organic food actually healthier or just marketing?",
        ],
        "tone": "educational",
    },
    "blissful_moments": {
        "default_style": "baby",   # Baby podcast is the viral trend
        "topics": [
            "The one habit that changed my entire perspective on life",
            "Why slowing down is the fastest path to happiness",
            "The science of gratitude — why it literally rewires your brain",
            "Is social media stealing your joy? A honest conversation",
            "The power of doing absolutely nothing — and why it matters",
            "Why comparing yourself to others is a trap nobody escapes",
            "Finding peace in chaos — a conversation about mindfulness",
        ],
        "tone": "educational",
    },
}


# ── Podcast Script Prompt ─────────────────────────────────────

PODCAST_SCRIPT_PROMPT = """You are a top-tier podcast scriptwriter who creates NATURAL, CHILL, scroll-stopping content that feels like two real friends having a genuine conversation.

Write a {duration}-second podcast conversation between two hosts:

🔴 SPARKY — The curious, bold one. Asks the questions everyone is thinking. Gets genuinely excited, surprised, even a little outraged. Uses casual language: "bro", "wait what", "no way", "hold on". Reacts naturally — laughs, interrupts, agrees, pushes back.

🔵 NOVA — The knowledgeable, chill one. Drops facts casually, like explaining something to a friend over coffee. Never lectures — just shares fascinating insights. Uses phrases like "here's the thing though", "so basically", "yeah but listen to this", "that's actually wild because..."

THE VIBE: This should feel like a REAL podcast conversation you'd hear on Joe Rogan or a viral TikTok clip. NOT scripted, NOT robotic, NOT a formal debate. Two friends talking about something that blows their minds.

TOPIC: "{topic}"
NICHE: {niche_name}
TONE: {tone}

{niche_style_guide}

CONVERSATION RULES:
1. Start with a SHOCKING statement or question that makes you stop scrolling
2. Each line = NATURAL conversational length. Some short ("Wait, seriously?"), some longer explanations
3. Include natural reactions: "That's actually insane", "Hold on, say that again", "No way, bro"
4. Include emotion tags from this list: {emotions}
5. Add natural FLOW: agreement, disagreement, surprise, laughter, thinking pauses
6. Include a MID-POINT TWIST — one fact that flips everything
7. End with a CLIFFHANGER that forces viewers to comment
8. Include at least one moment where SPARKY says "wait wait wait" and NOVA drops a mind-blowing fact
9. Total lines should create approximately {duration} seconds of natural dialogue
10. Make them occasionally AGREE with each other — real conversations aren't just debate

ENGAGEMENT MECHANICS (these make it VIRAL):
11. INTERRUPTIONS: At least 2 moments where one host cuts the other off mid-thought ("Wait wait wait—", "Hold on, stop—", "Bro, bro, bro—"). Tag these as CUTS OFF emotion.
12. AUDIBLE REACTIONS: Include gut reactions between explanations — "no way!", "bro...", "that's crazy", "*laughs*", "I'm dead". These are 1-3 word bursts that feel REAL.
13. PATTERN INTERRUPTS: If they agree twice in a row, the NEXT line MUST disagree or challenge. Never let the energy flatline. Flip between "YES and" to "BUT actually..."
14. ESCALATING INTENSITY: Each section should be MORE intense than the last. HOOK = 5/10 energy, ROUND 1 = 6/10, ROUND 2 = 7/10, THE TWIST = 9/10, CLIFFHANGER = 10/10.
15. FALSE AGREEMENTS: At least once, have one host say "Yeah totally... BUT" — agree then immediately flip. This creates tension viewers can't stop watching.
16. USE ALL 15 EMOTIONS: Don't just use SHOCKED and EXCITED. Mix in SARCASTIC, DISBELIEF, SMIRKING, NERVOUS, CONFUSED, FIRED UP, CALM, IMPRESSED — variety keeps viewers engaged.
17. BEAT DROPS: Before THE TWIST reveal, add a brief pause moment — SPARKY says something like "Wait... are you about to say what I think you're about to say?" (NERVOUS emotion). Then NOVA drops the bomb.

OUTPUT FORMAT — Return valid JSON:
{{
    "title": "Viral title (under 60 chars, include a number or specific claim)",
    "description": "YouTube description with keywords (100-150 words)",
    "caption": "Short caption for TikTok/Shorts with hooks and hashtags",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "character_style": "{character_style}",
    "lines": [
        {{
            "character": "SPARKY",
            "emotion": "SHOCKED",
            "text": "The exact words this character speaks",
            "section": "HOOK"
        }},
        {{
            "character": "NOVA",
            "emotion": "DEAD SERIOUS",
            "text": "The exact words this character speaks",
            "section": "HOOK"
        }}
    ],
    "sections": ["HOOK", "ROUND 1: sub-topic", "ROUND 2: sub-topic", "THE TWIST", "ROUND 3: sub-topic", "CLIFFHANGER CTA"],
    "viral_clip_moment": {{
        "description": "Description of the single most shareable 5-10 second moment",
        "line_indices": [5, 6, 7],
        "emotion_arc": ["DISBELIEF", "SHOCKED", "EXCITED"]
    }},
    "thumbnail_text": "Bold 2-4 word hook for thumbnail",
    "engagement_score": 8
}}

CONVERSATION FLOW (keep it feeling NATURAL, not scripted):
- HOOK (2-3 exchanges, intensity 5/10): Open with something WILD that makes people stop scrolling. One drops a bomb casually. Use SHOCKED, DISBELIEF, or DEAD SERIOUS emotions.
- ROUND 1 (3-4 exchanges, intensity 6/10): They dig in. Back and forth — one explains, the other reacts genuinely. Mix agreement with pushback. Use CONFUSED, IMPRESSED, SARCASTIC.
- ROUND 2 (3-4 exchanges, intensity 7/10): Go deeper. "Wait, are you serious?" moments. Include a FALSE AGREEMENT and at least one CUTS OFF moment.
- THE TWIST (2-3 exchanges, intensity 9/10): Beat drop pause → one drops a fact that FLIPS everything. The other is genuinely shook. Use NERVOUS before, then SHOCKED + FIRED UP. This is the viral clip moment.
- ROUND 3 (2-3 exchanges, intensity 8/10): They process the twist together. Use EXCITED, IMPRESSED, CALM. New perspective — two minds connecting.
- CLIFFHANGER CTA (2 exchanges, intensity 10/10): End on something that FORCES viewers to comment. Use DEAD SERIOUS + SMIRKING. Tease the next topic or ask a divisive question.

CRITICAL: Return ONLY valid JSON. No markdown, no code blocks, just raw JSON.
CRITICAL: "engagement_score" should be 1-10 based on: emotion variety (use 8+ different emotions), interruption count (2+), pattern interrupts, and cliffhanger strength.

Make the conversation feel like eavesdropping on two interesting friends. Controversial enough to share, factual enough to trust. This needs to go VIRAL.
"""


def _clean_json_response(text: str) -> str:
    """Extract JSON from AI response."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    return text


async def generate_podcast_script(
    topic: str,
    niche: str,
    duration: int = 90,
    character_style: str | None = None,
) -> dict | None:
    """
    Generate a two-character podcast debate script.

    Args:
        topic: The debate topic
        niche: Niche key
        duration: Target duration in seconds (60, 90, or 120)
        character_style: One of 'baby', 'robot', 'cartoon', 'realistic'

    Returns:
        Structured script dict with character lines, emotions, sections
    """
    from modules.script_writer import _clean_json_response, _add_affiliate_links, NICHE_STYLE_GUIDES

    niche_config = NICHES[niche]
    podcast_config = NICHE_PODCAST_CONFIG.get(niche, {})

    if not character_style:
        character_style = podcast_config.get("default_style", "baby")

    tone = podcast_config.get("tone", "controversial")
    niche_style = NICHE_STYLE_GUIDES.get(niche, "Write in an engaging, viewer-focused style.")

    prompt = PODCAST_SCRIPT_PROMPT.format(
        topic=topic,
        niche_name=niche_config["name"],
        tone=tone.upper(),
        niche_style_guide=niche_style,
        duration=duration,
        character_style=character_style,
        emotions=", ".join(f"[{e}]" for e in EMOTIONS[:10]),
    )

    # Try Gemini first
    script = await _generate_podcast_gemini(prompt)
    if not script:
        script = await _generate_podcast_claude(prompt)
    if not script:
        return None

    # Enrich the script
    script["niche"] = niche
    script["format"] = "podcast"
    script["character_style"] = character_style
    script["duration_target"] = duration
    script["generated_at"] = datetime.now().isoformat()

    if "description" in script:
        script["description"] = _add_affiliate_links(script["description"], niche)

    # Validate and fix structure
    if "lines" not in script or not script["lines"]:
        return None

    # Ensure all lines have required fields
    for line in script["lines"]:
        line.setdefault("character", "SPARKY")
        line.setdefault("emotion", "EXCITED")
        line.setdefault("text", "")
        line.setdefault("section", "HOOK")

    line_count = len(script["lines"])
    sparky_count = sum(1 for l in script["lines"] if l["character"] == "SPARKY")
    nova_count = sum(1 for l in script["lines"] if l["character"] == "NOVA")
    names = NICHE_CHARACTER_NAMES.get(niche, {"sparky": "SPARKY", "nova": "NOVA"})
    print(f"[Podcast] Script: {line_count} lines ({names['sparky']}: {sparky_count}, {names['nova']}: {nova_count})")

    return script


async def _generate_podcast_gemini(prompt: str) -> dict | None:
    """Generate podcast script using Gemini."""
    if not GEMINI_API_KEY:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        for model_name in models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    raw = _clean_json_response(response.text)
                    return json.loads(raw)
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    await asyncio.sleep(2)
                    continue
                print(f"[Podcast] Gemini {model_name} failed: {e}")
                continue
    except Exception as e:
        print(f"[Podcast] Gemini failed: {e}")
    return None


async def _generate_podcast_claude(prompt: str) -> dict | None:
    """Generate podcast script using Claude."""
    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _clean_json_response(message.content[0].text)
        return json.loads(raw)
    except Exception as e:
        print(f"[Podcast] Claude failed: {e}")
    return None


def parse_podcast_lines(script: dict) -> list[dict]:
    """
    Parse podcast script into structured line data for voice generation.

    Returns list of dicts with:
    - character: "SPARKY" or "NOVA"
    - emotion: emotion tag
    - text: dialogue text (cleaned of emotion tags)
    - section: which section this belongs to
    - voice_params: edge-tts rate/pitch for the emotion
    """
    lines = []
    for line in script.get("lines", []):
        character = line.get("character", "SPARKY").upper()
        emotion = line.get("emotion", "EXCITED").upper().strip("[]")
        text = line.get("text", "").strip()

        # Remove any inline emotion tags from text
        text = re.sub(r'\[[\w\s]+\]\s*', '', text).strip()

        if not text:
            continue

        voice_params = EMOTION_VOICE_MAP.get(emotion, {"rate": "+0%", "pitch": "+0Hz"})

        lines.append({
            "character": character,
            "emotion": emotion,
            "text": text,
            "section": line.get("section", ""),
            "voice_params": voice_params,
        })

    return lines


def get_podcast_narration_by_character(script: dict) -> dict:
    """
    Split podcast script into per-character narration blocks.

    Returns:
        {
            "SPARKY": [{"text": "...", "emotion": "...", "index": 0}, ...],
            "NOVA": [{"text": "...", "emotion": "...", "index": 1}, ...],
            "order": ["SPARKY", "NOVA", "SPARKY", ...],
        }
    """
    lines = parse_podcast_lines(script)
    sparky_lines = []
    nova_lines = []
    order = []

    for i, line in enumerate(lines):
        entry = {"text": line["text"], "emotion": line["emotion"], "index": i}
        if line["character"] == "SPARKY":
            sparky_lines.append(entry)
        else:
            nova_lines.append(entry)
        order.append(line["character"])

    return {
        "SPARKY": sparky_lines,
        "NOVA": nova_lines,
        "order": order,
        "all_lines": lines,
    }


async def generate_character_images(
    character_style: str,
    output_dir: Path,
    niche: str = "ai_trading",
) -> dict:
    """
    Generate or retrieve cached character images for the podcast.

    Returns:
        {"sparky": path_to_image, "nova": path_to_image}
    """
    from config import ASSETS_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check cache first
    cache_dir = ASSETS_DIR / "podcast_characters" / character_style
    cache_dir.mkdir(parents=True, exist_ok=True)

    sparky_cache = cache_dir / f"sparky_{niche}.png"
    nova_cache = cache_dir / f"nova_{niche}.png"

    if sparky_cache.exists() and nova_cache.exists():
        print(f"[Podcast] Using cached {character_style} characters")
        return {"sparky": str(sparky_cache), "nova": str(nova_cache)}

    # Generate new character images
    style = CHARACTER_STYLES.get(character_style, CHARACTER_STYLES["baby"])

    from modules.ai_images import generate_image

    sparky_path = cache_dir / f"sparky_{niche}.png"
    nova_path = cache_dir / f"nova_{niche}.png"

    # Use niche-specific baby prompts if available (viral baby podcast style)
    niche_prompts = NICHE_BABY_PROMPTS.get(niche, {})
    if character_style == "baby" and niche_prompts:
        sparky_prompt = niche_prompts["sparky"]
        nova_prompt = niche_prompts["nova"]
        print(f"[Podcast] Using niche-specific baby prompts for {niche}")
    else:
        sparky_prompt = style["sparky_prompt"]
        nova_prompt = style["nova_prompt"]

    # Generate both in parallel — portrait orientation for best face quality
    sparky_result, nova_result = await asyncio.gather(
        generate_image(
            sparky_prompt,
            sparky_path,
            niche=niche,
            orientation="portrait",
        ),
        generate_image(
            nova_prompt,
            nova_path,
            niche=niche,
            orientation="portrait",
        ),
        return_exceptions=True,
    )

    # Fallback to solid color placeholders if AI generation fails
    sparky_final = sparky_result if isinstance(sparky_result, str) else _create_placeholder_character("SPARKY", sparky_path)
    nova_final = nova_result if isinstance(nova_result, str) else _create_placeholder_character("NOVA", nova_path)

    return {"sparky": sparky_final, "nova": nova_final}


def _create_placeholder_character(name: str, output_path: Path) -> str:
    """Create a simple placeholder character image."""
    from PIL import Image, ImageDraw, ImageFont

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    color = (239, 68, 68) if name == "SPARKY" else (59, 130, 246)
    draw.ellipse([20, 20, size - 20, size - 20], fill=color)

    # Character letter
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 180)
    except Exception:
        font = ImageFont.load_default()

    letter = name[0]
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2, (size - th) / 2 - 20),
        letter,
        fill=(255, 255, 255),
        font=font,
    )

    # Name label
    try:
        label_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 48)
    except Exception:
        label_font = font
    label_bbox = draw.textbbox((0, 0), name, font=label_font)
    lw = label_bbox[2] - label_bbox[0]
    draw.text(
        ((size - lw) / 2, size - 120),
        name,
        fill=(255, 255, 255),
        font=label_font,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    return str(output_path)


# ── D-ID Animated Podcast Avatars ────────────────────────────
# Turns the character images into talking head VIDEO clips via D-ID Talks API.
# Each character gets their own animated clip synced to their dialogue audio.


def _get_dominant_emotion_for_character(
    character: str,
    line_timings: list[dict] | None,
) -> str:
    """
    Determine the most frequent emotion for a character across all their lines.

    Falls back to "EXCITED" for SPARKY and "CALM" for NOVA if no timings
    are provided or no lines match.

    Args:
        character: "SPARKY" or "NOVA"
        line_timings: List of dicts with at minimum {character, emotion}

    Returns:
        The most common emotion tag string for that character.
    """
    default = "EXCITED" if character.upper() == "SPARKY" else "CALM"
    if not line_timings:
        return default

    from collections import Counter
    char_emotions = [
        lt.get("emotion", default)
        for lt in line_timings
        if lt.get("character", "").upper() == character.upper()
    ]
    if not char_emotions:
        return default

    # Return most common
    return Counter(char_emotions).most_common(1)[0][0]


def _build_did_expression_config(
    character: str,
    line_timings: list[dict] | None = None,
) -> dict:
    """
    Build a D-ID expression configuration for a character.

    Creates timing-based expression segments from script line_timings so that
    the avatar's facial expression shifts to match the emotional tone of each
    dialogue line.  When D-ID supports per-timestamp driver_expressions this
    structure can be sent directly; until then the dominant emotion for the
    character is used as a single whole-clip expression hint.

    Args:
        character: "SPARKY" or "NOVA"
        line_timings: Optional list of per-line timing dicts. Each dict is
            expected to have:
                - character: str ("SPARKY" / "NOVA")
                - emotion: str (one of the EMOTIONS tags)
                - start_time: float (seconds from clip start)
                - end_time: float (seconds)
                - text: str (the dialogue text)
            If None, a single default expression config is returned.

    Returns:
        Dict with:
            dominant_emotion: str — most common emotion for this character
            dominant_expression: dict — D-ID expression params for dominant
            segments: list[dict] — per-line expression segments with timing
            driver_expression_override: dict|None — future D-ID API field
    """
    default_emotion = "EXCITED" if character.upper() == "SPARKY" else "CALM"
    fallback_expression = EMOTION_DID_EXPRESSION_MAP.get(
        default_emotion, EMOTION_DID_EXPRESSION_MAP["EXCITED"]
    )

    # Determine dominant emotion across all lines for this character
    dominant_emotion = _get_dominant_emotion_for_character(character, line_timings)
    dominant_expression = EMOTION_DID_EXPRESSION_MAP.get(
        dominant_emotion, fallback_expression
    )

    # Build per-segment expression list from line_timings
    segments = []
    if line_timings:
        for lt in line_timings:
            if lt.get("character", "").upper() != character.upper():
                continue
            emotion_tag = lt.get("emotion", default_emotion).upper()
            expr = EMOTION_DID_EXPRESSION_MAP.get(emotion_tag, fallback_expression)
            segments.append({
                "start_time": lt.get("start_time", 0.0),
                "end_time": lt.get("end_time", 0.0),
                "emotion": emotion_tag,
                "expression": expr["expression"],
                "intensity": expr["intensity"],
                "params": expr["params"],
                "text_preview": (lt.get("text", "")[:60] + "...")
                    if len(lt.get("text", "")) > 60
                    else lt.get("text", ""),
            })

    # Prepare the future D-ID driver_expressions payload.
    # D-ID's Talks API may support this in the future for per-timestamp
    # expression control — when that happens, this structure is ready to send.
    driver_expression_override = None
    if segments:
        driver_expression_override = {
            "expressions": [
                {
                    "start_time": seg["start_time"],
                    "duration": round(seg["end_time"] - seg["start_time"], 3),
                    "expression": seg["expression"],
                    "intensity": seg["intensity"],
                }
                for seg in segments
                if seg["end_time"] > seg["start_time"]
            ],
        }

    return {
        "dominant_emotion": dominant_emotion,
        "dominant_expression": dominant_expression,
        "segments": segments,
        "driver_expression_override": driver_expression_override,
    }


async def _check_did_credits() -> int:
    """Check remaining D-ID API credits. Returns remaining count or -1 on error."""
    import httpx
    from config import DID_API_KEY
    if not DID_API_KEY:
        return -1
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.d-id.com/credits",
                headers={"Authorization": f"Basic {DID_API_KEY}", "Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                remaining = data.get("remaining", 0)
                total = data.get("total", 0)
                print(f"[D-ID] Credits: {remaining}/{total} remaining")
                return remaining
    except Exception as e:
        print(f"[D-ID] Credit check failed: {e}")
    return -1


async def _generate_avatar_heygen(
    image_path: str,
    audio_path: str,
    output_path: Path,
    character: str = "SPARKY",
    max_wait: int = 300,
) -> str | None:
    """
    Generate a talking head video using HeyGen API as D-ID alternative.

    Args:
        image_path: Path to character image
        audio_path: Path to character audio
        output_path: Where to save the animated video
        character: Character name for logging
        max_wait: Max polling time in seconds

    Returns:
        Path to animated video or None on failure.
    """
    import httpx
    from config import HEYGEN_API_KEY

    if not HEYGEN_API_KEY:
        return None

    HEYGEN_BASE = "https://api.heygen.com"
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Accept": "application/json",
    }
    upload_headers = {
        "X-Api-Key": HEYGEN_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Upload the character image as a photo avatar
            print(f"[HeyGen] Uploading {character} image...")
            with open(image_path, "rb") as f:
                img_resp = await client.post(
                    f"{HEYGEN_BASE}/v1/photo_avatar",
                    headers=upload_headers,
                    files={"image": (Path(image_path).name, f, "image/png")},
                )
            if img_resp.status_code not in (200, 201):
                print(f"[HeyGen] {character} image upload failed: {img_resp.status_code} {img_resp.text[:200]}")
                return None
            img_data = img_resp.json()
            photo_id = img_data.get("data", {}).get("photo_avatar_id") or img_data.get("data", {}).get("id")

            # Step 2: Upload audio
            print(f"[HeyGen] Uploading {character} audio...")
            with open(audio_path, "rb") as f:
                audio_resp = await client.post(
                    f"{HEYGEN_BASE}/v2/voices/audio_upload",
                    headers=upload_headers,
                    files={"file": (Path(audio_path).name, f, "audio/mpeg")},
                )
            if audio_resp.status_code not in (200, 201):
                print(f"[HeyGen] {character} audio upload failed: {audio_resp.status_code} {audio_resp.text[:200]}")
                return None
            audio_data = audio_resp.json()
            voice_id = audio_data.get("data", {}).get("voice_id") or audio_data.get("data", {}).get("id")

            # Step 3: Create video
            print(f"[HeyGen] Creating {character} talking head...")
            video_body = {
                "video_inputs": [{
                    "character": {
                        "type": "photo_avatar",
                        "photo_avatar_id": photo_id,
                    },
                    "voice": {
                        "type": "audio",
                        "audio_asset_id": voice_id,
                    },
                }],
                "dimension": {"width": 512, "height": 512},
            }
            vid_resp = await client.post(
                f"{HEYGEN_BASE}/v2/video/generate",
                headers={**headers, "Content-Type": "application/json"},
                json=video_body,
            )
            if vid_resp.status_code not in (200, 201):
                print(f"[HeyGen] {character} video creation failed: {vid_resp.status_code} {vid_resp.text[:200]}")
                return None

            vid_data = vid_resp.json()
            video_id = vid_data.get("data", {}).get("video_id")
            if not video_id:
                print(f"[HeyGen] {character} no video_id returned")
                return None

            print(f"[HeyGen] {character} video queued: {video_id}")

            # Step 4: Poll for completion
            for _ in range(max_wait // 5):
                await asyncio.sleep(5)
                poll_resp = await client.get(
                    f"{HEYGEN_BASE}/v1/video_status.get?video_id={video_id}",
                    headers=headers,
                )
                if poll_resp.status_code != 200:
                    continue
                poll_data = poll_resp.json()
                status = poll_data.get("data", {}).get("status", "")
                if status == "completed":
                    video_url = poll_data.get("data", {}).get("video_url")
                    if video_url:
                        dl_resp = await client.get(video_url, timeout=120)
                        if dl_resp.status_code == 200:
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            output_path.write_bytes(dl_resp.content)
                            size_mb = len(dl_resp.content) / (1024 * 1024)
                            print(f"[HeyGen] {character} animated: {output_path.name} ({size_mb:.1f}MB)")
                            return str(output_path)
                    break
                elif status in ("failed", "error"):
                    err = poll_data.get("data", {}).get("error", status)
                    print(f"[HeyGen] {character} failed: {err}")
                    break
            else:
                print(f"[HeyGen] {character} timed out after {max_wait}s")

    except Exception as e:
        print(f"[HeyGen] {character} error: {e}")

    return None


async def generate_podcast_avatars(
    character_images: dict,
    character_audio: dict,
    output_dir: Path,
    niche: str = "ai_trading",
    max_wait: int = 300,
    line_timings: list[dict] | None = None,
) -> dict:
    """
    Animate character images into talking head videos.

    Priority chain:
    1. D-ID Talks API (if credits available)
    2. HeyGen API (fallback, if API key configured)
    3. Local: Wav2Lip (free, GPU preferred)
    4. Local: Audio-reactive mouth animation (free, CPU)
    5. Static images (final fallback)

    Uses emotion-aware expression configuration for D-ID to produce
    more natural facial movements matching dialogue tone.

    Args:
        character_images: {"sparky": image_path, "nova": image_path}
        character_audio: {"sparky": audio_path, "nova": audio_path}
        output_dir: Where to save animated clips
        niche: Niche key for logging context
        max_wait: Max seconds to poll for each character (default 300)
        line_timings: Optional per-line timing data from voice generation.

    Returns:
        {"sparky": video_path_or_None, "nova": video_path_or_None, "animated": True/False,
         "expression_configs": {"sparky": {...}, "nova": {...}}}
    """
    import httpx
    from config import DID_API_KEY, HEYGEN_API_KEY, LOCAL_AVATAR_ENABLED, LOCAL_AVATAR_PREFER_GPU

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    DID_BASE = "https://api.d-id.com"
    result = {"sparky": None, "nova": None, "animated": False, "expression_configs": {}}

    # ── Check which avatar API to use ────────────────────────
    use_did = False
    use_heygen = False

    if DID_API_KEY:
        did_credits = await _check_did_credits()
        if did_credits > 5:  # Need ~2 credits per character
            use_did = True
            print(f"[Podcast] Using D-ID for avatars ({did_credits} credits remaining)")
        else:
            print(f"[Podcast] D-ID credits exhausted ({did_credits} remaining) — trying alternatives")

    if not use_did and HEYGEN_API_KEY:
        use_heygen = True
        print("[Podcast] Using HeyGen API for avatars (D-ID fallback)")

    if not use_did and not use_heygen:
        reason = "credits exhausted" if DID_API_KEY else "no API key"
        print(f"[Podcast] No cloud avatar API available (D-ID: {reason}, HeyGen: {'not configured' if not HEYGEN_API_KEY else 'error'})")

        # Try local avatar generation (Sprites → Wav2Lip → Audio-reactive → static)
        if LOCAL_AVATAR_ENABLED:
            from modules.local_avatar import generate_local_avatar, _check_sprites_available
            print("[Podcast] Trying local avatar generation (FREE)...")

            # Log sprite library availability
            for _cn in ["sparky", "nova"]:
                _img = character_images.get(_cn)
                if _img and _check_sprites_available(_img):
                    print(f"[Podcast] {_cn.upper()}: D-ID sprite library available (FREE, D-ID quality)")

            for char_name in ["sparky", "nova"]:
                char_upper = char_name.upper()
                img_path = character_images.get(char_name)
                audio_path = character_audio.get(char_name)
                if not img_path or not audio_path:
                    continue
                if not Path(img_path).exists() or not Path(audio_path).exists():
                    continue

                out_path = output_dir / f"{char_name}_animated.mp4"
                local_result = await generate_local_avatar(
                    image_path=img_path,
                    audio_path=audio_path,
                    output_path=out_path,
                    character=char_upper,
                    prefer_gpu=LOCAL_AVATAR_PREFER_GPU,
                    line_timings=line_timings,
                )
                if local_result:
                    result[char_name] = local_result

            result["animated"] = bool(result["sparky"] or result["nova"])
            if result["animated"]:
                count = sum(1 for k in ("sparky", "nova") if result[k])
                print(f"[Podcast] Local animation complete: {count}/2 characters animated")
                return result
            else:
                print("[Podcast] Local animation failed — using static images")
        else:
            print("[Podcast] Local avatar disabled — using static images")

        return result

    # ── HeyGen path ──────────────────────────────────────────
    if use_heygen:
        for char_name in ["sparky", "nova"]:
            char_upper = char_name.upper()
            img_path = character_images.get(char_name)
            audio_path = character_audio.get(char_name)
            if not img_path or not audio_path:
                continue
            if not Path(img_path).exists() or not Path(audio_path).exists():
                continue
            out_path = output_dir / f"{char_name}_animated.mp4"
            avatar_path = await _generate_avatar_heygen(
                img_path, audio_path, out_path, char_upper, max_wait)
            if avatar_path:
                result[char_name] = avatar_path
        result["animated"] = bool(result["sparky"] or result["nova"])
        if result["animated"]:
            count = sum(1 for k in ("sparky", "nova") if result[k])
            print(f"[Podcast] HeyGen animation complete: {count}/2 characters animated")
        else:
            print("[Podcast] HeyGen animation failed — using static images")
        return result

    # ── D-ID path (original) ─────────────────────────────────
    if not DID_API_KEY:
        print("[Podcast] D-ID API key not set — using static character images")
        return result

    # Build per-character expression configs from line_timings
    expression_configs = {}
    for char_key in ["sparky", "nova"]:
        expr_cfg = _build_did_expression_config(char_key.upper(), line_timings)
        expression_configs[char_key] = expr_cfg
        dominant = expr_cfg["dominant_emotion"]
        seg_count = len(expr_cfg["segments"])
        print(f"[Podcast] {char_key.upper()} expression: dominant={dominant}, segments={seg_count}")
    result["expression_configs"] = expression_configs

    headers = {
        "Authorization": f"Basic {DID_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    upload_headers = {
        "Authorization": f"Basic {DID_API_KEY}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        for char_name in ["sparky", "nova"]:
            char_upper = char_name.upper()
            img_path = character_images.get(char_name)
            audio_path = character_audio.get(char_name)

            if not img_path or not audio_path:
                print(f"[Podcast] Skipping {char_upper} — missing image or audio")
                continue

            if not Path(img_path).exists() or not Path(audio_path).exists():
                print(f"[Podcast] Skipping {char_upper} — file not found")
                continue

            try:
                # Step 1: Upload character image
                print(f"[Podcast] Uploading {char_upper} image to D-ID...")
                with open(img_path, "rb") as f:
                    img_resp = await client.post(
                        f"{DID_BASE}/images",
                        headers=upload_headers,
                        files={"image": (Path(img_path).name, f, "image/png")},
                    )
                if img_resp.status_code not in (200, 201):
                    print(f"[Podcast] {char_upper} image upload failed: {img_resp.status_code}")
                    continue
                image_url = img_resp.json().get("url")

                # Step 2: Upload character audio
                print(f"[Podcast] Uploading {char_upper} audio to D-ID...")
                with open(audio_path, "rb") as f:
                    audio_resp = await client.post(
                        f"{DID_BASE}/audios",
                        headers=upload_headers,
                        files={"audio": (Path(audio_path).name, f, "audio/mpeg")},
                    )
                if audio_resp.status_code not in (200, 201):
                    print(f"[Podcast] {char_upper} audio upload failed: {audio_resp.status_code}")
                    continue
                audio_url = audio_resp.json().get("url")

                # Step 3: Build the D-ID talk request with expression-aware config
                char_expr = expression_configs.get(char_name, {})
                dominant_expr = char_expr.get("dominant_expression", {})
                dominant_emotion = char_expr.get("dominant_emotion", "EXCITED")

                # Base request body — maximum quality settings
                talk_body = {
                    "script": {
                        "type": "audio",
                        "audio_url": audio_url,
                        "subtitles": False,
                    },
                    "source_url": image_url,
                    "config": {
                        "result_format": "mp4",
                        "stitch": True,       # Smoother transitions, less jitter
                        "fluent": True,        # Natural head movement during speech
                        "pad_audio": 0.0,      # No extra silence padding
                        "auto_match": True,    # Auto-match face alignment
                    },
                    # bank://lively/ provides the most natural idle + talking movement
                    "driver_url": "bank://lively/",
                }

                # Attach expression metadata as a custom field.
                # D-ID currently uses driver_url for expression style, but when
                # per-timestamp driver_expressions become available on the API,
                # this payload is ready to be moved into the request body directly.
                driver_override = char_expr.get("driver_expression_override")
                if driver_override and driver_override.get("expressions"):
                    # Store expression timeline in the request body under a
                    # namespaced key. D-ID ignores unknown keys gracefully,
                    # so this is safe and future-ready.
                    talk_body["_expression_timeline"] = driver_override
                    print(
                        f"[Podcast] {char_upper} expression timeline: "
                        f"{len(driver_override['expressions'])} segments "
                        f"(prepared for future D-ID per-timestamp support)"
                    )
                else:
                    print(
                        f"[Podcast] {char_upper} using dominant expression: "
                        f"{dominant_emotion} ({dominant_expr.get('expression', 'neutral')})"
                    )

                print(f"[Podcast] Creating {char_upper} talking head animation...")
                talk_resp = await client.post(
                    f"{DID_BASE}/talks",
                    headers=headers,
                    json=talk_body,
                )

                if talk_resp.status_code not in (200, 201):
                    print(f"[Podcast] {char_upper} D-ID talk failed: {talk_resp.status_code} {talk_resp.text[:200]}")
                    continue

                talk_id = talk_resp.json()["id"]
                print(f"[Podcast] {char_upper} talk created: {talk_id}")

                # Step 4: Poll for completion
                output_path = output_dir / f"{char_name}_animated.mp4"
                for poll in range(max_wait // 3):
                    await asyncio.sleep(3)
                    poll_resp = await client.get(
                        f"{DID_BASE}/talks/{talk_id}", headers=headers,
                    )
                    if poll_resp.status_code != 200:
                        continue
                    data = poll_resp.json()
                    status = data.get("status")
                    if status == "done":
                        result_url = data.get("result_url")
                        if result_url:
                            video_resp = await client.get(result_url, timeout=120)
                            if video_resp.status_code == 200:
                                output_path.write_bytes(video_resp.content)
                                size_mb = len(video_resp.content) / (1024 * 1024)
                                print(f"[Podcast] {char_upper} animated: {output_path.name} ({size_mb:.1f}MB)")
                                result[char_name] = str(output_path)
                        break
                    elif status in ("error", "rejected"):
                        err = data.get("error", data.get("reject_reason", status))
                        print(f"[Podcast] {char_upper} D-ID failed: {err}")
                        break
                else:
                    print(f"[Podcast] {char_upper} D-ID timed out after {max_wait}s")

            except Exception as e:
                print(f"[Podcast] {char_upper} avatar error: {e}")
                continue

    # Mark as animated if at least one character succeeded
    result["animated"] = bool(result["sparky"] or result["nova"])
    if result["animated"]:
        animated_count = sum(1 for k in ("sparky", "nova") if result[k])
        print(f"[Podcast] D-ID animation complete: {animated_count}/2 characters animated")
    else:
        print("[Podcast] D-ID animation failed — falling back to static images")

    return result


# ── CLI Test ─────────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        script = await generate_podcast_script(
            topic="Will AI replace ALL jobs by 2030?",
            niche="ai_money",
            duration=90,
            character_style="baby",
        )
        if script:
            print(json.dumps(script, indent=2)[:2000])
            lines = parse_podcast_lines(script)
            print(f"\nParsed {len(lines)} dialogue lines")
            for l in lines[:4]:
                print(f"  [{l['character']}] [{l['emotion']}] {l['text'][:60]}...")
        else:
            print("Script generation failed")

    asyncio.run(test())
