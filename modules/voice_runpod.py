"""
Voice RunPod — self-hosted serverless TTS (Chatterbox-Turbo / Orpheus 3B).

Drop-in PRIMARY voice engine for chosen niches, called from
`voice_generator.generate_voice()` BEFORE the Kokoro step. On ANY failure or
timeout this module returns None so the caller falls straight through to the
existing Kokoro → edge-tts chain — behaviour is IDENTICAL to today when the
relevant endpoint env var is unset.

Environment variables (all optional — unset = no change to the live pipeline):
  RUNPOD_TTS_ENDPOINT_NEWS  — Chatterbox-Turbo endpoint for news-style niches
                              (tech_news / ai_money / daily_breakdown)
  RUNPOD_TTS_ENDPOINT_KIDS  — Orpheus 3B endpoint for kids niches
                              (kids_songs / blissful_moments)
  RUNPOD_TTS_ENDPOINT       — generic fallback endpoint used when the niche's
                              specific endpoint var is unset
  RUNPOD_API_KEY            — Bearer token for the RunPod serverless API

Endpoint values may be either the bare endpoint URL
(https://api.runpod.ai/v2/<id>) or the endpoint id (<id>); both are normalised.
"""
import asyncio
import base64
import time
from pathlib import Path


# Overall wall-clock budget for a single RunPod TTS call (submit + poll + decode)
_RUNPOD_TIMEOUT_S = 180.0
# How often we poll the /status endpoint while the job runs
_POLL_INTERVAL_S = 2.0


def _normalize_endpoint(endpoint: str) -> str:
    """Accept a full RunPod endpoint URL or a bare endpoint id → base URL."""
    endpoint = (endpoint or "").strip().rstrip("/")
    if not endpoint:
        return ""
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    # Bare endpoint id
    return f"https://api.runpod.ai/v2/{endpoint}"


def _extract_audio_b64(output) -> str | None:
    """Defensively pull base64 audio out of a RunPod worker `output` payload.

    Workers vary in the key they use — accept the common ones and also handle
    the case where `output` is itself the base64 string or a list of chunks.
    """
    if output is None:
        return None
    # Plain string output = the base64 audio itself
    if isinstance(output, str):
        return output or None
    # Some workers return a list (e.g. streamed chunks) — take the first dict/str
    if isinstance(output, list):
        for item in output:
            found = _extract_audio_b64(item)
            if found:
                return found
        return None
    if isinstance(output, dict):
        for key in (
            "audio_base64", "audio_b64", "audio",
            "wav_base64", "wav_b64", "wav",
            "mp3_base64", "mp3", "data", "base64",
        ):
            val = output.get(key)
            if isinstance(val, str) and val:
                return val
        # Nested under an "output" key
        if "output" in output:
            return _extract_audio_b64(output["output"])
    return None


def _looks_like_wav(raw: bytes) -> bool:
    """RIFF/WAVE magic header check so we know whether to transcode → mp3."""
    return len(raw) >= 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WAVE"


def _wav_bytes_to_mp3(raw: bytes, output_mp3: Path) -> bool:
    """Convert in-memory WAV bytes → mp3 file via imageio_ffmpeg.

    Mirrors how the rest of the codebase shells out to the bundled ffmpeg
    (see assemble_full.py / auto_reel.py). Returns True on success.
    """
    try:
        import subprocess
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        tmp_wav = Path(output_mp3).with_suffix(".tmp_runpod.wav")
        try:
            tmp_wav.write_bytes(raw)
            r = subprocess.run(
                [ff, "-y", "-i", str(tmp_wav), "-ar", "44100", "-b:a", "192k", str(output_mp3)],
                capture_output=True,
            )
            return r.returncode == 0 and output_mp3.exists() and output_mp3.stat().st_size > 512
        finally:
            tmp_wav.unlink(missing_ok=True)
    except Exception as e:
        print(f"[Voice] runpod wav→mp3 convert failed: {e}")
        return False


def _srt_ts(seconds: float) -> str:
    """Convert float seconds → SRT timestamp string (HH:MM:SS,mmm)."""
    ms = int(round((seconds % 1) * 1000))
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_proportional_srt(text: str, duration: float, srt_path: Path) -> None:
    """Build a word-level SRT with EVEN word timing across the estimated duration.

    Mirrors the SubMaker-free estimate used for the edge-tts / Kokoro fallback:
    ~2.5 words/sec narration pace.

    TODO: These are approximate, evenly-spaced timings only. Word-ACCURATE
    caption timing comes from the downstream whisper caption step, which
    re-transcribes the rendered audio — this SRT just guarantees captions
    still work if that step is skipped.
    """
    words = text.split()
    if not words:
        srt_path.write_text("", encoding="utf-8")
        return

    per_word = duration / len(words)
    lines = []
    t = 0.0
    for i, word in enumerate(words, 1):
        lines += [
            str(i),
            f"{_srt_ts(t)} --> {_srt_ts(t + per_word)}",
            word,
            "",
        ]
        t += per_word

    srt_path.write_text("\n".join(lines), encoding="utf-8")


