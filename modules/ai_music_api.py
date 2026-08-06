"""
AI Music API — Background music generation with smart caching.

Strategy: Generate music per mood/niche ONCE, cache aggressively, reuse forever.
After 1 week of operation, music generation costs drop to near-zero.

Sources (priority):
1. Local cache (FREE — already generated tracks)
2. Local MusicGen (FREE — runs on GPU, existing module)
3. Suno API via third-party (paid — ~$0.11/song, commercial license)

Cache strategy:
- Music cached by: niche + mood + tempo category
- Each niche gets 10-15 tracks in rotation
- Random selection from cache prevents repetitiveness
- New tracks generated only when cache < MIN_TRACKS_PER_CATEGORY
"""

import asyncio
import json
import os
import random
import shutil
import subprocess
import time
from pathlib import Path

import aiohttp

from config import ASSETS_DIR, ENABLE_AI_MUSIC

# ── Graceful import of local MusicGen module ─────────────────
try:
    from modules.ai_music_generator import generate_music as _musicgen_generate
    _HAS_MUSICGEN = True
except ImportError:
    _HAS_MUSICGEN = False
    _musicgen_generate = None

# ── API Configuration ────────────────────────────────────────
SUNO_API_KEY = os.getenv("SUNO_API_KEY", "")
SUNO_API_URL = os.getenv("SUNO_API_URL", "")

# ── Cache Configuration ──────────────────────────────────────
MUSIC_CACHE_DIR = ASSETS_DIR / "music_cache"
MIN_TRACKS_PER_CATEGORY = 5
MAX_TRACKS_PER_CATEGORY = 15
METADATA_FILE = "metadata.json"

# ── Mood System ──────────────────────────────────────────────
MOODS = (
    "energetic", "calm", "dramatic", "upbeat",
    "mysterious", "inspiring", "dark", "playful", "default",
)

NICHE_DEFAULT_MOODS: dict[str, str] = {
    "ai_money": "energetic",
    "tech_news": "mysterious",
    "motivation": "inspiring",
    "health_wellness": "calm",
    "blissful_moments": "calm",
    "daily_breakdown": "dramatic",
    "shopmo_products": "upbeat",
    "limitless_you": "inspiring",
}

