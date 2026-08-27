"""
The selection debate — "who starts, and why?"

Owner call 2026-08-24: analyse the strikers Chiefs have, argue who starts over
whom, and make it a debate. Engagement on this page comes from disagreement, so
the piece is built to be argued with rather than agreed with.

HONESTY RULE — read before adding anything here. The squad cache holds names,
shirt numbers and positions. It holds NO goals, NO appearances, NO minutes. So
this format never states a statistic. It names the real contenders, frames the
real question and hands it to the fans. The moment someone wires a stats source
in, put the numbers on screen; until then, inventing "8 goals in 12" to make the
video sound authoritative would be a lie the audience can check in one search.

    python build_debate_video.py --club chiefs --group forwards
    python build_debate_video.py --club chiefs --group forwards --post
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
    "forwards":   ("FW", "STRIKER DEBATE",   "strikers"),
    "attackers":  ("FW", "ATTACK DEBATE",    "attackers"),
    "midfield":   ("MF", "MIDFIELD DEBATE",  "midfielders"),
    "defence":    ("DF", "DEFENCE DEBATE",   "defenders"),
    "keepers":    ("GK", "KEEPER DEBATE",    "goalkeepers"),
}


def _log(m):
    print(f"[Debate] {m}", flush=True)


def contenders(club: str, pos_prefix: str) -> list[dict]:
    """Squad players in a position group, under the names FANS use.

    The owner name-fix map is applied here rather than in each builder.
    Owner call 2026-08-26: "macheke is kwinika, the fans know kwinika" - and
    on 2026-08-27 three new formats went straight past that rule because they
    read this function's raw output and printed the last token of the name.
    A rule enforced in every caller is a rule that gets missed by the next
    caller, so it lives at the source.
    """
    from modules.psl_squads import fix_name, fix_surname
    cache = json.loads((ROOT / "data" / "psl_squads_cache.json").read_text(encoding="utf-8"))
    squad = (cache.get(club) or {}).get("squad") or []
    out = []
    for p in squad:
        if (p.get("pos") or "").upper().startswith(pos_prefix):
            name = (p.get("name") or "").strip()
            if not name:
                continue
            name = fix_name(name)
            parts = name.split()
            if parts:
                fixed = fix_surname(parts[-1])
                if fixed != parts[-1]:
                    name = " ".join(parts[:-1] + [fixed])
            out.append({"no": str(p.get("no", "") or "").strip(),
                        "name": name})
    return out


def _font(size, bold=True):
    from PIL import ImageFont
    for f in (r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
              r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_debate_card(out_path, club: str, title: str, men: list[dict],
                     shown: int, question: str):
    """Contenders board. `shown` controls the reveal; slots never move."""
    from PIL import Image, ImageDraw
    from modules.club_brand import CLUB_BRAND, official_badge

    brand = CLUB_BRAND.get(club, {})
    accent = tuple(brand.get("colors", {}).get("primary", (255, 193, 7)))
    club_name = brand.get("name", club.title()).upper()

    card = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(card)

    # header band
    d.rectangle([0, 0, W, 132], fill=accent)
    d.text((44, 30), "GENESIS NEWS", font=_font(44), fill=(20, 20, 20))
    d.text((46, 84), "PSL & MZANSI FOOTBALL", font=_font(24, False), fill=(60, 55, 30))
    tw = d.textlength(title, font=_font(38))
    d.rounded_rectangle([W - tw - 96, 34, W - 40, 100], radius=16, fill=(190, 30, 40))
    d.text((W - tw - 68, 48), title, font=_font(38), fill=(255, 255, 255))

    # crest + club
    try:
        bp = official_badge(club)
        if bp:
            b = Image.open(bp).convert("RGBA")
            r = 190 / max(b.width, b.height)
            b = b.resize((int(b.width * r), int(b.height * r)))
            card.paste(b, (44, 168), b)
    except Exception:
        pass
    d.text((262, 214), club_name, font=_font(52), fill=(255, 255, 255))
    d.text((264, 276), f"{len(men)} in contention — one shirt",
           font=_font(28, False), fill=accent)

    # contenders, fixed rows so the reveal does not shuffle
    y0, row_h = 400, 108
    for i, m in enumerate(men):
        y = y0 + i * row_h
        if i >= shown:
            continue
        d.rounded_rectangle([44, y, W - 44, y + row_h - 18], radius=18,
                            fill=(24, 28, 34))
        d.ellipse([64, y + 12, 64 + 66, y + 78], fill=accent)
        num = m["no"] or "-"
        nw = d.textlength(num, font=_font(34))
        d.text((64 + 33 - nw / 2, y + 28), num, font=_font(34), fill=(20, 20, 20))
        d.text((156, y + 24), m["name"].upper(), font=_font(40), fill=(255, 255, 255))

    # the question
    qy = y0 + len(men) * row_h + 24
    d.rounded_rectangle([44, qy, W - 44, qy + 118], radius=20, fill=accent)
    d.text((72, qy + 22), question, font=_font(36), fill=(20, 20, 20))
    d.text((72, qy + 68), "Drop your XI in the comments", font=_font(28, False),
           fill=(70, 60, 30))

    d.text((44, H - 54), "GENESIS NEWS OPINION — NOT A CLUB ANNOUNCEMENT",
           font=_font(24, False), fill=(190, 60, 60))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    card.save(out_path)
    return str(out_path)


def narration_for(club_name: str, label: str, men: list[dict], opp: str) -> str:
    names = [m["name"].split()[-1] for m in men]
    lines = [
        f"{club_name} have {len(men)} {label} fighting for one shirt"
        + (f" against {opp}." if opp else "."),
    ]
    for m in men:
        no = f", number {m['no']}" if m["no"] else ""
        lines.append(f"{m['name']}{no}.")
    lines += [
        "Every one of them has a case.",
        "We are not going to pretend we know the coach's mind.",
        "So you tell us. Who starts, and who sits?",
        "Drop your front line in the comments and say why.",
        "Subscribe to Genesis News — we post the team sheets the moment they land.",
    ]
    return " ".join(lines)


def render(cards, out, total, reveal_frac=0.66):
    from PIL import Image
    from modules.motion_kit import _render, DARK
    frames = [Image.open(c).convert("RGB") for c in cards]
    n = len(frames)
    y = (1920 - frames[0].height) // 2
    per = (total * reveal_frac) / n
    fade = min(0.3, per * 0.35)

    def frame_fn(t):
        pos = t / per
        idx = min(n - 1, int(pos))
        into = (pos - idx) * per
        if idx < n - 1 and into > per - fade:
            u = (into - (per - fade)) / fade
            img = Image.blend(frames[idx], frames[idx + 1], min(1.0, max(0.0, u)))
        else:
            img = frames[idx]
        base = Image.new("RGB", (1080, 1920), DARK)
        base.paste(img, (0, y))
        return base

    return _render(frame_fn, out, duration=total, fps=24)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--group", default="forwards", choices=list(GROUPS))
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_debate_video.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    pos, title, label = GROUPS[a.group]
    men = contenders(a.club, pos)
    if len(men) < 2:
        _log(f"only {len(men)} {label} in the squad cache — nothing to debate")
        return 1
    # Availability gate. The squad cache lists everyone on the books, so
    # without this the format asks fans to choose between men who are not in
    # the squad — which reads as a page that does not watch the games.
    from modules.availability import confirmed_available
    men, held, ev = await confirmed_available(a.club, men)
    for m, why in held:
        _log(f"held back: {m['name']} — {why}")
    if ev:
        _log(f"evidence: {ev['match']} ({ev['date']}), {ev['squad_size']} named")
    if len(men) < 2:
        _log(f"only {len(men)} confirmed {label} — nothing to debate")
        return 1
    men = men[:6]
    _log(f"{len(men)} confirmed {label}: " + ", ".join(m["name"] for m in men))

    from modules.club_brand import CLUB_BRAND
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())

    # always the upcoming game, never one already played
    opp_name = ""
    from modules.psl_fixtures import next_fixture
    fx = await next_fixture(a.club)
    if fx:
        opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
        opp_name = CLUB_BRAND.get(opp_key, {}).get(
            "name", opp_key.replace("_", " ").title())
        _log(f"next fixture: {fx.get('home')} v {fx.get('away')} {fx.get('kickoff_sast')}")

    question = f"WHO STARTS vs {opp_name.upper()}?" if opp_name else "WHO STARTS?"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"debate_{a.club}_{a.group}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    cards = [make_debate_card(work / f"d_{i:02d}.png", a.club, title, men,
                              shown=i, question=question)
             for i in range(1, len(men) + 1)]
    _log(f"cards: {len(cards)}")

    narration = narration_for(club_name, label, men, opp_name)
    total = max(16.0, len(narration) / 15.0 + 5.0)
    silent = work / "debate_silent.mp4"
    render(cards, silent, total=total)
    _log(f"video: {total:.1f}s, {(total * 0.66) / len(cards):.1f}s per man")

    from modules.motion_kit import attach_voice
    final = await attach_voice(silent, narration, work / "final.mp4")

    cover = work / "cover.jpg"
    from PIL import Image
    Image.open(cards[-1]).convert("RGB").save(cover, quality=94)

    vs = f" vs {opp_name}" if opp_name else ""
    vid_title = f"{club_name} {label.title()}: Who Starts{vs}?"
    caption = (f"{club_name} have {len(men)} {label} for one shirt{vs}. "
               f"{', '.join(m['name'] for m in men)}.\n\n"
               f"Who starts and who sits? Tell us why 👇\n\n"
               f"#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover),
         "title": vid_title, "description": caption,
         "contenders": men, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, vid_title, caption, cover, niche=NICHE,
                          tags=["PSL", "KaizerChiefs", "Amakhosi",
                                "TeamNews", "BetwayPremiership"])
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
