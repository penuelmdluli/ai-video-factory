"""Auto-thumbnail for Zuzu & Friends — bright kids thumbnail with the character
+ big bold title. This is the #1 click-through lever for kids content.
1280x720 JPEG (YouTube spec). Requires a verified channel to upload."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720

def _font(size):
    for f in (r"C:\Windows\Fonts\comicbd.ttf",   # Comic Sans Bold — kid-friendly
              r"C:\Windows\Fonts\ARLRDBD.TTF",    # Arial Rounded Bold
              r"C:\Windows\Fonts\arialbd.ttf"):   # Arial Bold fallback
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]

def _text_outline(d, xy, text, fnt, fill, outline, ow):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=outline)
    d.text((x, y), text, font=fnt, fill=fill)

def make_thumbnail(base_image, title, out_path):
    img = Image.open(base_image).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))

    # dark gradient band at the bottom for title contrast
    band_h = int(H * 0.44)
    band = Image.new("RGBA", (W, band_h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for i in range(band_h):
        bd.line([(0, i), (W, i)], fill=(30, 12, 55, int(205 * (i / band_h))))
    base = img.convert("RGBA")
    base.alpha_composite(band, (0, H - band_h))
    img = base.convert("RGB")

    d = ImageDraw.Draw(img)
    # Title — big, wrapped, bottom
    fs = 112
    fnt = _font(fs)
    lines = _wrap(d, title.upper(), fnt, int(W * 0.92))
    while len(lines) > 2 and fs > 60:      # shrink if too many lines
        fs -= 12; fnt = _font(fs); lines = _wrap(d, title.upper(), fnt, int(W * 0.92))
    lh = int(fs * 1.12)
    total_h = lh * len(lines)
    y = H - 40 - total_h
    for ln in lines:
        tw = d.textlength(ln, font=fnt)
        _text_outline(d, ((W - tw) / 2, y), ln, fnt, (255, 255, 255), (120, 70, 190), 7)
        y += lh
    # top-left brand badge + a drawn star (emoji fonts aren't available headless)
    bfnt = _font(46)
    d.polygon([(46, 30), (56, 54), (82, 54), (61, 70), (69, 96),
               (46, 80), (23, 96), (31, 70), (10, 54), (36, 54)],
              fill=(255, 216, 90), outline=(120, 70, 190))
    _text_outline(d, (92, 34), "Zuzu & Friends", bfnt, (255, 240, 150), (120, 70, 190), 4)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=88)
    return str(out_path)