# ── Music Generation Prompts ─────────────────────────────────
# Keyed by (niche, mood). Short-form optimized: punchy, hook-worthy.
MUSIC_PROMPTS: dict[tuple[str, str], str] = {
    # ai_money
    ("ai_money", "energetic"): "high-energy electronic trap beat, punchy bass drops, motivational money vibes, crisp hi-hats, modern production",
    ("ai_money", "upbeat"): "upbeat electronic pop, catchy synth hook, confident swagger beat, clean modern production",
    ("ai_money", "dramatic"): "intense cinematic electronic, building tension, dark synth bass, powerful drops, stock market energy",
    ("ai_money", "default"): "high-energy electronic trap beat, punchy bass drops, motivational money vibes, crisp hi-hats, modern production",
    # tech_news
    ("tech_news", "mysterious"): "dark ambient electronic, glitchy textures, futuristic sci-fi atmosphere, pulsing sub-bass, digital artifacts",
    ("tech_news", "energetic"): "fast-paced tech house beat, futuristic synths, digital glitch textures, driving rhythm, cyberpunk energy",
    ("tech_news", "calm"): "ambient electronic soundscape, soft digital pads, minimal techno pulse, clean futuristic atmosphere",
    ("tech_news", "default"): "dark ambient electronic, glitchy textures, futuristic sci-fi atmosphere, pulsing sub-bass, digital artifacts",
    # motivation
    ("motivation", "inspiring"): "epic cinematic orchestral, powerful drums building intensity, soaring strings, triumphant brass, victorious energy",
    ("motivation", "energetic"): "driving motivational beat, powerful percussion, uplifting synth layers, unstoppable momentum, stadium anthem energy",
    ("motivation", "dramatic"): "intense cinematic score, deep war drums, dramatic strings, building to explosive climax, raw power",
    ("motivation", "default"): "epic cinematic orchestral, powerful drums building intensity, soaring strings, triumphant brass, victorious energy",
    # health_wellness
    ("health_wellness", "calm"): "gentle ambient piano with soft nature sounds, peaceful meditation music, warm pads, flowing water texture",
    ("health_wellness", "inspiring"): "uplifting acoustic guitar melody, gentle piano chords, warm positive atmosphere, morning sunrise feeling",
    ("health_wellness", "playful"): "light bouncy acoustic, soft xylophone melody, happy morning routine vibes, fresh and clean",
    ("health_wellness", "default"): "gentle ambient piano with soft nature sounds, peaceful meditation music, warm pads, flowing water texture",
    # blissful_moments
    ("blissful_moments", "calm"): "dreamy ambient pads, soft music box melody, gentle flowing piano, warm nostalgic atmosphere, tender lullaby feel",
    ("blissful_moments", "playful"): "sweet ukulele melody, gentle handclaps, happy childhood vibes, warm acoustic guitar, innocent joy",
    ("blissful_moments", "inspiring"): "warm orchestral strings, gentle piano melody, emotional cinematic, heartwarming family moment",
    ("blissful_moments", "default"): "dreamy ambient pads, soft music box melody, gentle flowing piano, warm nostalgic atmosphere, tender lullaby feel",
    # daily_breakdown
    ("daily_breakdown", "dramatic"): "serious news broadcast score, subtle tension building, professional urgency, deep bass pulse, journalistic gravity",
    ("daily_breakdown", "mysterious"): "dark investigative score, suspenseful strings, ominous undertone, conspiracy documentary feel",
    ("daily_breakdown", "energetic"): "fast-paced news beat, urgent percussion, breaking news energy, intense modern production",
    ("daily_breakdown", "default"): "serious news broadcast score, subtle tension building, professional urgency, deep bass pulse, journalistic gravity",
    # shopmo_products
    ("shopmo_products", "upbeat"): "catchy pop electronic, fun shopping beat, bright synth melody, energetic commercial jingle, buy-now energy",
    ("shopmo_products", "playful"): "bouncy fun electronic pop, happy claps, cheerful product showcase vibes, retail energy",
    ("shopmo_products", "energetic"): "high-energy commercial beat, flash sale urgency, punchy drums, exciting deal energy, fast tempo",
    ("shopmo_products", "default"): "catchy pop electronic, fun shopping beat, bright synth melody, energetic commercial jingle, buy-now energy",
    # limitless_you
    ("limitless_you", "inspiring"): "powerful cinematic synth, emotional piano chords, building orchestral layers, breakthrough moment energy, limitless feeling",
    ("limitless_you", "energetic"): "driving electronic beat, empowering bass drops, unstoppable momentum, peak performance energy, beast mode",
    ("limitless_you", "dramatic"): "intense orchestral buildup, deep percussion, dramatic strings to triumphant resolution, transformation arc",
    ("limitless_you", "default"): "powerful cinematic synth, emotional piano chords, building orchestral layers, breakthrough moment energy, limitless feeling",
}

# Fallback prompts when no niche-specific prompt exists
MOOD_FALLBACK_PROMPTS: dict[str, str] = {
    "energetic": "high-energy electronic beat, punchy drums, driving bass, modern production",
    "calm": "gentle ambient piano, soft pads, peaceful flowing melody, relaxing atmosphere",
    "dramatic": "intense cinematic score, powerful percussion, building tension, epic orchestral",
    "upbeat": "catchy upbeat pop electronic, bright melody, fun positive energy, modern beat",
    "mysterious": "dark ambient electronic, suspenseful atmosphere, glitchy textures, deep bass",
    "inspiring": "epic cinematic orchestral, soaring strings, triumphant brass, victorious energy",
    "dark": "deep dark ambient, ominous bass, sinister textures, industrial undertones, heavy",
    "playful": "bouncy fun melody, light percussion, cheerful vibes, happy and bright",
    "default": "modern background music, clean production, subtle energy, professional atmosphere",
}


