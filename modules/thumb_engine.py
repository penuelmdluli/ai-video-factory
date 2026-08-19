"""
Scroll-stopping thumbnail engine — one look, one promise, one brand.

Why the old covers failed: YouTube was auto-grabbing a mid-video frame, so a
vertical clip got letterboxed into a 16:9 box with blurred bars, the content
shrank to the middle third, and it was dark-on-dark with no hook. At feed
size that is invisible.

Rules this engine enforces:
  1. EDGE TO EDGE — the photo fills the frame, never a letterboxed inset.
  2. ONE HOOK — 2-4 huge words, white with a heavy dark outline, readable at
     thumbnail size on a phone.
  3. CONTRAST — a solid accent slab behind the hook so it never sits on busy
     photo detail.
  4. URGENCY CHIP — the one number that makes someone act (days left, score).
  5. BRAND BUG — same corner, same colours, every single time. That is what
     turns scattered posts into a community people recognise.

make_thumb() renders 1280x720 (YouTube) and make_cover() 1080x1350 vertical
(Facebook/TikTok cover) from the same inputs.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from modules.motion_kit import _font

BRANDS = {
    "careers": {"accent": (46, 200, 113), "chip": (220, 50, 50),
                "name": "MZANSI CAREERS", "tag": "VERIFIED · NEVER PAY"},
    "genesis": {"accent": (255, 200, 0), "chip": (220, 50, 50),
                "name": "GENESIS NEWS", "tag": "PSL · MZANSI FOOTBALL"},
}
DARK = (10, 12, 15)


def _fill(photo_path, w, h, focus=0.5, focus_y=0.35, punch=True):
    """Cover-crop a photo to fill w x h.

    focus / focus_y say where along each axis the crop window starts (0..1) —
    frame_picker supplies these so the subject stays inside the crop instead
    of a blind centre cut landing on empty grass.
    """
    im = Image.open(photo_path).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))),
                   Image.LANCZOS)
    x = int((im.width - w) * min(1, max(0, focus)))
    y = int((im.height - h) * min(1, max(0, focus_y)))
    im = im.crop((x, y, x + w, y + h))
    if punch:
        im = ImageEnhance.Color(im).enhance(1.28)
        im = ImageEnhance.Contrast(im).enhance(1.12)
        im = ImageEnhance.Brightness(im).enhance(1.05)
    return im


def _shade(im, side="left", frac=0.62, strength=232):
    """Darken one side so type stays legible over any photo."""
    w, h = im.size
    grad = Image.new("L", (w, 1), 0)
    px = grad.load()
    span = int(w * frac)
    for x in range(w):
        if side == "left":
            v = strength if x < span * 0.55 else max(
                0, int(strength * (1 - (x - span * 0.55) / (span * 0.45))))
        else:
            xx = w - 1 - x
            v = strength if xx < span * 0.55 else max(
                0, int(strength * (1 - (xx - span * 0.55) / (span * 0.45))))
        px[x, 0] = v
    mask = grad.resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), DARK), im, mask)


def _outline(d, xy, text, fnt, fill=(255, 255, 255), ow=9,
             oc=(6, 8, 10)):
    x, y = xy
    for dx in range(-ow, ow + 1, 3):
        for dy in range(-ow, ow + 1, 3):
            if dx or dy:
                d.text((x + dx, y + dy), text, font=fnt, fill=oc)
    d.text(xy, text, font=fnt, fill=fill)


def _hook_lines(d, hook, max_w, max_h, start=150, floor=52):
    """Largest font that fits the hook inside the box (width AND height).

    The old version only checked width, so a three-line hook grew taller than
    its zone and ran straight through the urgency chip and brand bug.
    """
    words = hook.upper().split()
    for size in range(start, floor - 1, -4):
        f = _font(size)
        if max(d.textlength(w, font=f) for w in words) > max_w:
            continue
        lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= 3 and len(lines) * int(size * 1.06) <= max_h:
            return f, lines, size
    f = _font(floor)
    return f, words[:3], floor


def _brand_bug(d, brand, x, y, small=False):
    b = BRANDS[brand]
    f = _font(34 if small else 40)
    d.text((x, y), b["name"], font=f, fill=(255, 255, 255))
    f2 = _font(20 if small else 24, False)
    d.text((x + 2, y + (40 if small else 48)), b["tag"], font=f2,
           fill=b["accent"])


def _render(w, h, hook, kicker, chip, photo, brand, focus, vertical=False,
            bottom_safe=0.0, focus_y=0.35):
    b = BRANDS[brand]
    if photo and Path(photo).exists():
        im = _fill(photo, w, h, focus=focus, focus_y=focus_y)
        im = _shade(im, "left" if not vertical else "left",
                    frac=0.72 if not vertical else 1.0,
                    strength=210 if not vertical else 170)
    else:
        im = Image.new("RGB", (w, h), DARK)
    # usable height: on a reel cover the bottom strip is covered by the
    # caption, profile row and action buttons, so nothing may live there
    uh = int(h * (1 - bottom_safe))
    # bottom scrim so the brand bug never disappears into busy photo detail
    scrim_h = int(h * 0.22)
    grad = Image.new("L", (1, scrim_h))
    gp = grad.load()
    for yy in range(scrim_h):
        gp[0, yy] = int(238 * (yy / scrim_h) ** 1.5)
    sc = Image.new("RGB", (w, scrim_h), DARK)
    im.paste(sc, (0, h - scrim_h), grad.resize((w, scrim_h)))
    d = ImageDraw.Draw(im, "RGBA")

    pad = int(w * 0.045)
    text_w = int(w * (0.60 if not vertical else 0.90))

    # Zones, bottom-up: brand bug, then chip, and whatever is left is the
    # hook's. Nothing is allowed to grow into its neighbour.
    brand_y = int(uh * (0.855 if not vertical else 0.905))
    chip_h = int(h * (0.115 if not vertical else 0.075))
    chip_y = brand_y - int(h * 0.030) - (chip_h if chip else 0)

    # accent rule + kicker
    ky = int(h * (0.11 if not vertical else 0.085))
    d.rectangle([pad, ky, pad + int(w * 0.10), ky + 12], fill=b["accent"])
    kf_size = int(h * (0.052 if not vertical else 0.040))
    if kicker:
        # shrink to fit — a kicker running off the edge reads as broken
        while kf_size > 18 and d.textlength(
                kicker.upper(), font=_font(kf_size)) > w - pad * 2:
            kf_size -= 2
        d.text((pad, ky + 30), kicker.upper(), font=_font(kf_size),
               fill=b["accent"])

    hook_top = ky + 34 + (int(kf_size * 1.35) if kicker else 0)
    hook_h = max(int(h * 0.18), chip_y - hook_top - int(h * 0.025))
    f, lines, size = _hook_lines(
        d, hook, text_w, hook_h,
        start=int(h * (0.21 if not vertical else 0.135)))
    lh = int(size * 1.06)
    y = hook_top
    for ln in lines:
        _outline(d, (pad, y), ln, f, ow=max(6, size // 16))
        y += lh

    if chip:
        cf_size = int(chip_h * 0.62)
        # shrink to fit: "CLOSES 31 AUGUST 2026" ran off the right edge
        while cf_size > 18 and d.textlength(
                chip.upper(), font=_font(cf_size)) > w - pad * 2 - 52:
            cf_size -= 2
        cf = _font(cf_size)
        cw = d.textlength(chip.upper(), font=cf)
        d.rounded_rectangle([pad, chip_y, pad + cw + 52, chip_y + chip_h],
                            radius=18, fill=b["chip"])
        d.text((pad + 26, chip_y + (chip_h - cf_size * 1.25) / 2 + 2),
               chip.upper(), font=cf, fill=(255, 255, 255))

    _brand_bug(d, brand, pad, brand_y, small=vertical)
    d.rectangle([0, h - 10, w, h], fill=b["accent"])
    return im


def make_thumb(out, hook, kicker="", chip="", photo=None, brand="careers",
               focus=0.62, focus_y=0.35):
    """1280x720 YouTube thumbnail."""
    im = _render(1280, 720, hook, kicker, chip, photo, brand, focus,
                 focus_y=focus_y)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=94)
    return str(out)


def make_cover(out, hook, kicker="", chip="", photo=None, brand="careers",
               focus=0.5, focus_y=0.35):
    """1080x1350 (4:5) cover for a Facebook/Instagram FEED photo post."""
    im = _render(1080, 1350, hook, kicker, chip, photo, brand, focus,
                 vertical=True, focus_y=focus_y)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=94)
    return str(out)


def make_reel_cover(out, hook, kicker="", chip="", photo=None,
                    brand="careers", focus=0.5, focus_y=0.35):
    """1080x1920 (9:16) cover for a REEL — Facebook, Instagram, TikTok.

    A reel cover MUST match the video's 9:16 or the platform crops it, which
    is what made our covers look the wrong size. The bottom ~26% is reserved
    because the caption, profile row and action buttons sit over it.
    """
    im = _render(1080, 1920, hook, kicker, chip, photo, brand, focus,
                 vertical=True, bottom_safe=0.26, focus_y=focus_y)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=94)
    return str(out)
