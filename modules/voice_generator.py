"""
Voice Generator — Smart routing: Kokoro (primary free) → ElevenLabs (premium) → edge-tts (fallback).

Priority chain:
  1. Kokoro TTS  — hexgrad/Kokoro-82M, 82M-param open-weight, runs on GPU, 54+ voices, 24kHz
  2. ElevenLabs  — premium cloud TTS (skipped when quota exhausted)
  3. edge-tts    — Microsoft Azure free tier, always available, unlimited

- Podcast dual-voice -> Kokoro by default (two distinct voices for SPARKY & NOVA characters)
- YouTube long-form -> Kokoro primary, ElevenLabs optional premium upgrade
- Shorts/TikTok/Reels -> Kokoro primary, edge-tts fallback
"""
import asyncio
import re
from pathlib import Path

from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID,
    ELEVENLABS_MODEL,
    ELEVENLABS_OUTPUT_FORMAT,
    DEFAULT_EDGE_VOICE,
    NICHES,
    VOICE_YOUTUBE_LONG,
    VOICE_SHORTS,
    OUTPUT_DIR,
)

# ── Module-level state ────────────────────────────────────────
# Set True after first ElevenLabs quota error — skips further EL calls this session
_el_quota_exhausted: bool = False
# Lazy-loaded Kokoro pipelines cached by lang_code ('a'=American, 'b'=British)
_kokoro_pipeline: dict = {}


def _alignment_to_word_segments(alignment) -> list[dict]:
    """Convert ElevenLabs character-level alignment to word-level subtitle segments."""
    try:
        characters = getattr(alignment, 'characters', None) or alignment.get("characters", [])
        starts = getattr(alignment, 'character_start_times_seconds', None) or alignment.get("character_start_times_seconds", [])
        ends = getattr(alignment, 'character_end_times_seconds', None) or alignment.get("character_end_times_seconds", [])
    except (AttributeError, TypeError):
        return []

    if not characters or len(characters) != len(starts):
        return []

    words = []
    current_word = ""
    word_start = None
    word_end = None

    for i, char in enumerate(characters):
        if char in (" ", "\n", "\t"):
            if current_word:
                words.append({
                    "start": round(word_start, 3),
                    "end": round(word_end, 3),
                    "text": current_word,
                })
                current_word = ""
                word_start = None
        else:
            if word_start is None:
                word_start = starts[i]
            word_end = ends[i]
            current_word += char

    # Don't forget the last word
    if current_word and word_start is not None:
        words.append({
            "start": round(word_start, 3),
            "end": round(word_end, 3),
            "text": current_word,
        })

    return words


