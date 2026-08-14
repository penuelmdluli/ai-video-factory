"""
News cards — stamp headline, kicker and source credit onto a photo.

Turns a bare image (Wikimedia CC photo, club media shot, or generated matchday
b-roll) into a branded 9:16 Genesis News card: club-coloured accent, headline,
and the mandatory source credit.

The credit line is not decoration. Every CC-BY / CC-BY-SA photo we use REQUIRES
visible attribution, and news claims require the outlet. Rendering it into the
frame means the obligation travels with the image wherever the reel is reposted.

Usage:
    from modules.news_card import make_news_card
    make_news_card("photo.jpg", "out.png",
                   headline="Monyane fires warning at Sundowns",
                   kicker="KAIZER CHIEFS",
                   credit="Soccer Laduma",
                   club="chiefs")
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from modules.club_brand import CLUB_BRAND, official_badge, resolve_clubs
except Exception:  # standalone use
    CLUB_BRAND = {}
    def official_badge(_club):
        return None
    def resolve_clubs(_text):
        return []


def _fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Scale an RGBA image to fit inside box_w x box_h, preserving aspect ratio."""
    r = min(box_w / img.width, box_h / img.height)
    return img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))), Image.LANCZOS)

W, H = 1080, 1920
LOGO = Path(__file__).parent.parent / "assets" / "youtube_branding" / "logo_sa_pulse.png"


