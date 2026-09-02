"""THE FANS' XI — the answer the gaps post promised.

Owner call 2026-09-02: "fans love filling, make it more interesting."

The thing that makes it more interesting is already written on every gaps card:
"we will read the most-backed eleven back to you before kickoff". Nothing has
ever read it back. This closes that loop, and the loop is the whole format -
the eleven the SUPPORTERS picked is a better post than the eleven we picked,
because they are in it, by name, with the count next to them.

It also converts one post into two on the same argument, and the second one
carries the first: everybody who commented has a reason to come back and see
whether their man made it.

    python build_gaps_verdict.py --club chiefs          # dry run, prints the count
    python build_gaps_verdict.py --club chiefs --post

Refuses rather than invents. No ask on record, no comments, or nobody naming a
real player means no post - a card claiming supporters picked someone they did
not name is worse than silence, and it would be found out in the replies within
a minute.
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

# Below this many voters the result is noise, not a verdict. Publishing "the
# fans picked Duba (1 vote)" reads as a page talking to itself, and tells the
# one person who replied that hardly anybody joined them.
MIN_VOTERS = 3


def _log(m):
    print(f"[Verdict] {m}", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--post-id", default="",
                    help="answer a specific post instead of the latest open ask")
    ap.add_argument("--min-voters", type=int, default=MIN_VOTERS)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    from modules.gaps_ledger import open_asks, latest_ask, close_ask
    from modules.gaps_answers import tally, fans_xi

    if a.post_id:
        ask = next((x for x in open_asks(a.club)
                    if x["post_id"] == a.post_id), None)
    else:
        ask = latest_ask(a.club)
    if not ask:
        _log("no unanswered gaps post on record — nothing to answer")
        return 1

    _log(f"answering {ask['mode']} ask from {ask['asked_at']} "
         f"(post {ask['post_id']}, {len(ask['withheld'])} shirt(s))")

    result = await tally(a.club, ask["post_id"])
    if result.get("error"):
        _log(f"cannot read the thread: {result['error']}")
        return 1

    _log(f"{result['comments']} comments, {result['voters']} people named a "
         f"real player, {result['unmatched']} named nobody we could match")
    for surname, n in list(result["votes"].items())[:8]:
        _log(f"   {n:>3} {surname}")

    if result["voters"] < a.min_voters:
        _log(f"only {result['voters']} voters — below the {a.min_voters} floor. "
             f"Not posting a verdict nobody voted in.")
        return 2

    xi, filled = fans_xi(ask, result)
    if not filled:
        _log("nobody named a player who was not already starting — no verdict")
        return 2

    club_name = "Kaizer Chiefs"
    try:
        from modules.club_brand import CLUB_BRAND
        club_name = CLUB_BRAND.get(a.club, {}).get("name", club_name)
    except Exception:
        pass

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"gaps_verdict_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    from modules.lineup_card import make_lineup_card
    card = work / "fans_xi.png"
    p = make_lineup_card(card, club=a.club, players=xi,
                         opponent="", formation=ask["formation"],
                         kickoff=ask.get("kickoff", ""),
                         competition="Betway Premiership", predicted=True,
                         badge={"fill": "THE FANS' XI",
                                "replace": "YOUR REPLACEMENT",
                                "start": "YOU DECIDED"}.get(ask["mode"],
                                                            "THE FANS' XI"))
    if not p:
        _log("card failed")
        return 1
    _log(f"card: {card}")

    picks = ", ".join(f"{s.upper()} ({n})" for _i, s, n in filled)
    nl = chr(10)
    caption = (
        f"YOU PICKED IT. 👇{nl}{nl}"
        f"{result['voters']} of you named a player, and this is the "
        f"{club_name} eleven you built: {picks}.{nl}{nl}"
        f"We said we would count them, so we counted them — one vote per "
        f"person, no matter how many times you shouted.{nl}{nl}"
        f"Disagree? The next shirt goes up soon.{nl}{nl}"
        f"#KaizerChiefs #Amakhosi #Khosi4Life #PSL #BetwayPremiership"
    )

    (work / "post_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "card": str(card), "caption": caption,
         "answers": result, "filled": filled, "ask": ask,
         "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")

    if not a.post:
        _log("dry run — pass --post to publish")
        print(nl + caption + nl)
        return 0

    from modules.uploader_facebook import upload_photo, post_comment
    r = await upload_photo(str(card), caption, NICHE)
    _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
    if (r or {}).get("status") != "uploaded":
        _log("post failed — ask stays OPEN so it can be answered on a retry")
        return 1

    close_ask(ask["post_id"])
    # Thank the people who actually answered, in the thread they answered in.
    try:
        await post_comment(
            ask["post_id"],
            f"Counted. {result['voters']} of you picked the eleven — "
            f"{picks}. Full card is up on the page now.", NICHE)
        _log("original thread answered")
    except Exception as e:
        _log(f"could not reply on the original post: {str(e)[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
