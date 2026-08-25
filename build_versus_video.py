"""
Head to head — two players, one shirt, and a real reason to argue.

Owner call 2026-08-24: compare the Chiefs keepers and say who should start.

Why head-to-head rather than another list. Facebook numbers on this page,
25 reels to 24 Aug:

    38,871  Count the passes (interactive)      272 likes    5 comments
    16,024  STRIKER debate (6 names, 09:19)     420 likes   65 comments
     9,550  Predicted XI (09:27)                218 likes  110 comments
     2,068  DEFENCE debate (13:02)               59 likes    7 comments
     1,534  MIDFIELD debate (12:41)              18 likes    0 comments
     1,066  median of everything else

Same format, same day: strikers did 16k and midfield did 1.5k. Two things
separate them — the morning slot, and how emotive the position is. A four-name
goalkeeper list would land like the midfield one. A straight Petersen-versus-
Bvuma argument is the one Chiefs fans have actually been having for years.

FACTS ONLY. There are no saves, no clean sheets and no minutes anywhere in
this pipeline. What there IS: the real team sheet — who started, who was named
on the bench, who was not in the squad at all. That is enough to make the case
and it cannot be contradicted, which is the whole point.

    python build_versus_video.py --club chiefs --group keepers
    python build_versus_video.py --club chiefs --group keepers --post
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "sa_pulse"
W, H = 1080, 1350

GROUPS = {
    "keepers":  ("GK", "KEEPER DEBATE",  "goalkeeper"),
    "forwards": ("FW", "STRIKER DEBATE", "striker"),
    "midfield": ("MF", "MIDFIELD BATTLE", "midfield spot"),
    "defence":  ("DF", "DEFENCE BATTLE", "defensive spot"),
}


def _log(m):
    print(f"[Versus] {m}", flush=True)


def _font(size, bold=True):
    from PIL import ImageFont
    for f in ((r"C:\Windows\Fonts\arialbd.ttf" if bold
               else r"C:\Windows\Fonts\arial.ttf"),
              r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def squad_group(club: str, prefix: str) -> list[dict]:
    cache = json.loads((ROOT / "data" / "psl_squads_cache.json")
                       .read_text(encoding="utf-8"))
    out = []
    for p in (cache.get(club) or {}).get("squad") or []:
        if (p.get("pos") or "").upper().startswith(prefix):
            nm = (p.get("name") or "").strip()
            if nm:
                out.append({"no": str(p.get("no", "") or "").strip(), "name": nm})
    return out


async def status_from_sheet(club: str, men: list[dict]) -> dict:
    """{surname: (status, detail)} straight off the last real team sheet."""
    from modules.psl_fixtures import last_lineup
    sheet = await last_lineup(club)
    if not sheet:
        return {}
    def sur(e):
        parts = str(e).split(None, 1)
        return (parts[1] if len(parts) > 1 else str(e)).strip().lower()
    started = {sur(p) for p in sheet["players"]}
    benched = {sur(b) for b in sheet.get("bench", [])}
    where = f"v {sheet['match'].split(' v ')[-1]}"
    out = {}
    for m in men:
        s = m["name"].split()[-1].lower()
        if s in started:
            out[s] = ("STARTED", f"started {where}")
        elif s in benched:
            out[s] = ("ON THE BENCH", f"named as cover {where}")
        else:
            out[s] = ("NOT IN SQUAD", f"not in the matchday squad {where}")
    return out


def make_vs_card(out_path, club, title, a, b, status, question, reveal=2,
                 others=None):
    """Two-up comparison. reveal 0=neither, 1=left only, 2=both."""
    from PIL import Image, ImageDraw
    from modules.club_brand import CLUB_BRAND, official_badge

    brand = CLUB_BRAND.get(club, {})
    accent = tuple(brand.get("colors", {}).get("primary", (255, 193, 7)))
    card = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(card)

    d.rectangle([0, 0, W, 132], fill=accent)
    d.text((44, 30), "GENESIS NEWS", font=_font(44), fill=(20, 20, 20))
    d.text((46, 84), "PSL & MZANSI FOOTBALL", font=_font(24, False), fill=(60, 55, 30))
    tw = d.textlength(title, font=_font(38))
    d.rounded_rectangle([W - tw - 96, 34, W - 40, 100], radius=16, fill=(190, 30, 40))
    d.text((W - tw - 68, 48), title, font=_font(38), fill=(255, 255, 255))

    try:
        bp = official_badge(club)
        if bp:
            im = Image.open(bp).convert("RGBA")
            r = 120 / max(im.width, im.height)
            im = im.resize((int(im.width * r), int(im.height * r)))
            card.paste(im, (W // 2 - im.width // 2, 152), im)
    except Exception:
        pass

    # VS divider
    d.line([W // 2, 300, W // 2, H - 250], fill=(40, 46, 54), width=3)
    vf = _font(72)
    vw = d.textlength("VS", font=vf)
    d.ellipse([W // 2 - 62, 596, W // 2 + 62, 720], fill=(12, 14, 18),
              outline=accent, width=4)
    d.text((W // 2 - vw / 2, 622), "VS", font=vf, fill=accent)

    for side, man in ((0, a), (1, b)):
        if side + 1 > reveal:
            continue
        cx = W // 4 if side == 0 else 3 * W // 4
        d.ellipse([cx - 62, 320, cx + 62, 444], fill=accent)
        num = man["no"] or "-"
        nf = _font(58)
        nw = d.textlength(num, font=nf)
        d.text((cx - nw / 2, 350), num, font=nf, fill=(20, 20, 20))

        nm = man["name"].split()[-1].upper()
        f = _font(46)
        while d.textlength(nm, font=f) > W // 2 - 60 and f.size > 22:
            f = _font(f.size - 2)
        d.text((cx - d.textlength(nm, font=f) / 2, 470), nm, font=f,
               fill=(255, 255, 255))
        first = man["name"].split()[0].upper()
        ff = _font(26, False)
        d.text((cx - d.textlength(first, font=ff) / 2, 526), first, font=ff,
               fill=(150, 156, 164))

        st, detail = status.get(man["name"].split()[-1].lower(),
                                ("", "no team-sheet record"))
        if st:
            col = ((34, 160, 84) if st == "STARTED"
                   else (210, 150, 30) if st == "ON THE BENCH" else (190, 55, 55))
            sf = _font(28)
            sw = d.textlength(st, font=sf)
            d.rounded_rectangle([cx - sw / 2 - 22, 770, cx + sw / 2 + 22, 826],
                                radius=14, fill=col)
            d.text((cx - sw / 2, 782), st, font=sf, fill=(255, 255, 255))
        df = _font(23, False)
        words, line, ly = detail.split(), "", 856
        for wd in words:
            t = (line + " " + wd).strip()
            if d.textlength(t, font=df) > W // 2 - 80:
                d.text((cx - d.textlength(line, font=df) / 2, ly), line,
                       font=df, fill=(170, 176, 184))
                line, ly = wd, ly + 30
            else:
                line = t
        if line:
            d.text((cx - d.textlength(line, font=df) / 2, ly), line, font=df,
                   fill=(170, 176, 184))

    # The rest of the group, in the gap between the two profiles and the
    # question. Leaving it empty wasted a third of the card, and these men are
    # part of the argument even if they are not the headline.
    others = [o for o in (others or [])]
    if others and reveal >= 2:
        oy = 990
        d.text((W // 2 - d.textlength("ALSO IN THE SQUAD", font=_font(24)) / 2, oy),
               "ALSO IN THE SQUAD", font=_font(24), fill=(120, 126, 134))
        chips, x0 = [], 0
        of = _font(24)
        for o in others[:4]:
            t = f"{o['no']} {o['name'].split()[-1].upper()}".strip()
            chips.append((t, d.textlength(t, font=of) + 30))
        total_w = sum(c[1] for c in chips) + 12 * (len(chips) - 1)
        x = W // 2 - total_w / 2
        for t, cw in chips:
            d.rounded_rectangle([x, oy + 36, x + cw, oy + 78], radius=10,
                                fill=(26, 30, 36))
            d.text((x + 15, oy + 45), t, font=of, fill=(200, 206, 214))
            x += cw + 12

    qy = H - 232
    d.rounded_rectangle([44, qy, W - 44, qy + 118], radius=20, fill=accent)
    qf = _font(38)
    while d.textlength(question, font=qf) > W - 140 and qf.size > 22:
        qf = _font(qf.size - 2)
    d.text((W // 2 - d.textlength(question, font=qf) / 2, qy + 22), question,
           font=qf, fill=(20, 20, 20))
    sub = "Comment your pick"
    sf2 = _font(26, False)
    d.text((W // 2 - d.textlength(sub, font=sf2) / 2, qy + 70), sub, font=sf2,
           fill=(70, 60, 30))

    d.text((44, H - 54), "GENESIS NEWS OPINION — NOT A CLUB ANNOUNCEMENT",
           font=_font(24, False), fill=(190, 60, 60))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    card.save(out_path)
    return str(out_path)


def narration(club_name, label, a, b, status, others, opp):
    def line_for(m):
        st, detail = status.get(m["name"].split()[-1].lower(), ("", ""))
        return f"{m['name']}, number {m['no']}. {detail.capitalize()}." if detail \
            else f"{m['name']}, number {m['no']}."
    out = [f"Who should be {club_name}'s {label}"
           + (f" against {opp}?" if opp else "?"),
           line_for(a), line_for(b)]
    if others:
        out.append("Also in the squad: "
                   + ", ".join(o["name"].split()[-1] for o in others) + ".")
    out += [
        "We are not going to invent numbers we do not have.",
        "That is the team sheet. The argument is yours.",
        "Who starts? Comment your pick and say why.",
        "Subscribe to Genesis News — we post the team sheets the moment they land.",
    ]
    return " ".join(out)


def render(cards, out, total):
    from PIL import Image
    from modules.motion_kit import _render, DARK
    frames = [Image.open(c).convert("RGB") for c in cards]
    n = len(frames)
    y = (1920 - frames[0].height) // 2
    per = min(2.6, (total * 0.42) / max(1, n))

    def frame_fn(t):
        idx = min(n - 1, int(t / per))
        base = Image.new("RGB", (1080, 1920), DARK)
        base.paste(frames[idx], (0, y))
        return base

    return _render(frame_fn, out, duration=total, fps=24)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--group", default="keepers", choices=list(GROUPS))
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_versus_video.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    prefix, title, label = GROUPS[a.group]
    men = squad_group(a.club, prefix)
    if len(men) < 2:
        _log(f"only {len(men)} in {a.group} — nothing to compare")
        return 1

    status = await status_from_sheet(a.club, men)
    # The two worth arguing about: whoever actually started, against the
    # best-known name who did NOT make the squad. That contrast IS the debate.
    def rank(m):
        st = status.get(m["name"].split()[-1].lower(), ("", ""))[0]
        return {"STARTED": 0, "ON THE BENCH": 2, "NOT IN SQUAD": 1}.get(st, 3)
    ordered = sorted(men, key=rank)
    left, right = ordered[0], ordered[1]
    others = [m for m in men if m not in (left, right)]
    _log(f"{left['name']} ({status.get(left['name'].split()[-1].lower(), ('?',))[0]}) "
         f"vs {right['name']} ({status.get(right['name'].split()[-1].lower(), ('?',))[0]})")

    from modules.club_brand import CLUB_BRAND
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_name = ""
    from modules.psl_fixtures import next_fixture
    fx = await next_fixture(a.club)
    if fx:
        k = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
        opp_name = CLUB_BRAND.get(k, {}).get("name", k.replace("_", " ").title())

    q = f"WHO STARTS vs {opp_name.upper()}?" if opp_name else "WHO STARTS?"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"versus_{a.club}_{a.group}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    cards = [make_vs_card(work / f"vs_{i}.png", a.club, title, left, right,
                          status, q, reveal=i, others=others)
             for i in (1, 2)]
    _log(f"cards: {len(cards)}")

    text = narration(club_name, label, left, right, status, others, opp_name)
    total = max(18.0, len(text) / 15.0 + 4.0)
    silent = work / "vs_silent.mp4"
    render(cards, silent, total=total)

    from modules.motion_kit import attach_voice
    final = await attach_voice(silent, text, work / "final.mp4")
    cover = work / "cover.jpg"
    from PIL import Image
    Image.open(cards[-1]).convert("RGB").save(cover, quality=94)

    vs = f" vs {opp_name}" if opp_name else ""
    vid_title = (f"{club_name} {label.title()}: "
                 f"{left['name'].split()[-1]} or {right['name'].split()[-1]}?")
    caption = (f"{left['name']} or {right['name']} — who should be "
               f"{club_name}'s {label}{vs}?\n\n"
               f"{left['name'].split()[-1]}: "
               f"{status.get(left['name'].split()[-1].lower(), ('', ''))[1]}.\n"
               f"{right['name'].split()[-1]}: "
               f"{status.get(right['name'].split()[-1].lower(), ('', ''))[1]}.\n\n"
               f"Comment your pick 👇\n\n"
               f"#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover),
         "title": vid_title, "description": caption,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, vid_title, caption, cover, niche=NICHE,
                          tags=["PSL", "KaizerChiefs", "Amakhosi", "TeamNews"])
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
