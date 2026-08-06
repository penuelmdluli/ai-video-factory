"""Premium thumbnail generator — ONE 'best' 1280x720 YouTube thumbnail for every channel.

Hero image (cover-fit) + accent-tinted cinematic gradient + soft drop-shadowed BIG bold
outlined title + accent eyebrow tag + accent underline + brand. Per-kind typography
(kids / news / music / default). Robust font fallbacks (Windows fonts → DejaVu → default).

    from modules.thumbnail_pro import make_pro_thumbnail
    make_pro_thumbnail(hero_jpg, "Count in isiZulu 1-10", "thumb.jpg",
                       accent="#E85D9E", eyebrow="LEARN", brand="Zuzu & Friends", kind="kids")
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720


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
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    try:
        from matplotlib import font_manager
        return ImageFont.truetype(font_manager.findfont("DejaVu Sans:bold"), size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, fnt, max_w, max_lines=3):
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
    return lines[:max_lines]


def _outline(d, xy, text, fnt, fill, outline, ow):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=outline)
    d.text((x, y), text, font=fnt, fill=fill)


def make_pro_thumbnail(base_image, title, out_path, accent="#FF3131",
                       eyebrow="", brand="", kind="default"):
    ac = _hex(accent)

    # hero cover-fit (or a dark ground if the image is missing)
    try:
        img = Image.open(base_image).convert("RGB")
        scale = max(W / img.width, H / img.height)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        l, t = (img.width - W) // 2, (img.height - H) // 2
        img = img.crop((l, t, l + W, t + H))
    except Exception:
        img = Image.new("RGB", (W, H), (18, 22, 28))
    img = img.convert("RGBA")

    # cinematic gradient: strong accent-tinted rise from the bottom + a soft top darken
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    bh = int(H * 0.62)
    for i in range(bh):
        a = int(230 * (i / bh) ** 1.3)
        col = (int(ac[0] * 0.16), int(ac[1] * 0.16), int(ac[2] * 0.16), a)
        gd.line([(0, H - bh + i), (W, H - bh + i)], fill=col)
    th = int(H * 0.22)
    for i in range(th):
        gd.line([(0, i), (W, i)], fill=(0, 0, 0, int(130 * (1 - i / th))))
    img.alpha_composite(grad)

    margin = 56
    # title (uppercase, wrapped) sized to fit
    fs = 128 if kind == "news" else 116
    fnt = _font(fs, kind)
    probe = ImageDraw.Draw(img)
    lines = _wrap(probe, title.upper(), fnt, int(W * 0.9))
    while len(lines) > 2 and fs > 62:
        fs -= 10; fnt = _font(fs, kind); lines = _wrap(probe, title.upper(), fnt, int(W * 0.9))
    lh = int(fs * 1.06)
    y0 = H - margin - lh * len(lines)

    # soft drop shadow behind the title
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    y = y0
    for ln in lines:
        sd.text((margin + 6, y + 9), ln, font=fnt, fill=(0, 0, 0, 190))
        y += lh
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(11)))

    d = ImageDraw.Draw(img)
    # accent underline bar above the title
    d.rectangle([margin, y0 - 26, margin + int(W * 0.15), y0 - 12], fill=ac + (255,))
    # crisp title
    y = y0
    for ln in lines:
        _outline(d, (margin, y), ln, fnt, (255, 255, 255), (12, 14, 20), 6)
        y += lh

    # eyebrow pill (top-left)
    if eyebrow:
        ef = _font(46, kind)
        et = str(eyebrow).upper()
        tb = d.textbbox((0, 0), et, font=ef)
        tw, tht = tb[2] - tb[0], tb[3] - tb[1]
        pad = 18
        d.rounded_rectangle([margin, 42, margin + tw + pad * 2, 42 + tht + pad * 2 + tb[1]],
                            radius=14, fill=ac + (255,))
        d.text((margin + pad, 42 + pad), et, font=ef, fill=(255, 255, 255))

    # brand (bottom-right)
    if brand:
        bf = _font(40, kind)
        tb = d.textbbox((0, 0), brand, font=bf)
        tw = tb[2] - tb[0]
        _outline(d, (W - margin - tw, H - margin - 44), brand, bf, (255, 255, 255), (12, 14, 20), 3)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, "JPEG", quality=92)
    return str(out_path)


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else ""
    make_pro_thumbnail(base, "Count in isiZulu 1-10", "thumb_demo.jpg",
                       accent="#E85D9E", eyebrow="LEARN", brand="Zuzu & Friends", kind="kids")
    print("wrote thumb_demo.jpg")
