"""
SFX Manager - Sound effects via ElevenLabs Sound Generation API.

Generates and caches sound effects for transitions, accents, and scene cues.
Uses text-to-sound-effects API (included in ElevenLabs subscription).
"""
import hashlib
import httpx
from pathlib import Path

from config import ELEVENLABS_API_KEY, SFX_CACHE_DIR, ENABLE_SFX


# ---- Pre-defined SFX library ------------------------------------------------
# Each entry maps a keyword to a text prompt for the ElevenLabs SFX API.

SFX_LIBRARY = {
    # ── Transitions ──
    "whoosh": {
        "prompt": "Fast cinematic whoosh transition sound, clean and punchy",
        "duration": 1.0,
    },
    "whoosh_soft": {
        "prompt": "Gentle soft whoosh, airy and subtle transition",
        "duration": 0.8,
    },
    "swoosh": {
        "prompt": "Quick swoosh swipe sound, short and snappy",
        "duration": 0.6,
    },
    # ── Impacts & Drama ──
    "impact": {
        "prompt": "Deep dramatic impact boom, cinematic hit with reverb",
        "duration": 1.5,
    },
    "impact_light": {
        "prompt": "Light punchy hit, subtle emphasis thud",
        "duration": 0.5,
    },
    "bass_drop": {
        "prompt": "Deep bass drop impact, heavy low frequency thud",
        "duration": 1.0,
    },
    "dramatic_boom": {
        "prompt": "Cinematic dramatic boom with echo, movie trailer impact",
        "duration": 2.0,
    },
    # ── War / conflict (Tech Pulse Africa) ──
    "explosion": {
        "prompt": "Massive explosion blast, deep boom with debris and rumble, war zone",
        "duration": 2.0,
    },
    "gunfire": {
        "prompt": "Rapid automatic gunfire, distant machine gun bursts, war zone combat",
        "duration": 1.5,
    },
    "jet": {
        "prompt": "Fighter jet flyover, fast military aircraft screaming past, sonic roar",
        "duration": 1.8,
    },
    "missile": {
        "prompt": "Missile launch ignition and whoosh, rocket firing into the sky",
        "duration": 1.6,
    },
    "helicopter": {
        "prompt": "Military helicopter rotor blades thumping, chopper flyover",
        "duration": 1.5,
    },
    "war_siren": {
        "prompt": "Air raid siren wailing, ominous emergency warning, war",
        "duration": 2.0,
    },
    # Long ominous bed used as the music track for war content (loops).
    "war_tension_bed": {
        "prompt": "Dark ominous cinematic tension drone, deep pulsing bass, building "
                  "suspense, distant rumble, war documentary underscore, no melody",
        "duration": 22.0,
    },
    # ── Money & Success ──
    "money": {
        "prompt": "Cash register cha-ching sound, coins and money",
        "duration": 1.0,
    },
    "coins": {
        "prompt": "Handful of coins clinking and falling, metallic jingle",
        "duration": 1.2,
    },
    "success": {
        "prompt": "Bright success achievement sound, uplifting chime",
        "duration": 1.0,
    },
    "level_up": {
        "prompt": "Video game level up achievement fanfare, triumphant",
        "duration": 1.5,
    },
    # ── Tech & Digital ──
    "notification": {
        "prompt": "Soft digital notification ding, subtle and modern",
        "duration": 0.8,
    },
    "data": {
        "prompt": "Futuristic data processing sound, digital beeps and clicks",
        "duration": 1.2,
    },
    "glitch": {
        "prompt": "Digital glitch distortion sound effect, short tech error",
        "duration": 0.6,
    },
    "typing": {
        "prompt": "Fast mechanical keyboard typing sound, tech coding",
        "duration": 1.5,
    },
    "beep": {
        "prompt": "Short digital beep, clean electronic tone",
        "duration": 0.4,
    },
    "scan": {
        "prompt": "Futuristic holographic scanning sound, tech interface",
        "duration": 1.0,
    },
    "power_up": {
        "prompt": "Electronic power up charging sound, energy build",
        "duration": 1.2,
    },
    # ── Atmosphere & Emotion ──
    "rise": {
        "prompt": "Rising cinematic tension riser, building suspense",
        "duration": 2.0,
    },
    "reveal": {
        "prompt": "Magical reveal shimmer sound, bright and sparkling",
        "duration": 1.2,
    },
    "tension": {
        "prompt": "Dark suspenseful tension drone, eerie and ominous",
        "duration": 2.5,
    },
    "sparkle": {
        "prompt": "Bright magical sparkle shimmer, fairy dust twinkle",
        "duration": 1.0,
    },
    "calm_wave": {
        "prompt": "Gentle ocean wave washing onto shore, peaceful calm",
        "duration": 2.0,
    },
    "wind_chime": {
        "prompt": "Gentle wind chimes tinkling in breeze, peaceful",
        "duration": 1.5,
    },
    "heartbeat": {
        "prompt": "Dramatic heartbeat pulse, slow and impactful thump thump",
        "duration": 2.0,
    },
    # ── Alerts & Emphasis ──
    "alarm": {
        "prompt": "Urgent alarm warning buzzer, attention-grabbing alert",
        "duration": 1.0,
    },
    "countdown": {
        "prompt": "Countdown tick tock clock ticking, building urgency",
        "duration": 2.0,
    },
    "pop": {
        "prompt": "Bright pop bubble burst sound, playful and light",
        "duration": 0.4,
    },
    # ── Trending / Viral Sounds ──
    "oh_no": {
        "prompt": "Dramatic comedic oh no sound effect, TikTok viral tension reveal",
        "duration": 1.2,
    },
    "wow": {
        "prompt": "Surprised wow reaction sound, amazed gasp with reverb",
        "duration": 0.8,
    },
    "vine_boom": {
        "prompt": "Deep dramatic bass boom meme sound effect, punchy low frequency hit",
        "duration": 0.6,
    },
    "ding": {
        "prompt": "Bright single ding bell chime, clean and satisfying notification",
        "duration": 0.5,
    },
    "bruh": {
        "prompt": "Low pitched comedic bruh moment sound effect, short deep tone",
        "duration": 0.7,
    },
    "suspense_hit": {
        "prompt": "Dramatic suspense reveal hit, orchestral stinger with tension",
        "duration": 1.0,
    },
    "cash_flow": {
        "prompt": "Rapid money counter machine sound, bills flipping fast",
        "duration": 1.5,
    },
    "laser": {
        "prompt": "Futuristic laser beam zap sound, sci-fi energy pulse",
        "duration": 0.6,
    },
    # Football, for the Genesis tactics reels. Owner 2026-09-02: "let's have
    # the ball kick sound or goal and more, make it feel live." A move drawn in
    # silence is a diagram; the same move with a boot striking leather and a
    # stand reacting is a match. Generated once and cached, like everything
    # else here.
    "ball_kick": {
        "prompt": "Football boot striking a leather ball hard, single clean "
                  "kick, close and punchy, no music",
        "duration": 1.0,
    },
    "goal_roar": {
        "prompt": "Large football stadium crowd erupting in a huge roar as a "
                  "goal is scored, celebration, no music",
        "duration": 4.0,
    },
    "stadium_ambience": {
        "prompt": "Football stadium crowd ambience, steady murmur and "
                  "occasional singing, distant, no music",
        "duration": 10.0,
    },
    "crowd_gasp": {
        "prompt": "Audience crowd gasping in shock, surprised reaction",
        "duration": 1.2,
    },
    "victory_fanfare": {
        "prompt": "Short triumphant victory trumpet fanfare, celebrating achievement",
        "duration": 1.5,
    },
}

