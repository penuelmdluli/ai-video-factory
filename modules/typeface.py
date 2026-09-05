"""ONE TYPEFACE, for every frame this factory draws.

Owner 2026-09-05, asking what professional studio we could bring in. The
answer started with the renderer, and the renderer starts here.

WHY THIS FILE EXISTS. Twenty-five modules each had their own `_font()`, and
twenty-five of them resolved to Arial. Arial is the single loudest amateur
signal on a sports graphic - no broadcaster on earth sets a scoreline in it -
and because the choice was copy-pasted into every module there was no single
place to change it. There is now.

WHAT WE SET INSTEAD. Bahnschrift, which ships with Windows and is Microsoft's
cut of DIN 1451 - the same industrial grotesque family the sports broadcasters
use for scoreboards and lower thirds. It is VARIABLE, carrying a weight axis
(300-700) and a width axis (75-100), so the condensed bold instance that reads
as "match graphic" is available without shipping a second file.

Condensed matters more than it sounds. A 1080-wide vertical frame has to hold
"NGOBESE-ZUMA" and a scoreline on one line, and a condensed face fits roughly
15% more characters at the same optical size. Every shrink-to-fit loop in this
repo exists because Arial ran out of room.

CACHED, because it was not. Every `_font()` in this codebase called
ImageFont.truetype() afresh, which reads and parses the font file. At dozens of
text calls per frame and thousands of frames per reel that was tens of
thousands of redundant file loads per video. The lru_cache below is the single
cheapest speed-up available to this renderer.

FALLS BACK, because a font is a machine detail. If Bahnschrift is missing the
chain walks to Franklin Gothic, then Arial, then whatever PIL can find. A reel
that renders in the wrong face beats a reel that raises ImportError at 3am on
the scheduler.

    from modules.typeface import font
    f = font(64)                        # bold condensed - the default voice
    f = font(28, weight="regular")      # body text
    f = font(90, width="normal")        # when a word needs room, not squeeze
"""
from functools import lru_cache
from pathlib import Path

# The family we want, in the order we want it. Each entry is
# (path, is_variable) - a variable file can be dialled to any instance, a
# static one is taken as it comes.
_CANDIDATES = [
    ("C:/Windows/Fonts/bahnschrift.ttf", True),    # DIN 1451 - the target
    ("C:/Windows/Fonts/framd.ttf", False),         # Franklin Gothic Medium
    ("C:/Windows/Fonts/arialbd.ttf", False),       # what we are leaving behind
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", False),
]

# Named instances inside Bahnschrift, keyed by how we ask for them here. The
# names are the font's own; PIL matches them exactly.
_INSTANCE = {
    ("bold", "condensed"): "Bold Condensed",
    ("bold", "semicondensed"): "Bold SemiCondensed",
    ("bold", "normal"): "Bold",
    ("semibold", "condensed"): "SemiBold Condensed",
    ("semibold", "normal"): "SemiBold",
    ("regular", "condensed"): "Condensed",
    ("regular", "semicondensed"): "SemiCondensed",
    ("regular", "normal"): "Regular",
    ("light", "condensed"): "Light Condensed",
    ("light", "normal"): "Light",
}


@lru_cache(maxsize=1)
def _resolve() -> tuple:
    """(path, is_variable) for the best face actually present. Cached."""
    for path, variable in _CANDIDATES:
        if Path(path).exists():
            return path, variable
    return "", False


@lru_cache(maxsize=512)
def font(size: int, weight: str = "bold", width: str = "condensed"):
    """A PIL font at `size`, in the house face.

    Cached on the full argument triple. Callers must NOT mutate what comes
    back - a variation set on a shared instance would change the face under
    every other caller holding the same object.
    """
    from PIL import ImageFont
    size = max(6, int(size))
    path, variable = _resolve()
    if not path:
        return ImageFont.load_default()
    try:
        f = ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()
    if not variable:
        return f
    want = _INSTANCE.get((weight, width)) or _INSTANCE[("bold", "condensed")]
    try:
        # PIL returns instance names as bytes on some builds and str on
        # others, so match on the decoded form rather than trusting either.
        names = []
        for n in f.get_variation_names():
            names.append(n.decode("utf-8", "ignore") if isinstance(n, bytes)
                         else str(n))
        if want in names:
            f.set_variation_by_name(want)
    except Exception:
        # No FreeType variation support on this build: the regular cut of
        # Bahnschrift is still a better face than Arial, so keep it.
        pass
    return f


def house_face() -> str:
    """Which file we ended up on - for logs, so a wrong face is visible."""
    return _resolve()[0] or "(pil default)"


if __name__ == "__main__":
    print("house face:", house_face())
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (1080, 620), (10, 10, 12))
    d = ImageDraw.Draw(im)
    y = 30
    for lbl, kw in [
        ("BOLD CONDENSED  0-0", dict()),
        ("SEMIBOLD COND   90'", dict(weight="semibold")),
        ("REGULAR CONDENSED", dict(weight="regular")),
        ("BOLD NORMAL WIDTH", dict(width="normal")),
    ]:
        d.text((40, y), lbl, font=font(72, **kw), fill=(255, 200, 0))
        y += 110
    d.text((40, y), "NGOBESE-ZUMA  \u2022  KAIZER CHIEFS  \u2022  1970",
           font=font(48), fill=(230, 235, 240))
    im.save("typeface_preview.png")
    print("wrote typeface_preview.png")