async def generate_voice_edge_tts(
    text: str,
    output_audio: Path,
    output_subs: Path | None = None,
    voice: str = DEFAULT_EDGE_VOICE,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> dict:
    """
    Generate voiceover using edge-tts (completely free, unlimited).

    Returns:
        dict with audio_path, subtitle_path, duration_estimate, engine
    """
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

    # Generate audio
    await communicate.save(str(output_audio))

    # Generate subtitles with word-level timestamps
    subtitle_path = output_subs or output_audio.with_suffix(".srt")
    submaker = edge_tts.SubMaker()

    communicate2 = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    async for chunk in communicate2.stream():
        if chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            submaker.feed(chunk)

    with open(subtitle_path, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())

    # Estimate duration from word count (~150 words per minute for narration)
    word_count = len(text.split())
    duration_estimate = word_count / 2.5  # ~150 wpm = 2.5 words/sec

    print(f"[Voice] edge-tts: {output_audio.name} ({word_count} words, ~{duration_estimate:.0f}s)")

    return {
        "audio_path": str(output_audio),
        "subtitle_path": str(subtitle_path),
        "duration_estimate": duration_estimate,
        "word_count": word_count,
        "engine": "edge-tts",
        "voice": voice,
    }


async def generate_voice_elevenlabs(
    text: str,
    output_audio: Path,
    voice_id: str = ELEVENLABS_VOICE_ID,
    output_subs: Path | None = None,
) -> dict | None:
    """
    Generate voiceover using ElevenLabs (premium quality).
    Uses convert_with_timestamps for subtitle alignment when available.
    """
    if not ELEVENLABS_API_KEY:
        return None

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        subtitle_path = None

        # Voice settings for maximum quality and expressiveness
        from elevenlabs import VoiceSettings
        voice_settings = VoiceSettings(
            stability=0.50,
            similarity_boost=0.75,
            style=0.45,
            use_speaker_boost=True,
        )

        # Try with timestamps first — gives us proper subtitle alignment
        try:
            response = client.text_to_speech.convert_with_timestamps(
                text=text,
                voice_id=voice_id,
                model_id=ELEVENLABS_MODEL,
                output_format=ELEVENLABS_OUTPUT_FORMAT,
                voice_settings=voice_settings,
            )

            # Decode and save audio — field is `audio_base_64` (Pydantic attr)
            import base64
            audio_b64 = response.audio_base_64
            audio_bytes = base64.b64decode(audio_b64)
            with open(output_audio, "wb") as f:
                f.write(audio_bytes)

            # Extract word-level timestamps from alignment
            alignment = response.alignment
            if alignment:
                word_segments = _alignment_to_word_segments(alignment)
                if word_segments and output_subs:
                    from modules.caption_generator import segments_to_srt
                    segments_to_srt(word_segments, output_subs)
                    subtitle_path = str(output_subs)
                    print(f"[Voice] ElevenLabs timestamps: {len(word_segments)} words synced")

        except Exception as ts_err:
            # Fallback to basic convert (no timestamps)
            print(f"[Voice] Timestamps unavailable ({ts_err}), using standard convert")
            audio_generator = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=ELEVENLABS_MODEL,
                output_format=ELEVENLABS_OUTPUT_FORMAT,
                voice_settings=voice_settings,
            )
            with open(output_audio, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)

        word_count = len(text.split())
        duration_estimate = word_count / 2.5

        print(f"[Voice] ElevenLabs: {output_audio.name} ({word_count} words, ~{duration_estimate:.0f}s)")

        return {
            "audio_path": str(output_audio),
            "subtitle_path": subtitle_path,
            "duration_estimate": duration_estimate,
            "word_count": word_count,
            "engine": "elevenlabs",
            "voice": voice_id,
        }

    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("quota", "limit", "429", "insufficient_quota", "exceeded")):
            global _el_quota_exhausted
            _el_quota_exhausted = True
            print(f"[Voice] ElevenLabs quota exhausted — switching to Kokoro for remaining lines")
        else:
            print(f"[Voice] ElevenLabs failed: {e}")
        return None


# ── Kokoro TTS Engine ─────────────────────────────────────────────────────────
# Voice naming: af_ = American Female, am_ = American Male,
#               bf_ = British Female, bm_ = British Male
# Confirmed working voices (tested 2026-03-13 on RTX 2080 Ti):
#   af_heart, am_michael, af_nova, am_adam, bf_emma, bm_george


def _get_kokoro_pipeline(lang_code: str = "a"):
    """Lazy-load and cache a Kokoro KPipeline. Reuses across calls."""
    global _kokoro_pipeline
    if lang_code not in _kokoro_pipeline:
        from kokoro import KPipeline
        _kokoro_pipeline[lang_code] = KPipeline(lang_code=lang_code)
        print(f"[Voice] Kokoro pipeline loaded (lang_code='{lang_code}')")
    return _kokoro_pipeline[lang_code]


def _generate_kokoro_sync(
    text: str,
    voice: str,
    output_path: Path,
    speed: float = 1.0,
) -> float:
    """
    Sync Kokoro generation: text → 24 kHz numpy array → WAV → MP3.
    Runs in a thread executor (KPipeline is not async-native).
    Returns audio duration in seconds.
    """
    import numpy as np
    import soundfile as sf
    from pydub import AudioSegment

    # lang_code: 'b' for British voices (bf_/bm_), 'a' for American (af_/am_)
    lang_code = "b" if voice.startswith("b") else "a"
    pipeline = _get_kokoro_pipeline(lang_code)

    # Collect all audio chunks from the generator
    audio_chunks = []
    for _graphemes, _phonemes, audio_np in pipeline(text, voice=voice, speed=speed):
        if audio_np is not None and len(audio_np) > 0:
            audio_chunks.append(audio_np)

    if not audio_chunks:
        raise RuntimeError(f"Kokoro produced no audio for voice='{voice}'")

    combined = np.concatenate(audio_chunks)
    sample_rate = 24_000  # Kokoro always outputs 24 kHz

    # Save as temp WAV (soundfile handles numpy → WAV natively)
    tmp_wav = Path(output_path).with_suffix(".tmp_kokoro.wav")
    try:
        sf.write(str(tmp_wav), combined, sample_rate)
        # Convert WAV → MP3 for compatibility with the rest of the pipeline
        AudioSegment.from_wav(str(tmp_wav)).export(
            str(output_path), format="mp3", bitrate="192k"
        )
    finally:
        tmp_wav.unlink(missing_ok=True)

    return len(combined) / sample_rate  # exact duration