# Keyword -> SFX type mapping for auto-detection from narration text
KEYWORD_SFX_MAP = {
    # War / conflict (checked first for the war page)
    "explosion": "explosion", "explode": "explosion", "blast": "explosion",
    "bomb": "explosion", "airstrike": "explosion", "strike": "explosion",
    "attack": "explosion", "bombard": "explosion", "detonat": "explosion",
    "missile": "missile", "rocket": "missile", "launch": "missile",
    "gunfire": "gunfire", "shooting": "gunfire", "firefight": "gunfire",
    "troops": "gunfire", "soldiers": "gunfire", "combat": "gunfire", "battle": "gunfire",
    "jet": "jet", "fighter": "jet", "aircraft": "jet", "warplane": "jet", "f-35": "jet",
    "helicopter": "helicopter", "chopper": "helicopter",
    "siren": "war_siren", "air raid": "war_siren", "evacuat": "war_siren",
    "war": "explosion", "conflict": "gunfire", "military": "gunfire",
    # Money & finance
    "profit": "money", "earn": "money", "income": "money", "$": "money",
    "revenue": "money", "salary": "money", "million": "coins", "billion": "coins",
    "invest": "money", "wealth": "money", "rich": "money",
    # Impact & drama
    "shocking": "impact", "breaking": "impact", "incredible": "impact_light",
    "huge": "impact", "massive": "dramatic_boom", "crash": "bass_drop",
    "destroyed": "impact", "insane": "impact_light", "unbelievable": "impact",
    # Data & tech
    "data": "data", "chart": "data", "graph": "data", "analysis": "scan",
    "statistics": "data", "numbers": "data", "percent": "data",
    "ai": "scan", "robot": "power_up", "algorithm": "data",
    "code": "typing", "build": "typing", "create": "typing", "program": "typing",
    # Alerts & warnings
    "alert": "alarm", "warning": "alarm", "danger": "alarm",
    "urgent": "alarm", "careful": "tension",
    "update": "notification", "new": "notification", "just": "notification",
    # Reveals & secrets
    "secret": "reveal", "discover": "reveal", "finally": "reveal",
    "trick": "reveal", "hidden": "reveal", "truth": "reveal",
    "actually": "reveal", "real reason": "reveal",
    # Growth & momentum
    "growing": "rise", "increasing": "rise", "rising": "rise",
    "skyrocket": "rise", "surge": "rise", "explode": "rise",
    "boom": "bass_drop", "launch": "power_up",
    # Success & achievement
    "success": "success", "achieve": "level_up", "winner": "level_up",
    "best": "success", "top": "success", "proven": "success",
    # Calm & wellness
    "peace": "calm_wave", "calm": "wind_chime", "relax": "calm_wave",
    "breathe": "calm_wave", "mindful": "sparkle", "grateful": "sparkle",
    "beautiful": "sparkle", "bliss": "sparkle", "serene": "calm_wave",
    "nature": "wind_chime", "heal": "sparkle",
    # Urgency & timing
    "now": "countdown", "fast": "swoosh", "quick": "swoosh",
    "hurry": "countdown", "deadline": "countdown",
    # Health
    "health": "sparkle", "sleep": "calm_wave", "energy": "power_up",
    "exercise": "pop", "diet": "pop", "superfood": "sparkle",
    # Trending / viral emphasis
    "mistake": "oh_no", "wrong": "oh_no", "fail": "oh_no", "lost": "oh_no",
    "wait": "suspense_hit", "but": "suspense_hit", "however": "suspense_hit",
    "imagine": "wow", "amazing": "wow", "mind-blowing": "wow",
    "crazy": "vine_boom", "wild": "vine_boom", "insane": "vine_boom",
    "free": "ding", "tip": "ding", "hack": "ding", "step": "ding",
    "cash": "cash_flow", "paid": "cash_flow", "payment": "cash_flow",
    "future": "laser", "next": "laser", "revolution": "laser",
    "won": "victory_fanfare", "champion": "victory_fanfare", "first": "crowd_gasp",
}