def _run_runpod_sync(
    text: str,
    output_audio: Path,
    base_url: str,
    voice: str,
    api_key: str,
    deadline: float,
) -> float | None:
    """Blocking submit → poll → decode → write. Returns audio duration or None.

    Runs inside a thread executor (uses the sync `requests` library like the
    rest of the codebase). Never raises — returns None on any problem.
    """
    try:
        import requests
    except Exception as e:
        print(f"[Voice] runpod: requests unavailable ({e})")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"input": {"text": text, "voice": voice}}

    try:
        submit = requests.post(
            f"{base_url}/run", json=payload, headers=headers,
            timeout=max(5.0, deadline - time.monotonic()),
        )
    except Exception as e:
        print(f"[Voice] runpod submit failed: {e}")
        return None

    if submit.status_code not in (200, 201):
        print(f"[Voice] runpod submit HTTP {submit.status_code}: {submit.text[:200]}")
        return None

    try:
        job = submit.json()
    except Exception as e:
        print(f"[Voice] runpod: bad submit JSON ({e})")
        return None

    job_id = job.get("id")
    status = job.get("status")
    output = job.get("output")

    # Poll /status until the job completes (unless /run already returned output)
    while status not in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT") and output is None:
        if job_id is None:
            print("[Voice] runpod: no job id returned, aborting")
            return None
        if time.monotonic() >= deadline:
            print("[Voice] runpod: polling timed out")
            return None
        time.sleep(_POLL_INTERVAL_S)
        try:
            poll = requests.get(
                f"{base_url}/status/{job_id}", headers=headers,
                timeout=max(5.0, deadline - time.monotonic()),
            )
            job = poll.json()
        except Exception as e:
            print(f"[Voice] runpod poll error: {e}")
            return None
        status = job.get("status")
        output = job.get("output")

    if status == "FAILED" or status in ("CANCELLED", "TIMED_OUT"):
        print(f"[Voice] runpod job {status}: {str(job.get('error'))[:200]}")
        return None

    audio_b64 = _extract_audio_b64(output)
    if not audio_b64:
        print(f"[Voice] runpod: no audio in output (keys={list(output) if isinstance(output, dict) else type(output).__name__})")
        return None

    # Strip a possible data-URI prefix ("data:audio/wav;base64,....")
    if "base64," in audio_b64:
        audio_b64 = audio_b64.split("base64,", 1)[1]

    try:
        raw = base64.b64decode(audio_b64)
    except Exception as e:
        print(f"[Voice] runpod: base64 decode failed ({e})")
        return None

    if not raw or len(raw) < 512:
        print("[Voice] runpod: decoded audio too small")
        return None

    output_audio = Path(output_audio)
    if _looks_like_wav(raw):
        if not _wav_bytes_to_mp3(raw, output_audio):
            return None
    else:
        # Already compressed (mp3/other) — write straight through
        output_audio.write_bytes(raw)

    if not output_audio.exists() or output_audio.stat().st_size < 512:
        print("[Voice] runpod: written audio file invalid")
        return None

    # Best-effort exact duration; fall back to word-count estimate
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_file(str(output_audio))
        return len(seg) / 1000.0
    except Exception:
        return len(text.split()) / 2.5


async def generate_voice_runpod(
    text: str,
    output_audio: Path,
    output_subs: Path | None,
    endpoint: str,
    voice: str,
    api_key: str,
) -> dict | None:
    """
    Generate a voiceover via a self-hosted RunPod serverless TTS endpoint.

    POSTs {input: {text, voice}} to `{endpoint}/run`, polls `{endpoint}/status/{id}`
    with a Bearer token, decodes the returned base64 audio, writes mp3, and emits
    a proportional .srt so captions still work.

    Returns the standard voice dict on success:
        {audio_path, subtitle_path, duration_estimate, word_count, engine, voice}
    Returns None on ANY failure or timeout (caller falls through to Kokoro).
    Never raises.
    """
    try:
        base_url = _normalize_endpoint(endpoint)
        if not base_url or not api_key:
            return None

        output_audio = Path(output_audio)
        output_audio.parent.mkdir(parents=True, exist_ok=True)
        subtitle_path = Path(output_subs) if output_subs else output_audio.with_suffix(".srt")

        word_count = len(text.split())
        print(f"[Voice] runpod: submitting {word_count} words → {voice} @ {base_url}")

        loop = asyncio.get_event_loop()
        deadline = time.monotonic() + _RUNPOD_TIMEOUT_S
        duration = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                _run_runpod_sync,
                text,
                output_audio,
                base_url,
                voice,
                api_key,
                deadline,
            ),
            timeout=_RUNPOD_TIMEOUT_S,
        )

        if duration is None:
            return None

        _write_proportional_srt(text, duration, subtitle_path)

        print(f"[Voice] runpod ({voice}): {output_audio.name} "
              f"({word_count} words, {duration:.1f}s)")

        return {
            "audio_path": str(output_audio),
            "subtitle_path": str(subtitle_path),
            "duration_estimate": duration,
            "word_count": word_count,
            "engine": f"runpod:{voice}",
            "voice": voice,
        }

    except asyncio.TimeoutError:
        print(f"[Voice] runpod TIMEOUT ({_RUNPOD_TIMEOUT_S:.0f}s) — falling through to Kokoro")
        return None
    except Exception as e:
        print(f"[Voice] runpod failed: {e}")
        return None
