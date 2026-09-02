"""Which post asked the question, so the answer can be given.

Every "fill the gaps" caption makes a promise:

    "Drop the names in the comments and we will read the most-backed eleven
     back to you before kickoff."
    "One name in the comments. We will count them."

Nothing in this repo has ever counted them. No module reads those comments,
and build_fill_the_gaps writes its manifest BEFORE the post exists, so the
Facebook post id was printed to the console and dropped on the floor. The page
has made that promise on every gaps post and kept it zero times.

That is worse than not asking. Supporters who take the trouble to reply are
the page's most valuable readers, and the format teaches them their answer goes
nowhere. It also throws away the best content this page could run: the eleven
the SUPPORTERS picked is a better post than the eleven we picked, because they
are in it.

So the ask is recorded here at post time - the id, the shirts left empty, the
names withheld, the XI they were cut from - and modules/gaps_answers.py reads
the comments back against it.

    from modules.gaps_ledger import record_asked, open_asks, close_ask
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "gaps_asks.json"


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"asks": []}


def _save(d: dict):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    except Exception as e:
        print(f"[GapsLedger] write failed (non-critical): {e}")


def record_asked(club: str, post_id: str, fixture_id: str, gaps: list,
                 withheld: list, xi: list, formation: str, mode: str,
                 kickoff: str = "") -> bool:
    """Log a question that actually went out. Called after a confirmed post."""
    if not post_id:
        print("[GapsLedger] no post id - cannot promise an answer we can't find")
        return False
    d = _load()
    # Same post twice is a retry, not a second question.
    if any(a.get("post_id") == str(post_id) for a in d["asks"]):
        return False
    d["asks"].append({
        "club": club,
        "post_id": str(post_id),
        "fixture_id": str(fixture_id or ""),
        "gaps": list(gaps or []),
        "withheld": list(withheld or []),
        "xi": list(xi or []),
        "formation": formation,
        "mode": mode,
        "kickoff": kickoff,
        "asked_at": datetime.now().isoformat(timespec="seconds"),
        "answered_at": "",
    })
    d["asks"] = d["asks"][-60:]
    _save(d)
    print(f"[GapsLedger] recorded {mode} ask on post {post_id} "
          f"({len(withheld or [])} shirt(s))")
    return True


def open_asks(club: str = "") -> list[dict]:
    """Questions that went out and have not been answered yet, oldest first."""
    return [a for a in _load().get("asks", [])
            if not a.get("answered_at") and (not club or a.get("club") == club)]


def latest_ask(club: str = "") -> dict | None:
    asks = open_asks(club)
    return asks[-1] if asks else None


def close_ask(post_id: str) -> bool:
    """Mark a question as answered, so the verdict is never posted twice."""
    d = _load()
    for a in d.get("asks", []):
        if a.get("post_id") == str(post_id) and not a.get("answered_at"):
            a["answered_at"] = datetime.now().isoformat(timespec="seconds")
            _save(d)
            return True
    return False
