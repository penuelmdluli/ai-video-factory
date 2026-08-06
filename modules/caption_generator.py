"""
Caption Generator — Creates SRT/VTT subtitle files from audio.

Primary: Uses edge-tts built-in timestamps (already generated in voice module)
Fallback: Uses faster-whisper for transcription when edge-tts subs unavailable
"""
import re
from pathlib import Path

try:
    from config import CAPTION_MAX_WORDS
except Exception:
    CAPTION_MAX_WORDS = 3


def parse_subtitle_to_segments(sub_path: str | Path) -> list[dict]:
    """
    Parse a VTT or SRT subtitle file into segments.

    Returns:
        List of {start, end, text} dicts with times in seconds
    """
    sub_path = Path(sub_path)
    if not sub_path.exists():
        return []

    content = sub_path.read_text(encoding="utf-8")
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    segments = []

    # Match both VTT (00:00:01.500) and SRT (00:00:01,500) time formats
    pattern = r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*\n(.+?)(?=\n\n|\n\d+\n|\Z)"
    matches = re.findall(pattern, content, re.DOTALL)

    for start_str, end_str, text in matches:
        start = _timestamp_to_seconds(start_str.replace(",", "."))
        end = _timestamp_to_seconds(end_str.replace(",", "."))
        clean_text = text.strip().replace("\n", " ")
        if clean_text:
            segments.append({"start": start, "end": end, "text": clean_text})

    return segments


# Keep backward-compat alias
parse_vtt_to_segments = parse_subtitle_to_segments


def _timestamp_to_seconds(ts: str) -> float:
    """Convert HH:MM:SS.mmm to seconds."""
    parts = ts.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    sec_parts = parts[2].split(".")
    seconds = int(sec_parts[0])
    millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def translate_srt(srt_path: str | Path, lang_code: str, lang_name: str) -> str | None:
    """
    Translate an English SRT into `lang_name`, keeping timestamps.
    Returns the translated SRT path (e.g. captions.ar.srt) or None.
    Used to attach multi-language caption tracks for international reach.
    """
    import os
    segs = parse_subtitle_to_segments(srt_path)
    if not segs:
        return None
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    # Batch: numbered lines in, numbered lines out — preserves alignment.
    numbered = "\n".join(f"{i+1}. {s['text']}" for i, s in enumerate(segs))
    prompt = (
        f"Translate each numbered caption line into {lang_name}. This is neutral "
        f"war/news content. Keep it concise for on-screen subtitles, keep the SAME "
        f"numbering, one line each, translation only (no notes, no transliteration).\n\n{numbered}"
    )
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        out = msg.content[0].text.strip()
    except Exception as e:
        print(f"[Captions] Translate to {lang_name} failed: {e}")
        return None

    # Parse "N. text" back into order
    import re as _re
    trans = {}
    for line in out.splitlines():
        m = _re.match(r"\s*(\d+)[.)]\s*(.+)", line)
        if m:
            trans[int(m.group(1))] = m.group(2).strip()
    if not trans:
        return None
    for i, s in enumerate(segs):
        s["text"] = trans.get(i + 1, s["text"])

    out_path = Path(srt_path).with_suffix(f".{lang_code}.srt")
    segments_to_srt(segs, out_path)
    print(f"[Captions] Translated captions -> {out_path.name} ({lang_name})")
    return str(out_path)


