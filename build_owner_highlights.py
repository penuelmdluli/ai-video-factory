"""
Owner highlights — turn a long WhatsApp video from the vault into:
  1. a branded landscape YouTube highlights video (blurred fill, brand bar,
     club crests, "Genesis News footage" credit), uploaded + playlisted, and
  2. short clips cut back into the vault inbox so reels rotate through
     different moments instead of always playing the first 38 seconds.

After cutting, the long original moves to assets/owner_media/longform/ so the
reel window only ever grabs short pieces; the full video lives on in the
YouTube upload.

Usage:
    python build_owner_highlights.py                 # newest long inbox video
    python build_owner_highlights.py --no-post       # render only
    python build_owner_highlights.py --title "..."   # override YouTube title
"""
import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

from modules.owner_media import INBOX, VAULT, _caption, _playback_path
from modules.club_brand import CLUB_BRAND, resolve_clubs

LONGFORM = VAULT / "longform"
BADGES = Path(__file__).parent / "assets" / "club_badges"
MIN_LONG = 90.0          # anything shorter is already reel-sized
PART_LEN = 68.0          # short clip length for the reel window rotation
CANVAS = (1920, 1080)


def _log(m):
    print(f"[Highlights] {m}", flush=True)


def _dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _badge(key: str):
    # the OFFICIAL crest, same as every card — never the stylized fan badges
    from modules.club_brand import official_badge
    return official_badge(key)


def _brand_overlay(clubs: list[str], out: Path) -> Path:
    """1920x1080 RGBA: top brand strip, crest-VS-crest, bottom credit."""
    from PIL import Image, ImageDraw, ImageFont

    def font(sz, bold=True):
        name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", sz)

    im = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # top strip
    d.rectangle([0, 0, CANVAS[0], 92], fill=(10, 10, 12, 215))
    d.text((36, 22), "GENESIS NEWS", font=font(42), fill=(255, 200, 0, 255))
    w = d.textlength("GENESIS NEWS", font=font(42))
    d.text((36 + w + 26, 34), "PSL & MZANSI FOOTBALL", font=font(24, False),
           fill=(235, 235, 235, 255))
    # crest VS crest, top-right, riding on the strip edge
    x = CANVAS[0] - 40
    b2 = _badge(clubs[1]) if len(clubs) > 1 else None
    b1 = _badge(clubs[0]) if clubs else None
    if b1 and b2:
        from PIL import Image as I
        c2 = I.open(b2).convert("RGBA").resize((120, 120))
        c1 = I.open(b1).convert("RGBA").resize((120, 120))
        x -= 120
        im.paste(c2, (x, 30), c2)
        x -= 78
        d.text((x + 8, 62), "VS", font=font(40), fill=(255, 200, 0, 255))
        x -= 120
        im.paste(c1, (x, 30), c1)
    # bottom credit
    d.rectangle([0, CANVAS[1] - 56, CANVAS[0], CANVAS[1]], fill=(10, 10, 12, 190))
    d.text((36, CANVAS[1] - 44), "Genesis News footage", font=font(24, False),
           fill=(235, 235, 235, 255))
    sub = "@GenesisNewsPSL — SUBSCRIBE"
    sw = d.textlength(sub, font=font(24))
    d.text((CANVAS[0] - 36 - sw, CANVAS[1] - 44), sub,
           font=font(24), fill=(255, 60, 60, 255))
    im.save(out)
    return out


def render(norm: Path, clubs: list[str], work: Path) -> Path:
    overlay = _brand_overlay(clubs, work / "brand_overlay.png")
    out = work / "highlights.mp4"
    fc = ("[0:v]scale=1920:1080,boxblur=24:2[bg];"
          "[0:v]scale=-2:1080[fg];"
          "[bg][fg]overlay=(W-w)/2:(H-h)/2[v1];"
          "[v1][1:v]overlay=0:0,fps=30,format=yuv420p[v]")
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(norm), "-i", str(overlay),
         "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"render failed: {r.stderr[-300:]}")
    return out


