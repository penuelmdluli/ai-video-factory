"""
OUR CALLS tracker — the prediction franchise's scoreboard.

Every "OUR CALL: CHIEFS 2-1 — BAARTMAN TO SCORE" gets recorded when made and
settled against the real result at full-time. Once a week the record posts as
a card: "OUR CALLS: 3/5 this week — beat us in the comments." Honest accuracy,
published win or lose — that's what makes it a franchise instead of noise.

Data: data/call_history.json
Usage:
    from modules.call_tracker import record_call, settle_calls, weekly_summary
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

HIST = Path(__file__).parent.parent / "data" / "call_history.json"


def _load() -> list:
    try:
        return json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(calls: list):
    HIST.parent.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(calls[-200:], indent=2, ensure_ascii=False),
                    encoding="utf-8")


def record_call(fav_club: str, other_club: str, score: str, scorer: str,
                text: str):
    """Log a prediction once per matchup per day (reels repeat the same call)."""
    calls = _load()
    today = datetime.now().strftime("%Y-%m-%d")
    key = {c for c in (fav_club, other_club)}
    for c in calls:
        if c["date"] == today and set((c["fav"], c["other"])) == key:
            return                                  # already recorded today
    calls.append({"date": today, "fav": fav_club, "other": other_club,
                  "score": score, "scorer": scorer, "text": text,
                  "settled": False, "result": "", "won": None,
                  "scorer_hit": None})
    _save(calls)
    print(f"[Calls] recorded: {text[:60]}")


def settle_calls(home_key: str, away_key: str, home_score: int, away_score: int,
                 scorers: list[str]):
    """Settle any open call on this fixture against the real result."""
    calls = _load()
    changed = False
    match_clubs = {home_key, away_key}
    scorer_blob = " ".join(scorers).lower()
    for c in calls:
        if c["settled"] or set((c["fav"], c["other"])) != match_clubs:
            continue
        # did the predicted winner win?
        if home_score == away_score:
            fav_won = False                          # we never call draws
        elif home_score > away_score:
            fav_won = c["fav"] == home_key
        else:
            fav_won = c["fav"] == away_key
        c["won"] = bool(fav_won)
        c["scorer_hit"] = bool(c.get("scorer") and
                               c["scorer"].lower() in scorer_blob)
        c["result"] = f"{home_score}-{away_score}"
        c["settled"] = True
        changed = True
        print(f"[Calls] settled {c['fav']} vs {c['other']}: "
              f"winner {'HIT' if c['won'] else 'MISS'}, "
              f"scorer {'HIT' if c['scorer_hit'] else 'MISS'}")
    if changed:
        _save(calls)


def weekly_summary() -> dict:
    """Last 7 days of settled calls: {total, wins, scorer_hits, lines}."""
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    settled = [c for c in _load() if c["settled"] and c["date"] >= cutoff]
    return {
        "total": len(settled),
        "wins": sum(1 for c in settled if c["won"]),
        "scorer_hits": sum(1 for c in settled if c["scorer_hit"]),
        "lines": [f"{c['fav'].title()} vs {c['other'].title()}: called "
                  f"{c['score']}, real {c['result']} — "
                  f"{'✅' if c['won'] else '❌'}" for c in settled],
    }
