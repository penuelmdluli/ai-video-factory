"""
Who has actually been playing — and who has not played in a long time.

Owner call 2026-08-26: "we can always change the lineup to bring the argument,
use some players been on the bench or never used in a long time".

The big calls used to pick whoever was next off the bench, preferring anyone
the news happened to mention. That produces a change, but rarely an argument:
swapping in the man who played sixty minutes last week is not a position, it
is a rotation. The selection that starts a fight is the one nobody has seen
for a month — the fans' own "why does he never play?" said out loud by the
page.

So this counts starts and bench appearances across the club's recent team
sheets and hands back a coldness score. Everything is derived from published
sheets, so a name that has genuinely not featured is a fact, not a guess.

Cached to data/rotation_cache.json for a day: it costs one ESPN summary call
per fixture and the answer does not change between builds.

    from modules.rotation import coldness
    cold = await coldness("chiefs")     # {surname: matches since last start}
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "rotation_cache.json"
CACHE_HOURS = 20
LOOKBACK_DAYS = 70
MAX_MATCHES = 8


def _surname(entry: str) -> str:
    parts = str(entry).split(None, 1)
    return (parts[1] if len(parts) > 1 else str(entry)).strip().lower()


def _load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    except Exception:
        pass


async def match_log(club_key: str, force: bool = False) -> list[dict]:
    """The club's recent team sheets, newest first.

    [{date, match, starters: [surname], bench: [surname]}]
    """
    cache = _load()
    entry = cache.get(club_key) or {}
    if not force and entry.get("at"):
        try:
            age = (datetime.now() -
                   datetime.fromisoformat(entry["at"])).total_seconds() / 3600
            if age < CACHE_HOURS and entry.get("log"):
                return entry["log"]
        except Exception:
            pass

    from modules.psl_fixtures import fixtures_for, official_lineups, SAST
    now = datetime.now(SAST)
    log = []
    for i in range(1, LOOKBACK_DAYS + 1):
        if len(log) >= MAX_MATCHES:
            break
        day = now - timedelta(days=i)
        for f in await fixtures_for(day):
            if club_key not in (f.get("home_key"), f.get("away_key")):
                continue
            sheets = await official_lineups(f["id"])
            sheet = sheets.get(club_key)
            if not sheet or len(sheet.get("players") or []) < 11:
                continue
            log.append({
                "date": day.strftime("%Y-%m-%d"),
                "match": f"{f.get('home')} v {f.get('away')}",
                "starters": [_surname(p) for p in sheet["players"][:11]],
                "bench": [_surname(b) for b in (sheet.get("bench") or [])],
            })
            break

    cache[club_key] = {"at": datetime.now().isoformat(), "log": log}
    _save(cache)
    return log


async def coldness(club_key: str) -> dict:
    """{surname: how many of the recent matches he has NOT started}.

    A man who started the last game scores 0. One who has not started any of
    the eight sheets we can see scores 8 — and if he was not even on the bench
    for them, he is the selection that makes people argue.
    """
    log = await match_log(club_key)
    if not log:
        return {}
    seen = set()
    for m in log:
        seen.update(m["starters"])
        seen.update(m["bench"])

    out = {}
    for name in seen:
        gap = 0
        for m in log:                       # newest first
            if name in m["starters"]:
                break
            gap += 1
        out[name] = gap
    return out


async def describe(club_key: str, surname: str) -> str:
    """A line the narration can use, or "" when we cannot say anything true."""
    cold = await coldness(club_key)
    n = cold.get(str(surname).lower())
    if n is None or n <= 0:
        return ""
    if n == 1:
        return "left out last time"
    if n >= MAX_MATCHES:
        return "has not started a game we can find"
    return f"has not started in {n} matches"
