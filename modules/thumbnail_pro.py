"""Premium thumbnail / cover generator — ONE 'best' look for EVERY channel, both
16:9 YouTube thumbnails and 9:16 Facebook-Reel / Shorts covers.

Hero image (cover-fit) + accent-tinted cinematic gradient + soft drop-shadowed BIG bold
outlined title + accent eyebrow pill + accent underline + brand. Per-kind typography
(kids / news / music / default). Portrait covers place the title in the reel-safe zone
(below the top chyron, above the bottom caption/UI). Robust font fallbacks.

    from modules.thumbnail_pro import make_pro_thumbnail, niche_style
    make_pro_thumbnail(hero, "Count in isiZulu 1-10", "thumb.jpg", *niche_style("kids_songs"))          # 16:9
    make_pro_thumbnail(hero, "BREAKING", "cover.jpg", *niche_style("tech_news"), size=(1080, 1920))     # 9:16 reel
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Per-channel style: (accent, eyebrow, brand, kind). Use via niche_style(niche).
NICHE_STYLE = {
    "tech_news":       ("#FF3131", "BREAKING", "Tech Pulse Africa",   "news"),
    "daily_breakdown": ("#2F7FE0", "TODAY",    "Daily Breakdown",     "news"),
    "ai_money":        ("#E0A400", "MONEY",    "Smart Money AI",      "default"),
    "ai_trading":      ("#E0A400", "MARKETS",  "",                    "default"),
    "motivation":      ("#A855F7", "MINDSET",  "Elevate You",         "default"),
    "health_wellness": ("#2E9E6B", "WELLNESS", "Herbal Organic Life", "default"),
    "blissful_moments":("#00C2A0", "",         "Blissful Moments",    "default"),
    "shopmo_products": ("#E8720C", "MUST-HAVE","ShopMo",              "default"),
    "limitless_you":   ("#6366F1", "GROW",     "Limitless You",       "default"),
    "kids_songs":      ("#E85D9E", "LEARN",    "Zuzu & Friends",      "kids"),
    "deep_chill":      ("#22D3EE", "",         "AlphaZone Sounds",    "music"),
}


def niche_style(niche):
    """(accent, eyebrow, brand, kind) for a niche — sensible red default if unknown."""
    return NICHE_STYLE.get(niche, ("#FF3131", "", "", "default"))


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _font(size, kind):
    win = r"C:\Windows\Fonts"
    presets = {
        "kids":    [rf"{win}\comicbd.ttf", rf"{win}\ARLRDBD.TTF", rf"{win}\arialbd.ttf"],
        "news":    [rf"{win}\impact.ttf", rf"{win}\seguibl.ttf", rf"{win}\arialbd.ttf"],
        "music":   [rf"{win}\seguibl.ttf", rf"{win}\arialbd.ttf"],
        "default": [rf"{win}\arialbd.ttf", rf"{win}\seguibl.ttf"],
    }
    for f in presets.get(kind, presets["default"]):
        try:
            return ImageFont.truetype(f, max(8, int(size)))
        except Exception:
            continue
    try:
        from matplotlib import font_manager
        return ImageFont.truetype(font_manager.findfont("DejaVu Sans:bold"), max(8, int(size)))
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, fnt, max_w, max_lines=3, truncate=True):
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
    return lines[:max_lines] if truncate else lines


def _outline(d, xy, text, fnt, fill, outline, ow):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=outline)
    d.text((x, y), text, font=fnt, fill=fill)


def make_pro_thumbnail(base_image, title, out_path, accent="#FF3131",
                       eyebrow="", brand="", kind="default", size=(1280, 720)):
    """Render a premium thumbnail/cover. size=(1280,720) landscape (YouTube) or
    (1080,1920) portrait (Reel/Short cover)."""
    W, H = int(size[0]), int(size[1])
    portrait = H > W
    ac = _hex(accent)
    margin = int(W * 0.05)

    # hero cover-fit (or a dark ground if the image is missing/unreadable)
    try:
        img = Image.open(base_image).convert("RGB")
        scale = max(W / img.width, H / img.height)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        l, t = (img.width - W) // 2, (img.height - H) // 2
        img = img.crop((l, t, l + W, t + H))
    except Exception:
        img = Image.new("RGB", (W, H), (18, 22, 28))
    img = img.convert("RGBA")

    # gradient / darken for text legibility
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    tint = (int(ac[0] * 0.16), int(ac[1] * 0.16), int(ac[2] * 0.16))
    if portrait:
        # reel/short cover: keep the hero visible in the middle, darken toward the edges
        for i in range(H):
            f = abs((i / H) - 0.5) * 2.0
            a = int(70 + 150 * (f ** 1.3))
            gd.line([(0, i), (W, i)], fill=(*tint, a))
    else:
        bh = int(H * 0.62)
        for i in range(bh):
            a = int(230 * (i / bh) ** 1.3)
            gd.line([(0, H - bh + i), (W, H - bh + i)], fill=(*tint, a))
        th = int(H * 0.22)
        for i in range(th):
            gd.line([(0, i), (W, i)], fill=(0, 0, 0, int(130 * (1 - i / th))))
    img.alpha_composite(grad)

    # title — sized to the frame width so it fits + wraps
    fs = int(W * (0.10 if kind == "news" else 0.092))
    fnt = _font(fs, kind)
    probe = ImageDraw.Draw(img)
    max_lines = 3 if portrait else 2
    # shrink the font until the WHOLE title fits within max_lines (don't chop words off)
    lines = _wrap(probe, str(title).upper(), fnt, int(W * 0.9), max_lines, truncate=False)
    while len(lines) > max_lines and fs > int(W * 0.045):
        fs -= int(W * 0.006); fnt = _font(fs, kind)
        lines = _wrap(probe, str(title).upper(), fnt, int(W * 0.9), max_lines, truncate=False)
    lines = lines[:max_lines]   # final safety if it still won't fit at the min size
    lh = int(fs * 1.06)
    total = lh * len(lines)
    y0 = int(H * 0.30) if portrait else (H - margin - total)   # reel-safe zone vs bottom

    # soft drop shadow behind the title
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    y = y0
    for ln in lines:
        sd.text((margin + 6, y + 9), ln, font=fnt, fill=(0, 0, 0, 190))
        y += lh
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(6, int(fs * 0.09)))))

    d = ImageDraw.Draw(img)
    ow = max(4, int(fs * 0.05))
    # accent underline above the title
    d.rectangle([margin, y0 - int(fs * 0.24), margin + int(W * 0.15), y0 - int(fs * 0.11)], fill=ac + (255,))
    y = y0
    for ln in lines:
        _outline(d, (margin, y), ln, fnt, (255, 255, 255), (12, 14, 20), ow)
        y += lh

    # eyebrow pill (top-left)
    if eyebrow:
        efs = int(W * 0.036)
        ef = _font(efs, kind)
        et = str(eyebrow).upper()
        tw = d.textlength(et, font=ef)
        pad = int(W * 0.014)
        d.rounded_rectangle([margin, margin, margin + tw + pad * 2, margin + efs + pad * 2],
                            radius=int(pad * 0.8), fill=ac + (255,))
        d.text((margin + pad, margin + pad - int(efs * 0.05)), et, font=ef, fill=(255, 255, 255))

    # brand — under the title on portrait (bottom is the UI zone), bottom-right on landscape
    if brand:
        bf = _font(int(W * 0.031), kind)
        tw = d.textlength(brand, font=bf)
        if portrait:
            _outline(d, (margin, y0 + total + int(fs * 0.18)), brand, bf, (255, 255, 255), (12, 14, 20), 3)
        else:
            _outline(d, (W - margin - tw, H - margin - int(fs * 0.35)), brand, bf, (255, 255, 255), (12, 14, 20), 3)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, "JPEG", quality=92)
    return str(out_path)


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else ""
    make_pro_thumbnail(base, "Count in isiZulu 1-10", "thumb_demo.jpg", *niche_style("kids_songs"))
    make_pro_thumbnail(base, "Breaking: Global Conflict Explained", "cover_demo.jpg",
                       *niche_style("tech_news"), size=(1080, 1920))
    print("wrote thumb_demo.jpg + cover_demo.jpg")
