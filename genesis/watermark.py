"""
Genesis Content Engine — Premium Watermark Pipeline

Burns animated "Genesis Studio" watermark onto every video using FFmpeg.
Premium design: center-bottom, pulsing opacity, glow effect, larger font.
"""
import subprocess
import shutil
import time
from pathlib import Path

from genesis.genesis_config import WATERMARK, OUTPUT_DIR, BRANDS
from genesis.db import update_video, log_pipeline


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None


def apply_watermark(video_path: str, video_id: int, brand: str) -> str | None:
    """Apply premium Genesis Studio watermark to a video.

    Features:
    - Bottom-center placement (visible but not intrusive)
    - Animated pulse: fades in, holds, pulses gently
    - Semi-transparent dark pill background with padding
    - Clean white text, larger font for visibility

    Returns the path to the branded video, or None on failure.
    """
    start = time.time()

    if not check_ffmpeg():
        log_pipeline("watermark", brand, "failed", "FFmpeg not found in PATH")
        print("  FFmpeg not found! Install from https://ffmpeg.org")
        return None

    input_path = Path(video_path)
    if not input_path.exists():
        log_pipeline("watermark", brand, "failed", f"Input video not found: {video_path}")
        return None

    # Output path
    branded_filename = f"genesis_{brand}_{video_id}_branded.mp4"
    branded_path = OUTPUT_DIR / branded_filename

    wm = WATERMARK
    text = wm.get("text", "Genesis Studio")
    font_size = wm.get("font_size", 28)
    font = wm.get("font", "Arial")

    # ── Premium animated watermark using FFmpeg drawtext ──
    #
    # Animation: Fade in over 0.8s, hold at 85% opacity, gentle pulse (85%-70%-85%)
    # every 3 seconds throughout the video. Looks professional and alive.
    #
    # Position: Bottom-center, 40px from bottom edge
    # Style: White text on dark rounded pill, generous padding

    # Alpha animation expression:
    # - 0-0.8s: fade in from 0 to 0.85
    # - 0.8s+: gentle sine wave pulse between 0.70 and 0.85
    alpha_expr = "if(lt(t\\,0.8)\\,t/0.8*0.85\\,0.775+0.075*sin(t*2.1))"

    # Build the filter complex with two drawtext passes:
    # Pass 1: Dark box background (the pill shape)
    # Pass 2: White text on top
    # Using a single drawtext with box=1 for simplicity and compatibility

    drawtext = (
        f"drawtext="
        f"text='{text}':"
        f"fontcolor=white@1.0:"
        f"fontsize={font_size}:"
        f"x=(w-tw)/2:"               # Center horizontally
        f"y=h-th-50:"                 # 50px from bottom
        f"font='{font}':"
        f"box=1:"
        f"boxcolor=black@0.55:"       # Semi-transparent dark pill
        f"boxborderw=14:"             # Generous padding for pill shape
        f"alpha='{alpha_expr}':"      # Animated opacity
        f"shadowcolor=black@0.4:"     # Subtle shadow for depth
        f"shadowx=2:shadowy=2"        # Shadow offset
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", drawtext,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        str(branded_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute max
        )

        if result.returncode != 0:
            error = result.stderr[-500:] if result.stderr else "Unknown error"
            log_pipeline("watermark", brand, "failed", f"FFmpeg error: {error}", time.time() - start)
            print(f"  FFmpeg failed for {brand}: {error[:100]}")
            return None

        if not branded_path.exists() or branded_path.stat().st_size < 1000:
            log_pipeline("watermark", brand, "failed", "Output file missing or too small", time.time() - start)
            return None

        # Update DB
        update_video(video_id, branded_video_path=str(branded_path), status="branded")

        duration = time.time() - start
        size_mb = branded_path.stat().st_size / (1024 * 1024)
        log_pipeline("watermark", brand, "success", f"Branded: {branded_filename} ({size_mb:.1f} MB)", duration)

        return str(branded_path)

    except subprocess.TimeoutExpired:
        log_pipeline("watermark", brand, "failed", "FFmpeg timed out (2 min)", time.time() - start)
        return None
    except Exception as e:
        log_pipeline("watermark", brand, "failed", str(e), time.time() - start)
        return None


def apply_all_watermarks(videos: dict) -> dict:
    """Apply watermark to all generated videos."""
    print("\nPHASE 4: Applying Watermarks...")

    results = {}
    for brand, video_data in videos.items():
        if not video_data:
            print(f"  SKIP {BRANDS[brand]['name']}: No video")
            continue

        branded_path = apply_watermark(
            video_data["video_path"],
            video_data["video_id"],
            brand,
        )

        if branded_path:
            video_data["branded_path"] = branded_path
            results[brand] = video_data
            print(f"  OK {BRANDS[brand]['name']}: Watermarked -> {Path(branded_path).name}")
        else:
            print(f"  FAIL {BRANDS[brand]['name']}: Watermark failed")

    return results


if __name__ == "__main__":
    if not check_ffmpeg():
        print("FFmpeg not found!")
    else:
        print("FFmpeg is available")
        print("Run the full pipeline to test watermarking.")
