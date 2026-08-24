"""
Line-up video + analysis — the format the audience actually asks for.

Owner call 2026-08-24: "make a line up video and also lineup analysis, with top
class graphics". The graphics already existed — modules/lineup_card.py renders a
broadcast-grade XI on a pitch with real crests — but nothing in the pipeline
ever called it. This wires it into a posted video.

Why it is built from graphics and not faces: no Kaizer Chiefs player has a
freely-licensed photograph on Wikimedia Commons (checked 2026-08-24, 0 of 39).
PSL photography belongs to BackpagePix and Getty. A pitch graphic carrying real
names, real numbers and the real crest is both legal and, at feed size, clearer
than a face.

    python build_lineup_video.py --club chiefs --opponent sundowns
    python build_lineup_video.py --club chiefs --post
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "sa_pulse"
W, H = 1080, 1920

FORMATIONS = {"4-3-3": [1, 4, 3, 3], "4-2-3-1": [1, 4, 2, 3, 1],
              "3-5-2": [1, 3, 5, 2], "4-4-2": [1, 4, 4, 2]}


def _log(m):
    print(f"[Lineup] {m}", flush=True)


async def pick_xi_real(club: str) -> tuple[list[str], str, str, list[str]]:
    """(XI, formation, provenance) from the club's most recent REAL team sheet.

    Squad-list order is not a team. Basing the side on who actually started
    last time is the only version a fan cannot call invented — and it is what
    put Phili, Monyane, Mmodi, Moloisane and Mthethwa back in the XI after the
    first cut dropped all five despite every one of them having started.
    """
    from modules.psl_fixtures import last_lineup
    sheet = await last_lineup(club)
    if sheet:
        return (sheet["players"], sheet["formation"],
                f"last XI v {sheet['match'].split(' v ')[-1]} ({sheet['date']})",
                sheet.get("bench", []))
    return [], "", "", []


def pick_xi(club: str, formation: str = "4-3-3") -> list[str]:
    """A plausible XI from the real cached squad — real names, real numbers.

    Chosen by listed position so the shape is honest: goalkeeper in goal,
    defenders in the back line. It is a prediction and the card says so.
    """
    cache = json.loads((ROOT / "data" / "psl_squads_cache.json").read_text(encoding="utf-8"))
    squad = (cache.get(club) or {}).get("squad") or []
    by_pos = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in squad:
        pos = (p.get("pos") or "").upper()
        bucket = ("GK" if pos.startswith("G") else
                  "DF" if pos.startswith("D") else
                  "MF" if pos.startswith("M") else
                  "FW" if pos else "")
        if bucket:
            by_pos[bucket].append(p)
    want = FORMATIONS.get(formation, FORMATIONS["4-3-3"])
    n_gk, n_df = want[0], want[1]
    n_fw = want[-1]
    n_mf = 11 - n_gk - n_df - n_fw
    plan = [("GK", n_gk), ("DF", n_df), ("MF", n_mf), ("FW", n_fw)]

    xi = []
    for bucket, n in plan:
        pool = by_pos.get(bucket, [])
        for p in pool[:n]:
            no = str(p.get("no", "") or "").strip()
            surname = (p.get("name", "") or "").split()[-1]
            xi.append(f"{no} {surname}".strip())
    return xi[:11]


def analysis_lines(club: str, opponent: str, formation: str, xi: list[str],
                   provenance: str = "", bench: list[str] | None = None) -> list[str]:
    """Narration. Built from what is actually on the card, so it can never
    describe a player who is not in the XI."""
    from modules.club_brand import CLUB_BRAND
    name = CLUB_BRAND.get(club, {}).get("name", club.title())
    opp = CLUB_BRAND.get(opponent, {}).get("name", opponent.title()) if opponent else ""
    parts = formation.split("-")
    keeper = xi[0].split(" ", 1)[-1] if xi else ""
    back = [p.split(" ", 1)[-1] for p in xi[1:1 + int(parts[0])]] if len(parts) > 1 else []
    front = [p.split(" ", 1)[-1] for p in xi[-int(parts[-1]):]] if len(parts) > 1 else []

    bench = bench or []
    lines = [
        f"This is the {name} eleven Genesis News expects"
        + (f" against {opp}." if opp else "."),
    ]
    # Saying WHERE the side comes from is what makes it undeniable. An XI
    # nobody can argue with is one built on the last team sheet, not on a guess.
    if provenance:
        lines.append(f"This is the side that started {provenance}.")
    lines.append(f"The shape is {formation.replace('-', ' ')}.")
    if keeper:
        lines.append(f"{keeper} starts in goal.")
    if back:
        lines.append("The back line reads " + ", ".join(back) + ".")
    if front:
        lines.append("Up top, " + " and ".join(front) + " carry the goals.")
    lines += [
        (("On the bench: " + ", ".join(b.split(" ", 1)[-1] for b in bench[:5]) + ".")
         if bench else ""),
        "That is the Genesis News call, not the official team sheet.",
        "Tell us who you would drop in the comments.",
        "Subscribe to Genesis News — we post the team sheets the moment they land.",
    ]
    return [l for l in lines if l]


def build_frames(work: Path, club: str, opponent: str, formation: str,
                 xi: list[str], kickoff: str,
                 bench: list[str] | None = None) -> list[Path]:
    """One card per revealed player — the build-up animation."""
    from modules.lineup_card import make_lineup_card
    cards = []
    for n in range(1, len(xi) + 1):
        out = work / f"reveal_{n:02d}.png"
        # pad to a full XI so row widths — and therefore x positions — never
        # change between frames; blank entries render nothing
        revealed = xi[:n] + [""] * (len(xi) - n)
        p = make_lineup_card(out, club=club, players=revealed, opponent=opponent,
                             formation=formation, kickoff=kickoff,
                             competition="Betway Premiership", predicted=True,
                             # bench on EVERY frame: it shortens the pitch, so
                             # adding it only at the end would move all eleven
                             # markers on the last card and smear the crossfade
                             bench=bench)
        if p:
            cards.append(Path(p))
    return cards


def render_video(cards: list[Path], out: Path, total: float,
                 reveal_frac: float = 0.62, formation: str = "4-3-3",
                 players: list[str] | None = None, bg: Path | None = None,
                 bench: bool = False, accent=(255, 193, 7)) -> str:
    """Reveal the XI one man at a time, then hold the full card.

    Owner note 2026-08-24: the first cut fired all eleven in about four
    seconds and then sat on a static card for the remaining twenty-five —
    the reveal was over before the narration had named anyone. The build now
    spans most of the video so each man lands roughly as he is talked about,
    and consecutive cards cross-fade instead of hard-cutting.
    """
    from PIL import Image
    from modules.motion_kit import _render, DARK

    frames = [Image.open(c).convert("RGB") for c in cards]
    n = len(frames)
    canvas_y = (H - frames[0].height) // 2
    reveal_t = total * reveal_frac
    per = reveal_t / n                       # seconds per player
    fade = min(0.28, per * 0.35)             # tail of each slot spent blending

    # Phase two: once the side is named, animate the SHAPE. Owner call — the
    # reveal ends around 16s and the rest of the runtime should show the block
    # moving as one, forward into an attacking shape and back into a defensive
    # one, so it reads like a team rather than eleven dots.
    motion_t = max(0.0, total - reveal_t)
    bg_img = Image.open(bg).convert("RGB") if bg and Path(bg).exists() else None
    if motion_t > 4 and bg_img is not None and players:
        u = motion_t / 5.0
        plan = [("base", u * 0.7), ("attack", u * 1.4), ("base", u * 0.9),
                ("defend", u * 1.4), ("base", u * 0.6)]
    else:
        plan = None

    def frame_fn(t):
        base = Image.new("RGB", (W, H), DARK)
        if plan and t >= reveal_t:
            from modules.tactics_motion import frame as tframe
            img = tframe(bg_img, formation, players, t - reveal_t, plan,
                         accent=accent, bench=bench)
        else:
            pos = t / per
            idx = min(n - 1, int(pos))
            into = (pos - idx) * per         # seconds into this player's slot
            if idx < n - 1 and into > per - fade:
                # cross-fade into the next card so the reveal reads as motion
                u2 = (into - (per - fade)) / fade
                img = Image.blend(frames[idx], frames[idx + 1],
                                  min(1.0, max(0.0, u2)))
            else:
                img = frames[idx]
        base.paste(img, (0, canvas_y))
        return base

    return _render(frame_fn, out, duration=total, fps=24)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--opponent", default="",
                    help="override; normally resolved from the next fixture")
    ap.add_argument("--formation", default="4-3-3")
    ap.add_argument("--kickoff", default="")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_lineup_video.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    # ALWAYS the upcoming game. A predicted XI against a match already played
    # tells the reader we are not watching — on 24 Aug this shipped "Chiefs vs
    # Sundowns", a fixture from the 15th.
    competition = "Betway Premiership"
    if not a.opponent:
        from modules.psl_fixtures import next_fixture
        fx = await next_fixture(a.club)
        if not fx:
            _log(f"no upcoming fixture for {a.club} — refusing to build against "
                 f"a past game. Pass --opponent to override.")
            return 1
        a.opponent = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
        home = fx["home_key"] == a.club
        a.kickoff = a.kickoff or " · ".join(
            x for x in (fx.get("kickoff_sast", ""), fx.get("venue", "")) if x)
        _log(f"next fixture: {fx.get('home')} v {fx.get('away')} — "
             f"{fx.get('kickoff_sast')} ({'home' if home else 'away'})")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"lineup_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    # Prefer the real team sheet; fall back to the squad only if ESPN has none.
    xi, real_formation, provenance, bench = await pick_xi_real(a.club)
    if xi:
        a.formation = real_formation or a.formation
        _log(f"using REAL {provenance} — formation {a.formation}")
    else:
        _log("no published team sheet found — falling back to squad order")
        xi = pick_xi(a.club, a.formation)
    if len(xi) < 11:
        _log(f"only {len(xi)} players resolved — squad cache is thin, aborting")
        return 1

    # Never name a man who cannot play. Building from the last team sheet makes
    # this failure likely: someone who started the previous match and has been
    # injured since is still, to the sheet, a starter. A fan spotted exactly
    # that on 24 Aug — "fielding injured players like Frosler" — and it is the
    # comment that costs credibility, because it proves we are not watching.
    from modules.injuries import filter_xi
    xi, swaps = filter_xi(a.club, xi, bench)
    for dropped, came_in, why in swaps:
        if came_in:
            _log(f"INJURY: {dropped} out ({why}) — {came_in} in")
        else:
            _log(f"INJURY: {dropped} out ({why}) — no cover on the bench")
    bench = [b for b in bench if b not in xi]
    _log(f"XI: {', '.join(xi)}")

    cards = build_frames(work, a.club, a.opponent, a.formation, xi, a.kickoff,
                         bench=bench)
    _log(f"reveal frames: {len(cards)}")
    if not cards:
        _log("no cards rendered — aborting")
        return 1

    lines = analysis_lines(a.club, a.opponent, a.formation, xi,
                           provenance=provenance, bench=bench)
    narration = " ".join(lines)
    _log(f"narration: {len(narration)} chars")

    # Kokoro runs ~2.8 words/sec; the estimate matched the real 25.1s narration
    # to within a second on the first build, so pace the whole video off it.
    total = max(14.0, len(narration) / 15.0 + 5.0)
    # empty pitch for the motion phase to draw markers onto
    from modules.lineup_card import make_lineup_card as _mk
    bg = work / "pitch_bg.png"
    _mk(bg, club=a.club, players=[""] * len(xi), opponent=a.opponent,
        formation=a.formation, kickoff=a.kickoff,
        competition="Betway Premiership", predicted=True, bench=bench)
    from modules.club_brand import CLUB_BRAND as _CB
    accent = tuple(_CB.get(a.club, {}).get("colors", {}).get("primary", (255, 193, 7)))

    silent = work / "lineup_silent.mp4"
    render_video(cards, silent, total=total, formation=a.formation,
                 players=xi, bg=bg, bench=bool(bench), accent=accent)
    _log(f"video: {silent.name} — {total:.1f}s, "
         f"{(total * 0.62) / max(1, len(cards)):.1f}s per player")

    from modules.motion_kit import attach_voice
    final = await attach_voice(silent, narration, work / "final.mp4")
    _log(f"voiced: {Path(final).name}")

    # Cover: the finished card, crest and all
    cover = work / "cover.jpg"
    from PIL import Image
    Image.open(cards[-1]).convert("RGB").save(cover, quality=94)

    # Proper club names, never the internal keys: a reel went out on 24 Aug
    # captioned "vs Richards_Bay" because .title() was applied to the key.
    from modules.club_brand import CLUB_BRAND
    club_name = CLUB_BRAND.get(a.club, {}).get(
        "name", a.club.replace("_", " ").title())
    opp_name = CLUB_BRAND.get(a.opponent, {}).get(
        "name", a.opponent.replace("_", " ").title()) if a.opponent else ""
    when = f" — {a.kickoff}" if a.kickoff else ""
    title = (f"{club_name} Predicted XI vs {opp_name}" if opp_name
             else f"{club_name} Predicted XI")
    src_line = ((chr(10) * 2) + "Based on the XI that started "
                + provenance + ".") if provenance else ""
    caption = (f"GENESIS NEWS PREDICTION — the {club_name} eleven we expect"
               f"{' vs ' + opp_name if opp_name else ''}{when} "
               f"({a.formation}). Our call as a page, not the official team "
               f"sheet, and not us speaking for you. "
               f"Who would you drop? 👇" + src_line +
               f"\n\n#PSL #BetwayPremiership #KaizerChiefs "
               f"#Amakhosi #PredictedXI")

    manifest = {"niche": NICHE, "format_type": "short", "is_short": True,
                "built_at": datetime.now().isoformat(),
                "video_path": str(final), "thumbnail": str(cover),
                "title": title, "description": caption, "xi": xi,
                "formation": a.formation}
    (work / "upload_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title, caption, cover, niche=NICHE,
                          tags=["PSL", "KaizerChiefs", "Amakhosi",
                                "PredictedXI", "BetwayPremiership"])
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