def _font(size: int, bold: bool = True):
    paths = (["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
              "C:/Windows/Fonts/impact.ttf"] if bold else
             ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"])
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Fill w x h without distortion (crop the overflow)."""
    src_ratio, dst_ratio = img.width / img.height, w / h
    if src_ratio > dst_ratio:
        new_w = int(img.height * dst_ratio)
        img = img.crop(((img.width - new_w) // 2, 0, (img.width + new_w) // 2, img.height))
    else:
        new_h = int(img.width / dst_ratio)
        # bias the crop upward — faces and action sit in the top half of sports photos
        top = int((img.height - new_h) * 0.30)
        img = img.crop((0, top, img.width, top + new_h))
    return img.resize((w, h), Image.LANCZOS)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def make_news_card(
    image_path: str | Path,
    output_path: str | Path,
    headline: str,
    kicker: str = "",
    credit: str = "",
    club: str = "",
    max_lines: int = 4,
    archive_year: str = "",
    prediction: str = "",
    log_rows: list | None = None,
    cover_mode: bool = False,
) -> str | None:
    """
    Render a branded news card. Returns the output path, or None on failure.

    archive_year: stamp an ARCHIVE badge when the photo is not from this story.
    Most freely-licensed PSL photography on Commons is years old, and running a
    1992 team photo under a 2026 headline reads as "this is today" — which is
    exactly the kind of misleading framing the fact guards exist to prevent.
    """
    try:
        base = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"[NewsCard] cannot open {image_path}: {e}")
        return None

    brand = CLUB_BRAND.get(club, {})
    accent = brand.get("colors", {}).get("primary", (255, 193, 7))

    card = _cover(base, W, H)

    # Bottom scrim so text is always legible over any photo.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(int(H * 0.52)):
        y = H - 1 - i
        alpha = int(238 * (i / (H * 0.52)) ** 0.85)
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    sd.rectangle([0, 0, W, int(H * 0.16)], fill=(0, 0, 0, 140))  # top bar for the logo
    card = Image.alpha_composite(card.convert("RGBA"), scrim).convert("RGB")
    d = ImageDraw.Draw(card)

    # ── Logo (top-left) ──
    # cover_mode: the thumbnail wants the brand BIG in the empty top space —
    # one large logo (it carries its own wordmark), no small text lines.
    try:
        if LOGO.exists():
            size = 250 if cover_mode else 150
            logo = Image.open(LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
            card.paste(logo, (44, 26 if cover_mode else 40), logo)
    except Exception:
        pass
    if not cover_mode:
        d.text((214, 74), "GENESIS NEWS", font=_font(44), fill=(255, 255, 255))
        d.text((216, 126), "PSL & MZANSI FOOTBALL", font=_font(26, bold=False),
               fill=(190, 195, 200))
    # cover_mode: no wordmark text — the big logo carries it, and the crests
    # own the rest of the top row

    # ── Official club crest(s) (top-right) ──
    # Shown on every card so the reel reads as the club at a glance. A soft white
    # "sticker" panel sits behind each crest so a dark crest (e.g. the Pirates
    # skull) never disappears into the dark top bar. When the headline is a
    # two-club story ("Chiefs vs Sundowns"), BOTH crests appear with a VS chip.
    badge_bottom = 40
    matchup = resolve_clubs(headline)
    if club and club in matchup:
        matchup.remove(club)
    show = ([club] if official_badge(club) else []) + \
           [c for c in matchup if official_badge(c)]
    show = show[:2]
    if show:
        try:
            crest_box = 176 if len(show) == 1 else 148
            crests = [_fit(Image.open(official_badge(c)).convert("RGBA"),
                           crest_box, crest_box) for c in show]
            pad = 28
            panels = [(cr.width + pad, cr.height + pad) for cr in crests]
            vs_f = _font(44)
            vs_w = int(d.textlength("VS", font=vs_f)) + 24 if len(show) == 2 else 0
            total_w = sum(p[0] for p in panels) + (vs_w + 16 if vs_w else 0)
            x = W - 44 - total_w          # right edge inset 44px
            by = 34
            card = card.convert("RGBA")
            row_h = max(p[1] for p in panels)
            for j, (cr, (pw, ph)) in enumerate(zip(crests, panels)):
                py = by + (row_h - ph) // 2
                panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                ImageDraw.Draw(panel).rounded_rectangle(
                    [0, 0, pw - 1, ph - 1], radius=26, fill=(255, 255, 255, 235))
                card.alpha_composite(panel, (x, py))
                card.alpha_composite(cr, (x + (pw - cr.width) // 2,
                                          py + (ph - cr.height) // 2))
                x += pw
                if j == 0 and len(show) == 2:
                    dd = ImageDraw.Draw(card)
                    vy = by + row_h // 2 - 26
                    dd.text((x + 11, vy + 3), "VS", font=vs_f, fill=(0, 0, 0, 230))
                    dd.text((x + 8, vy), "VS", font=vs_f, fill=(255, 193, 7, 255))
                    x += vs_w + 16
            card = card.convert("RGB")
            d = ImageDraw.Draw(card)
            badge_bottom = by + row_h
        except Exception as e:
            print(f"[NewsCard] badge skipped: {e}")

    # ── ARCHIVE badge — never let an old photo read as today ──
    # Sits just under the crest, right-aligned; drops below the prediction
    # chip's row when one is present so the two never collide.
    if archive_year:
        label = f"ARCHIVE {archive_year}".strip()
        af = _font(30)
        aw = d.textlength(label, font=af)
        ay1 = badge_bottom + 16
        if prediction:
            ay1 = max(ay1, 300)
        ax1 = W - aw - 96
        d.rectangle([ax1, ay1, W - 44, ay1 + 52], fill=(200, 40, 40))
        d.text((ax1 + 22, ay1 + 10), label, font=af, fill=(255, 255, 255))

    # ── Prediction chip (top-left, under the brand row) ──
    # "OUR CALL: CHIEFS 2-1 — BAARTMAN TO SCORE" — labelled opinion, the kind
    # of take fans screenshot to argue with.
    if prediction:
        pf = _font(30)
        pw = d.textlength(prediction, font=pf)
        x1, y1 = 60, 222
        d.rounded_rectangle([x1, y1, x1 + pw + 66, y1 + 62], radius=16,
                            fill=(15, 17, 22), outline=accent, width=3)
        d.ellipse([x1 + 20, y1 + 21, x1 + 40, y1 + 41], fill=accent,
                  outline=(255, 255, 255), width=2)     # ball dot
        d.text((x1 + 52, y1 + 14), prediction, font=pf, fill=(255, 255, 255))

    # ── Mini log table (right column over the photo) ──
    if log_rows:
        lx2 = W - 44
        lx1 = lx2 - 400
        row_h = 54
        ly1 = max(int(badge_bottom) + 26, 330)
        ly2 = ly1 + 64 + row_h * len(log_rows) + 18
        d.rounded_rectangle([lx1, ly1, lx2, ly2], radius=20, fill=(10, 12, 16, 210))
        tf = _font(30)
        d.text((lx1 + 24, ly1 + 16), "BETWAY LOG", font=tf, fill=accent)
        rf, pf2 = _font(28), _font(28, bold=False)
        y = ly1 + 64
        for r in log_rows:
            hot = club and r.get("team_key") == club
            if hot:                                   # highlight our club's row
                d.rounded_rectangle([lx1 + 10, y - 4, lx2 - 10, y + row_h - 12],
                                    radius=10, fill=accent)
            fg = (10, 10, 10) if hot else (235, 238, 242)
            d.text((lx1 + 24, y), f"{r['rank']}", font=rf, fill=fg)
            d.text((lx1 + 70, y), str(r["name"])[:12], font=rf, fill=fg)
            pts = f"{r['points']} pts"
            d.text((lx2 - 24 - d.textlength(pts, font=pf2), y), pts,
                   font=pf2, fill=fg)
            y += row_h

    # ── Kicker (club name strip) ──
    # Headline block sits higher than a normal card so the burned-in subtitles
    # (which live in the bottom ~300px) never collide with it.
    y = int(H * 0.50)
    if kicker:
        kf = _font(40)
        kw = d.textlength(kicker.upper(), font=kf)
        d.rectangle([60, y, 60 + kw + 44, y + 66], fill=accent)
        d.text((82, y + 12), kicker.upper(), font=kf, fill=(10, 10, 10))
        y += 96

    # ── Headline ──
    hf = _font(72)
    lines = _wrap(d, headline, hf, W - 130)
    if len(lines) > max_lines:                      # shrink once rather than truncate mid-word
        hf = _font(58)
        lines = _wrap(d, headline, hf, W - 130)[:max_lines]
    for ln in lines:
        d.text((62, y + 3), ln, font=hf, fill=(0, 0, 0))     # drop shadow
        d.text((60, y), ln, font=hf, fill=(255, 255, 255))
        y += int(hf.size * 1.22)

    # ── Accent rule + credit ──
    y += 18
    d.rectangle([60, y, 260, y + 7], fill=accent)
    if credit:
        cf = _font(26, bold=False)
        # Wrap rather than run off the edge — an attribution that is cut in half
        # does not satisfy the CC licence it exists to satisfy.
        for ln in _wrap(d, f"Source: {credit}", cf, W - 120)[:3]:
            d.text((60, y + 34), ln, font=cf, fill=(205, 210, 215))
            y += 32

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    card.save(output_path, quality=95)
    print(f"[NewsCard] {output_path.name}")
    return str(output_path)


if __name__ == "__main__":
    import asyncio
    from modules.free_press_images import photos_for_club, download

    async def _test():
        out = Path("output/news_card_test")
        out.mkdir(parents=True, exist_ok=True)
        hits = await photos_for_club("chiefs", 1)
        if not hits:
            print("no photos found")
            return
        h = hits[0]
        raw = await download(h, out / "raw.jpg")
        if raw:
            make_news_card(
                raw, out / "card.png",
                headline="Monyane fires warning at Sundowns: 'We know their weaknesses'",
                kicker="Kaizer Chiefs",
                credit=f"Soccer Laduma · photo: {h['credit']}",
                club="chiefs",
            )
    asyncio.run(_test())
