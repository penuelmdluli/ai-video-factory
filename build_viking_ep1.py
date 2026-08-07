#!/usr/bin/env python
"""SAGA OF THE NORTH — Episode 1 (Hollywood-style Viking short).

Veo 3 Lite makes the cinematic, DYNAMIC battle visuals (character-locked hero via REFERENCE_2_VIDEO,
camera movement + action every shot). We layer a deep saga-teller NARRATOR (Kokoro am_onyx) + an
epic score + ducked Veo battle sound — the Hollywood footage + narration + score formula.

  python build_viking_ep1.py            # build only (review)
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import imageio_ffmpeg

from modules.veo_kie import generate_veo, upload_image, check_key, estimate_cost
from modules.wild_brand import brand_video

HERO = ROOT / "assets" / "viking" / "hero.png"
W, H, FPS = 1080, 1920, 24

STYLE = ("Epic cinematic Viking film, photorealistic, FULL-BODY, anamorphic 35mm film look, dramatic "
         "cold Nordic light, storm and mist, film grain, thunderous natural sound, ultra sharp 4k. No "
         "on-screen text. The SAME Viking warrior from the reference image. ")

# SHORT format: 2 punchy shots (~16s) — cheap (~$0.80) and made to post often.
SHOTS = [
    "Sweeping CRANE SHOT over a Viking longship crashing through a towering storm wave at dawn, "
    "warriors rowing furiously through freezing spray; at the dragon-prow the warrior raises his axe "
    "and ROARS defiantly into the storm.",
    "LOW-ANGLE HERO SHOT: the warrior LEAPS off the longship onto a fog-shrouded black shore, shield "
    "raised, charging up the beach with his roaring warband as war drums thunder.",
]

SAGA = ("They came from the cold north, where the sea itself screams. And when the storm broke... "
        "the Northmen did not pray. They attacked.")


def _ff():
    return imageio_ffmpeg.get_ffmpeg_exe()


def _dur(path):
    r = subprocess.run([_ff(), "-i", path], capture_output=True, text=True)
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 40.0


def concat_uniform(clips, out):
    ff = _ff()
    inputs = []
    for c in clips:
        inputs += ["-i", c]
    n = len(clips)
    filt = [f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v{i}]" for i in range(n)]
    fc = ";".join(filt) + ";" + "".join(f"[v{i}][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    subprocess.run([ff, "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", out], capture_output=True)
    return out


def main():
    if not check_key():
        print("KIE_API_KEY not set.", flush=True)
        return
    if not HERO.exists():
        print("hero image missing.", flush=True)
        return
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"viking_ep1_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    hero_url = upload_image(str(HERO))
    est = sum(estimate_cost("veo3_lite", 8) for _ in SHOTS)
    print(f"=== SAGA OF THE NORTH EP1 — {len(SHOTS)} char-locked dynamic shots ~${est:.2f} ===", flush=True)

    clips = []
    for i, p in enumerate(SHOTS):
        c = out / f"shot_{i}.mp4"
        try:
            generate_veo(STYLE + p, str(c), model="veo3_lite", aspect="9:16", resolution="1080p",
                         duration=8, image_urls=[hero_url], generation_type="REFERENCE_2_VIDEO")
            clips.append(str(c))
        except Exception as e:
            print(f"  shot {i} FAILED: {e}", flush=True)
            if i == 0:
                return
    if not clips:
        print("no clips.", flush=True)
        return

    visuals = out / "visuals.mp4"
    concat_uniform(clips, str(visuals))

    # $0 finish: deep saga-narrator + score + brand + synced subtitles + follow + comment-bait
    from finish_short import finish
    final = finish(out, voiceover=False)
    print(f"EPISODE -> {final}", flush=True)


if __name__ == "__main__":
    main()
