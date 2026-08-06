"""
Baby Podcast AI Avatar Pipeline — Full Automation Script

Produces lip-synced talking baby avatar videos using a 3-stage pipeline:
  Stage 1: SadTalker  — image + audio -> animated talking head video
  Stage 2: MuseTalk   — refine lip sync on SadTalker output
  Stage 3: GFPGAN     — face restoration / sharpening

Supports:
  - Single audio file or batch folder processing
  - Text -> ElevenLabs TTS -> pipeline
  - Multiple pipeline tiers (sadtalker+musetalk, sadtalker-only, wav2lip, audio-reactive)
  - Automatic vertical 9:16 (1080x1920) export for YouTube Shorts / TikTok

Usage:
  # Single audio + image
  python baby_podcast_generator.py --audio voice.wav --image baby.png

  # Batch: folder of WAV files
  python baby_podcast_generator.py --audio-dir wavs/ --image baby.png

  # Text -> ElevenLabs -> pipeline
  python baby_podcast_generator.py --text "Hello world" --image baby.png --voice elevenlabs

  # Choose pipeline tier
  python baby_podcast_generator.py --audio voice.wav --image baby.png --tier sadtalker+musetalk
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
MODELS_DIR = ASSETS_DIR / "models"
OUTPUT_DIR = ROOT_DIR / "output" / "baby_podcast"

# External tool paths (set these to your actual install locations)
SADTALKER_DIR = Path(os.getenv("SADTALKER_DIR", r"C:\Users\PenuelM\Documents\SadTalker"))
MUSETALK_DIR = Path(os.getenv("MUSETALK_DIR", r"C:\Users\PenuelM\Documents\MuseTalk"))
GFPGAN_MODEL = MODELS_DIR / "GFPGANv1.4.pth"

# Conda environment names
SADTALKER_ENV = os.getenv("SADTALKER_ENV", "sadtalker")
MUSETALK_ENV = os.getenv("MUSETALK_ENV", "musetalk")

# FFmpeg path
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

# ElevenLabs config (from .env)
from dotenv import load_dotenv
load_dotenv(override=True)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "") or os.getenv("ELEVEN_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "") or os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel

# RTX 2080 Ti optimized defaults
SADTALKER_PREPROCESS = "full"       # full quality, fits 11GB
SADTALKER_EXPRESSION_SCALE = 1.2    # slight exaggeration for baby
MUSETALK_BATCH_SIZE = 4             # 11GB handles this
MUSETALK_BBOX_SHIFT = 8            # higher for cartoon baby faces
GFPGAN_UPSCALE = 1                  # restore only, no upscale
FFMPEG_CRF = 18                     # high quality
FFMPEG_PRESET = "slow"              # better compression

# Output resolution (9:16 vertical)
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920


def log(msg: str, level: str = "INFO"):
    """Print timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "[*]", "OK": "[+]", "ERR": "[!]", "WARN": "[~]"}.get(level, "[*]")
    print(f"  {ts} {prefix} {msg}")


