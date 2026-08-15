"""
Full-time result cards — the score graphic fans share after the whistle.

Both official crests, a huge score, the scorers under each side, competition
line and Genesis News branding. 1080x1350 feed image, same visual family as
the lineup card so the page's matchday sequence (lineup -> result) reads as
one broadcast package.

Usage:
    from modules.result_card import make_result_card
    make_result_card("out.png", home="chiefs", away="sundowns", score="2-1",
                     scorers_home=["Du Preez 34'", "Shabalala 78'"],
                     scorers_away=["Rayners 60'"],
                     competition="Betway Premiership", venue="FNB Stadium")
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from modules.club_brand import CLUB_BRAND, official_badge
except Exception:
    from club_brand import CLUB_BRAND, official_badge  # standalone

W, H = 1080, 1350
LOGO = Path(__file__).parent.parent / "assets" / "youtube_branding" / "logo_sa_pulse.png"


def _font(size: int, bold: bool = True):
    paths = (["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
             if bold else ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"])
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _fit(img: Image.Image, box: int) -> Image.Image:
    r = min(box / img.width, box / img.height)
    return img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))),
                      Image.LANCZOS)


def _crest(card: Image.Image, club: str, cx: int, cy: int, box: int = 200):
    badge = official_badge(club)
    if not badge:
        return
    crest = _fit(Image.open(badge).convert("RGBA"), box)
    pw, ph = crest.width + 32, crest.height + 32
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=28,
                                            fill=(255, 255, 255, 238))
    card.alpha_composite(panel, (cx - pw // 2, cy - ph // 2))
    card.alpha_composite(crest, (cx - crest.width // 2, cy - crest.height // 2))


def make_result_card(
    output_path: str | Path,
    home: str,
    away: str,
    score: str,
    scorers_home: list[str] | None = None,
    scorers_away: list[str] | None = None,
    competition: str = "Betway Premiership",
    venue: str = "",
    status: str = "FULL-TIME",
    cards_home: list[str] | None = None,
    cards_away: list[str] | None = None,
) -> str | None:
    """Render the FT score graphic. Returns the path, or None on failure."""
    try:
        hb = CLUB_BRAND.get(home, {})
        ab = CLUB_BRAND.get(away, {})
        h_accent = tuple(hb.get("colors", {}).get("primary", (255, 193, 7)))
        a_accent = tuple(ab.get("colors", {}).get("primary", (255, 193, 7)))
        h_name = hb.get("name", home.title()).upper()
        a_name = ab.get("name", away.title()).upper()

        card = Image.new("RGBA", (W, H), (12, 14, 18, 255))
        d = ImageDraw.Draw(card)
        # split glow: home colour left edge, away colour right edge
        for i in range(180):
            a = int(46 * (1 - i / 180))
            d.line([(0, i), (W // 2, i)], fill=h_accent + (a,))
            d.line([(W // 2, i), (W, i)], fill=a_accent + (a,))

        # ── Header ──
        try:
            if LOGO.exists():
                lg = Image.open(LOGO).convert("RGBA").resize((92, 92), Image.LANCZOS)
                card.alpha_composite(lg, (44, 30))
        except Exception:
            pass
        hdr = (12, 14, 18) if sum(h_accent) > 550 else (255, 255, 255)
        subc = (60, 64, 70) if sum(h_accent) > 550 else (200, 205, 210)
        d.text((152, 40), "GENESIS NEWS", font=_font(36), fill=hdr)
        d.text((153, 84), "PSL & MZANSI FOOTBALL", font=_font(20, bold=False),
               fill=subc)
        sf = _font(40)
        sw = d.textlength(status, font=sf)
        d.rounded_rectangle([W - sw - 110, 38, W - 40, 106], radius=16,
                            fill=(200, 40, 40))
        d.text((W - sw - 76, 50), status, font=sf, fill=(255, 255, 255))

        # ── Crests + score ──
        cy = 430
        _crest(card, home, 230, cy)
        _crest(card, away, W - 230, cy)
        d = ImageDraw.Draw(card)

        score_txt = str(score).replace("-", " - ").replace("  ", " ")
        scf = _font(150)
        scw = d.textlength(score_txt, font=scf)
        d.text((W // 2 - scw / 2 + 4, cy - 95 + 4), score_txt, font=scf,
               fill=(0, 0, 0))
        d.text((W // 2 - scw / 2, cy - 95), score_txt, font=scf,
               fill=(255, 255, 255))

        nf = _font(34)
        for name, cx in ((h_name, 230), (a_name, W - 230)):
            f, nm = nf, name
            while d.textlength(nm, font=f) > 380 and f.size > 22:
                f = _font(f.size - 2)
            d.text((cx - d.textlength(nm, font=f) / 2, cy + 138), nm, font=f,
                   fill=(255, 255, 255))

        # ── Scorers ──
        y0 = cy + 220
        d.line([(W // 2, y0), (W // 2, y0 + 260)], fill=(70, 75, 82), width=3)
        gf = _font(30, bold=False)
        for scorers, cx, acc in ((scorers_home or [], 270, h_accent),
                                 (scorers_away or [], W - 270, a_accent)):
            y = y0 + 10
            for s in scorers[:6]:
                tw = d.textlength(s, font=gf)
                x = cx - tw / 2
                d.ellipse([x - 26, y + 9, x - 10, y + 25], fill=acc,
                          outline=(255, 255, 255), width=2)   # goal dot
                d.text((x, y), s, font=gf, fill=(225, 230, 235))
                y += 44
            if not scorers:
                d.text((cx - d.textlength("—", font=gf) / 2, y), "—", font=gf,
                       fill=(120, 125, 130))

        # ── Bookings — yellow squares, the detail fans argue about ──
        cf = _font(26, bold=False)
        for cards, cx in ((cards_home or [], 270), (cards_away or [], W - 270)):
            y = y0 + 290
            for c in cards[:5]:
                tw = d.textlength(c, font=cf)
                x = cx - tw / 2
                d.rectangle([x - 24, y + 4, x - 8, y + 26], fill=(255, 205, 40),
                            outline=(120, 95, 10), width=2)   # yellow card
                d.text((x, y), c, font=cf, fill=(200, 205, 212))
                y += 38

        # ── Footer ──
        info = " · ".join(x for x in (competition, venue) if x)
        if info:
            inf = _font(28, bold=False)
            d.text((W // 2 - d.textlength(info, font=inf) / 2, H - 130), info,
                   font=inf, fill=(210, 215, 220))
        foot = "GENESIS NEWS · PSL & MZANSI FOOTBALL"
        ff = _font(24, bold=False)
        d.text((W // 2 - d.textlength(foot, font=ff) / 2, H - 78), foot,
               font=ff, fill=(170, 175, 180))
        d.rectangle([W // 2 - 160, H - 34, W // 2, H - 28], fill=h_accent)
        d.rectangle([W // 2, H - 34, W // 2 + 160, H - 28], fill=a_accent)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        card.convert("RGB").save(output_path, quality=95)
        print(f"[ResultCard] {output_path.name} ({home} {score} {away})")
        return str(output_path)
    except Exception as e:
        print(f"[ResultCard] failed: {e}")
        return None


if __name__ == "__main__":
    make_result_card(
        "output/result_test.png", home="chiefs", away="sundowns", score="2-1",
        scorers_home=["Du Preez 34'", "Shabalala 78'"], scorers_away=["Rayners 60'"],
        venue="FNB Stadium",
    )
