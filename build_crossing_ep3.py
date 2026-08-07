#!/usr/bin/env python
"""WILD MINDS: THE CROSSING — Episode 3 (frame-chained, Veo 3 Lite, 1080p).

The human's video went viral. Now a crowd gathers at the wall to see the 'famous' animals — and
the trio who mocked humans for living through glowing rectangles are now ON the rectangles, facing
a choice between fame and freedom. Fresh scene (time jump), chained internally for continuity.

  python build_crossing_ep3.py            # build only (review)
  python build_crossing_ep3.py --post     # build + post
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

from modules.veo_series import build_chained_episode
from modules.wild_brand import brand_video
from modules.thumbnail_pro import _font

CAST = ROOT / "assets" / "animals" / "cast_crossing.png"
W, H, FPS = 1080, 1920, 24

STYLE = ("Epic cinematic wildlife film, photorealistic, FULL-BODY, anamorphic 35mm film look, cold "
         "blue dawn light at the base of a towering stone wall, drifting mist, atmospheric haze, "
         "shallow depth of field, film grain, natural ambient dawn sounds, ultra sharp. No on-screen "
         "text. The SAME lion, tiger and monkey. ")

V = {"lion": "a deep, powerful, gravelly baritone, slow and weighty",
     "tiger": "a low, smooth, cold, cynical voice",
     "monkey": "a high, quick, giddy, cheeky voice"}

SCRIPT = [
    ("lion", "Cold blue dawn at the great wall. The lion, tiger and monkey approach their gap but "
             "freeze — on the far side a huge crowd of humans has gathered, phones and cameras raised, "
             "waiting.",
     "They came back. All of them. And they brought their rectangles."),
    ("monkey", "The monkey peeks through the gap at the sea of glowing phones and flashing lights, "
               "eyes enormous with delight.",
     "They are all looking for US. We are famous!"),
    ("tiger", "The tiger watches the humans push and shove each other for a better angle, its lip "
              "curling in disgust.",
     "Famous. Yesterday they feared us. Today they collect us, like little pictures."),
    ("lion", "The lion notices a small human child at the very front, holding a crayon drawing of a "
             "lion, eyes full of pure wonder, not filming, only watching.",
     "No. Not all of them collect. Look at that little one. It only wants to see."),
    ("monkey", "The monkey gestures at the roaring crowd, torn between the attention and the open wild "
               "behind them.",
     "So do we give them their show? Or vanish into the wild and become a legend?"),
    ("lion", "The lion turns toward the deep golden savanna, then back to the wide-eyed child, caught "
             "between two worlds.",
     "A legend cannot live inside a rectangle. But that child... deserves to believe."),
]

CAPTION = ("WILD MINDS · THE CROSSING — Episode 3 \U0001F981\U0001F42F\U0001F412\n\n"
           "The video went viral. Now the whole world is at the wall with their phones... and the "
           "animals who mocked humans for living through screens are now ON every screen. \U0001F440\n\n"
           "Fame or freedom? One little child changes everything. Episode 4 soon — follow WILD MINDS.\n\n"
           "\U0001F3AC AI-generated • #WildMinds #TheCrossing #AI #TalkingAnimals #Reels")

NICHES = ["tech_news", "ai_money", "motivation", "health_wellness",
          "blissful_moments", "limitless_you", "sa_pulse"]


def prompts():
    return [STYLE + a + f' The {who} says in {V[who]}: "{line}"' for who, a, line in SCRIPT]


def endcard_clip(out_dir):
    img = Image.new("RGB", (W, H), (6, 7, 10))
    d = ImageDraw.Draw(img)
    f1 = _font(int(W * 0.095), "news")
    f2 = _font(int(W * 0.045), "news")
    t1 = "TO BE CONTINUED"
    d.text(((W - d.textlength(t1, font=f1)) // 2, int(H * 0.42)), t1, font=f1, fill=(255, 255, 255))
    t2 = "WILD MINDS  ·  THE CROSSING  ·  EP 4 SOON"
    d.text(((W - d.textlength(t2, font=f2)) // 2, int(H * 0.52)), t2, font=f2, fill=(224, 164, 0))
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
    fc = ";".join(filt) + ";" + "".join(f"[v{i}][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    subprocess.run([ff, "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", out], capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    from modules.veo_kie import check_key
    if not check_key():
        print("KIE_API_KEY not set.", flush=True)
        return

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"crossing_ep3_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    print("=== THE CROSSING EP3 — frame-chained Veo 3 Lite 1080p (~$2.40) ===", flush=True)

    clips = build_chained_episode(prompts(), cast_image=CAST, out_dir=out, model="veo3_lite",
                                  resolution="1080p", duration=8)
    if not clips:
        print("no clips generated.", flush=True)
        return

    ec = endcard_clip(out)
    stitched = out / "stitched.mp4"
    concat_uniform(clips + [ec], str(stitched))
    final = out / "the_crossing_ep3.mp4"
    brand_video(str(stitched), str(final))
    print(f"EPISODE -> {final}  ({len(clips)} shots)", flush=True)

    if not a.post:
        print("  (built — review; run with --post to publish)", flush=True)
        return
    import asyncio
    from modules.uploader_facebook import upload_to_facebook
    ok = 0
    for n in NICHES:
        try:
            res = asyncio.run(upload_to_facebook(
                video_path=str(final), title="WILD MINDS: The Crossing - Ep 3", description=CAPTION,
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