def _srt_ts(seconds: float) -> str:
    """Convert float seconds → SRT timestamp string (HH:MM:SS,mmm)."""
    ms = int(round((seconds % 1) * 1000))
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _generate_estimated_srt(text: str, duration: float, srt_path: Path) -> None:
    """
    Build a word-level SRT from raw text + total audio duration.
    Distributes timing proportionally by character count — a reasonable
    approximation when phoneme-level alignment is unavailable.
    """
    words = text.split()
    if not words:
        srt_path.write_text("", encoding="utf-8")
        return

    total_chars = sum(len(w) for w in words) or 1
    lines = []
    t = 0.0
    for i, word in enumerate(words, 1):
        word_dur = (len(word) / total_chars) * duration
        lines += [
            str(i),
            f"{_srt_ts(t)} --> {_srt_ts(t + word_dur)}",
            word,
            "",
        ]
        t += word_dur

    srt_path.write_text("\n".join(lines), encoding="utf-8")


async def generate_voice_kokoro(
    text: str,
    output_audio: Path,
    voice: str = "af_heart",
    speed: float = 1.0,
    output_subs: Path | None = None,
) -> dict | None:
    """
    Generate voiceover with Kokoro TTS (free, GPU-accelerated, 54+ voices).

    Returns dict with audio_path, subtitle_path, duration_estimate, engine, voice.
    Returns None on failure so callers can fall through to the next engine.
    """
    loop = asyncio.get_event_loop()
    try:
        duration = await loop.run_in_executor(
            None,
            _generate_kokoro_sync,
            text,
            voice,
            output_audio,
            speed,
        )

        subtitle_path = output_subs or output_audio.with_suffix(".srt")
        _generate_estimated_srt(text, duration, subtitle_path)

        word_count = len(text.split())
        print(f"[Voice] Kokoro ({voice}, {speed}x): {output_audio.name} "
              f"({word_count} words, {duration:.1f}s)")

        return {
            "audio_path": str(output_audio),
            "subtitle_path": str(subtitle_path),
            "duration_estimate": duration,
            "word_count": word_count,
            "engine": "kokoro",
            "voice": voice,
        }

    except Exception as e:
        print(f"[Voice] Kokoro failed (voice={voice}): {e}")
        return None


