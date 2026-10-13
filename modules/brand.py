"""
Branding and theft-resistance for the dance reels.

Owner call 2026-08-30: these are his own dance videos now, they need their own
branding rather than the Mzansi Baby Stars name, and people are stealing them.

WHAT ACTUALLY STOPS A THIEF, IN ORDER OF HOW WELL IT WORKS
---------------------------------------------------------
1. RECURRING CHARACTERS. This is the real moat and it is already built. A
   stolen clip of Mkhulu still shows Mkhulu, and an audience that knows him
   knows where it came from. modules/dance_cast.py locks the cast for exactly
   this reason - reposting a face people recognise advertises the original.
2. TWO WATERMARKS, NOT ONE. A single corner mark is cropped off in seconds.
   Two marks on opposite thirds mean a crop tight enough to remove both also
   removes the dancer's head or feet, which ruins the clip.
3. FACEBOOK RIGHTS MANAGER. The platform's own tool, and the only one with
   teeth - it matches re-uploads against a reference library and can block
   them. It has to be applied for; nothing in this file replaces it.

What does NOT work: metadata, invisible watermarks, and disabling downloads.
Social re-encoding strips metadata, and a thief screen-records anyway.

The mark is deliberately understated. The top reels on this profile carry no
branding at all and did 2.7M; a heavy watermark costs reach because it reads
as an advert. Small, low-opacity, always in the same two places.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Set BRAND to the handle you want burned in. Kept as one constant so the
# whole system renames in one edit.
#
# Owner call 2026-10-12: every video now markets TradeRadar and NOTHING else
# (was iVideo Studio since 2026-09-14). The site mark, the end card and the
# caption call to action all point to gettraderadar.com. Copy lives in
# modules/tr_promo.py. The mid-video banner stays dropped (2026-09-25 note in
# watermark_video()).
BRAND = "gettraderadar.com"
SITE = "gettraderadar.com"
ICON = ROOT / "assets" / "traderadar" / "icon.png"
CARD_TAG = "traderadar-endcard"
OLD_CARD_TAGS = ("ivideostudio-endcard",)   # retired cards: swapped for the TradeRadar card in market_post
OLD_CARD_SECONDS = 3.5                      # add_end_card's default length when those were made


def _cta():
    from modules import tr_promo
    return tr_promo.caption_cta("profile", "profile", "brand")


CTA = _cta()


def _card_tag(path) -> str:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
                            "-of", "default=nw=1:nk=1", str(path)],
                           capture_output=True, text=True, timeout=60)
        return r.stdout
    except Exception:
        return ""


def has_end_card(path) -> bool:
    """True when the video already carries the TradeRadar end card."""
    return CARD_TAG in _card_tag(path)


def _strip_old_card(src: Path) -> Path:
    """Cut the retired iVideo Studio end card (the last OLD_CARD_SECONDS) off a video. Returns the trimmed file,
    or src unchanged when it has no old card or anything fails."""
    if not any(t in _card_tag(src) for t in OLD_CARD_TAGS):
        return src
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "default=nw=1:nk=1", str(src)],
                                   capture_output=True, text=True, timeout=60).stdout.strip())
        out = src.with_name(src.stem + "_nocard.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", f"{dur - OLD_CARD_SECONDS:.3f}",
                        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                        "-map_metadata", "-1", "-movflags", "+faststart", str(out)],
                       check=True, capture_output=True, timeout=900)
        print(f"[Brand] removed the old iVideo Studio end card from {src.name}")
        return out
    except Exception as e:
        print(f"[Brand] old end card not removed: {str(e)[:150]}")
        return src


def _strip_old_cta(message: str) -> str:
    """Drop iVideo Studio lines / hashtags from a caption (owner 2026-10-12: TradeRadar only)."""
    import re
    message = re.sub(r"\s*#iVideoStudio\b", "", message, flags=re.I)
    lines = [ln for ln in message.splitlines() if "ivideostudio" not in ln.lower()]
    msg = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", msg).strip()


def market_post(message: str, media_path):
    """Last stop before anything reaches the personal timeline (and the repost page path).

    Owner call 2026-10-12: every video posted markets TradeRadar only. Swaps a
    retired iVideo Studio end card for the TradeRadar card, adds the card to a
    video that lacks it, removes iVideo lines from the caption and adds the
    TradeRadar call to action. Returns (message, media_path).
    """
    if media_path and Path(media_path).suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
        if not has_end_card(media_path):
            src = _strip_old_card(Path(media_path))
            carded = add_end_card(src, Path(media_path).with_name(Path(media_path).stem + "_tr.mp4"))
            media_path = str(carded)
    if message is not None:
        message = _strip_old_cta(message)
        if SITE not in message:
            message = (message.rstrip() + "\n\n" + CTA) if message.strip() else CTA
    return message, media_path


FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/ariblk.ttf",
    # Linux cloud server (fonts-noto-core / fonts-dejavu)
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int):
    from PIL import ImageFont
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    return ImageFont.load_default()


def watermark_image(src, out=None, brand: str = "", opacity: int = 105):
    """Burn two marks onto a still: upper-left and lower-centre.

    Opposite thirds on purpose - see the note above. Returns the output path,
    or None if the image cannot be opened, because a missing watermark should
    not take the post down with it.
    """
    from PIL import Image, ImageDraw
    brand = brand or BRAND
    src = Path(src)
    out = Path(out) if out else src.with_name(src.stem + "_branded.png")
    try:
        base = Image.open(src).convert("RGBA")
    except Exception as e:
        print(f"[Brand] cannot open {src.name}: {str(e)[:80]}")
        return None

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    size = max(18, base.width // 28)
    font = _font(size)
    pad = base.width // 22

    def stamp(x, y, anchor):
        # A soft shadow first so the mark survives both a bright sky and a
        # dark tar road without needing a box behind it.
        d.text((x + 2, y + 2), brand, font=font, fill=(0, 0, 0, opacity // 2),
               anchor=anchor)
        d.text((x, y), brand, font=font, fill=(255, 255, 255, opacity),
               anchor=anchor)

    stamp(pad, pad, "la")                                   # upper-left
    stamp(base.width // 2, base.height - pad, "ms")         # lower-centre

    Image.alpha_composite(base, layer).convert("RGB").save(out)
    print(f"[Brand] {out.name} <- {brand}")
    return out


def watermark_video(src, out=None, brand: str = "", opacity: float = 0.42):
    """Burn the same two marks into a video with ffmpeg.

    Returns the output path, or None if ffmpeg is unavailable or fails - the
    caller should then post the unbranded cut rather than post nothing.
    """
    brand = brand or BRAND
    src = Path(src)
    out = Path(out) if out else src.with_name(src.stem + "_branded.mp4")
    font = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
    if not font:
        print("[Brand] no usable font found")
        return None

    # ffmpeg wants the drive colon escaped inside a filter expression.
    fontfile = font.replace(":", "\\:")
    common = (f"fontfile='{fontfile}':text='{brand}':"
              f"fontcolor=white@{opacity}:shadowcolor=black@{opacity/2:.2f}:"
              f"shadowx=2:shadowy=2:fontsize=h/34")
    vf = (f"drawtext={common}:x=w/22:y=w/22,"
          f"drawtext={common}:x=(w-text_w)/2:y=h-w/22-text_h")
    # The mid-reel "Made with AI | ivideostudio.ai" banner (seconds 5-9, lower
    # third) was removed on the owner's call 2026-09-25.
    #
    # It announced the one thing these reels depend on the viewer not deciding
    # too early. The formats that travel - the arena spectacle especially -
    # work because they read as footage somebody filmed, and a caption saying
    # it is AI, placed exactly where the act peaks, tells the viewer to stop
    # watching and start judging. It also landed over the middle of the frame
    # during the strongest seconds of the clip.
    #
    # The product is still advertised: the persistent site mark (gettraderadar.com since 2026-10-12) stays
    # (it is a site handle, not a disclosure), and add_end_card appends the
    # TradeRadar end card after the reel has finished playing - which
    # is where a call to action belongs.

    cmd = ["ffmpeg", "-y", "-i", str(src), "-vf", vf,
           "-c:a", "copy", "-movflags", "+faststart",
           "-pix_fmt", "yuv420p", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        print("[Brand] ffmpeg not on PATH")
        return None
    except subprocess.TimeoutExpired:
        print("[Brand] ffmpeg timed out")
        return None
    if r.returncode != 0:
        print(f"[Brand] ffmpeg failed: {r.stderr[-300:]}")
        return None
    print(f"[Brand] {out.name} <- {brand}")
    return out


def add_end_card(src, out=None, seconds: float = 3.5, style: str = "default"):
    """Append the TradeRadar end card (owner 2026-10-12; was the iVideo Studio card).

    style="soft" is the news/sport outro the traderadar-ai newsclips engine uses
    ("Protect your trading account: free tools at gettraderadar.com").

    Built from the reel's own last frame (blurred and darkened) so it belongs
    to the video, at the reel's exact size, fps and audio format so the join is
    seamless. Returns the output path, or the source unchanged if anything
    fails - a reel without a card is better than no reel.
    """
    import json
    import tempfile
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
    src = Path(src)
    out = Path(out) if out else src.with_name(src.stem + "_card.mp4")
    tmp = Path(tempfile.gettempdir())
    try:
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height,r_frame_rate,sample_rate,channels",
             "-of", "json", str(src)], capture_output=True, text=True, timeout=60).stdout)
        v = next(x for x in probe["streams"] if x["codec_type"] == "video")
        a = next((x for x in probe["streams"] if x["codec_type"] == "audio"), None)
        W, H = int(v["width"]), int(v["height"])
        num, den = v["r_frame_rate"].split("/")
        fps = round(float(num) / float(den or 1)) or 30
        rate = int(a["sample_rate"]) if a else 44100

        last = tmp / "ivs_last.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.3", "-i", str(src),
                        "-frames:v", "1", str(last)], check=True, timeout=120)
        bg = Image.open(last).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(W // 30))
        bg = ImageEnhance.Brightness(bg).enhance(0.35)
        d = ImageDraw.Draw(bg)

        def centred(text, size, y, fill):
            d.text((W // 2, y), text, font=_font(size), fill=fill, anchor="mm")

        if ICON.exists():
            ic = Image.open(ICON).convert("RGBA").resize((W // 7, W // 7))
            bg.paste(ic, ((W - ic.width) // 2, int(H * 0.33) - ic.height // 2), ic)
        if style == "soft":
            centred("PROTECT YOUR", W // 13, int(H * 0.44), (255, 255, 255))
            centred("TRADING ACCOUNT", W // 13, int(H * 0.50), (255, 255, 255))
            centred("Free tools: loss-limit warnings, lot size from your risk %", W // 34, int(H * 0.565),
                    (205, 205, 215))
        else:
            centred("TRACK GOLD, THE RAND", W // 13, int(H * 0.44), (255, 255, 255))
            centred("AND THE MARKETS", W // 13, int(H * 0.50), (255, 255, 255))
            centred("Read by AI, every day", W // 26, int(H * 0.565), (205, 205, 215))
        centred(SITE, W // 13, int(H * 0.64), (46, 229, 157))
        centred("Free to start", W // 22, int(H * 0.70), (255, 255, 255))
        centred("Analysis, not advice", W // 34, int(H * 0.75), (170, 170, 185))
        card_png = tmp / "ivs_card.png"
        bg.save(card_png)

        card = tmp / "ivs_card.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", str(seconds), "-i", str(card_png),
                        "-f", "lavfi", "-t", str(seconds), "-i",
                        f"anullsrc=channel_layout=stereo:sample_rate={rate}",
                        "-vf", f"fps={fps},format=yuv420p,fade=t=in:d=0.25",
                        "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
                        "-shortest", str(card)], check=True, timeout=300)

        if a:
            fc = (f"[0:v]scale={W}:{H},setsar=1,fps={fps}[v0];"
                  f"[1:v]scale={W}:{H},setsar=1,fps={fps}[v1];"
                  f"[0:a]aformat=sample_rates={rate}:channel_layouts=stereo[a0];"
                  f"[1:a]aformat=sample_rates={rate}:channel_layouts=stereo[a1];"
                  f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
            maps = ["-map", "[v]", "-map", "[a]"]
        else:
            fc = (f"[0:v]scale={W}:{H},setsar=1,fps={fps}[v0];"
                  f"[1:v]scale={W}:{H},setsar=1,fps={fps}[v1];"
                  f"[v0][v1]concat=n=2:v=1:a=0[v]")
            maps = ["-map", "[v]"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-i", str(card),
                        "-filter_complex", fc, *maps,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                        "-metadata", f"comment={CARD_TAG}", str(out)],
                       check=True, capture_output=True, timeout=900)
        print(f"[Brand] end card -> {out.name}")
        return out
    except Exception as e:
        print(f"[Brand] end card skipped: {str(e)[:200]}")
        return src


# Page reels (uploader_facebook.upload_to_facebook) get the card too (owner 2026-10-13: the countdown that went
# viral on Genesis News had no TradeRadar outro). Sport/news niches get the soft outro, like the newsclips engine.
SOFT_NICHES = {"sa_pulse", "genesis", "tech_news", "blissful_moments", "motivation", "limitless_you",
               "mzansi_baby", "health_wellness"}
SPOKEN_SOFT = "And protect your trading account: free tools with TradeRadar, at gettraderadar.com."


def page_end_card(path, niche: str):
    """Video path with the TradeRadar end card (idempotent). Never raises; returns the input on failure."""
    try:
        p = Path(path)
        if p.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm") or has_end_card(p):
            return str(p)
        src = _strip_old_card(p)
        return str(add_end_card(src, p.with_name(p.stem + "_tr.mp4"),
                                style="soft" if niche in SOFT_NICHES else "default"))
    except Exception as e:
        print(f"[Brand] page end card skipped: {str(e)[:150]}")
        return str(path)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Burn the brand onto an image or video")
    ap.add_argument("src")
    ap.add_argument("--out")
    ap.add_argument("--brand", default="")
    a = ap.parse_args()
    fn = watermark_video if Path(a.src).suffix.lower() in (
        ".mp4", ".mov", ".mkv", ".webm") else watermark_image
    print(fn(a.src, a.out, a.brand))