def thumbnail(final: Path, work: Path) -> Path:
    t = work / "thumb.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-ss", f"{_dur(final) * 0.4:.1f}", "-i", str(final),
                    "-frames:v", "1", "-q:v", "2", str(t)], capture_output=True)
    return t


def cut_parts(norm: Path, src: Path, caption: str) -> int:
    """Reel-sized pieces back into the inbox, then retire the long original."""
    total = _dur(norm)
    n, made = max(1, round(total / PART_LEN)), 0
    step = total / n
    for i in range(n):
        name = f"{src.stem}_part{i+1}.mp4"
        dst = INBOX / name
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{i*step:.2f}",
             "-i", str(norm), "-t", f"{step:.2f}", "-c:v", "libx264",
             "-preset", "fast", "-crf", "20", "-c:a", "aac", str(dst)],
            capture_output=True)
        if r.returncode != 0 or not dst.exists():
            continue
        (INBOX / (name + ".json")).write_text(json.dumps(
            {"caption": f"{caption} — part {i+1}", "from": "owner",
             "ts": int(src.stat().st_mtime * 1000) + i, "kind": "video"},
            indent=2), encoding="utf-8")
        # already constant-fps: pre-seed the normalized cache
        norm_dst = VAULT / "normalized" / name
        norm_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, norm_dst)
        made += 1
    LONGFORM.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), LONGFORM / src.name)
    sc = src.parent / (src.name + ".json")
    if sc.exists():
        shutil.move(str(sc), LONGFORM / sc.name)
    _log(f"cut {made} reel clips, original retired to longform/")
    return made


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="")
    ap.add_argument("--no-post", action="store_true")
    a = ap.parse_args()

    longs = [p for p in sorted(INBOX.glob("*.mp4"),
                               key=lambda x: x.stat().st_mtime, reverse=True)
             if _dur(p) >= MIN_LONG]
    if not longs:
        _log(f"no inbox video >= {MIN_LONG:.0f}s — nothing to do")
        return
    src = longs[0]
    caption = _caption(src) or "PSL matchday"
    clubs = resolve_clubs(caption)
    names = [CLUB_BRAND.get(c, {}).get("name", c.title()) for c in clubs]
    _log(f"source: {src.name} ({_dur(src):.0f}s) caption='{caption}' clubs={clubs}")

    work = Path("output") / f"owner_highlights_{datetime.now():%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)

    norm = Path(_playback_path(src))          # constant 30fps, real speed
    final = render(norm, clubs, work)
    thumb = thumbnail(final, work)
    _log(f"rendered: {final} ({_dur(final):.0f}s)")

    if not a.no_post:
        vs = " vs ".join(names[:2]) if len(names) >= 2 else (names[0] if names else "PSL")
        title = a.title or (f"{vs} — Inside the Stadium | Genesis News Fan "
                            f"Highlights ({datetime.now():%d %b %Y})")
        desc = (f"Our own footage from the stands — {vs}, Betway Premiership.\n"
                "Real matchday atmosphere, filmed by Genesis News.\n\n"
                "SUBSCRIBE for daily PSL news, live matchday updates, lineups "
                "and results: https://www.youtube.com/@GenesisNewsPSL\n"
                "#PSL #BetwayPremiership" +
                "".join(f" #{n.replace(' ', '')}" for n in names))
        from modules.uploader_youtube import upload_to_youtube
        r = await upload_to_youtube(
            video_path=str(final), title=title, description=desc,
            tags=["PSL", "BetwayPremiership"] + [n.replace(" ", "") for n in names],
            niche="sa_pulse", thumbnail_path=str(thumb), is_short=False)
        vid = r.get("video_id") if isinstance(r, dict) else None
        _log(f"YouTube: {vid or r}")
        if vid:
            try:
                from modules.playlists import add_youtube
                add_youtube(vid, shorts=False)
            except Exception as e:
                _log(f"playlist skipped: {e}")

    cut_parts(norm, src, caption)
    _log("DONE")


if __name__ == "__main__":
    asyncio.run(main())