async def generate_voice(
    text: str,
    output_dir: Path,
    filename_base: str = "voiceover",
    format_type: str = "long",
    niche: str | None = None,
    scenes: list[dict] | None = None,
) -> dict:
    """
    Smart voice routing — picks the best engine based on format type.

    Supports scene-level emotion detection for edge-tts (varies rate/pitch
    based on content — faster for hooks, slower for key reveals).

    Args:
        text: The narration text
        output_dir: Directory to save audio files
        filename_base: Base filename (without extension)
        format_type: "long" for YouTube, "short" for Shorts/TikTok/Reels
        niche: Niche key for voice selection
        scenes: Optional list of scene dicts for emotion-aware TTS

    Returns:
        dict with audio_path, subtitle_path, duration, engine info
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{filename_base}.mp3"
    subs_path = output_dir / f"{filename_base}.srt"

    # ── 1. Try Kokoro (primary free engine) ──────────────────
    # Choose a niche-appropriate Kokoro voice (default: af_heart for female narration)
    kokoro_voices = {
        "ai_trading":       "am_michael",
        "ai_money":         "am_adam",
        "tech_news":        "bm_george",
        "motivation":       "am_michael",
        "health_wellness":  "af_heart",
        "blissful_moments": "af_nova",
    }
    kokoro_voice = kokoro_voices.get(niche or "", "af_heart")
    result = await generate_voice_kokoro(text, audio_path, voice=kokoro_voice, output_subs=subs_path)
    if result:
        return result

    # ── 2. Try ElevenLabs (premium, if available and quota not exhausted) ──
    if format_type == "long" and VOICE_YOUTUBE_LONG == "elevenlabs" and not _el_quota_exhausted:
        result = await generate_voice_elevenlabs(text, audio_path, output_subs=subs_path)
        if result:
            if not result["subtitle_path"]:
                print("[Voice] Falling back to Kokoro for subtitle timing...")
                kok_sub = await generate_voice_kokoro(
                    text,
                    output_dir / f"{filename_base}_subs_only.mp3",
                    voice=kokoro_voice,
                    output_subs=subs_path,
                )
                (output_dir / f"{filename_base}_subs_only.mp3").unlink(missing_ok=True)
                result["subtitle_path"] = str(subs_path) if subs_path.exists() else None
            return result

    # ── 3. Fall back to edge-tts (always available, unlimited) ──
    edge_voice = DEFAULT_EDGE_VOICE
    if niche and niche in NICHES:
        edge_voice = NICHES[niche].get("edge_voice", DEFAULT_EDGE_VOICE)

    emotion = detect_voice_emotion(text)
    rate = emotion["rate"]
    pitch = emotion["pitch"]

    if scenes and len(scenes) > 0:
        hook_text = scenes[0].get("narration", "")
        if hook_text and format_type == "short":
            hook_emotion = detect_voice_emotion(hook_text)
            rate = hook_emotion["rate"]
            pitch = hook_emotion["pitch"]

    print(f"[Voice] Falling back to edge-tts for {filename_base}")
    return await generate_voice_edge_tts(text, audio_path, subs_path, voice=edge_voice, rate=rate, pitch=pitch)


def split_text_for_scenes(text: str, max_chars: int = 500) -> list[str]:
    """Split long text into manageable chunks for TTS processing."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += " " + sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ── Voice Emotion/Speed Detection ───────────────────────────

# Keywords that indicate the voice should speed up (excitement, urgency)
FAST_KEYWORDS = {
    "breaking", "urgent", "just", "now", "incredible", "insane", "shocking",
    "exploding", "skyrocket", "fast", "quick", "hurry", "immediately",
    "boom", "massive", "crazy", "unbelievable", "alert", "warning",
}

# Keywords that indicate the voice should slow down (emphasis, revelation)
SLOW_KEYWORDS = {
    "secret", "truth", "actually", "real reason", "important",
    "listen", "remember", "key", "crucial", "never forget",
    "here's the thing", "but", "however", "pause",
}

# Keywords for deeper/lower pitch (authority, gravity)
DEEP_KEYWORDS = {
    "danger", "warning", "risk", "crash", "lost", "failed",
    "death", "serious", "critical", "devastating",
}

# Keywords for higher pitch (excitement, positivity)
HIGH_KEYWORDS = {
    "amazing", "incredible", "profit", "success", "won", "earned",
    "beautiful", "wonderful", "love", "peace", "grateful", "blessed",
}


def detect_voice_emotion(text: str) -> dict:
    """
    Detect the emotional tone of text and return voice parameters.

    Returns dict with 'rate' and 'pitch' adjustments for edge-tts.
    """
    text_lower = text.lower()
    words = set(text_lower.split())

    rate = "+0%"
    pitch = "+0Hz"

    # Check for speed indicators
    fast_count = len(words & FAST_KEYWORDS)
    slow_count = len(words & SLOW_KEYWORDS)

    if fast_count > slow_count and fast_count >= 2:
        rate = "+12%"  # Noticeably faster for excitement
    elif fast_count > 0 and slow_count == 0:
        rate = "+6%"   # Slightly faster
    elif slow_count > fast_count and slow_count >= 1:
        rate = "-8%"   # Slower for emphasis
    elif "?" in text:
        rate = "+4%"   # Questions slightly faster (conversational)

    # Check for pitch indicators
    deep_count = len(words & DEEP_KEYWORDS)
    high_count = len(words & HIGH_KEYWORDS)

    if deep_count > high_count:
        pitch = "-15Hz"  # Deeper for serious moments
    elif high_count > deep_count:
        pitch = "+10Hz"  # Higher for excitement/positivity
    elif text.endswith("!"):
        pitch = "+5Hz"   # Slight lift for exclamations

    return {"rate": rate, "pitch": pitch}


