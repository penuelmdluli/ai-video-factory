"""
Lineup cards — broadcast-style Starting XI / Predicted XI graphics.

The pre-match lineup drop is the single highest-engagement moment of a PSL
matchday: fans screenshot it, argue about it and share it before a ball is
kicked. This renders the XI on a proper pitch layout (not a boring list) with
both club crests, in the club's colours, as a 1080x1350 feed image.

PREDICTED XI is first-class: clearly labelled as OUR prediction (standard SA
football media format — iDiski, Soccer Laduma all run it) so it never reads as
an official team sheet.

Usage:
    from modules.lineup_card import make_lineup_card
    make_lineup_card(
        "out.png", club="chiefs", opponent="sundowns",
        players=["32 Petersen", "2 Frosler", ...],   # GK first, then by line
        formation="4-3-3", kickoff="TODAY 15:00 · FNB STADIUM",
        predicted=True,
    )
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


def _crest_panel(card: Image.Image, club: str, cx: int, cy: int, box: int = 128):
    """Crest on a white rounded sticker, centered at (cx, cy)."""
    badge = official_badge(club)
    if not badge:
        return
    crest = _fit(Image.open(badge).convert("RGBA"), box)
    pw, ph = crest.width + 24, crest.height + 24
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=22,
                                            fill=(255, 255, 255, 235))
    card.alpha_composite(panel, (cx - pw // 2, cy - ph // 2))
    card.alpha_composite(crest, (cx - crest.width // 2, cy - crest.height // 2))


def _parse_player(s: str) -> tuple[str, str]:
    """'32 Petersen' -> ('32', 'Petersen'); 'Petersen' -> ('', 'Petersen')."""
    parts = str(s).strip().split(None, 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[0], parts[1]
    return "", str(s).strip()


def make_lineup_card(
    output_path: str | Path,
    club: str,
    players: list[str],
    opponent: str = "",
    formation: str = "4-3-3",
    kickoff: str = "",
    competition: str = "Betway Premiership",
    predicted: bool = False,
    heads: dict | None = None,
    bench: list[str] | None = None,
) -> str | None:
    """Render the XI on a pitch. Returns the path, or None on failure."""
    try:
        brand = CLUB_BRAND.get(club, {})
        accent = tuple(brand.get("colors", {}).get("primary", (255, 193, 7)))
        club_name = brand.get("name", club.title()).upper()
        opp_name = CLUB_BRAND.get(opponent, {}).get("name", opponent.title()).upper()

        card = Image.new("RGBA", (W, H), (12, 14, 18, 255))
        d = ImageDraw.Draw(card)
        # club-colour glow behind the header — soft, so foreground text keeps contrast
        for i in range(150):
            a = int(38 * (1 - i / 150))
            d.line([(0, i), (W, i)], fill=accent + (a,))

        # ── Header: brand + label pill ──
        try:
            if LOGO.exists():
                lg = Image.open(LOGO).convert("RGBA").resize((92, 92), Image.LANCZOS)
                card.alpha_composite(lg, (44, 30))
        except Exception:
            pass
        hdr = (12, 14, 18) if sum(accent) > 550 else (255, 255, 255)
        sub = (60, 64, 70) if sum(accent) > 550 else (200, 205, 210)
        d.text((152, 40), "GENESIS NEWS", font=_font(36), fill=hdr)
        d.text((153, 84), "PSL & MZANSI FOOTBALL", font=_font(20, bold=False),
               fill=sub)

        label = "PREDICTED XI" if predicted else "STARTING XI"
        lf = _font(40)
        lw = d.textlength(label, font=lf)
        pill = (200, 40, 40) if predicted else accent
        txtc = (255, 255, 255) if predicted else (10, 10, 10)
        d.rounded_rectangle([W - lw - 110, 38, W - 40, 106], radius=16, fill=pill)
        d.text((W - lw - 76, 50), label, font=lf, fill=txtc)

        # ── Matchup strip ──
        my = 210
        _crest_panel(card, club, 200, my, box=132)
        d = ImageDraw.Draw(card)
        if opponent:
            vf = _font(52)
            vw = d.textlength("VS", font=vf)
            d.text((W // 2 - vw // 2 + 3, my - 32 + 3), "VS", font=vf, fill=(0, 0, 0))
            d.text((W // 2 - vw // 2, my - 32), "VS", font=vf, fill=(255, 255, 255))
            _crest_panel(card, opponent, W - 200, my, box=132)
            d = ImageDraw.Draw(card)
        nf = _font(30)
        d.text((200 - d.textlength(club_name, font=nf) / 2, my + 92), club_name,
               font=nf, fill=(255, 255, 255))
        if opponent:
            d.text((W - 200 - d.textlength(opp_name, font=nf) / 2, my + 92),
                   opp_name, font=nf, fill=(255, 255, 255))

        info = " · ".join(x for x in (competition, kickoff) if x)
        if info:
            inf = _font(26, bold=False)
            d.text((W // 2 - d.textlength(info, font=inf) / 2, my + 140), info,
                   font=inf, fill=(210, 215, 220))

        # ── Pitch ──
        # Owner call 2026-08-24: show the subs. ESPN publishes the bench on the
        # same team sheet and it was simply never read. When there is one, give
        # up a strip of pitch rather than crowding the footer.
        bench = [b for b in (bench or []) if str(b).strip()]
        bench_h = 132 if bench else 0
        px1, py1, px2, py2 = 60, 420, W - 60, H - 120 - bench_h
        d.rounded_rectangle([px1, py1, px2, py2], radius=28, fill=(18, 92, 48))
        # stripes
        for i, y in enumerate(range(py1, py2, 93)):
            if i % 2:
                d.rectangle([px1 + 4, y, px2 - 4, min(y + 93, py2 - 4)],
                            fill=(22, 102, 54))
        line = (235, 245, 235, 200)
        d.rounded_rectangle([px1 + 18, py1 + 18, px2 - 18, py2 - 18], radius=18,
                            outline=line, width=4)
        cyy = (py1 + py2) // 2
        d.ellipse([W // 2 - 90, cyy - 90, W // 2 + 90, cyy + 90], outline=line, width=4)
        d.line([px1 + 18, cyy, px2 - 18, cyy], fill=line, width=3)   # halfway line
        d.rectangle([W // 2 - 190, py2 - 118, W // 2 + 190, py2 - 18],
                    outline=line, width=4)   # our box (bottom)
        d.rectangle([W // 2 - 190, py1 + 18, W // 2 + 190, py1 + 118],
                    outline=line, width=4)   # their box (top)
        for cx_, cy_ in ((px1 + 18, py1 + 18), (px2 - 18, py1 + 18),
                         (px1 + 18, py2 - 18), (px2 - 18, py2 - 18)):
            d.arc([cx_ - 26, cy_ - 26, cx_ + 26, cy_ + 26], 0, 360, fill=line, width=3)

        # ── Formation rows (GK bottom, attack top) ──
        rows = [1] + [max(1, int(n)) for n in str(formation).split("-") if n.strip().isdigit()]
        need = sum(rows)
        players = [str(p) for p in players][:need]
        row_players, idx = [], 0
        for n in rows:
            row_players.append(players[idx:idx + n])
            idx += n

        n_rows = len(row_players)
        pitch_h = (py2 - 40) - (py1 + 60)
        pf_num, pf_name = _font(26), _font(23)
        heads = heads or {}
        head_credits = []
        for r, row in enumerate(row_players):
            # r=0 GK at the bottom → highest y
            y = int((py2 - 60) - (pitch_h / max(1, n_rows - 1)) * r) if n_rows > 1 \
                else (py1 + py2) // 2
            for c, p in enumerate(row):
                x = int(W * (c + 1) / (len(row) + 1))
                # A blank slot holds its place but draws nothing. The reveal
                # animation in build_lineup_video pads the XI to eleven so that
                # x — which is derived from len(row) — stays fixed while the
                # side fills up. Without this, every man already on the pitch
                # slid sideways each time another was added.
                if not str(p).strip():
                    continue
                num, name = _parse_player(p)
                rr = 37
                head = heads.get(p)
                if head:
                    # real face in a club-colour ring
                    try:
                        hp = Image.open(head["path"]).convert("RGBA") \
                            .resize((rr * 2 - 6, rr * 2 - 6), Image.LANCZOS)
                        d.ellipse([x - rr, y - rr - 26, x + rr, y + rr - 26],
                                  fill=(255, 255, 255), outline=accent, width=5)
                        card.alpha_composite(hp, (x - rr + 3, y - rr - 23))
                        d = ImageDraw.Draw(card)
                        if head.get("credit"):
                            head_credits.append(head["credit"])
                        if num:   # small number chip on the ring
                            nf = _font(20)
                            nw = d.textlength(num, font=nf)
                            d.ellipse([x + rr - 26, y + rr - 52, x + rr + 2, y + rr - 24],
                                      fill=accent, outline=(255, 255, 255), width=2)
                            numc = (255, 255, 255) if sum(accent) < 380 else (10, 10, 10)
                            d.text((x + rr - 12 - nw / 2, y + rr - 48), num,
                                   font=nf, fill=numc)
                    except Exception:
                        head = None
                if not head:
                    # jersey dot
                    d.ellipse([x - rr, y - rr - 26, x + rr, y + rr - 26],
                              fill=accent, outline=(255, 255, 255), width=3)
                    if num:
                        nw = d.textlength(num, font=pf_num)
                        numc = (255, 255, 255) if sum(accent) < 380 else (10, 10, 10)
                        d.text((x - nw / 2, y - 46), num, font=pf_num, fill=numc)
                # name pill under the marker — crisper than raw text on grass
                name = name.upper()
                f = pf_name
                while d.textlength(name, font=f) > 158 and f.size > 14:
                    f = _font(f.size - 2)
                nw = d.textlength(name, font=f)
                pill = Image.new("RGBA", (int(nw) + 26, f.size + 14), (0, 0, 0, 0))
                ImageDraw.Draw(pill).rounded_rectangle(
                    [0, 0, pill.width - 1, pill.height - 1], radius=10,
                    fill=(8, 10, 14, 185))
                card.alpha_composite(pill, (int(x - pill.width / 2), y + 15))
                d = ImageDraw.Draw(card)
                d.text((x - nw / 2, y + 21), name, font=f, fill=(255, 255, 255))

        # ── Footer ──
        foot = ("GENESIS NEWS PREDICTION — NOT THE OFFICIAL TEAM SHEET"
                if predicted else "GENESIS NEWS · PSL & MZANSI FOOTBALL")
        ff = _font(24, bold=False)
        d.text((W // 2 - d.textlength(foot, font=ff) / 2, H - 82), foot,
               font=ff, fill=(200, 40, 40) if predicted else (170, 175, 180))
        if head_credits:
            # CC licences require visible attribution for every face used
            cf = _font(16, bold=False)
            cred = "photos: " + " · ".join(dict.fromkeys(head_credits))[:140]
            d.text((W // 2 - d.textlength(cred, font=cf) / 2, H - 50), cred,
                   font=cf, fill=(150, 155, 160))
        d.rectangle([W // 2 - 100, H - 34, W // 2 + 100, H - 28], fill=accent)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if bench:
            by = py2 + 26
            d.text((px1 + 6, by), "SUBS", font=_font(26), fill=accent)
            row, x, y = 0, px1 + 6, by + 34
            for b in bench[:9]:
                txt = str(b).upper()
                w = d.textlength(txt, font=_font(23)) + 26
                if x + w > px2 - 6:
                    row += 1
                    if row > 1:
                        break
                    x, y = px1 + 6, y + 38
                d.rounded_rectangle([x, y, x + w, y + 32], radius=10,
                                    fill=(28, 32, 38))
                d.text((x + 13, y + 5), txt, font=_font(23), fill=(226, 230, 235))
                x += w + 10

        card.convert("RGB").save(output_path, quality=95)

        print(f"[LineupCard] {output_path.name} ({label}, {formation})")
        return str(output_path)
    except Exception as e:
        print(f"[LineupCard] failed: {e}")
        return None


if __name__ == "__main__":
    make_lineup_card(
        "output/lineup_test.png", club="chiefs", opponent="sundowns",
        formation="4-3-3", kickoff="TODAY 15:00 · FNB STADIUM", predicted=True,
        players=["32 Petersen", "2 Frosler", "5 Miguel", "4 Dove", "3 Cross",
                 "6 Sithebe", "8 Maart", "10 Shabalala", "7 Saile", "9 Duba",
                 "11 Velebayi"],
    )