# ── Metadata Helpers ─────────────────────────────────────────

def _metadata_path(niche: str, mood: str) -> Path:
    """Return the metadata JSON path for a niche/mood cache directory."""
    return MUSIC_CACHE_DIR / niche / mood / METADATA_FILE


def _load_metadata(niche: str, mood: str) -> dict:
    """Load metadata for a niche/mood category. Returns empty structure if missing."""
    path = _metadata_path(niche, mood)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"tracks": [], "created": time.time(), "updated": time.time()}


def _save_metadata(niche: str, mood: str, data: dict) -> None:
    """Save metadata JSON for a niche/mood category."""
    path = _metadata_path(niche, mood)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated"] = time.time()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _next_track_number(niche: str, mood: str) -> int:
    """Return the next sequential track number for naming."""
    meta = _load_metadata(niche, mood)
    if not meta["tracks"]:
        return 1
    existing_nums = []
    for t in meta["tracks"]:
        fname = t.get("filename", "")
        # Parse track_NNN.mp3 / track_NNN.wav
        stem = Path(fname).stem
        if stem.startswith("track_"):
            try:
                existing_nums.append(int(stem.split("_")[1]))
            except (ValueError, IndexError):
                pass
    return max(existing_nums, default=0) + 1


# ── Duration Handling (trim / loop / fade) ───────────────────