# ── Podcast Dual Voice Generation ────────────────────────────

# Per-niche voice pairs for podcast characters
# SPARKY = bold/energetic voice, NOVA = calm/analytical voice
PODCAST_EDGE_VOICES = {
    # SPARKY/NOVA voice MUST match the character gender defined in NICHE_CHARACTER_NAMES
    # ai_trading:  SPARKY=JAYDEN(M)    NOVA=ZOE(F)
    # ai_money:    SPARKY=MALIK(M)     NOVA=LUNA(F)
    # tech_news:   SPARKY=KAI(M)       NOVA=AMARA(F)
    # motivation:  SPARKY=BLAZE(M)     NOVA=SAGE(F)
    # health_wellness:   SPARKY=MIA(F)  NOVA=NOAH(M)  ← SPARKY is FEMALE here
    # blissful_moments:  SPARKY=ARIA(F) NOVA=LIAM(M)  ← SPARKY is FEMALE here
    "ai_trading":       {"SPARKY": "en-US-GuyNeural",          "NOVA": "en-US-JennyNeural"},
    "ai_money":         {"SPARKY": "en-US-ChristopherNeural",  "NOVA": "en-US-AriaNeural"},
    "tech_news":        {"SPARKY": "en-GB-RyanNeural",         "NOVA": "en-GB-SoniaNeural"},
    "motivation":       {"SPARKY": "en-US-ChristopherNeural",  "NOVA": "en-US-JennyNeural"},
    "health_wellness":  {"SPARKY": "en-US-JennyNeural",        "NOVA": "en-US-GuyNeural"},
    "blissful_moments": {"SPARKY": "en-US-JennyNeural",        "NOVA": "en-US-ChristopherNeural"},
}

# ── Kokoro Podcast Voices ─────────────────────────────────────
# Per-niche (voice_id, speed) pairs — gender-matched to character names
# ai_trading:        SPARKY=JAYDEN(M)  NOVA=ZOE(F)
# ai_money:          SPARKY=MALIK(M)   NOVA=LUNA(F)
# tech_news:         SPARKY=KAI(M)     NOVA=AMARA(F)
# motivation:        SPARKY=BLAZE(M)   NOVA=SAGE(F)
# health_wellness:   SPARKY=MIA(F)     NOVA=NOAH(M)  ← SPARKY is female
# blissful_moments:  SPARKY=ARIA(F)    NOVA=LIAM(M)  ← SPARKY is female
PODCAST_KOKORO_VOICES: dict[str, dict[str, tuple[str, float]]] = {
    "ai_trading":       {"SPARKY": ("am_michael", 1.05), "NOVA": ("af_heart",  0.95)},
    "ai_money":         {"SPARKY": ("am_adam",    1.05), "NOVA": ("af_nova",   0.95)},
    "tech_news":        {"SPARKY": ("bm_george",  1.00), "NOVA": ("bf_emma",   0.95)},
    "motivation":       {"SPARKY": ("am_michael", 1.10), "NOVA": ("af_nova",   0.95)},
    "health_wellness":  {"SPARKY": ("af_heart",   1.05), "NOVA": ("am_adam",   0.95)},
    "blissful_moments": {"SPARKY": ("af_nova",    1.00), "NOVA": ("am_michael",0.95)},
}

# ── Premium ElevenLabs Voices for Podcast Characters ─────────
# Selected for maximum natural, conversational podcast feel.
# SPARKY: Bold, energetic, charming — drives the conversation
# NOVA: Smooth, trustworthy, calm — drops facts and balances

PODCAST_ELEVENLABS_VOICES = {
    # Default pair — Two friends having a natural chill conversation
    "SPARKY": "iP95p4xoKVk53GoZ742B",   # "Chris" — Charming, Down-to-Earth, Conversational
    "NOVA": "cjVigY5qzO86Huf0OWal",     # "Eric" — Smooth, Trustworthy, Conversational
}

