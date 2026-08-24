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


def analysis_lines(club: str, opponent: str, formation: str, xi: list[str]) -> list[str]:
    """Narration. Built from what is actually on the card, so it can never
    describe a player who is not in the XI."""
    from modules.club_brand import CLUB_BRAND
    name = CLUB_BRAND.get(club, {}).get("name", club.title())
    opp = CLUB_BRAND.get(opponent, {}).get("name", opponent.title()) if opponent else ""
    parts = formation.split("-")
    keeper = xi[0].split(" ", 1)[-1] if xi else ""
    back = [p.split(" ", 1)[-1] for p in xi[1:1 + int(parts[0])]] if len(parts) > 1 else []
    front = [p.split(" ", 1)[-1] for p in xi[-int(parts[-1]):]] if len(parts) > 1 else []

    lines = [
        f"Here is our predicted {name} eleven" + (f" against {opp}." if opp else "."),
        f"The shape is {formation.replace('-', ' ')}.",
    ]
    if keeper:
        lines.append(f"{keeper} starts in goal.")
    if back:
        lines.append("The back line reads " + ", ".join(back) + ".")
    if front:
        lines.append("Up top, " + " and ".join(front) + " carry the goals.")
    lines += [
        "This is our call, not the official team sheet.",
        "Tell us who you would drop in the comments.",
        "Subscribe to Genesis News — we post the team sheets the moment they land.",
    ]
    return lines


def build_frames(work: Path, club: str, opponent: str, formation: str,
                 xi: list[str], kickoff: str) -> list[Path]:
    """One card per revealed player — the build-up animation."""
    from modules.lineup_card import make_lineup_card
    cards = []
    for n in range(1, len(xi) + 1):
        out = work / f"reveal_{n:02d}.png"
        p = make_lineup_card(out, club=club, players=xi[:n], opponent=opponent,
                             formation=formation, kickoff=kickoff,
                             competition="Betway Premiership", predicted=True)
        if p:
            cards.append(Path(p))
    return cards


def render_video(cards: list[Path], out: Path, hold: float, per: float = 0.45) -> str:
    """Reveal the XI one man at a time, then hold the full card."""
    from PIL import Image
    from modules.motion_kit import _render, DARK

    frames = [Image.open(c).convert("RGB") for c in cards]
    canvas_y = (H - frames[0].height) // 2
    build_t = per * len(frames)
    total = build_t + hold

    def frame_fn(t):
        idx = min(len(frames) - 1, int(t / per)) if t < build_t else len(frames) - 1
        base = Image.new("RGB", (W, H), DARK)
        base.paste(frames[idx], (0, canvas_y))
        return base

    return _render(frame_fn, out, duration=total, fps=24)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--opponent", default="sundowns")
    ap.add_argument("--formation", default="4-3-3")
    ap.add_argument("--kickoff", default="")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_lineup_video.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"lineup_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    xi = pick_xi(a.club, a.formation)
    if len(xi) < 11:
        _log(f"only {len(xi)} players resolved — squad cache is thin, aborting")
        return 1
    _log(f"XI: {', '.join(xi)}")

    cards = build_frames(work, a.club, a.opponent, a.formation, xi, a.kickoff)
    _log(f"reveal frames: {len(cards)}")
    if not cards:
        _log("no cards rendered — aborting")
        return 1

    lines = analysis_lines(a.club, a.opponent, a.formation, xi)
    narration = " ".join(lines)
    _log(f"narration: {len(narration)} chars")

    silent = work / "lineup_silent.mp4"
    render_video(cards, silent, hold=max(8.0, len(narration) / 15.0))
    _log(f"video: {silent.name}")

    from modules.motion_kit import attach_voice
    final = await attach_voice(silent, narration, work / "final.mp4")
    _log(f"voiced: {Path(final).name}")

    # Cover: the finished card, crest and all
    cover = work / "cover.jpg"
    from PIL import Image
    Image.open(cards[-1]).convert("RGB").save(cover, quality=94)

    title = f"{a.club.title()} Predicted XI vs {a.opponent.title()}"
    caption = (f"Our predicted {a.club.title()} eleven"
               f"{' vs ' + a.opponent.title() if a.opponent else ''} "
               f"({a.formation}). Our call — not the official team sheet. "
               f"Who would you drop? 👇\n\n#PSL #BetwayPremiership #KaizerChiefs "
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
        from modules.uploader_facebook import upload_to_facebook
        r = await upload_to_facebook(str(final), title, caption, NICHE,
                                     is_reel=True, thumbnail_path=str(cover))
        _log(f"Facebook: {r}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
