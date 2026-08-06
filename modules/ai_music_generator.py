"""
AI Music Generator — generates copyright-free background music using Meta's MusicGen.

Uses facebook/musicgen-small (~4GB VRAM) to produce niche-specific background
tracks. Generated tracks are cached by niche so identical styles aren't
regenerated unnecessarily.

Falls back gracefully if transformers/torch are unavailable — returns None
so the assembler can use templates/music/ as a last resort.
"""

import asyncio
import hashlib
import os
import subprocess
import time
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────
ENABLE_AI_MUSIC = os.getenv("ENABLE_AI_MUSIC", "true").lower() in ("true", "1", "yes")
AI_MUSIC_CACHE_DIR = Path(__file__).parent.parent / "assets" / "ai_music_cache"

MUSICGEN_MODEL_ID = "facebook/musicgen-small"
SAMPLE_RATE = 32000
MAX_GENERATION_SECONDS = 30
CACHE_MAX_AGE_DAYS = 7

# ── Niche Music Styles ────────────────────────────────────────
NICHE_MUSIC_STYLES = {
    "ai_trading": "ambient electronic lo-fi beats, subtle synthesizer pads, modern corporate technology background music, steady rhythm, calm and focused",
    "ai_money": "upbeat inspiring electronic music, positive energy, motivational corporate background, subtle bass, modern production",
    "tech_news": "futuristic ambient electronic, digital synthesizer textures, modern tech podcast background music, clean and minimal",
    "motivation": "epic cinematic orchestral, powerful drums, inspirational strings, building intensity, triumphant motivational score",
    "health_wellness": "calm ambient nature sounds with soft piano, peaceful meditation music, gentle flowing melody, relaxing spa atmosphere",
    "blissful_moments": "gentle acoustic guitar and soft piano, warm peaceful melody, dreamy ambient pads, calming positive atmosphere",
    "daily_breakdown": "serious news broadcast background music, subtle tension, professional journalism score, steady pulsing rhythm",
    "shopmo_products": "upbeat cheerful pop electronic, fun and energetic, commercial jingle style, catchy modern beat, shopping mood",
    "limitless_you": "powerful motivational cinematic score, driving percussion, inspirational synth layers, building energy, empowering atmosphere",
}

# ── Module-level model cache (lazy loaded) ────────────────────
_musicgen_model = None
_musicgen_processor = None