def _cache_key(sfx_type: str) -> str:
    """Generate a cache filename for an SFX type."""
    return f"sfx_{sfx_type}.mp3"


def get_sfx_sync(sfx_type: str, force: bool = False) -> str | None:
    """
    Synchronous SFX/bed fetch (for the assembler's sync music picker).
    Returns a cached path, generating once via ElevenLabs if missing.

    force=True bypasses the global ENABLE_SFX switch for a caller that has been
    asked for a specific sound by name. ENABLE_SFX is off for the whole system,
    and flipping it on so the Genesis tactics reels could have a kick and a
    crowd would silently add sound effects to every other page's videos too.
    A cached file is returned either way, so a forced sound is generated once
    and costs nothing after that.
    """
    if sfx_type not in SFX_LIBRARY:
        return None
    cache_path = SFX_CACHE_DIR / _cache_key(sfx_type)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return str(cache_path)
    if (not ENABLE_SFX and not force) or not ELEVENLABS_API_KEY:
        return None
    try:
        import requests
        cfg = SFX_LIBRARY[sfx_type]
        SFX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        r = requests.post(
            "https://api.elevenlabs.io/v1/sound-generation",
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={"text": cfg["prompt"], "duration_seconds": cfg["duration"],
                  "prompt_influence": 0.5},
            timeout=45,
        )
        if r.status_code == 200 and r.content:
            cache_path.write_bytes(r.content)
            print(f"[SFX] Generated {sfx_type} ({len(r.content)/1024:.0f}KB) -> cached")
            return str(cache_path)
        print(f"[SFX] {sfx_type} API error {r.status_code}")
    except Exception as e:
        print(f"[SFX] {sfx_type} sync gen failed: {e}")
    return None


