"""
The XI with holes in it — let the supporters pick the rest.

Owner call 2026-08-26: "post a post with missing players on the lineup, ask the
support to just who should fill it".

This is the cheapest engagement on the page and the most honest. A predicted XI
invites people to disagree with a finished opinion, which some will not bother
to do. A team sheet with three empty shirts asks a question that has no wrong
answer, and the only way to answer it is to comment. The gaps are left in the
positions people actually argue about — never the goalkeeper, never a shirt we
have already made a big call on.

A photo post, not a reel: it is a question, and a still image is read in the
half second it takes to scroll past.

    python build_fill_the_gaps.py --club chiefs
    python build_fill_the_gaps.py --club chiefs --post --gaps 3
"""
import argparse
import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "sa_pulse"


def _log(m):
    print(f"[Gaps] {m}", flush=True)


def _surname(entry: str) -> str:
    parts = str(entry).split(None, 1)
    return (parts[1] if len(parts) > 1 else str(entry)).strip()


def pick_gaps(xi: list[str], formation: str, n: int = 3) -> list[int]:
    """Which shirts to leave empty.

    Never the keeper — "who should be in goal" is a different post and a
    weaker one, because most fans have the same answer. The gaps are spread
    across different lines so the question is about the whole side rather
    than one argument, and the attacking end is always represented because
    that is where this page's comments actually come from.
    """
    parts = [int(x) for x in str(formation).split("-") if x.strip().isdigit()]
    if not parts:
        parts = [4, 3, 3]
    lines, i = [], 1                       # index 0 is the keeper
    for count in parts:
        lines.append(list(range(i, min(11, i + count))))
        i += count

    rng = random.Random(datetime.now().strftime("%Y%m%d"))
    gaps = []
    # one from the forward line first, then spread backwards
    for line in reversed(lines):
        if len(gaps) >= n or not line:
            continue
        gaps.append(rng.choice([k for k in line if k not in gaps]))
    # top up from anywhere outfield if the shape did not give us enough
    pool = [k for k in range(1, len(xi)) if k not in gaps]
    rng.shuffle(pool)
    while len(gaps) < n and pool:
        gaps.append(pool.pop())
    return sorted(gaps[:n])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--gaps", type=int, default=3)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    from modules.psl_fixtures import next_fixture
    from modules.club_brand import CLUB_BRAND

    fx = await next_fixture(a.club)
    if not fx:
        _log("no upcoming fixture")
        return 1
    fid = str(fx.get("id", ""))
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
    home = fx["home_key"] == a.club
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_name = CLUB_BRAND.get(opp_key, {}).get("name",
                                               opp_key.replace("_", " ").title())

    # Build the holes into the side we have ALREADY published for this
    # fixture, so the page is asking about one team rather than inventing a
    # second one an hour after the first.
    xi, formation = [], "4-3-3"
    try:
        pp = ROOT / "data" / "xi_predictions.json"
        pred = (json.loads(pp.read_text(encoding="utf-8")).get(fid) or {}) \
            if pp.exists() else {}
        xi, formation = pred.get("xi") or [], pred.get("formation") or formation
    except Exception:
        pass
    if not xi:
        from build_lineup_video import pick_xi_real
        xi, real_f, _prov, _bench = await pick_xi_real(a.club)
        formation = real_f or formation
    if len(xi) < 11:
        _log("no usable XI")
        return 1

    gaps = pick_gaps(xi, formation, a.gaps)
    missing = [_surname(xi[g]) for g in gaps]
    holed = [("" if i in gaps else p) for i, p in enumerate(xi)]
    _log(f"gaps at {gaps} — holding out {', '.join(missing)}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"gaps_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    from modules.lineup_card import make_lineup_card
    card = work / "gaps.png"
    kickoff = " · ".join(x for x in (fx.get("kickoff_sast", ""),
                                     fx.get("venue", "")) if x)
    p = make_lineup_card(card, club=a.club, players=holed, opponent=opp_key,
                         formation=formation, kickoff=kickoff,
                         competition="Betway Premiership", predicted=True,
                         pending=True,   # the empty shirts must be VISIBLE
                         badge="YOU PICK THE REST")
    if not p:
        _log("card failed")
        return 1
    _log(f"card: {card}")

    caption = (
        f"YOU PICK THE REST. 👇{chr(10)}{chr(10)}"
        f"{len(gaps)} shirts are empty in our {club_name} side "
        f"{'vs' if home else 'away to'} {opp_name} tonight — "
        f"{formation}, {kickoff}.{chr(10)}{chr(10)}"
        f"Who fills them? Drop the names in the comments and we will read the "
        f"most-backed eleven back to you before kickoff.{chr(10)}{chr(10)}"
        f"#KaizerChiefs #Amakhosi #Khosi4Life #PSL #BetwayPremiership")

    (work / "post_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "card": str(card), "caption": caption,
         "gaps": gaps, "withheld": missing, "formation": formation,
         "fixture": fid, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")

    if a.post:
        from modules.uploader_facebook import upload_photo, post_comment
        r = await upload_photo(str(card), caption, NICHE)
        _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
        if (r or {}).get("status") == "uploaded":
            # Seed the thread. An empty comment box is a harder ask than one
            # that already has a name in it to argue with.
            target = r.get("photo_id") or r.get("post_id")
            try:
                await post_comment(
                    target,
                    "Reply with your names for the empty shirts — position "
                    "first, e.g. \"RW: Duba\"." + chr(10) +
                    "▶️ More on YouTube: "
                    "https://www.youtube.com/@GenesisNewsPSL", NICHE)
                _log("first comment seeded")
            except Exception as e:
                _log(f"first comment failed: {str(e)[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