# Per-niche ElevenLabs voice pair overrides for best fit
PODCAST_NICHE_ELEVENLABS = {
    "ai_trading": {
        "SPARKY": "IKne3meq5aSn9XLyUdCD",  # "Charlie" — Deep, Confident, Energetic (Australian)
        "NOVA": "cjVigY5qzO86Huf0OWal",    # "Eric" — Smooth, Trustworthy
    },
    "ai_money": {
        "SPARKY": "iP95p4xoKVk53GoZ742B",  # "Chris" — Charming, Down-to-Earth
        "NOVA": "cjVigY5qzO86Huf0OWal",    # "Eric" — Smooth, Trustworthy
    },
    "tech_news": {
        "SPARKY": "TX3LPaxmHKxFdv7VOQHJ",  # "Liam" — Energetic, Social Media Creator
        "NOVA": "SAz9YHcvj6GT2YYXdXww",    # "River" — Relaxed, Neutral, Informative
    },
    "motivation": {
        "SPARKY": "IKne3meq5aSn9XLyUdCD",  # "Charlie" — Deep, Confident, Energetic
        "NOVA": "CwhRBWXzGAHq8TQ4Fs17",    # "Roger" — Laid-Back, Casual, Resonant
    },
    "health_wellness": {
        # MIA (girl) = female voice, NOAH (boy) = male voice
        "SPARKY": "9BWtsMINqrJLrRacOk9x",  # "Aria" — Bright, Expressive, Curious Female
        "NOVA":   "iP95p4xoKVk53GoZ742B",  # "Chris" — Charming, Warm Male
    },
    "blissful_moments": {
        # ARIA (girl) = female voice, LIAM (boy) = male voice
        "SPARKY": "9BWtsMINqrJLrRacOk9x",  # "Aria" — Bright, Expressive Female (matches character name!)
        "NOVA":   "bIHbv24MWmeRgasZH58o",  # "Will" — Relaxed Optimist Male
    },
}