def _get_cached(sfx_type: str) -> str | None:
    """Check if SFX is already cached. Returns path or None."""
    cache_path = SFX_CACHE_DIR / _cache_key(sfx_type)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return str(cache_path)
    return None


async def generate_sfx(sfx_type: str) -> str | None:
    """
    Generate a sound effect using ElevenLabs API, with caching.

    Args:
        sfx_type: Key from SFX_LIBRARY (e.g., "whoosh", "impact", "money")

    Returns:
        Path to the generated MP3 file, or None on failure.
    """
    if not ENABLE_SFX or not ELEVENLABS_API_KEY:
        return None

    if sfx_type not in SFX_LIBRARY:
        return None

    # Check cache first
    cached = _get_cached(sfx_type)
    if cached:
        return cached

    sfx_config = SFX_LIBRARY[sfx_type]
    SFX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SFX_CACHE_DIR / _cache_key(sfx_type)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": sfx_config["prompt"],
                    "duration_seconds": sfx_config["duration"],
                    "prompt_influence": 0.5,
                },
            )

            if response.status_code == 200:
                output_path.write_bytes(response.content)
                size_kb = len(response.content) / 1024
                print(f"[SFX] Generated {sfx_type} ({size_kb:.0f}KB) -> cached")
                return str(output_path)
            else:
                print(f"[SFX] API error {response.status_code}: {response.text[:200]}")
                return None

    except Exception as e:
        print(f"[SFX] Generation failed for {sfx_type}: {e}")
        return None


def detect_sfx_for_text(text: str) -> str | None:
    """
    Auto-detect which SFX to use based on narration text keywords.

    Returns the SFX type key or None.
    """
    text_lower = text.lower()
    for keyword, sfx_type in KEYWORD_SFX_MAP.items():
        if keyword in text_lower:
            return sfx_type
    return None


import random as _random

# Varied transition sounds — rotate instead of just whoosh
TRANSITION_SFX = ["whoosh", "whoosh_soft", "swoosh", "whoosh", "swoosh"]


async def generate_scene_sfx(scenes: list[dict]) -> list[dict]:
    """
    Generate SFX for scenes based on narration content and sfx_hint.

    Uses varied transition sounds and smart placement to avoid repetitive audio.
    Only adds transition SFX every 2-3 scenes for variety.

    Args:
        scenes: List of scene dicts with optional "sfx_hint" and "narration" keys.

    Returns:
        List of {sfx_path, start_time, sfx_type} for each detected SFX.
    """
    if not ENABLE_SFX:
        return []

    sfx_placements = []
    current_time = 0
    last_sfx_type = None  # Avoid back-to-back identical SFX

    # Pre-generate transition sounds
    transition_paths = {}
    for t in set(TRANSITION_SFX):
        path = await generate_sfx(t)
        if path:
            transition_paths[t] = path

    for i, scene in enumerate(scenes):
        duration = scene.get("duration", 10)

        # Varied transition SFX — only every 2-3 scenes, not every scene
        if i > 0 and i % 2 == 0 and transition_paths:
            trans_type = TRANSITION_SFX[i % len(TRANSITION_SFX)]
            trans_path = transition_paths.get(trans_type)
            if trans_path:
                sfx_placements.append({
                    "sfx_path": trans_path,
                    "start_time": current_time - 0.3,
                    "sfx_type": trans_type,
                    "volume": 0.3,
                })

        # Check for explicit sfx_hint from script writer
        sfx_hint = scene.get("sfx_hint", "")
        if sfx_hint and sfx_hint != "none":
            # Avoid duplicate of the same SFX type back-to-back
            if sfx_hint != last_sfx_type:
                sfx_path = await generate_sfx(sfx_hint)
                if sfx_path:
                    sfx_placements.append({
                        "sfx_path": sfx_path,
                        "start_time": current_time + 0.5,
                        "sfx_type": sfx_hint,
                        "volume": 0.25,
                    })
                    last_sfx_type = sfx_hint
        else:
            # Auto-detect from narration
            narration = scene.get("narration", "")
            detected = detect_sfx_for_text(narration)
            if detected and detected != last_sfx_type:
                sfx_path = await generate_sfx(detected)
                if sfx_path:
                    sfx_placements.append({
                        "sfx_path": sfx_path,
                        "start_time": current_time + 1.0,
                        "sfx_type": detected,
                        "volume": 0.25,
                    })
                    last_sfx_type = detected

        current_time += duration

    if sfx_placements:
        types_used = set(s["sfx_type"] for s in sfx_placements)
        print(f"[SFX] Placed {len(sfx_placements)} sound effects: {', '.join(types_used)}")

    return sfx_placements


