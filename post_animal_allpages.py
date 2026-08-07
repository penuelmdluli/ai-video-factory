#!/usr/bin/env python
"""Brand the talking-animal short (WILD MINDS) and post it to ALL configured FB pages to
A/B test which audience performs best."""
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import imageio_ffmpeg
from PIL import Image, ImageDraw

from modules.emoji_util import render_emoji
from modules.thumbnail_pro import _font

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = ROOT / "output" / "animal_short_20260807_161007" / "short.mp4"
D = SRC.parent
W, H = 720, 1280

CAPTION = ("If animals could talk \U0001F981\U0001F42F\U0001F430\n\n"
           "The lion, tiger and rabbit can't understand why humans obey a small glowing rectangle "
           "every single morning \U0001F602\n\n"
           "\U0001F3AC AI-generated • Follow WILD MINDS for more.\n\n"
           "#TalkingAnimals #WildMinds #AI #Funny #Reels")

NICHES = ["tech_news", "ai_money", "motivation", "health_wellness",
          "blissful_moments", "limitless_you", "sa_pulse"]


def brand():
    name = "WILD MINDS"
    fs = 34
    f = _font(fs, "news")
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(name, font=f)
    em = render_emoji("\U0001F981", px=int(fs * 1.25))
    esz = int(fs * 1.15)
    pad, gap = 22, 12
    w = int(pad * 2 + esz + gap + tw)
    h = int(fs * 1.8)
    badge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=(12, 14, 20, 205))
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, outline=(255, 255, 255, 60), width=2)
    x = pad
    em = em.resize((esz, esz), Image.LANCZOS)
    badge.paste(em, (x, (h - esz) // 2), em)
    x += esz + gap
    d.text((x, (h - fs) // 2 - 2), name, font=f, fill=(255, 255, 255, 255))
    bp = D / "brand_badge.png"
    badge.save(bp)

    hf = _font(28, "news")
    handle = "FOLLOW FOR MORE"
    hb = Image.new("RGBA", (W, 64), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hb)
    tw2 = hd.textlength(handle, font=hf)
    hx = (W - tw2) // 2
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            hd.text((hx + dx, 14 + dy), handle, font=hf, fill=(0, 0, 0, 220))
    hd.text((hx, 14), handle, font=hf, fill=(255, 255, 255, 255))
    hbp = D / "brand_handle.png"
    hb.save(hbp)

    out = D / "short_branded.mp4"
    subprocess.run([FF, "-y", "-i", str(SRC), "-i", str(bp), "-i", str(hbp), "-filter_complex",
                    "[0:v][1:v]overlay=(W-w)/2:36[a];[a][2:v]overlay=0:H-100[v]",
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", str(out)], capture_output=True)
    return str(out)


def main():
    branded = brand()
    print(f"branded -> {branded}", flush=True)
    from modules.uploader_facebook import upload_to_facebook
    ok = 0
    for n in NICHES:
        try:
            res = asyncio.run(upload_to_facebook(
                video_path=branded, title="If Animals Could Talk", description=CAPTION,
                niche=n, hashtags=["TalkingAnimals", "WildMinds", "AI", "Funny", "Reels"],
                is_reel=True))
            print(f"{n}: {res}", flush=True)
            if isinstance(res, dict) and res.get("status") == "uploaded":
                ok += 1
        except Exception as e:
            print(f"{n} FAILED: {e}", flush=True)
    print(f"DONE — {ok}/{len(NICHES)} posted", flush=True)


if __name__ == "__main__":
    main()
