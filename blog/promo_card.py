"""
Promo card — 1200x630 branded share image for a blog article.

Used as the article's og:image (so any share shows a real card) and attached
to the Facebook cross-post as a photo (a bare link post with no image is a
dead post — owner note 2026-08-16).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

W, H = 1200, 630


def make_promo(title: str, club_key: str, out_path) -> str | None:
    from PIL import Image, ImageDraw, ImageFont

    def font(sz, bold=True):
        name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", sz)

    try:
        from modules.club_brand import CLUB_BRAND, official_badge
        accent = CLUB_BRAND.get(club_key, {}).get("colors", {}).get(
            "primary", (255, 193, 7))
        badge = official_badge(club_key) if club_key else None
    except Exception:
        accent, badge = (255, 193, 7), None

    im = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 10], fill=accent)
    d.text((56, 44), "GENESIS NEWS", font=font(44), fill=(255, 200, 0))
    lw = d.textlength("GENESIS NEWS", font=font(44))
    d.text((56 + lw + 24, 56), "PSL & MZANSI FOOTBALL", font=font(24, False),
           fill=(200, 205, 210))

    # crest panel, right side
    text_right = W - 80
    if badge:
        try:
            crest = Image.open(badge).convert("RGBA")
            r = min(240 / crest.width, 240 / crest.height)
            crest = crest.resize((int(crest.width * r), int(crest.height * r)),
                                 Image.LANCZOS)
            panel = Image.new("RGBA", (crest.width + 44, crest.height + 44),
                              (255, 255, 255, 235))
            im.paste(panel, (W - panel.width - 56, 150), panel)
            im.paste(crest, (W - panel.width - 56 + 22, 172), crest)
            text_right = W - panel.width - 120
        except Exception:
            pass

    # wrapped headline
    tf = font(56)
    words, lines, cur = title.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if d.textlength(trial, font=tf) > text_right - 56 and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = trial
    lines.append(cur)
    y = 170
    for ln in lines[:5]:
        d.text((56, y), ln, font=tf, fill=(255, 255, 255))
        y += 74
    d.rectangle([56, y + 14, 216, y + 22], fill=accent)

    d.text((56, H - 76), "READ THE FULL STORY  ·  blog.genesisstudio.app",
           font=font(30), fill=(235, 238, 242))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, quality=92)
    return str(out_path)
