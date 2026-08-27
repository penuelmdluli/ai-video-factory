"""
Position corrections — where the crowd overrules the feed.

The squad cache comes from Wikipedia and ESPN, and both had Langelihle Phili
down as FW. Chiefs supporters put us right in the comments on 2026-08-24:
"Phili is not striker is a left wing u don't know chiefs". On squad detail the
fans are a better source than the feed, and a striker debate that lists a
winger as a striker gets dismissed on sight.

Corrections live in data/position_overrides.json and are applied on top of the
cache every read, so a cache refresh cannot quietly undo them.

    from modules.positions import apply_overrides, group_of
    squad = apply_overrides("chiefs", squad)
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
OVERRIDES = ROOT / "data" / "position_overrides.json"

# Fine labels -> the bucket a debate or a line-up should treat them as.
# A winger is an attacker, but he is NOT a centre forward, which is the whole
# distinction the comments were making.
GROUP = {
    "GK": "GK", "DF": "DF", "MF": "MF", "FW": "FW",
    "LW": "FW", "RW": "FW", "ST": "FW",
    "CDM": "MF", "CAM": "MF", "LB": "DF", "RB": "DF", "CB": "DF",
}
# Which fine labels count as a genuine centre forward
STRIKERS = {"ST", "FW"}


def _load() -> dict:
    try:
        return json.loads(OVERRIDES.read_text(encoding="utf-8"))
    except Exception:
        return {}


def override_for(club: str, name: str) -> str:
    """The corrected fine position for this player, or "" if none."""
    surname = (str(name).split()[-1] if name else "").lower()
    rec = (_load().get(club) or {}).get(surname)
    if isinstance(rec, str):
        return rec.upper()
    return str((rec or {}).get("pos", "")).upper()


def apply_overrides(club: str, squad: list[dict]) -> list[dict]:
    """Squad with corrected positions. `pos` becomes the bucket (GK/DF/MF/FW)
    and `pos_fine` keeps the specific label so callers can tell a winger from
    a centre forward."""
    out = []
    for p in squad:
        q = dict(p)
        fine = override_for(club, q.get("name", ""))
        if fine:
            q["pos_fine"] = fine
            q["pos"] = GROUP.get(fine, q.get("pos", ""))
        else:
            q.setdefault("pos_fine", (q.get("pos") or "").upper())
        out.append(q)
    return out


def is_striker(player: dict) -> bool:
    """True only for a genuine centre forward — a winger is not one."""
    return str(player.get("pos_fine", player.get("pos", ""))).upper() in STRIKERS


def group_of(player: dict) -> str:
    fine = str(player.get("pos_fine", player.get("pos", ""))).upper()
    return GROUP.get(fine, fine[:2] if fine else "")