async def generate_podcast_dual_voice(
    script_data: dict,
    output_dir: Path,
    niche: str = "ai_trading",
    use_elevenlabs: bool = True,
) -> dict:
    """
    Generate PREMIUM dual-character podcast audio with ElevenLabs voices.

    Creates separate audio for each dialogue line with the appropriate
    character voice, then merges into a single audio track with natural
    conversational pauses and timing.

    ALWAYS uses ElevenLabs when available for top-quality podcast voices.
    Falls back to edge-tts if ElevenLabs quota is exhausted.

    Args:
        script_data: Parsed podcast script with lines
        output_dir: Directory to save audio files
        niche: Niche for voice selection
        use_elevenlabs: Use ElevenLabs (default True for podcast quality)

    Returns:
        dict with audio_path, subtitle_path, line_timings, duration, engine
    """
    from pydub import AudioSegment

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lines_dir = output_dir / "podcast_lines"
    lines_dir.mkdir(exist_ok=True)

    # Voice pairs for each engine tier
    kokoro_voice_pair = PODCAST_KOKORO_VOICES.get(niche, PODCAST_KOKORO_VOICES["ai_trading"])
    el_voice_pair = PODCAST_NICHE_ELEVENLABS.get(niche, PODCAST_ELEVENLABS_VOICES)
    edge_voice_pair = PODCAST_EDGE_VOICES.get(niche, PODCAST_EDGE_VOICES["ai_money"])

    # Parse lines from script
    from modules.podcast_generator import parse_podcast_lines
    lines = parse_podcast_lines(script_data)

    if not lines:
        raise ValueError("No dialogue lines found in podcast script")

    # Generate audio for each line — Kokoro → ElevenLabs → edge-tts
    line_audios = []
    kokoro_success = 0
    el_success = 0
    edge_fallback = 0

    for i, line in enumerate(lines):
        character = line["character"]
        text = line["text"]
        line_path = lines_dir / f"line_{i:03d}_{character.lower()}.mp3"

        generated = False

        # ── Tier 1: Kokoro (primary free voice, best quality) ──────────────
        kok_voice, kok_speed = kokoro_voice_pair.get(character, ("af_heart", 1.0))
        result = await generate_voice_kokoro(text, line_path, voice=kok_voice, speed=kok_speed)
        if result:
            line_audios.append({"path": line_path, "line": line, "index": i})
            kokoro_success += 1
            generated = True

        # ── Tier 2: ElevenLabs (premium upgrade when Kokoro fails) ──────────
        if not generated and use_elevenlabs and ELEVENLABS_API_KEY and not _el_quota_exhausted:
            el_voice_id = el_voice_pair.get(character, PODCAST_ELEVENLABS_VOICES.get(character))
            if el_voice_id:
                result = await generate_voice_elevenlabs(text, line_path, voice_id=el_voice_id)
                if result:
                    line_audios.append({"path": line_path, "line": line, "index": i})
                    el_success += 1
                    generated = True

        # ── Tier 3: edge-tts (always-available fallback) ────────────────────
        if not generated:
            import edge_tts
            voice = edge_voice_pair.get(character, edge_voice_pair["SPARKY"])
            emotion_params = line["voice_params"]
            communicate = edge_tts.Communicate(
                text, voice,
                rate=emotion_params.get("rate", "+0%"),
                pitch=emotion_params.get("pitch", "+0Hz"),
            )
            await communicate.save(str(line_path))
            line_audios.append({"path": line_path, "line": line, "index": i})
            edge_fallback += 1

    engine_used = "kokoro" if kokoro_success >= el_success else ("elevenlabs" if el_success > edge_fallback else "edge-tts")
    print(f"[Voice] Podcast: {len(line_audios)} lines "
          f"(Kokoro: {kokoro_success}, ElevenLabs: {el_success}, edge-tts: {edge_fallback})")

    print(f"[Voice] Podcast: Generated {len(line_audios)} dialogue lines")

    # Merge all lines into a single audio track with dynamic pauses
    combined = AudioSegment.silent(duration=300)  # Start with 300ms silence
    line_timings = []
    current_ms = 300

    # Emotions that benefit from a dramatic pre-pause
    HIGH_INTENSITY = {"SHOCKED", "ANGRY", "FIRED UP", "DISBELIEF", "CUTS OFF"}
    SLOW_EMOTIONS = {"WHISPERING", "DEAD SERIOUS", "CALM", "NERVOUS"}

    for i, audio_data in enumerate(line_audios):
        line = audio_data["line"]
        line_audio = AudioSegment.from_mp3(str(audio_data["path"]))

        # ── Dynamic pause calculation ──
        section = line.get("section", "")
        emotion = line.get("emotion", "")
        prev_section = line_audios[i - 1]["line"].get("section", "") if i > 0 else ""
        prev_emotion = line_audios[i - 1]["line"].get("emotion", "") if i > 0 else ""
        prev_word_count = len(line_audios[i - 1]["line"].get("text", "").split()) if i > 0 else 0

        # Base pause
        pause_ms = 250  # Normal conversational gap

        # Section transition — longer pause to signal new segment
        if section != prev_section and i > 0:
            if "TWIST" in section:
                pause_ms = 900  # Extra long before THE TWIST (let it land)
            elif "CLIFFHANGER" in section:
                pause_ms = 700  # Suspenseful pause before cliffhanger
            else:
                pause_ms = 600  # Standard section break

        # Dramatic pre-pause before high-intensity emotions (if coming from calm)
        elif emotion in HIGH_INTENSITY and prev_emotion not in HIGH_INTENSITY:
            pause_ms = 450  # Beat drop — silence before the outburst

        # Slow/dramatic emotions get breathing room
        elif emotion in SLOW_EMOTIONS:
            pause_ms = 500

        # After long previous lines, add extra breathing room
        if prev_word_count > 20:
            pause_ms += 100
        elif prev_word_count > 12:
            pause_ms += 50

        # CUTS OFF emotion means interruption — shorter pause
        if emotion == "CUTS OFF":
            pause_ms = max(100, pause_ms - 200)  # Quick interruption feel

        if i > 0:
            combined += AudioSegment.silent(duration=pause_ms)
            current_ms += pause_ms

        line_start_ms = current_ms
        combined += line_audio
        current_ms += len(line_audio)

        line_timings.append({
            "character": line["character"],
            "emotion": line["emotion"],
            "text": line["text"],
            "section": line.get("section", ""),
            "start": line_start_ms / 1000.0,
            "end": current_ms / 1000.0,
            "index": i,
        })

    # Add 500ms silence at end
    combined += AudioSegment.silent(duration=500)

    # Export combined audio
    final_audio_path = output_dir / "podcast_audio.mp3"
    combined.export(str(final_audio_path), format="mp3", bitrate="192k")

    total_duration = len(combined) / 1000.0
    print(f"[Voice] Podcast audio: {total_duration:.1f}s ({len(line_timings)} lines)")

    # Generate SRT subtitles with character labels
    srt_path = output_dir / "podcast_captions.srt"
    _generate_podcast_srt(line_timings, srt_path)

    # ── Build per-character audio tracks for D-ID lip sync ────
    # Each character gets audio with their lines + silence for the other's parts
    # This way SPARKY only moves lips when SPARKY talks
    char_audio_paths = {}
    try:
        for char_name in ["SPARKY", "NOVA"]:
            char_audio = AudioSegment.silent(duration=300)  # Initial silence
            audio_idx = 0
            for i, audio_data in enumerate(line_audios):
                line = audio_data["line"]

                # Same dynamic pause logic as combined track
                section = line.get("section", "")
                emotion = line.get("emotion", "")
                prev_section = line_audios[i - 1]["line"].get("section", "") if i > 0 else ""
                prev_emotion = line_audios[i - 1]["line"].get("emotion", "") if i > 0 else ""
                prev_word_count = len(line_audios[i - 1]["line"].get("text", "").split()) if i > 0 else 0

                pause_ms = 250
                if section != prev_section and i > 0:
                    if "TWIST" in section:
                        pause_ms = 900
                    elif "CLIFFHANGER" in section:
                        pause_ms = 700
                    else:
                        pause_ms = 600
                elif emotion in HIGH_INTENSITY and prev_emotion not in HIGH_INTENSITY:
                    pause_ms = 450
                elif emotion in SLOW_EMOTIONS:
                    pause_ms = 500
                if prev_word_count > 20:
                    pause_ms += 100
                elif prev_word_count > 12:
                    pause_ms += 50
                if emotion == "CUTS OFF":
                    pause_ms = max(100, pause_ms - 200)

                if i > 0:
                    char_audio += AudioSegment.silent(duration=pause_ms)

                line_audio = AudioSegment.from_mp3(str(audio_data["path"]))

                if line["character"] == char_name:
                    # This character's line — include actual audio
                    char_audio += line_audio
                else:
                    # Other character's line — insert silence (no lip movement)
                    char_audio += AudioSegment.silent(duration=len(line_audio))

            char_audio += AudioSegment.silent(duration=500)  # End silence

            char_audio_path = output_dir / f"{char_name.lower()}_audio.mp3"
            char_audio.export(str(char_audio_path), format="mp3", bitrate="192k")
            char_audio_paths[char_name.lower()] = str(char_audio_path)

        print(f"[Voice] Per-character audio: SPARKY={Path(char_audio_paths.get('sparky','')).stat().st_size//1024}KB, NOVA={Path(char_audio_paths.get('nova','')).stat().st_size//1024}KB")
    except Exception as e:
        print(f"[Voice] Per-character audio failed: {e}")

    # Cleanup individual line files
    for audio_data in line_audios:
        try:
            Path(audio_data["path"]).unlink()
        except Exception:
            pass
    try:
        lines_dir.rmdir()
    except Exception:
        pass

    return {
        "audio_path": str(final_audio_path),
        "subtitle_path": str(srt_path),
        "line_timings": line_timings,
        "duration": total_duration,
        "line_count": len(line_timings),
        "engine": engine_used,
        "character_audio": char_audio_paths,  # Per-character audio for D-ID
    }


def _generate_podcast_srt(line_timings: list[dict], output_path: Path):
    """Generate SRT subtitles for podcast with character labels."""
    from modules.caption_generator import _seconds_to_srt_timestamp

    lines = []
    for i, timing in enumerate(line_timings, 1):
        start = _seconds_to_srt_timestamp(timing["start"])
        end = _seconds_to_srt_timestamp(timing["end"])
        # Split long lines into shorter caption phrases
        text = timing["text"]
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


# CLI test
if __name__ == "__main__":

    async def test():
        result = await generate_voice(
            text="This is a test of the AI video factory voice generation system. "
                 "We are testing both the audio quality and subtitle generation.",
            output_dir=OUTPUT_DIR / "test",
            filename_base="test_voice",
            format_type="short",
            niche="ai_trading",
        )
        print(f"Audio: {result['audio_path']}")
        print(f"Subs: {result['subtitle_path']}")
        print(f"Engine: {result['engine']}")

    asyncio.run(test())
