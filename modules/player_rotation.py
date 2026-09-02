"""Stop the same eleven faces carrying every card.

Owner call 2026-09-02: "we keep posting the similar players always, even where
you select only best 5 players they are always the same. Fans always want to
see what we have for them in that video."

He is describing a determinism, not a preference. Every selector in this repo
ranks by RECENT REAL STARTS, then shirt number - psl_squads.predict_xi2,
build_best_xi, the reveal cards. That is a total order over a squad that barely
changes week to week, so the same input produces the same output forever. Five
consecutive builds on 2 Sep, each with a genuinely different formation and a
different bold call, still shared ten of eleven names: Leaner, Monyane,
Frosler, Moloisane, Maboe, Ndlovu, Mthethwa, Mmodi, Baartman, Ighodaro. The
rotation was real and it was invisible, because it only ever moved one shirt.

So merit stays, and OVER-EXPOSURE is charged for. A player's ranking score is
his recent starts minus a penalty for how many of our recent cards he has
already appeared in. A regular who has fronted the last eight posts drifts
below a squad man who has fronted none, without anybody being picked at random.

That distinction matters. Picking at random would produce an XI no supporter
believes, and this page lives on being argued with, not laughed at. Charging
for exposure keeps every card defensible - these are all men in the squad, in
form order - while guaranteeing the page does not show the same faces twice in
a row. Unpredictable, not implausible.

The ledger is written only by record_featured(), and only after a confirmed
post, for the same reason modules/lineup_variety.record_posted exists: a build
that fails before publishing must not burn a player's turn. This repo has paid
for recording-at-pick-time twice already.

    from modules.player_rotation import exposure_penalty, record_featured
    pen = exposure_penalty("chiefs")          # {surname: penalty}
    ...
    record_featured("chiefs", xi)             # AFTER the post is confirmed
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "player_rotation.json"

# How many recent cards count as "recently seen". Eight is roughly two weeks of
# posting: long enough that a fan notices the repetition, short enough that a
# genuine first-choice regular comes back around rather than vanishing.
WINDOW = 8

# What one appearance costs, measured in "recent starts". At 0.6 a man who has
# started four of the club's last matches and fronted six of our cards scores
# 4 - 3.6 = 0.4, which puts him just below an unused squad player on three
# starts. Raise it for more churn, lower it for a more conventional XI.
PENALTY_PER_APPEARANCE = 0.6


def _surname(entry: str) -> str:
    """'50 Ighodaro' and 'Chris Ighodaro' both key on 'ighodaro'."""
    txt = str(entry or "").strip()
    if not txt:
        return ""
    words = [w for w in txt.split() if not w.isdigit()]
    if len(words) >= 2 and words[-2].lower() in ("du", "de", "van", "von", "le", "da", "dos"):
        return " ".join(words[-2:]).lower()
    return (words[-1] if words else txt).lower()


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Rotation] state write failed (non-critical): {e}")


def recent_cards(club: str, window: int = WINDOW) -> list[list[str]]:
    """The last `window` posted line-ups for this club, newest last."""
    return (_load().get(club) or {}).get("cards", [])[-window:]


def appearances(club: str, window: int = WINDOW) -> dict:
    """{surname: how many of the last `window` cards he appeared in}."""
    counts: dict[str, int] = {}
    for card in recent_cards(club, window):
        # A name counts once per card even if it somehow appears twice, so a
        # duplicate entry cannot exile a player.
        for sn in {_surname(x) for x in card if x}:
            counts[sn] = counts.get(sn, 0) + 1
    return counts


def exposure_penalty(club: str, window: int = WINDOW,
                     per_appearance: float = PENALTY_PER_APPEARANCE) -> dict:
    """{surname: score to SUBTRACT from his merit ranking}."""
    return {sn: n * per_appearance for sn, n in appearances(club, window).items()}


def record_featured(club: str, players: list[str]) -> bool:
    """Log a line-up that ACTUALLY went out. Call after a confirmed post.

    Refuses to log an identical card twice in a row, so a retry or a rebuild of
    the same post does not double-charge every player in it.
    """
    card = [_surname(p) for p in (players or []) if str(p).strip()]
    if not card:
        return False
    state = _load()
    cs = state.setdefault(club, {"cards": []})
    if cs["cards"] and cs["cards"][-1] == card:
        return False
    cs["cards"].append(card)
    cs["cards"] = cs["cards"][-40:]
    cs["last"] = datetime.now().isoformat()
    _save(state)
    print(f"[Rotation] logged {len(card)} players for {club}")
    return True


def freshest(club: str, candidates: list[str], n: int = 5,
             window: int = WINDOW) -> list[str]:
    """The n least-recently-featured of `candidates`, least-seen first.

    For formats that pick a handful rather than an XI - "best 5", a player
    spotlight - where there is no merit order to preserve and the only job is
    to not show the same faces again.
    """
    seen = appearances(club, window)
    return sorted(candidates, key=lambda c: (seen.get(_surname(c), 0),
                                             candidates.index(c)))[:n]


if __name__ == "__main__":
    club = "chiefs"
    print(f"last {WINDOW} cards for {club}: {len(recent_cards(club))}")
    ap = appearances(club)
    if not ap:
        print("(no cards logged yet - penalties are all zero until posts record)")
    for sn, n in sorted(ap.items(), key=lambda kv: -kv[1]):
        print(f"  {n} appearances  -{n * PENALTY_PER_APPEARANCE:.1f}  {sn}")
