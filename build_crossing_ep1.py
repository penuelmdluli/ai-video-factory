#!/usr/bin/env python
"""WILD MINDS: THE CROSSING — Episode 1 (character-locked serialized Veo 3 short).

The cast (lion / tiger / monkey) is locked to a reference image via REFERENCE_2_VIDEO so they stay
identical across every shot; each character has a fixed voice profile repeated in every prompt so
voices stay matched; the episode ends on a cliffhanger. Builds + stitches + brands. Review, then post.

  python build_crossing_ep1.py            # build only (review before posting)
  python build_crossing_ep1.py --post     # build + post to all pages
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import imageio_ffmpeg
from PIL import Image, ImageDraw

from modules.veo_kie import generate_veo, upload_image, check_key, estimate_cost
from modules.wild_brand import brand_video
from modules.thumbnail_pro import _font

CAST = ROOT / "assets" / "animals" / "cast_crossing.png"
W, H, FPS = 720, 1280, 24

STYLE = ("Epic cinematic wildlife film, photorealistic, FULL-BODY, anamorphic 35mm film look, "
         "moonlit night, cool blue moonlight, atmospheric haze, shallow depth of field, film grain, "
         "natural ambient night sounds, ultra sharp. No on-screen text or logos. The SAME lion, tiger "
         "and monkey from the reference image. ")

VOICE = {
    "lion": "a deep, powerful, gravelly baritone, slow and regal",
    "tiger": "a low, smooth, cold, menacing growl",
    "monkey": "a high, quick, cheeky, mischievous voice",
}

SCRIPT = [
    ("lion", "Wide full-body shot at night: the lion, tiger and monkey creep toward a towering long "
             "stone wall under the moon. The lion stops.",
     "This is the wall. No animal has ever crossed it."),
    ("monkey", "The monkey scampers to the base of the wall and finds a dark gap at the bottom, then "
               "turns to the others, grinning with excitement.",
     "Ha! A hole! The great wall has a little mouse-door!"),
    ("tiger", "The tiger narrows its eyes at the dark gap, tail flicking slowly, uneasy.",
     "And what if the humans catch us on the other side?"),
    ("lion", "The lion looks back at the dark savanna one last time, then forward through the gap, and "
             "steps toward it with resolve.",
     "Then we will finally know what they are so afraid of losing."),
    ("monkey", "Wide shot on the OTHER side of the wall: the three animals emerge and freeze, staring "
               "ahead as the glow of a vast human city lights up the night sky.",
     "By the moon... what IS that?"),
    ("lion", "Two blinding white headlights suddenly swing toward the three animals out of the darkness, "
             "lighting up their startled faces.",
     "Nobody move."),
]

CAPTION = ("WILD MINDS · THE CROSSING — Episode 1 \U0001F981\U0001F42F\U0001F412\n\n"
           "No animal has ever crossed the human wall... until tonight. They found a gap. They went "
           "through. And then the lights came.\n\n"
           "What happens next? \U0001F440 Follow WILD MINDS — Episode 2 soon.\n\n"
           "\U0001F3AC AI-generated • #WildMinds #TheCrossing #AI #TalkingAnimals #Reels")

NICHES = ["tech_news", "ai_money", "motivation", "health_wellness",
          "blissful_moments", "limitless_you", "sa_pulse"]


def shot_prompt(who, action, line):
    return STYLE + action + f' The {who} says in {VOICE[who]}: "{line}"'


def endcard_clip(out_dir):
    img = Image.new("RGB", (W, H), (6, 7, 10))
    d = ImageDraw.Draw(img)
    f1 = _font(int(W * 0.095), "news")
    f2 = _font(int(W * 0.045), "news")
    t1 = "TO BE CONTINUED"
    w1 = d.textlength(t1, font=f1)
    d.text(((W - w1) // 2, int(H * 0.42)), t1, font=f1, fill=(255, 255, 255))
    t2 = "WILD MINDS  ·  THE CROSSING  ·  EP 2 SOON"
    w2 = d.textlength(t2, font=f2)
    d.text(((W - w2) // 2, int(H * 0.52)), t2, font=f2, fill=(224, 164, 0))
    png = out_dir / "endcard.png"
    img.save(png)
    out = out_dir / "endcard.mp4"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loop", "1", "-i", str(png), "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=stereo", "-t", "1.9",
                    "-vf", f"scale={W}:{H},setsar=1", "-r", str(FPS),
                    "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest", str(out)],
                   capture_output=True)
    return str(out)


def concat_uniform(clips, out):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs = []
    for c in clips:
        inputs += ["-i", c]
    n = len(clips)
    filt = [f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v{i}]" for i in range(n)]
    concat = "".join(f"[v{i}][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    fc = ";".join(filt) + ";" + concat
    subprocess.run([ff, "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", out], capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    if not check_key():
        print("KIE_API_KEY not set.", flush=True)
        return
    if not CAST.exists():
        print(f"cast image missing: {CAST}", flush=True)
        return

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"crossing_ep1_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    try:
        cast_url = upload_image(str(CAST))
    except Exception as e:
        print(f"cast upload FAILED: {e}", flush=True)
        return

    est = sum(estimate_cost("veo3_fast", 8) for _ in SCRIPT)
    print(f"=== THE CROSSING EP1 — {len(SCRIPT)} character-locked shots ~${est:.2f} ===", flush=True)
    clips = []
    for i, (who, action, line) in enumerate(SCRIPT):
        c = out / f"shot_{i}.mp4"
        try:
            generate_veo(shot_prompt(who, action, line), str(c), model="veo3_fast", aspect="9:16",
                         resolution="720p", duration=8, image_urls=[cast_url],
                         generation_type="REFERENCE_2_VIDEO")
            clips.append(str(c))
        except Exception as e:
            print(f"  shot {i} FAILED: {e}", flush=True)
            if i == 0:
                print("  first shot failed — aborting to save credit.", flush=True)
                return
    if not clips:
        print("no clips generated.", flush=True)
        return

    ec = endcard_clip(out)
    stitched = out / "stitched.mp4"
    concat_uniform(clips + [ec], str(stitched))
    final = out / "the_crossing_ep1.mp4"
    brand_video(str(stitched), str(final))
    print(f"EPISODE -> {final}", flush=True)

    if not a.post:
        print("  (built — review it; run with --post to publish to all pages)", flush=True)
        return

    import asyncio
    from modules.uploader_facebook import upload_to_facebook
    ok = 0
    for n in NICHES:
        try:
            res = asyncio.run(upload_to_facebook(
                video_path=str(final), title="WILD MINDS: The Crossing — Ep 1", description=CAPTION,
                niche=n, hashtags=["WildMinds", "TheCrossing", "AI", "TalkingAnimals", "Reels"],
                is_reel=True))
            print(f"{n}: {res}", flush=True)
            if isinstance(res, dict) and res.get("status") == "uploaded":
                ok += 1
        except Exception as e:
            print(f"{n} FAILED: {e}", flush=True)
    print(f"DONE — {ok}/{len(NICHES)} posted", flush=True)


if __name__ == "__main__":
    main()