def run_conda_command(env_name: str, cmd: str, cwd: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a command inside a conda environment via subprocess."""
    # On Windows, use conda run
    full_cmd = f'conda run -n {env_name} --no-banner {cmd}'
    log(f"Running in '{env_name}': {cmd[:100]}...")

    result = subprocess.run(
        full_cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        log(f"Command failed (exit {result.returncode})", "ERR")
        if result.stderr:
            # Print last 20 lines of stderr
            lines = result.stderr.strip().split('\n')
            for line in lines[-20:]:
                log(f"  {line}", "ERR")

    return result


def check_conda_env(env_name: str) -> bool:
    """Check if a conda environment exists."""
    result = subprocess.run(
        f"conda env list",
        shell=True,
        capture_output=True,
        text=True,
    )
    return env_name in result.stdout


def generate_elevenlabs_audio(text: str, output_path: Path, voice_id: str = None) -> Path:
    """Generate audio from text using ElevenLabs API.

    Returns path to the generated WAV file.
    """
    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY not set in .env file")

    import requests

    voice_id = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.3,
            "use_speaker_boost": True,
        },
    }

    log(f"Calling ElevenLabs API (voice: {voice_id})...")
    response = requests.post(url, json=data, headers=headers, timeout=60)
    if response.status_code == 401:
        error_detail = response.json().get("detail", {})
        msg = error_detail.get("message", str(error_detail)) if isinstance(error_detail, dict) else str(error_detail)
        raise ValueError(f"ElevenLabs auth failed: {msg}")
    response.raise_for_status()

    # Save as MP3 first
    mp3_path = output_path.with_suffix(".mp3")
    mp3_path.write_bytes(response.content)
    log(f"ElevenLabs MP3: {mp3_path} ({len(response.content) / 1024:.0f} KB)")

    # Convert MP3 -> WAV (required by SadTalker/MuseTalk)
    wav_path = output_path.with_suffix(".wav")
    subprocess.run(
        [FFMPEG_PATH, "-y", "-i", str(mp3_path), "-ar", "16000", "-ac", "1", str(wav_path)],
        capture_output=True,
        check=True,
    )
    mp3_path.unlink(missing_ok=True)
    log(f"Converted to WAV: {wav_path}", "OK")

    return wav_path


def generate_kokoro_audio(text: str, output_path: Path) -> Path:
    """Generate audio using Kokoro TTS (free, local).

    Falls back to edge-tts if Kokoro not available.
    """
    wav_path = output_path.with_suffix(".wav")

    try:
        from kokoro import KPipeline
        log("Using Kokoro TTS (free, local)...")
        pipeline = KPipeline(lang_code="a")
        generator = pipeline(text, voice="af_heart", speed=1.0)

        import soundfile as sf
        import numpy as np

        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)

        full_audio = np.concatenate(audio_chunks)
        sf.write(str(wav_path), full_audio, 24000)
        log(f"Kokoro WAV: {wav_path}", "OK")
        return wav_path

    except ImportError:
        log("Kokoro not available, falling back to edge-tts...", "WARN")
        return generate_edge_tts_audio(text, output_path)


def generate_edge_tts_audio(text: str, output_path: Path) -> Path:
    """Generate audio using edge-tts (free, no API key needed)."""
    import asyncio
    import edge_tts

    wav_path = output_path.with_suffix(".wav")
    mp3_path = output_path.with_suffix(".mp3")

    async def _generate():
        communicate = edge_tts.Communicate(text, "en-US-GuyNeural", rate="+5%")
        await communicate.save(str(mp3_path))

    log("Using edge-tts (free)...")
    asyncio.run(_generate())

    # Convert to WAV
    subprocess.run(
        [FFMPEG_PATH, "-y", "-i", str(mp3_path), "-ar", "16000", "-ac", "1", str(wav_path)],
        capture_output=True,
        check=True,
    )
    mp3_path.unlink(missing_ok=True)
    log(f"edge-tts WAV: {wav_path}", "OK")
    return wav_path


# ── Stage 1: SadTalker ──────────────────────────────────────────

def run_sadtalker(audio_path: Path, image_path: Path, output_dir: Path) -> Path:
    """Run SadTalker to create animated talking head from image + audio.

    Returns path to the generated video file.
    """
    log("=" * 50)
    log("STAGE 1: SadTalker — Image Animation")
    log("=" * 50)

    if not SADTALKER_DIR.exists():
        raise FileNotFoundError(
            f"SadTalker not found at {SADTALKER_DIR}\n"
            f"Clone it: git clone https://github.com/OpenTalker/SadTalker {SADTALKER_DIR}"
        )

    if not check_conda_env(SADTALKER_ENV):
        raise EnvironmentError(
            f"Conda env '{SADTALKER_ENV}' not found.\n"
            f"Create it: conda create -n {SADTALKER_ENV} python=3.10"
        )

    result_dir = output_dir / "sadtalker_output"
    result_dir.mkdir(parents=True, exist_ok=True)

    cmd = (
        f'python inference.py '
        f'--driven_audio "{audio_path}" '
        f'--source_image "{image_path}" '
        f'--enhancer gfpgan '
        f'--preprocess {SADTALKER_PREPROCESS} '
        f'--still '
        f'--expression_scale {SADTALKER_EXPRESSION_SCALE} '
        f'--result_dir "{result_dir}" '
        f'--size 512'
    )

    start = time.time()
    result = run_conda_command(SADTALKER_ENV, cmd, str(SADTALKER_DIR), timeout=600)
    elapsed = time.time() - start

    if result.returncode != 0:
        raise RuntimeError(f"SadTalker failed (exit {result.returncode}). Check logs above.")

    # Find the output video (SadTalker saves with timestamp)
    videos = sorted(result_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not videos:
        raise FileNotFoundError(f"SadTalker produced no output video in {result_dir}")

    output_video = videos[0]
    log(f"SadTalker output: {output_video} ({elapsed:.1f}s)", "OK")
    return output_video


# ── Stage 2: MuseTalk ────────────────────────────────────────────

def run_musetalk(video_path: Path, audio_path: Path, output_dir: Path) -> Path:
    """Run MuseTalk to refine lip sync on SadTalker output.

    Returns path to the refined video.
    """
    log("=" * 50)
    log("STAGE 2: MuseTalk — Lip Sync Refinement")
    log("=" * 50)

    if not MUSETALK_DIR.exists():
        raise FileNotFoundError(
            f"MuseTalk not found at {MUSETALK_DIR}\n"
            f"Clone it: git clone https://github.com/TMElyralab/MuseTalk {MUSETALK_DIR}"
        )

    if not check_conda_env(MUSETALK_ENV):
        raise EnvironmentError(
            f"Conda env '{MUSETALK_ENV}' not found.\n"
            f"Create it: conda create -n {MUSETALK_ENV} python=3.10"
        )

    result_dir = output_dir / "musetalk_output"
    result_dir.mkdir(parents=True, exist_ok=True)

    output_video = result_dir / "result.mp4"

    cmd = (
        f'python -m scripts.inference '
        f'--video_path "{video_path}" '
        f'--audio_path "{audio_path}" '
        f'--bbox_shift {MUSETALK_BBOX_SHIFT} '
        f'--batch_size {MUSETALK_BATCH_SIZE} '
        f'--result_dir "{result_dir}" '
        f'--use_float16'
    )

    start = time.time()
    result = run_conda_command(MUSETALK_ENV, cmd, str(MUSETALK_DIR), timeout=900)
    elapsed = time.time() - start

    if result.returncode != 0:
        log("MuseTalk failed — using SadTalker output directly", "WARN")
        return video_path

    # Find output
    videos = sorted(result_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not videos:
        log("MuseTalk produced no output — using SadTalker output", "WARN")
        return video_path

    output_video = videos[0]
    log(f"MuseTalk output: {output_video} ({elapsed:.1f}s)", "OK")
    return output_video


# ── Stage 3: GFPGAN Face Restoration ────────────────────────────

def run_gfpgan(video_path: Path, output_dir: Path) -> Path:
    """Apply GFPGAN face restoration to every frame of the video.

    Returns path to the restored video.
    """
    log("=" * 50)
    log("STAGE 3: GFPGAN — Face Restoration")
    log("=" * 50)

    if not GFPGAN_MODEL.exists():
        raise FileNotFoundError(f"GFPGAN model not found: {GFPGAN_MODEL}")

    import cv2
    import numpy as np

    try:
        from gfpgan import GFPGANer
    except ImportError:
        log("GFPGAN not installed — skipping face restoration", "WARN")
        return video_path

    start = time.time()

    # Initialize restorer
    restorer = GFPGANer(
        model_path=str(GFPGAN_MODEL),
        upscale=GFPGAN_UPSCALE,
        arch='clean',
        channel_multiplier=2,
        bg_upsampler=None,  # no background upsampling (faster)
    )

    # Open input video
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    log(f"Input: {w}x{h} @ {fps:.1f}fps, {total_frames} frames")

    # Write restored frames as raw images, then encode with FFmpeg (more reliable than cv2.VideoWriter)
    import tempfile
    frames_dir = Path(tempfile.mkdtemp(prefix="gfpgan_frames_"))

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply GFPGAN
        try:
            _, _, restored = restorer.enhance(
                frame,
                has_aligned=False,
                only_center_face=True,
                paste_back=True,
            )
            cv2.imwrite(str(frames_dir / f"frame_{frame_count:06d}.png"), restored)
        except Exception:
            # If GFPGAN fails on a frame, use original
            cv2.imwrite(str(frames_dir / f"frame_{frame_count:06d}.png"), frame)

        frame_count += 1
        if frame_count % 50 == 0:
            log(f"  Restored {frame_count}/{total_frames} frames...")

    cap.release()

    if frame_count == 0:
        log("GFPGAN: No frames processed, returning original", "WARN")
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)
        return video_path

    # Encode frames + mux audio with FFmpeg (much more reliable than cv2.VideoWriter)
    final_video = output_dir / "gfpgan_restored.mp4"
    subprocess.run(
        [
            FFMPEG_PATH, "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%06d.png"),
            "-i", str(video_path),
            "-c:v", "libx264", "-crf", str(FFMPEG_CRF), "-preset", FFMPEG_PRESET,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest",
            str(final_video),
        ],
        capture_output=True,
        check=True,
    )

    # Cleanup temp frames
    import shutil
    shutil.rmtree(frames_dir, ignore_errors=True)
    elapsed = time.time() - start
    log(f"GFPGAN restored: {final_video} ({elapsed:.1f}s, {frame_count} frames)", "OK")
    return final_video


# ── Final Export ─────────────────────────────────────────────────

def export_vertical(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """Export final video in 9:16 vertical format (1080x1920) for Shorts/TikTok.

    Centers the talking head in the frame with padding/scaling.
    """
    log("=" * 50)
    log("FINAL: Export 9:16 Vertical (1080x1920)")
    log("=" * 50)

    # Scale and pad to 1080x1920 vertical
    # The talking head is likely square-ish, so we center it vertically
    filter_str = (
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"
    )

    cmd = [
        FFMPEG_PATH, "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-vf", filter_str,
        "-c:v", "libx264", "-crf", str(FFMPEG_CRF), "-preset", FFMPEG_PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",  # YouTube optimization
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"FFmpeg export failed: {result.stderr[-500:]}", "ERR")
        # Fall back: just copy the video as-is
        shutil.copy2(video_path, output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    log(f"Final video: {output_path} ({size_mb:.1f} MB)", "OK")
    return output_path


# ── Fallback: Existing Wav2Lip Pipeline ──────────────────────────

def run_wav2lip_fallback(audio_path: Path, image_path: Path, output_dir: Path) -> Path:
    """Use existing Wav2Lip pipeline from local_avatar.py as fallback."""
    log("=" * 50)
    log("FALLBACK: Wav2Lip (existing local_avatar.py)")
    log("=" * 50)

    sys.path.insert(0, str(ROOT_DIR))
    from modules.local_avatar import generate_local_avatar

    import asyncio

    output_path = output_dir / "wav2lip_output.mp4"

    start = time.time()
    result_path = asyncio.run(generate_local_avatar(
        image_path=str(image_path),
        audio_path=str(audio_path),
        output_path=str(output_path),
    ))
    elapsed = time.time() - start

    log(f"Wav2Lip output: {result_path} ({elapsed:.1f}s)", "OK")
    return Path(result_path)


def run_audio_reactive_fallback(audio_path: Path, image_path: Path, output_dir: Path,
                                 line_timings: list = None) -> Path:
    """Use audio-reactive compositor from local_avatar.py."""
    log("=" * 50)
    log("FALLBACK: Audio-Reactive Compositor")
    log("=" * 50)

    sys.path.insert(0, str(ROOT_DIR))
    from modules.local_avatar import generate_audio_reactive_avatar

    import asyncio

    output_path = output_dir / "audio_reactive_output.mp4"

    start = time.time()
    result_path = asyncio.run(generate_audio_reactive_avatar(
        image_path=str(image_path),
        audio_path=str(audio_path),
        output_path=str(output_path),
        line_timings=line_timings,
    ))
    elapsed = time.time() - start

    log(f"Audio-reactive output: {result_path} ({elapsed:.1f}s)", "OK")
    return Path(result_path)


# ── Main Pipeline ────────────────────────────────────────────────

def process_single(
    audio_path: Path,
    image_path: Path,
    output_dir: Path,
    tier: str = "sadtalker+musetalk",
    skip_gfpgan: bool = False,
) -> Path:
    """Process a single audio+image pair through the full pipeline.

    Tiers:
      - sadtalker+musetalk: SadTalker -> MuseTalk -> GFPGAN (best quality)
      - sadtalker: SadTalker -> GFPGAN (faster, still good)
      - wav2lip: Existing Wav2Lip pipeline (GPU, fast)
      - audio-reactive: CPU-based cartoon animation (always works)

    Returns path to the final exported video.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = audio_path.stem
    job_dir = output_dir / f"{stem}_{timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)

    log(f"\n{'#' * 60}")
    log(f"Processing: {audio_path.name}")
    log(f"Character:  {image_path.name}")
    log(f"Tier:       {tier}")
    log(f"Output:     {job_dir}")
    log(f"{'#' * 60}\n")

    video_path = None

    try:
        if tier in ("sadtalker+musetalk", "sadtalker"):
            # Stage 1: SadTalker
            video_path = run_sadtalker(audio_path, image_path, job_dir)

            # Stage 2: MuseTalk (optional)
            if tier == "sadtalker+musetalk":
                video_path = run_musetalk(video_path, audio_path, job_dir)

        elif tier == "wav2lip":
            video_path = run_wav2lip_fallback(audio_path, image_path, job_dir)

        elif tier == "audio-reactive":
            video_path = run_audio_reactive_fallback(audio_path, image_path, job_dir)

        else:
            raise ValueError(f"Unknown tier: {tier}. Use: sadtalker+musetalk, sadtalker, wav2lip, audio-reactive")

        # Stage 3: GFPGAN (skip for audio-reactive, it draws its own faces)
        if not skip_gfpgan and tier != "audio-reactive":
            video_path = run_gfpgan(video_path, job_dir)

        # Final export: 9:16 vertical
        final_path = job_dir / f"FINAL_{stem}_{timestamp}.mp4"
        final_path = export_vertical(video_path, audio_path, final_path)

        log(f"\n{'=' * 60}")
        log(f"COMPLETE: {final_path}", "OK")
        log(f"{'=' * 60}\n")

        return final_path

    except Exception as e:
        log(f"Pipeline error: {e}", "ERR")

        # Fallback chain: try wav2lip, then audio-reactive
        if tier not in ("wav2lip", "audio-reactive"):
            log("Attempting fallback to Wav2Lip...", "WARN")
            try:
                video_path = run_wav2lip_fallback(audio_path, image_path, job_dir)
                final_path = job_dir / f"FINAL_{stem}_{timestamp}_fallback.mp4"
                return export_vertical(video_path, audio_path, final_path)
            except Exception as e2:
                log(f"Wav2Lip fallback failed: {e2}", "ERR")
                log("Attempting audio-reactive fallback...", "WARN")
                try:
                    video_path = run_audio_reactive_fallback(audio_path, image_path, job_dir)
                    final_path = job_dir / f"FINAL_{stem}_{timestamp}_audioreactive.mp4"
                    return export_vertical(video_path, audio_path, final_path)
                except Exception as e3:
                    log(f"All fallbacks failed: {e3}", "ERR")
                    raise
        raise


def process_batch(
    audio_dir: Path,
    image_path: Path,
    output_dir: Path,
    tier: str = "sadtalker+musetalk",
) -> list:
    """Process all WAV files in a directory sequentially.

    Returns list of (audio_file, output_path, success) tuples.
    """
    wav_files = sorted(audio_dir.glob("*.wav"))
    if not wav_files:
        # Also check for MP3 files and convert them
        mp3_files = sorted(audio_dir.glob("*.mp3"))
        if mp3_files:
            log(f"Found {len(mp3_files)} MP3 files — converting to WAV...")
            for mp3 in mp3_files:
                wav = mp3.with_suffix(".wav")
                subprocess.run(
                    [FFMPEG_PATH, "-y", "-i", str(mp3), "-ar", "16000", "-ac", "1", str(wav)],
                    capture_output=True,
                    check=True,
                )
            wav_files = sorted(audio_dir.glob("*.wav"))

    if not wav_files:
        log("No WAV or MP3 files found in directory!", "ERR")
        return []

    log(f"\n{'#' * 60}")
    log(f"BATCH: {len(wav_files)} audio files")
    log(f"Character: {image_path.name}")
    log(f"Tier: {tier}")
    log(f"{'#' * 60}\n")

    results = []
    for i, wav_file in enumerate(wav_files, 1):
        log(f"\n--- Batch [{i}/{len(wav_files)}] ---")
        try:
            output = process_single(wav_file, image_path, output_dir, tier)
            results.append((wav_file.name, str(output), True))
        except Exception as e:
            log(f"Failed: {wav_file.name} — {e}", "ERR")
            results.append((wav_file.name, str(e), False))

        # Brief pause between jobs to let GPU cool
        if i < len(wav_files):
            log("Cooling pause (5s)...")
            time.sleep(5)

    # Print summary
    log(f"\n{'=' * 60}")
    log("BATCH SUMMARY")
    log(f"{'=' * 60}")
    success = sum(1 for _, _, ok in results if ok)
    log(f"Total: {len(results)} | Success: {success} | Failed: {len(results) - success}")
    for name, path_or_err, ok in results:
        status = "OK" if ok else "FAIL"
        log(f"  [{status}] {name} -> {path_or_err}")

    return results


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Baby Podcast AI Avatar Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single audio file
  python baby_podcast_generator.py --audio voice.wav --image baby.png

  # Batch folder
  python baby_podcast_generator.py --audio-dir wavs/ --image baby.png

  # Text -> speech -> video
  python baby_podcast_generator.py --text "Hello world" --image baby.png

  # Use specific tier
  python baby_podcast_generator.py --audio voice.wav --image baby.png --tier wav2lip
        """,
    )

    # Input sources (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--audio", type=Path, help="Path to a single audio file (.wav or .mp3)")
    input_group.add_argument("--audio-dir", type=Path, help="Path to folder of audio files for batch processing")
    input_group.add_argument("--text", type=str, help="Text to convert to speech first (uses TTS)")

    # Required
    parser.add_argument("--image", type=Path, required=True, help="Path to character image (.png)")

    # Options
    parser.add_argument(
        "--tier",
        choices=["sadtalker+musetalk", "sadtalker", "wav2lip", "audio-reactive"],
        default="sadtalker+musetalk",
        help="Pipeline tier (default: sadtalker+musetalk)",
    )
    parser.add_argument(
        "--voice",
        choices=["elevenlabs", "kokoro", "edge-tts"],
        default="kokoro",
        help="TTS engine for --text mode (default: kokoro)",
    )
    parser.add_argument("--voice-id", type=str, help="ElevenLabs voice ID override")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--skip-gfpgan", action="store_true", help="Skip GFPGAN face restoration")
    parser.add_argument(
        "--bbox-shift", type=int, default=MUSETALK_BBOX_SHIFT,
        help=f"MuseTalk bbox_shift (default: {MUSETALK_BBOX_SHIFT}, higher for cartoon faces)",
    )
    parser.add_argument(
        "--expression-scale", type=float, default=SADTALKER_EXPRESSION_SCALE,
        help=f"SadTalker expression scale (default: {SADTALKER_EXPRESSION_SCALE})",
    )

    args = parser.parse_args()

    # Validate image exists
    if not args.image.exists():
        print(f"Error: Image not found: {args.image}")
        sys.exit(1)

    # Apply overrides via module-level update
    import baby_podcast_generator as _self
    _self.MUSETALK_BBOX_SHIFT = args.bbox_shift
    _self.SADTALKER_EXPRESSION_SCALE = args.expression_scale

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  BABY PODCAST AI AVATAR PIPELINE")
    print(f"  GPU: RTX 2080 Ti (11GB) | Tier: {args.tier}")
    print(f"{'=' * 60}\n")

    # Handle text -> TTS
    if args.text:
        log("Step 0: Text -> Speech")
        tts_dir = args.output_dir / "tts_audio"
        tts_dir.mkdir(parents=True, exist_ok=True)
        tts_path = tts_dir / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        audio_path = None
        if args.voice == "elevenlabs":
            try:
                audio_path = generate_elevenlabs_audio(args.text, tts_path, args.voice_id)
            except Exception as e:
                log(f"ElevenLabs failed: {e}", "WARN")
                log("Falling back to edge-tts...", "WARN")
        elif args.voice == "kokoro":
            try:
                audio_path = generate_kokoro_audio(args.text, tts_path)
            except Exception as e:
                log(f"Kokoro failed: {e}", "WARN")
                log("Falling back to edge-tts...", "WARN")
        if audio_path is None:
            audio_path = generate_edge_tts_audio(args.text, tts_path)

        process_single(audio_path, args.image, args.output_dir, args.tier, args.skip_gfpgan)

    # Handle single audio
    elif args.audio:
        if not args.audio.exists():
            print(f"Error: Audio not found: {args.audio}")
            sys.exit(1)

        # Convert MP3 to WAV if needed
        audio_path = args.audio
        if audio_path.suffix.lower() == ".mp3":
            wav_path = args.output_dir / f"{audio_path.stem}.wav"
            subprocess.run(
                [FFMPEG_PATH, "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                capture_output=True,
                check=True,
            )
            audio_path = wav_path

        process_single(audio_path, args.image, args.output_dir, args.tier, args.skip_gfpgan)

    # Handle batch
    elif args.audio_dir:
        if not args.audio_dir.is_dir():
            print(f"Error: Directory not found: {args.audio_dir}")
            sys.exit(1)

        process_batch(args.audio_dir, args.image, args.output_dir, args.tier)


if __name__ == "__main__":
    main()
