"""
Live Betway Premiership log — for the mini-table on news cards.

ESPN's standings feed, cached 6h. Rows come back newest-first by rank with the
club key resolved so cards can show crest colours later if wanted.

Usage:
    from modules.psl_standings import get_log
    rows = await get_log(6)   # [{"rank",1 "name","Chiefs", "team_key","chiefs",
                              #   "played",2, "points",6}, ...]
"""
import json
import time
from pathlib import Path

import httpx

from modules.psl_squads import ESPN_TEAMS

CACHE = Path(__file__).parent.parent / "data" / "psl_standings_cache.json"
CACHE_TTL = 6 * 3600
URL = "https://site.api.espn.com/apis/v2/sports/soccer/rsa.1/standings"
_ID_TO_KEY = {str(v): k for k, v in ESPN_TEAMS.items()}

# short display names that fit a card column
_SHORT = {
    "Kaizer Chiefs": "Chiefs", "Orlando Pirates": "Pirates",
    "Mamelodi Sundowns": "Sundowns", "Polokwane City FC": "Polokwane",
    "Sekhukhune United FC": "Sekhukhune", "Richards Bay FC": "Richards Bay",
    "Golden Arrows": "Arrows", "TS Galaxy FC": "TS Galaxy",
    "Marumo Gallants": "Gallants", "Chippa United": "Chippa",
    "Durban City": "Durban City", "Kruger United": "Kruger Utd",
    "Milford FC": "Milford", "Siwelele": "Siwelele",
    "Stellenbosch": "Stellenbosch", "AmaZulu": "AmaZulu",
}


async def get_log(top: int = 6, force_refresh: bool = False) -> list[dict]:
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
        if not force_refresh and time.time() - cache.get("at", 0) < CACHE_TTL:
            return cache["rows"][:top]
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(URL)
            entries = (r.json().get("children") or [{}])[0] \
                .get("standings", {}).get("entries", [])
    except Exception as e:
        print(f"[Standings] fetch failed: {e}")
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))["rows"][:top]
        except Exception:
            return []
    rows = []
    for e in entries:
        t = e.get("team", {})
        stats = {s.get("name"): s for s in e.get("stats", [])}
        name = t.get("displayName", "")
        rows.append({
            "rank": int(stats.get("rank", {}).get("value") or 0),
            "name": _SHORT.get(name, name[:12]),
            "team_key": _ID_TO_KEY.get(str(t.get("id", "")), ""),
            "played": int(stats.get("gamesPlayed", {}).get("value") or 0),
            "points": int(stats.get("points", {}).get("value") or 0),
        })
    rows.sort(key=lambda r: r["rank"] or 99)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"at": time.time(), "rows": rows},
                                ensure_ascii=False), encoding="utf-8")
    print(f"[Standings] live log: {len(rows)} teams")
    return rows[:top]


if __name__ == "__main__":
    import asyncio
    for r in asyncio.run(get_log(8, force_refresh=True)):
        print(f"  {r['rank']:>2} {r['name']:<14} P{r['played']} {r['points']} pts")
