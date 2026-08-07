#!/usr/bin/env python
"""WILD MINDS: THE CROSSING — Episode 2 (frame-chained, 1080p).

Continues EXACTLY from Episode 1's final frame (the headlights) via image-to-video, then chains
every shot from the previous shot's last frame for seamless, director-level continuity. Same cast,
fixed voice profiles, emotional first-contact payoff, cliffhanger for Ep 3.

  python build_crossing_ep2.py            # build only (review)
  python build_crossing_ep2.py --post     # build + post to all pages
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

from modules.veo_series import build_chained_episode, _last_frame
from modules.wild_brand import brand_video
from modules.thumbnail_pro import _font

CAST = ROOT / "assets" / "animals" / "cast_crossing.png"
EP1_LAST_SHOT = ROOT / "output" / "crossing_ep1_20260807_170204" / "shot_5.mp4"
W, H, FPS = 1080, 1920, 24

STYLE = ("Epic cinematic wildlife film, photorealistic, FULL-BODY, anamorphic 35mm film look, night "
         "at the edge of a glowing human city, headlight beams and distant neon glow, atmospheric "
         "haze, shallow depth of field, film grain, natural ambient night sounds, ultra sharp. No "
         "on-screen text. The SAME lion, tiger and monkey. ")

V = {"lion": "a deep, powerful, gravelly baritone, slow and steady",
     "tiger": "a low, smooth, cold, wary voice",
     "monkey": "a high, quick, cheeky, awestruck whisper"}

SCRIPT = [
    ("lion", "The three animals stand frozen in the blinding white headlights of a car stopped on a "
             "dark road at the city's edge, eyes wide, not moving.",
     "Stay calm. Do not run."),
    ("monkey", "A car door opens; a lone human silhouette steps out slowly and raises a glowing phone "
               "to film them, hand trembling.",
     "It's... pointing the little glowing rectangle at US."),
    ("tiger", "The human freezes, mouth open in disbelief, the phone half-lowered, breath visible in "
              "the cold.",
     "It is not running. Why is it not afraid?"),
    ("lion", "The lion steps forward into the headlight beams, regal and calm, and meets the human's "
             "eyes directly.",
     "Because tonight, little human... you finally see us."),
    ("monkey", "Wide shot: the trembling human and the three animals stand facing each other in the "
               "headlights, a strange fragile peace between them.",
     "Take your picture, human. Nobody will ever believe you."),
    ("lion", "The three animals turn and walk back toward the distant wall, silhouettes against the "
             "glowing city, as the human watches them vanish into the dark.",
     "Come. We have seen enough of their world... for one night."),
]

CAPTION = ("WILD MINDS · THE CROSSING — Episode 2 \U0001F981\U0001F42F\U0001F412\n\n"
           "They crossed the wall. Now a human has seen them... and it's pointing a glowing rectangle "
           "right at them. First contact. \U0001F440\n\n"
           "What happens when the human tells the world? Episode 3 soon. Follow WILD MINDS.\n\n"
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
    t2 = "WILD MINDS  ·  THE CROSSING  ·  EP 3 SOON"
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
    out = ROOT / "output" / f"crossing_ep2_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    start_img = None
    if EP1_LAST_SHOT.exists():
        start_img = out / "ep1_end.png"
        _last_frame(str(EP1_LAST_SHOT), str(start_img))
        print(f"  continuing from Ep1 final frame: {start_img}", flush=True)

    print("=== THE CROSSING EP2 — frame-chained 1080p (~$7.20) ===", flush=True)
    clips = build_chained_episode(prompts(), cast_image=CAST, out_dir=out, model="veo3_lite",
                                  resolution="1080p", duration=8, start_image=str(start_img) if start_img else None)
    if not clips:
        print("no clips generated.", flush=True)
        return

    ec = endcard_clip(out)
    stitched = out / "stitched.mp4"
    concat_uniform(clips + [ec], str(stitched))
    final = out / "the_crossing_ep2.mp4"
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
                video_path=str(final), title="WILD MINDS: The Crossing - Ep 2", description=CAPTION,
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