def segments_to_srt(segments: list[dict], output_path: str | Path) -> str:
    """Convert segments to SRT subtitle file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for i, seg in enumerate(segments, 1):
        start = _seconds_to_srt_timestamp(seg["start"])
        end = _seconds_to_srt_timestamp(seg["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def group_words_into_phrases(
    segments: list[dict],
    max_words: int = CAPTION_MAX_WORDS,
    min_words: int = 2,
    max_duration: float = 3.0,
) -> list[dict]:
    """
    Group word-level segments into readable phrases for on-screen captions.

    edge-tts/Kokoro often output word-by-word. This groups them into
    phrases of 2-4 words for punchy, readable on-screen captions.

    Rules:
    - Each phrase has min_words to max_words words
    - Natural break points: punctuation triggers a phrase boundary
    - No orphan single-word captions (merged with neighbors)
    """
    if not segments:
        return []

    phrases = []
    current_words = []
    current_start = segments[0]["start"]

    # Punctuation that signals a natural break point
    break_chars = {".", "!", "?", "...", ",", ";", ":"}

    for i, seg in enumerate(segments):
        current_words.append(seg["text"])

        duration = seg["end"] - current_start
        word_count = len(current_words)

        # Check for natural break (punctuation at end of word)
        has_break = any(seg["text"].rstrip().endswith(c) for c in break_chars)

        # Create phrase if: hit max words, OR natural break with enough words, OR max duration
        should_break = (
            word_count >= max_words
            or (has_break and word_count >= min_words)
            or (duration >= max_duration and word_count >= min_words)
        )

        if should_break:
            phrases.append({
                "start": current_start,
                "end": seg["end"],
                "text": " ".join(current_words),
            })
            current_words = []
            # Next phrase starts at this word's end
            if i + 1 < len(segments):
                current_start = segments[i + 1]["start"]

    # Handle remaining words
    if current_words:
        if len(current_words) < min_words and phrases:
            # Merge orphan words into last phrase instead of creating tiny caption
            last = phrases[-1]
            last["end"] = segments[-1]["end"]
            last["text"] += " " + " ".join(current_words)
        else:
            phrases.append({
                "start": current_start,
                "end": segments[-1]["end"],
                "text": " ".join(current_words),
            })

    return phrases


def split_sentences_into_phrases(
    segments: list[dict],
    max_words: int = 6,
    min_words: int = 2,
    min_duration: float = 0.5,
) -> list[dict]:
    """
    Split sentence-level segments into shorter caption phrases.

    When edge-tts provides sentence boundaries instead of word boundaries,
    this splits each sentence into display-friendly chunks of max_words words,
    distributing timing evenly across the chunks.

    Avoids orphan single-word phrases by merging them with the previous chunk.
    Enforces minimum display duration for readability.
    """
    phrases = []
    for seg in segments:
        words = seg["text"].split()
        if len(words) <= max_words:
            # Enforce minimum duration even for short segments
            duration = seg["end"] - seg["start"]
            if duration < min_duration:
                seg = {**seg, "end": round(seg["start"] + min_duration, 3)}
            phrases.append(seg)
            continue

        # Split into chunks of max_words
        total_duration = seg["end"] - seg["start"]
        total_words = len(words)
        time_per_word = total_duration / total_words if total_words else 0

        pos = 0
        seg_phrases = []
        while pos < total_words:
            remaining = total_words - pos
            chunk_size = min(max_words, remaining)
            chunk_words = words[pos:pos + chunk_size]
            chunk_start = seg["start"] + pos * time_per_word
            chunk_end = seg["start"] + (pos + chunk_size) * time_per_word
            if pos + chunk_size >= total_words:
                chunk_end = seg["end"]
            seg_phrases.append({
                "start": round(chunk_start, 3),
                "end": round(chunk_end, 3),
                "text": " ".join(chunk_words),
            })
            pos += chunk_size

        # Fix orphan single-word last phrase: borrow a word from previous chunk
        if len(seg_phrases) > 1 and len(seg_phrases[-1]["text"].split()) < min_words:
            last = seg_phrases[-1]
            prev = seg_phrases[-2]
            prev_words = prev["text"].split()
            last_words = last["text"].split()
            # Move last word from previous chunk to the final chunk
            borrowed = prev_words.pop()
            last_words.insert(0, borrowed)
            prev["text"] = " ".join(prev_words)
            last["text"] = " ".join(last_words)
            # Adjust timing: shift boundary by one word
            boundary = prev["start"] + len(prev_words) * time_per_word
            prev["end"] = round(boundary, 3)
            last["start"] = round(boundary, 3)

        # Enforce minimum duration on each phrase
        for p in seg_phrases:
            if p["end"] - p["start"] < min_duration:
                p["end"] = round(p["start"] + min_duration, 3)

        phrases.extend(seg_phrases)

    return phrases


async def generate_captions_whisper(
    audio_path: str | Path,
    output_path: str | Path,
    model_size: str = "base",
) -> list[dict]:
    """
    Generate captions using faster-whisper (fallback when VTT not available).

    Returns: list of segments {start, end, text}
    """
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, compute_type="int8")
        segments_iter, info = model.transcribe(
            str(audio_path),
            word_timestamps=True,
        )

        segments = []
        for segment in segments_iter:
            for word in segment.words:
                segments.append({
                    "start": word.start,
                    "end": word.end,
                    "text": word.word.strip(),
                })

        # Group into phrases
        phrases = group_words_into_phrases(segments)

        # Save as SRT
        segments_to_srt(phrases, output_path)
        print(f"[Captions] Whisper generated {len(phrases)} caption phrases")

        return phrases

    except Exception as e:
        print(f"[Captions] Whisper failed: {e}")
        return []


async def generate_captions(
    audio_path: str | Path,
    vtt_path: str | Path | None,
    output_dir: Path,
    filename_base: str = "captions",
) -> dict:
    """
    Generate captions from audio, using VTT if available, Whisper as fallback.

    Returns:
        dict with srt_path, segments, phrase_count
    """
    output_dir = Path(output_dir)
    srt_path = output_dir / f"{filename_base}.srt"

    # Try using existing subtitle file from edge-tts (SRT or VTT)
    if vtt_path and Path(vtt_path).exists():
        segments = parse_subtitle_to_segments(vtt_path)
        if segments:
            # Detect if segments are word-level (avg ~1 word) or sentence-level
            avg_words = sum(len(s["text"].split()) for s in segments) / len(segments)
            if avg_words <= 1.5:
                # Word-level (Kokoro/edge-tts word timestamps) — group into phrases
                phrases = group_words_into_phrases(segments, min_words=2)
            else:
                # Sentence-level — split into shorter caption phrases
                phrases = split_sentences_into_phrases(segments, max_words=CAPTION_MAX_WORDS)
            srt_file = segments_to_srt(phrases, srt_path)
            print(f"[Captions] Parsed subtitles -> SRT: {len(phrases)} phrases")
            return {
                "srt_path": srt_file,
                "segments": phrases,
                "phrase_count": len(phrases),
                "source": "edge-tts",
            }

    # Fallback to Whisper
    phrases = await generate_captions_whisper(audio_path, srt_path)
    return {
        "srt_path": str(srt_path) if phrases else None,
        "segments": phrases,
        "phrase_count": len(phrases),
        "source": "whisper",
    }


# CLI test
if __name__ == "__main__":
    import asyncio
    from config import OUTPUT_DIR

    async def test():
        # Test VTT parsing
        test_vtt = OUTPUT_DIR / "test" / "test.vtt"
        if test_vtt.exists():
            segments = parse_vtt_to_segments(test_vtt)
            phrases = group_words_into_phrases(segments)
            print(f"Parsed {len(segments)} words -> {len(phrases)} phrases")
            for p in phrases[:5]:
                print(f"  [{p['start']:.1f}-{p['end']:.1f}] {p['text']}")

    asyncio.run(test())