def _adjust_duration(input_path: str, target_duration: float, output_path: str) -> str:
    """
    Adjust audio file to match target duration exactly.

    - If longer: trim to target duration.
    - If shorter: loop with 0.5s crossfade.
    - Always applies fade-in (0.3s) and fade-out (0.5s).

    Returns path to the adjusted file.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        # pydub not available — try ffmpeg directly
        return _adjust_duration_ffmpeg(input_path, target_duration, output_path)

    audio = AudioSegment.from_file(input_path)
    target_ms = int(target_duration * 1000)
    current_ms = len(audio)

    if current_ms > target_ms:
        # Trim
        audio = audio[:target_ms]
    elif current_ms < target_ms:
        # Loop with crossfade
        crossfade_ms = min(500, current_ms // 4)  # 0.5s or 25% of track, whichever is smaller
        result = audio
        while len(result) < target_ms:
            overlap = min(crossfade_ms, len(result), len(audio))
            if overlap < 10:
                result = result + audio
            else:
                result = result.append(audio, crossfade=overlap)
        audio = result[:target_ms]

    # Apply fades
    fade_in_ms = min(300, len(audio) // 4)
    fade_out_ms = min(500, len(audio) // 4)
    audio = audio.fade_in(fade_in_ms).fade_out(fade_out_ms)

    # Export
    out = Path(output_path)
    fmt = "mp3" if out.suffix.lower() == ".mp3" else "wav"
    audio.export(str(out), format=fmt, bitrate="192k")
    return str(out)


def _adjust_duration_ffmpeg(input_path: str, target_duration: float, output_path: str) -> str:
    """Fallback duration adjustment using ffmpeg when pydub is unavailable."""
    try:
        # Get current duration
        probe = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        current_duration = float(probe.stdout.strip()) if probe.returncode == 0 else 0.0

        if current_duration <= 0:
            # Can't probe — just copy
            shutil.copy2(input_path, output_path)
            return output_path

        # Build ffmpeg filter for trim/loop + fades
        filters = []

        if current_duration > target_duration:
            # Trim
            filters.append(f"atrim=0:{target_duration}")
        elif current_duration < target_duration:
            # Loop: calculate how many times to loop
            loops = int(target_duration / current_duration) + 1
            filters.append(f"aloop=loop={loops}:size={int(current_duration * 48000)}")
            filters.append(f"atrim=0:{target_duration}")

        # Fade in 0.3s, fade out 0.5s
        filters.append(f"afade=t=in:st=0:d=0.3")
        filters.append(f"afade=t=out:st={target_duration - 0.5}:d=0.5")

        filter_str = ",".join(filters) if filters else "anull"

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-af", filter_str,
                "-codec:a", "libmp3lame", "-b:a", "192k",
                output_path,
            ],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode == 0 and Path(output_path).exists():
            return output_path
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    # Last resort: just copy the file as-is
    shutil.copy2(input_path, output_path)
    return output_path


# ── Cache Operations ─────────────────────────────────────────

def get_cached_track(niche: str, mood: str) -> str | None:
    """
    Return a random track from the cache for the given niche/mood.

    Returns absolute path to the track, or None if cache is empty.
    """
    cache_dir = MUSIC_CACHE_DIR / niche / mood
    if not cache_dir.exists():
        return None

    tracks = [
        f for f in cache_dir.iterdir()
        if f.suffix.lower() in (".mp3", ".wav") and f.is_file()
    ]

    if not tracks:
        return None

    chosen = random.choice(tracks)
    print(f"[MusicAPI] Cache hit: {chosen.name} ({niche}/{mood}, {len(tracks)} available)")
    return str(chosen)


def cache_track(file_path: str, niche: str, mood: str, tags: list[str] | None = None) -> str:
    """
    Copy a track into the cache and update metadata.

    If the category is at MAX_TRACKS_PER_CATEGORY, removes the oldest track first.

    Returns the cached file path.
    """
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"Source track not found: {file_path}")

    cache_dir = MUSIC_CACHE_DIR / niche / mood
    cache_dir.mkdir(parents=True, exist_ok=True)

    meta = _load_metadata(niche, mood)

    # Enforce max tracks
    existing_tracks = [
        f for f in cache_dir.iterdir()
        if f.suffix.lower() in (".mp3", ".wav") and f.is_file()
    ]
    while len(existing_tracks) >= MAX_TRACKS_PER_CATEGORY:
        # Remove oldest by modification time
        oldest = min(existing_tracks, key=lambda f: f.stat().st_mtime)
        oldest_name = oldest.name
        oldest.unlink(missing_ok=True)
        meta["tracks"] = [t for t in meta["tracks"] if t.get("filename") != oldest_name]
        existing_tracks = [f for f in existing_tracks if f != oldest]
        print(f"[MusicAPI] Cache full, removed oldest: {oldest_name}")

    # Determine filename
    track_num = _next_track_number(niche, mood)
    ext = src.suffix if src.suffix.lower() in (".mp3", ".wav") else ".mp3"
    dest_name = f"track_{track_num:03d}{ext}"
    dest = cache_dir / dest_name

    shutil.copy2(str(src), str(dest))

    # Update metadata
    meta["tracks"].append({
        "filename": dest_name,
        "tags": tags or [],
        "source": "local" if "musicgen" in str(src).lower() or "ai_music" in str(src).lower() else "external",
        "cached_at": time.time(),
        "size_bytes": dest.stat().st_size,
    })
    _save_metadata(niche, mood, meta)

    print(f"[MusicAPI] Cached: {dest_name} -> {niche}/{mood} ({len(meta['tracks'])} tracks)")
    return str(dest)


def get_cache_stats() -> dict:
    """
    Return cache statistics: total tracks, tracks per niche/mood, disk usage.
    """
    stats: dict = {
        "total_tracks": 0,
        "total_size_bytes": 0,
        "niches": {},
    }

    if not MUSIC_CACHE_DIR.exists():
        return stats

    for niche_dir in MUSIC_CACHE_DIR.iterdir():
        if not niche_dir.is_dir() or niche_dir.name.startswith("."):
            continue

        niche_name = niche_dir.name
        niche_stats: dict = {"moods": {}, "total_tracks": 0, "total_size_bytes": 0}

        for mood_dir in niche_dir.iterdir():
            if not mood_dir.is_dir() or mood_dir.name.startswith("."):
                continue

            tracks = [
                f for f in mood_dir.iterdir()
                if f.suffix.lower() in (".mp3", ".wav") and f.is_file()
            ]
            size = sum(f.stat().st_size for f in tracks)

            niche_stats["moods"][mood_dir.name] = {
                "tracks": len(tracks),
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
            }
            niche_stats["total_tracks"] += len(tracks)
            niche_stats["total_size_bytes"] += size

        niche_stats["total_size_mb"] = round(niche_stats["total_size_bytes"] / (1024 * 1024), 2)
        stats["niches"][niche_name] = niche_stats
        stats["total_tracks"] += niche_stats["total_tracks"]
        stats["total_size_bytes"] += niche_stats["total_size_bytes"]

    stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
    return stats


# ── Music Generation Sources ─────────────────────────────────

def _get_prompt(niche: str, mood: str) -> str:
    """Build the music generation prompt for a niche/mood pair."""
    prompt = MUSIC_PROMPTS.get((niche, mood))
    if prompt:
        return prompt

    # Try niche with default mood
    prompt = MUSIC_PROMPTS.get((niche, "default"))
    if prompt:
        return prompt

    # Fall back to mood-only prompt
    return MOOD_FALLBACK_PROMPTS.get(mood, MOOD_FALLBACK_PROMPTS["default"])


_musicgen_disabled = False  # Set True after timeout — prevents retry loop

async def generate_music_local(prompt: str, duration: float, output_path: str) -> str | None:
    """
    Generate music using the local MusicGen module (GPU, free).

    Args:
        prompt: Text description of the music to generate.
        duration: Desired duration in seconds.
        output_path: Where to save the generated file.

    Returns:
        Path to the generated file, or None if unavailable/failed.
    """
    global _musicgen_disabled
    if _musicgen_disabled:
        return None

    if not _HAS_MUSICGEN:
        print("[MusicAPI] Local MusicGen not available (module not installed)")
        return None

    if not ENABLE_AI_MUSIC:
        print("[MusicAPI] AI music generation disabled (ENABLE_AI_MUSIC=false)")
        return None

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        # The existing module's generate_music() takes (niche, duration, output_path)
        # but we need prompt-based generation. We'll call _generate_audio_sync via
        # the module's lower-level function if available, otherwise use the high-level API.
        from modules.ai_music_generator import (
            _check_dependencies,
            _cuda_available,
            _generate_audio_sync,
        )

        if not _check_dependencies():
            print("[MusicAPI] MusicGen dependencies missing (torch/transformers)")
            return None

        if not _cuda_available():
            print("[MusicAPI] CUDA not available for MusicGen")
            return None

        # Cap at 30s (MusicGen small model limitation)
        gen_duration = min(max(duration, 5.0), 30.0)

        print(f"[MusicAPI] Generating {gen_duration:.0f}s track via local MusicGen...")
        loop = asyncio.get_event_loop()
        # 60-second timeout — GPU can hang after SDXL/other model crashes
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, _generate_audio_sync, prompt, gen_duration, out,
            ),
            timeout=60.0,
        )
        return result

    except asyncio.TimeoutError:
        _musicgen_disabled = True
        print("[MusicAPI] MusicGen TIMEOUT (60s) — GPU stuck, DISABLED for this session")
        return None
    except ImportError:
        print("[MusicAPI] Cannot import MusicGen internals, falling back")
        return None
    except Exception as e:
        print(f"[MusicAPI] Local generation failed: {e}")
        return None


async def generate_music_suno(prompt: str, duration: float, output_path: str) -> str | None:
    """
    Generate music via Suno API (third-party provider, paid).

    Requires SUNO_API_KEY and SUNO_API_URL environment variables.
    The third-party endpoint should accept POST with JSON body and return
    audio data or a download URL.

    Args:
        prompt: Text description of the music to generate.
        duration: Desired duration in seconds.
        output_path: Where to save the generated file.

    Returns:
        Path to the generated file, or None if unavailable/failed.
    """
    if not SUNO_API_KEY or not SUNO_API_URL:
        print("[MusicAPI] Suno API not configured (set SUNO_API_KEY and SUNO_API_URL)")
        return None

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = {
            "prompt": prompt,
            "duration": min(int(duration), 120),
            "make_instrumental": True,
            "wait_audio": True,
        }
        headers = {
            "Authorization": f"Bearer {SUNO_API_KEY}",
            "Content-Type": "application/json",
        }

        print(f"[MusicAPI] Requesting Suno generation ({duration:.0f}s)...")
        t0 = time.time()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SUNO_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    print(f"[MusicAPI] Suno API error {resp.status}: {body[:200]}")
                    return None

                data = await resp.json()

        # Parse response — adapt to your provider's format
        # Common patterns: direct audio_url, or nested in data[0].audio_url
        audio_url = None
        if isinstance(data, list) and data:
            audio_url = data[0].get("audio_url") or data[0].get("url")
        elif isinstance(data, dict):
            audio_url = data.get("audio_url") or data.get("url")
            if not audio_url and "data" in data:
                items = data["data"]
                if isinstance(items, list) and items:
                    audio_url = items[0].get("audio_url") or items[0].get("url")

        if not audio_url:
            print(f"[MusicAPI] Suno API returned no audio URL. Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            return None

        # Download the audio file
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    print(f"[MusicAPI] Failed to download Suno audio: {resp.status}")
                    return None
                audio_bytes = await resp.read()

        with open(str(out), "wb") as f:
            f.write(audio_bytes)

        elapsed = time.time() - t0
        size_mb = len(audio_bytes) / (1024 * 1024)
        print(f"[MusicAPI] Suno track downloaded: {size_mb:.1f}MB in {elapsed:.1f}s -> {out.name}")
        return str(out)

    except asyncio.TimeoutError:
        print("[MusicAPI] Suno API request timed out")
        return None
    except Exception as e:
        print(f"[MusicAPI] Suno generation failed: {e}")
        return None


# ── Core Entry Point ─────────────────────────────────────────

async def get_background_music(
    niche: str,
    mood: str = "default",
    duration: float = 30.0,
    output_path: str | None = None,
) -> str | None:
    """
    Get background music for a video. Cache-first strategy.

    Priority:
    1. Local cache (instant, free)
    2. Local MusicGen (GPU, free, ~30s generation)
    3. Suno API (paid, ~$0.11/track)

    Args:
        niche: Content niche (ai_money, tech_news, etc.).
        mood: Music mood. Uses niche default if "default".
        duration: Target duration in seconds.
        output_path: Optional output path. If None, returns cached/generated path directly.

    Returns:
        Absolute path to the music file (adjusted to target duration), or None on failure.
    """
    if not ENABLE_AI_MUSIC:
        print("[MusicAPI] AI music disabled (ENABLE_AI_MUSIC=false)")
        return None

    # Resolve mood
    if mood == "default":
        mood = NICHE_DEFAULT_MOODS.get(niche, "default")

    # Validate mood
    if mood not in MOODS:
        print(f"[MusicAPI] Unknown mood '{mood}', falling back to niche default")
        mood = NICHE_DEFAULT_MOODS.get(niche, "default")

    print(f"[MusicAPI] Requesting music: niche={niche}, mood={mood}, duration={duration:.1f}s")

    # ── 1. Check cache ────────────────────────────────────
    cached = get_cached_track(niche, mood)
    if cached:
        if output_path:
            return _adjust_duration(cached, duration, output_path)
        return cached

    # ── 2. Generate via local MusicGen ────────────────────
    prompt = _get_prompt(niche, mood)
    temp_dir = MUSIC_CACHE_DIR / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = str(temp_dir / f"gen_{niche}_{mood}_{int(time.time())}.mp3")

    result = await generate_music_local(prompt, duration, temp_file)

    # ── 3. Fall back to Suno API ──────────────────────────
    if not result:
        result = await generate_music_suno(prompt, duration, temp_file)

    # ── 4. Cache and return ───────────────────────────────
    if result:
        tags = [niche, mood, f"duration_{int(duration)}s"]
        cached_path = cache_track(result, niche, mood, tags=tags)

        # Clean up temp file if it differs from cached path
        temp = Path(result)
        if temp.exists() and str(temp) != cached_path:
            temp.unlink(missing_ok=True)

        if output_path:
            return _adjust_duration(cached_path, duration, output_path)
        return cached_path

    print(f"[MusicAPI] All generation sources failed for {niche}/{mood}")
    return None


async def ensure_minimum_cache(niche: str, mood: str = "default") -> int:
    """
    Ensure the cache has at least MIN_TRACKS_PER_CATEGORY tracks for a niche/mood.

    Generates missing tracks using available sources. Useful for pre-warming
    the cache during off-peak hours.

    Args:
        niche: Content niche.
        mood: Music mood. Uses niche default if "default".

    Returns:
        Number of tracks generated (0 if cache was already sufficient).
    """
    if mood == "default":
        mood = NICHE_DEFAULT_MOODS.get(niche, "default")

    cache_dir = MUSIC_CACHE_DIR / niche / mood
    existing = 0
    if cache_dir.exists():
        existing = len([
            f for f in cache_dir.iterdir()
            if f.suffix.lower() in (".mp3", ".wav") and f.is_file()
        ])

    needed = max(0, MIN_TRACKS_PER_CATEGORY - existing)
    if needed == 0:
        print(f"[MusicAPI] Cache sufficient for {niche}/{mood}: {existing} tracks")
        return 0

    print(f"[MusicAPI] Cache needs {needed} more tracks for {niche}/{mood} (have {existing})")

    generated = 0
    prompt = _get_prompt(niche, mood)
    temp_dir = MUSIC_CACHE_DIR / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for i in range(needed):
        temp_file = str(temp_dir / f"fill_{niche}_{mood}_{int(time.time())}_{i}.mp3")

        # Vary the prompt slightly to get different tracks
        varied_prompt = prompt
        if i > 0:
            variations = [
                ", slightly different arrangement",
                ", alternative mix",
                ", variation with different instruments",
                ", remixed version",
            ]
            varied_prompt = prompt + variations[i % len(variations)]

        result = await generate_music_local(varied_prompt, 30.0, temp_file)
        if not result:
            result = await generate_music_suno(varied_prompt, 30.0, temp_file)

        if result:
            tags = [niche, mood, "auto_generated", f"fill_{i+1}"]
            cache_track(result, niche, mood, tags=tags)
            # Clean up temp
            temp = Path(result)
            if temp.exists() and MUSIC_CACHE_DIR / "_temp" in temp.parents:
                temp.unlink(missing_ok=True)
            generated += 1
        else:
            print(f"[MusicAPI] Failed to generate fill track {i+1}/{needed}")
            break  # Stop if generation is failing

    # Clean up temp dir if empty
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        temp_dir.rmdir()

    print(f"[MusicAPI] Generated {generated}/{needed} tracks for {niche}/{mood}")
    return generated


async def warm_cache(niches: list[str] | None = None) -> dict[str, int]:
    """
    Pre-warm the music cache for all (or specified) niches with their default moods.

    Returns dict mapping "niche/mood" to number of tracks generated.
    """
    if niches is None:
        niches = list(NICHE_DEFAULT_MOODS.keys())

    results = {}
    for niche in niches:
        mood = NICHE_DEFAULT_MOODS.get(niche, "default")
        key = f"{niche}/{mood}"
        generated = await ensure_minimum_cache(niche, mood)
        results[key] = generated

    total = sum(results.values())
    print(f"[MusicAPI] Cache warm-up complete: {total} new tracks across {len(niches)} niches")
    return results
