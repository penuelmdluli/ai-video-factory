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
BRAND = "@penuel.mdluli.7"

FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/ariblk.ttf",
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