async def pre_generate_common_sfx():
    """Pre-generate commonly used SFX to warm the cache."""
    common = ["whoosh", "whoosh_soft", "swoosh", "impact", "impact_light", "money",
              "notification", "data", "rise", "reveal", "success", "sparkle", "calm_wave"]
    generated = 0
    for sfx_type in common:
        if _get_cached(sfx_type):
            continue
        result = await generate_sfx(sfx_type)
        if result:
            generated += 1
    if generated:
        print(f"[SFX] Pre-generated {generated} common sound effects")


# ── Podcast-Specific SFX ────────────────────────────────────

# Section -> SFX mapping for podcast transitions
PODCAST_SECTION_SFX = {
    "HOOK":              "whoosh_soft",
    "ROUND 1":           "ding",
    "ROUND 2":           "notification",
    "THE TWIST":         "suspense_hit",
    "ROUND 3":           "whoosh",
    "CLIFFHANGER CTA":   "rise",
}

# Emotion -> reaction SFX (subtle, low volume accents)
PODCAST_EMOTION_SFX = {
    "SHOCKED":     "crowd_gasp",
    "ANGRY":       "impact_light",
    "LAUGHS":      "pop",
    "EXCITED":     "wow",
    "CUTS OFF":    "swoosh",
    "FIRED UP":    "bass_drop",
    "DISBELIEF":   "vine_boom",
    "NERVOUS":     "heartbeat",
}


async def generate_podcast_sfx(line_timings: list) -> list[dict]:
    """
    Generate SFX placements for podcast videos.

    Adds two types of SFX:
    1. Section transition stingers (when section changes)
    2. Emotion reaction sounds (for high-intensity emotions)

    Returns list of {sfx_path, start_time, sfx_type, volume} dicts.
    """
    if not ENABLE_SFX:
        return []

    sfx_placements = []
    seen_sections = set()
    last_emotion_sfx_time = -5.0  # Avoid back-to-back emotion SFX

    for timing in line_timings:
        section = timing.get("section", "")
        emotion = timing.get("emotion", "")
        start = timing.get("start", 0)

        # ── Section transition SFX ──
        # Match section prefix (e.g., "ROUND 1: Trading" matches "ROUND 1")
        section_key = None
        for key in PODCAST_SECTION_SFX:
            if section.startswith(key) and key not in seen_sections:
                section_key = key
                break

        if section_key:
            seen_sections.add(section_key)
            sfx_type = PODCAST_SECTION_SFX[section_key]
            sfx_path = await generate_sfx(sfx_type)
            if sfx_path:
                sfx_placements.append({
                    "sfx_path": sfx_path,
                    "start_time": max(0, start - 0.3),
                    "sfx_type": sfx_type,
                    "volume": 0.2,
                })

        # ── Emotion reaction SFX (spaced at least 5s apart) ──
        if emotion in PODCAST_EMOTION_SFX and (start - last_emotion_sfx_time) > 5.0:
            sfx_type = PODCAST_EMOTION_SFX[emotion]
            sfx_path = await generate_sfx(sfx_type)
            if sfx_path:
                sfx_placements.append({
                    "sfx_path": sfx_path,
                    "start_time": start + 0.1,
                    "sfx_type": sfx_type,
                    "volume": 0.12,  # Subtle — don't overpower dialogue
                })
                last_emotion_sfx_time = start

    if sfx_placements:
        types_used = set(s["sfx_type"] for s in sfx_placements)
        print(f"[SFX] Podcast: {len(sfx_placements)} effects ({', '.join(types_used)})")

    return sfx_placements


# CLI test
if __name__ == "__main__":
    import asyncio

    async def test():
        print("[SFX] Testing sound effects manager...")
        if not ELEVENLABS_API_KEY:
            print("[SFX] No API key - skipping generation test")
            return

        # Test single SFX generation
        path = await generate_sfx("whoosh")
        if path:
            print(f"[SFX] Whoosh generated: {path}")

        # Test auto-detection
        test_texts = [
            "This AI trading bot made $500 profit today",
            "Breaking news: massive data breach",
            "Here's the secret trick nobody tells you",
        ]
        for text in test_texts:
            detected = detect_sfx_for_text(text)
            print(f"[SFX] '{text[:40]}...' -> {detected}")

    asyncio.run(test())
