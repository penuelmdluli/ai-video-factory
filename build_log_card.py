"""
The Betway Log post — the full table as a shareable card.

Fans screenshot league tables more than any other graphic. Full 16 teams,
big-three rows in club colours, movement arrows vs the last posted table.
Posted after each weekend round (Mon 09:00) and on demand.

Usage: python build_log_card.py [--post]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
SNAP = Path("data/log_snapshot.json")
LOGO = Path("assets/youtube_branding/logo_sa_pulse.png")
BIG = {"chiefs": (255, 193, 7), "pirates": (235, 235, 235),
       "sundowns": (255, 205, 30)}


def _font(size, bold=True):
    try:
        return ImageFont.truetype(
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


async def build(post: bool):
    from modules.psl_standings import get_log
    rows = await get_log(16, force_refresh=True)
    if not rows:
        print("[Log] no standings")
        return
    try:
        prev = json.loads(SNAP.read_text(encoding="utf-8"))
    except Exception:
        prev = {}

    img = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(img)
    for i in range(140):
        a = 1 - i / 140
        d.line([(0, i), (W, i)], fill=(int(30 * a) + 12, int(60 * a) + 14,
                                       int(30 * a) + 18))
    try:
        lg = Image.open(LOGO).convert("RGBA").resize((110, 110))
        img.paste(lg, (44, 30), lg)
    except Exception:
        pass
    d.text((172, 44), "GENESIS NEWS", font=_font(40), fill=(255, 255, 255))
    d.text((174, 94), "THE BETWAY LOG", font=_font(26, False), fill=(255, 193, 7))
    stamp = datetime.now().strftime("%d %b %Y")
    sf = _font(26, False)
    d.text((W - 44 - d.textlength(stamp, font=sf), 60), stamp, font=sf,
           fill=(180, 185, 192))

    hf = _font(26)
    y0 = 200
    for label, x in (("#", 70), ("CLUB", 210), ("P", 700), ("PTS", 820),
                     ("", 960)):
        d.text((x, y0 - 46), label, font=hf, fill=(150, 155, 162))
    row_h = 96
    rf, pf = _font(34), _font(34)
    mf = _font(28)
    for i, r in enumerate(rows):
        y = y0 + i * row_h
        key = r.get("team_key", "")
        hot = key in BIG
        if hot:
            acc = BIG[key]
            d.rounded_rectangle([44, y - 8, W - 44, y + row_h - 24], radius=16,
                                fill=acc)
            fg = (10, 10, 10)
        else:
            if i % 2 == 0:
                d.rounded_rectangle([44, y - 8, W - 44, y + row_h - 24],
                                    radius=16, fill=(19, 22, 28))
            fg = (232, 236, 242)
        d.text((70, y + 8), str(r["rank"]), font=rf, fill=fg)
        d.text((210, y + 8), r["name"][:20], font=rf, fill=fg)
        d.text((700, y + 8), str(r["played"]), font=pf, fill=fg)
        d.text((820, y + 8), str(r["points"]), font=pf, fill=fg)
        # movement vs last posted table
        old = prev.get(key or r["name"])
        if old:
            diff = old - r["rank"]
            if diff > 0:
                d.polygon([(966, y + 34), (986, y + 34), (976, y + 14)],
                          fill=(60, 190, 90))          # up
            elif diff < 0:
                d.polygon([(966, y + 14), (986, y + 14), (976, y + 34)],
                          fill=(215, 65, 65))          # down
            else:
                d.rectangle([966, y + 22, 986, y + 28], fill=(120, 126, 134))

    foot = "Where does YOUR team finish this season? 👇"
    ff = _font(30)
    d.text(((W - d.textlength(foot.replace('👇', ''), font=ff)) / 2, H - 120),
           foot.replace(" 👇", ""), font=ff, fill=(255, 193, 7))

    out = Path("output/matchday") / f"log_{datetime.now():%Y%m%d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95)
    print(f"[Log] card -> {out}")

    SNAP.parent.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps({r.get("team_key") or r["name"]: r["rank"]
                                for r in rows}, indent=2), encoding="utf-8")
    if post:
        from matchday import _post_photo
        top = rows[0]
        caption = (f"📊 THE BETWAY LOG — {stamp}\n\n{top['name']} lead on "
                   f"{top['points']} points. Where does your team finish this "
                   f"season?\n\n#PSL #BetwayPremiership #KaizerChiefs "
                   f"#OrlandoPirates #MamelodiSundowns")
        await _post_photo(str(out), caption,
                          "Call your team's final position — screenshot this and "
                          "we'll check back in May 👇")
    return str(out)


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build("--post" in sys.argv))