def _check_dependencies() -> bool:
    """Check if torch and transformers are available."""
    try:
        import torch
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _cuda_available() -> bool:
    """Check if CUDA is available for GPU acceleration."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _load_model():
    """Lazy-load MusicGen model and processor onto GPU with float16."""
    global _musicgen_model, _musicgen_processor

    if _musicgen_model is not None and _musicgen_processor is not None:
        return _musicgen_model, _musicgen_processor

    import torch
    from transformers import AutoProcessor, MusicgenForConditionalGeneration

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"[AIMusic] Loading MusicGen model ({MUSICGEN_MODEL_ID}) on {device} ({dtype})...")
    t0 = time.time()

    _musicgen_processor = AutoProcessor.from_pretrained(MUSICGEN_MODEL_ID)
    _musicgen_model = MusicgenForConditionalGeneration.from_pretrained(
        MUSICGEN_MODEL_ID,
        torch_dtype=dtype,
    ).to(device)

    elapsed = time.time() - t0
    print(f"[AIMusic] MusicGen model loaded in {elapsed:.1f}s")

    return _musicgen_model, _musicgen_processor


def _generate_audio_sync(prompt: str, duration_seconds: float, output_path: Path) -> str | None:
    """Synchronous audio generation. Run via run_in_executor for async."""
    import torch
    import scipy.io.wavfile as wavfile
    import numpy as np

    duration_seconds = min(duration_seconds, MAX_GENERATION_SECONDS)

    model, processor = _load_model()
    device = next(model.parameters()).device

    # Calculate max_new_tokens from desired duration
    # MusicGen generates audio at ~50 tokens/second for the small model
    tokens_per_second = 50
    max_new_tokens = int(duration_seconds * tokens_per_second)

    print(f"[AIMusic] Generating {duration_seconds:.0f}s track via MusicGen ({max_new_tokens} tokens)...")
    t0 = time.time()

    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        audio_values = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            guidance_scale=3.0,
        )

    elapsed = time.time() - t0
    print(f"[AIMusic] Generation completed in {elapsed:.1f}s")

    # audio_values shape: (batch, channels, samples)
    audio_data = audio_values[0, 0].cpu().float().numpy()

    # Normalize to prevent clipping
    peak = np.max(np.abs(audio_data))
    if peak > 0:
        audio_data = audio_data / peak * 0.95

    # Apply fade in/out to avoid clicks
    fade_samples = int(SAMPLE_RATE * 0.5)  # 0.5s fade
    if len(audio_data) > fade_samples * 2:
        fade_in = np.linspace(0.0, 1.0, fade_samples)
        fade_out = np.linspace(1.0, 0.0, fade_samples)
        audio_data[:fade_samples] *= fade_in
        audio_data[-fade_samples:] *= fade_out

    # Save as WAV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = output_path.with_suffix(".wav")

    # Convert to int16 for WAV
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(str(wav_path), SAMPLE_RATE, audio_int16)

    actual_duration = len(audio_data) / SAMPLE_RATE
    print(f"[AIMusic] Saved {actual_duration:.1f}s WAV to {wav_path}")

    # Try converting to MP3 via ffmpeg
    mp3_path = output_path.with_suffix(".mp3")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(wav_path),
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                "-ar", str(SAMPLE_RATE),
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and mp3_path.exists():
            wav_path.unlink(missing_ok=True)
            print(f"[AIMusic] Converted to MP3: {mp3_path}")
            return str(mp3_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("[AIMusic] ffmpeg not available, keeping WAV format")

    return str(wav_path)


def _get_cache_path(niche: str) -> Path:
    """Return the cache file path for a given niche."""
    return AI_MUSIC_CACHE_DIR / f"bgm_{niche}.wav"


def _find_cached_track(niche: str) -> str | None:
    """Find a cached track for the niche (WAV or MP3), checking age."""
    base = AI_MUSIC_CACHE_DIR / f"bgm_{niche}"
    for ext in (".mp3", ".wav"):
        path = base.with_suffix(ext)
        if path.exists():
            age_days = (time.time() - path.stat().st_mtime) / 86400
            if age_days < CACHE_MAX_AGE_DAYS:
                return str(path)
            else:
                print(f"[AIMusic] Cache expired for {niche} ({age_days:.1f} days old)")
                path.unlink(missing_ok=True)
    return None


async def generate_music(niche: str, duration_seconds: float, output_path: Path) -> str | None:
    """
    Generate background music for a niche using MusicGen.

    Args:
        niche: One of the supported niche keys.
        duration_seconds: Desired track length (capped at 30s).
        output_path: Where to save the generated audio file.

    Returns:
        Path to the generated audio file, or None on failure.
    """
    if not ENABLE_AI_MUSIC:
        print("[AIMusic] AI music generation disabled (ENABLE_AI_MUSIC=false)")
        return None

    if not _check_dependencies():
        print("[AIMusic] Missing dependencies (torch/transformers). Install with:")
        print("[AIMusic]   pip install torch transformers scipy")
        return None

    if not _cuda_available():
        print("[AIMusic] CUDA not available. MusicGen requires GPU for practical use.")
        return None

    prompt = NICHE_MUSIC_STYLES.get(niche)
    if not prompt:
        print(f"[AIMusic] Unknown niche '{niche}', using generic style")
        prompt = "ambient background music, calm and professional, modern production"

    duration_seconds = min(max(duration_seconds, 5.0), MAX_GENERATION_SECONDS)

    print(f"[AIMusic] Generating {duration_seconds:.0f}s track for {niche} via MusicGen...")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _generate_audio_sync,
            prompt,
            duration_seconds,
            output_path,
        )
        return result
    except Exception as e:
        print(f"[AIMusic] Generation failed: {e}")
        return None


async def get_music_track(niche: str, duration_seconds: float = 30.0) -> str | None:
    """
    Get a background music track for a niche, using cache when possible.

    Args:
        niche: One of the supported niche keys.
        duration_seconds: Desired track length (capped at 30s).

    Returns:
        Path to the audio file, or None if generation fails
        (assembler should fall back to templates/music/).
    """
    if not ENABLE_AI_MUSIC:
        return None

    # Check cache first
    cached = _find_cached_track(niche)
    if cached:
        print(f"[AIMusic] Using cached track for {niche}: {cached}")
        return cached

    # Generate new track
    AI_MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _get_cache_path(niche)

    result = await generate_music(niche, duration_seconds, output_path)
    return result


def get_music_track_sync(niche: str, duration_seconds: float = 30.0) -> str | None:
    """
    Synchronous wrapper for get_music_track() — called by video_assembler._get_music_track().

    Checks cache first (no async needed). Only generates new tracks
    if there's a running event loop to schedule on.
    """
    if not ENABLE_AI_MUSIC:
        return None

    # Check cache first (synchronous — no model needed)
    cached = _find_cached_track(niche)
    if cached:
        print(f"[AIMusic] Using cached track for {niche}: {cached}")
        return cached

    # For fresh generation, we need the model + async
    if not _check_dependencies() or not _cuda_available():
        return None

    # Generate synchronously (we're already in a thread from the assembler)
    prompt = NICHE_MUSIC_STYLES.get(niche)
    if not prompt:
        prompt = "ambient background music, calm and professional, modern production"

    AI_MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _get_cache_path(niche)

    try:
        result = _generate_audio_sync(prompt, min(max(duration_seconds, 5.0), MAX_GENERATION_SECONDS), output_path)
        return result
    except Exception as e:
        print(f"[AIMusic] Sync generation failed: {e}")
        return None


def unload_musicgen() -> None:
    """Free VRAM by deleting the MusicGen model and clearing CUDA cache."""
    global _musicgen_model, _musicgen_processor

    if _musicgen_model is None and _musicgen_processor is None:
        print("[AIMusic] No MusicGen model loaded, nothing to unload")
        return

    _musicgen_model = None
    _musicgen_processor = None

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

    print("[AIMusic] MusicGen model unloaded, VRAM freed")
