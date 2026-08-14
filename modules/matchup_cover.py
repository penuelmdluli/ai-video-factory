"""
Matchup covers — the bold both-badges thumbnail for reels and posts.

A derby thumbnail must be readable at feed size: two HUGE crests, a hard
club-colour split, a big VS. Nothing else competes for the eye — headline and
detail live in the video itself, not the cover.

Usage:
    from modules.matchup_cover import make_matchup_cover
    make_matchup_cover("cover.png", home="chiefs", away="sundowns",
                       line="SAT 15:00 · FNB STADIUM")
    # single club (non-matchup story): away=None -> one giant centred crest
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from modules.club_brand import CLUB_BRAND, official_badge
except Exception:
    from club_brand import CLUB_BRAND, official_badge

W, H = 1080, 1920
LOGO = Path(__file__).parent.parent / "assets" / "youtube_branding" / "logo_sa_pulse.png"


def _font(size: int, bold: bool = True):
    for p in (["C:/Windows/Fonts/arialbd.ttf"] if bold else ["C:/Windows/Fonts/arial.ttf"]):
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _fit(img: Image.Image, box: int) -> Image.Image:
    r = min(box / img.width, box / img.height)
    return img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))),
                      Image.LANCZOS)


def _big_crest(canvas: Image.Image, club: str, cy: int, box: int = 560,
               cx: int | None = None):
    """Huge crest on a soft white disc with a glow, centred at (cx, cy)."""
    badge = official_badge(club)
    if not badge:
        return
    cx = W // 2 if cx is None else cx
    crest = _fit(Image.open(badge).convert("RGBA"), box)
    disc = box + 90
    glow = Image.new("RGBA", (disc + 80, disc + 80), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([40, 40, disc + 40, disc + 40],
                                 fill=(255, 255, 255, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    canvas.alpha_composite(glow, (cx - (disc + 80) // 2, cy - (disc + 80) // 2))
    panel = Image.new("RGBA", (disc, disc), (0, 0, 0, 0))
    ImageDraw.Draw(panel).ellipse([0, 0, disc - 1, disc - 1],
                                  fill=(255, 255, 255, 244))
    canvas.alpha_composite(panel, (cx - disc // 2, cy - disc // 2))
    canvas.alpha_composite(crest, (cx - crest.width // 2, cy - crest.height // 2))


_GOLD_WORDS = {"chiefs", "kaizer", "sundowns", "pirates", "orlando", "mamelodi",
               "derby", "vs", "win", "wins", "lose", "war", "battle", "test",
               "warning", "fear", "revenge", "crisis", "final"}


def _draw_title(canvas: Image.Image, title: str, y0: int, y1: int):
    """Hero title: wrapped, shrink-to-fit, key words in gold, heavy outline."""
    d = ImageDraw.Draw(canvas)
    words = title.split()
    max_w = W - 130

    def layout(f):
        lines, cur = [], []
        for w in words:
            if d.textlength(" ".join(cur + [w]), font=f) <= max_w or not cur:
                cur.append(w)
            else:
                lines.append(cur)
                cur = [w]
        if cur:
            lines.append(cur)
        return lines

    fs = 104
    f = _font(fs)
    lines = layout(f)
    while (len(lines) * fs * 1.18 > (y1 - y0) or len(lines) > 4) and fs > 56:
        fs -= 6
        f = _font(fs)
        lines = layout(f)

    y = y0 + max(0, int(((y1 - y0) - len(lines) * fs * 1.18) / 2))
    for line in lines:
        lw = sum(d.textlength(w, font=f) for w in line) + \
            d.textlength(" ", font=f) * (len(line) - 1)
        x = (W - lw) // 2
        for w in line:
            gold = w.strip(".,!?:;'\"—-").lower() in _GOLD_WORDS or \
                any(ch.isdigit() for ch in w)
            for dx in (-4, 0, 4):
                for dy in (-4, 0, 4):
                    d.text((x + dx, y + dy), w, font=f, fill=(0, 0, 0, 240))
            d.text((x, y), w, font=f,
                   fill=(255, 193, 7, 255) if gold else (255, 255, 255, 255))
            x += d.textlength(w, font=f) + d.textlength(" ", font=f)
        y += int(fs * 1.18)


def _cover_bg(canvas: Image.Image, bg_path: str):
    """Real photo behind the badges — blurred + darkened so the crests own
    the frame, but the texture reads as REAL fans/stadium, not flat colour."""
    img = Image.open(bg_path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)),
                     Image.LANCZOS)
    img = img.crop(((img.width - W) // 2, (img.height - H) // 2,
                    (img.width - W) // 2 + W, (img.height - H) // 2 + H))
    img = img.filter(ImageFilter.GaussianBlur(5))
    canvas.alpha_composite(img.convert("RGBA"))


def make_matchup_cover(
    output_path: str | Path,
    home: str,
    away: str | None = None,
    line: str = "",
    bg_path: str | None = None,
    bg_credit: str = "",
    title: str = "",
) -> str | None:
    """Bold badge-first cover, optionally over a real (licensed) photo."""
    try:
        hb = CLUB_BRAND.get(home, {})
        h_col = tuple(hb.get("colors", {}).get("primary", (255, 193, 7)))
        h_name = hb.get("name", home.title()).upper()

        canvas = Image.new("RGBA", (W, H), (10, 12, 16, 255))
        d = ImageDraw.Draw(canvas)

        if bg_path:
            try:
                _cover_bg(canvas, bg_path)
            except Exception as e:
                print(f"[Cover] bg skipped: {e}")
                bg_path = None

        if away:
            ab = CLUB_BRAND.get(away, {})
            a_col = tuple(ab.get("colors", {}).get("primary", (255, 193, 7)))
            a_name = ab.get("name", away.title()).upper()
            # diagonal colour split — home top-left, away bottom-right.
            # Solid when flat; a translucent tint when a real photo is behind,
            # so the crowd texture shows through in each club's colour.
            top = Image.new("RGBA", (W, H), h_col + (255,))
            bot = Image.new("RGBA", (W, H), a_col + (255,))
            mask = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mask).polygon([(0, 0), (W, 0), (W, H // 2 - 180),
                                          (0, H // 2 + 180)], fill=255)
            split = Image.composite(top, bot, mask)
            if bg_path:
                split.putalpha(92)
            canvas.alpha_composite(split)
            # darken for contrast, keep colour identity
            shade = Image.new("RGBA", (W, H), (8, 10, 14, 150 if bg_path else 132))
            canvas.alpha_composite(shade)
            d = ImageDraw.Draw(canvas)

            if title:
                # TITLE LAYOUT: badges side by side up top, title owns the
                # centre — thumbnail says WHO and WHAT in the same glance.
                _big_crest(canvas, home, 470, box=350, cx=272)
                _big_crest(canvas, away, 470, box=350, cx=W - 272)
                d = ImageDraw.Draw(canvas)
                vs_f = _font(120)
                vw = d.textlength("VS", font=vs_f)
                d.text((W // 2 - vw / 2 + 5, 470 - 68 + 5), "VS", font=vs_f,
                       fill=(0, 0, 0, 255))
                d.text((W // 2 - vw / 2, 470 - 68), "VS", font=vs_f,
                       fill=(255, 193, 7, 255))
                _draw_title(canvas, title, 850, 1620)
                d = ImageDraw.Draw(canvas)
            else:
                # TOWER LAYOUT: badge / VS / badge, nothing else
                _big_crest(canvas, home, 520)
                _big_crest(canvas, away, 1420)
                d = ImageDraw.Draw(canvas)
                vs_f = _font(170)
                vw = d.textlength("VS", font=vs_f)
                burst = Image.new("RGBA", (560, 560), (0, 0, 0, 0))
                ImageDraw.Draw(burst).ellipse([80, 80, 480, 480],
                                              fill=(10, 12, 16, 235))
                burst = burst.filter(ImageFilter.GaussianBlur(6))
                canvas.alpha_composite(burst, (W // 2 - 280, H // 2 - 280))
                d = ImageDraw.Draw(canvas)
                d.text((W // 2 - vw / 2 + 6, H // 2 - 108 + 6), "VS", font=vs_f,
                       fill=(0, 0, 0, 255))
                d.text((W // 2 - vw / 2, H // 2 - 108), "VS", font=vs_f,
                       fill=(255, 193, 7, 255))
        else:
            # single-club story: one giant crest on the club colour
            bg = Image.new("RGBA", (W, H), h_col + (255,))
            if bg_path:
                bg.putalpha(92)
            canvas.alpha_composite(bg)
            canvas.alpha_composite(Image.new("RGBA", (W, H),
                                             (8, 10, 14, 165 if bg_path else 150)))
            if title:
                _big_crest(canvas, home, 470, box=440)
                _draw_title(canvas, title, 850, 1620)
                d = ImageDraw.Draw(canvas)
            else:
                _big_crest(canvas, home, H // 2 - 120, box=640)
                d = ImageDraw.Draw(canvas)
                nf = _font(64)
                nw = d.textlength(h_name, font=nf)
                d.text((W // 2 - nw / 2 + 3, H // 2 + 343), h_name, font=nf,
                       fill=(0, 0, 0))
                d.text((W // 2 - nw / 2, H // 2 + 340), h_name, font=nf,
                       fill=(255, 255, 255))

        # branding top + info line bottom
        try:
            if LOGO.exists():
                lg = Image.open(LOGO).convert("RGBA").resize((110, 110), Image.LANCZOS)
                canvas.alpha_composite(lg, (44, 42))
        except Exception:
            pass
        d.text((172, 56), "GENESIS NEWS", font=_font(44), fill=(255, 255, 255))
        d.text((174, 108), "PSL & MZANSI FOOTBALL", font=_font(24, bold=False),
               fill=(225, 228, 232))
        if line:
            lf = _font(40)
            lw = d.textlength(line, font=lf)
            pill = Image.new("RGBA", (int(lw) + 72, 84), (0, 0, 0, 0))
            ImageDraw.Draw(pill).rounded_rectangle(
                [0, 0, pill.width - 1, 83], radius=22, fill=(10, 12, 16, 220))
            canvas.alpha_composite(pill, (W // 2 - pill.width // 2, H - 170))
            d = ImageDraw.Draw(canvas)
            d.text((W // 2 - lw / 2, H - 150), line, font=lf, fill=(255, 255, 255))
        if bg_path and bg_credit:
            # the licence travels with the image, even on a thumbnail
            cf = _font(20, bold=False)
            cw = d.textlength(bg_credit, font=cf)
            d.text((W // 2 - cw / 2, H - 44), bg_credit, font=cf,
                   fill=(205, 210, 215))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(output_path, quality=95)
        print(f"[Cover] {output_path.name} ({home}{' vs ' + away if away else ''})")
        return str(output_path)
    except Exception as e:
        print(f"[Cover] failed: {e}")
        return None


if __name__ == "__main__":
    make_matchup_cover("output/cover_test.png", "chiefs", "sundowns",
                       line="SAT 15:00 · FNB STADIUM")
    make_matchup_cover("output/cover_single_test.png", "pirates",
                       line="TRANSFER NEWS")
