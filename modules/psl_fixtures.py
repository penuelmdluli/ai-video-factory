"""
Live PSL fixtures — game-day awareness for the Genesis News page.

ESPN's rsa.1 scoreboard gives every Betway Premiership fixture with kickoff
time and live status. This is what lets the page behave like a real outlet:
more posts on game days (prediction -> lineup -> result), normal news cadence
on quiet days.

Usage:
    from modules.psl_fixtures import fixtures_for, todays_fixtures
    fx = await todays_fixtures()
    # -> [{"id","home_key","away_key","home","away","kickoff_sast","status",
    #      "home_score","away_score"}, ...]
"""
from datetime import datetime, timedelta, timezone

import httpx

try:
    from modules.psl_squads import ESPN_TEAMS
except ImportError:  # standalone run
    from psl_squads import ESPN_TEAMS

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/scoreboard"
_ID_TO_KEY = {str(v): k for k, v in ESPN_TEAMS.items()}
SAST = timezone(timedelta(hours=2))


def _key_for(team: dict) -> str:
    return _ID_TO_KEY.get(str(team.get("id", "")), "")


async def fixtures_for(day: datetime) -> list[dict]:
    """All PSL fixtures on a calendar day (SAST)."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(SCOREBOARD, params={"dates": day.strftime("%Y%m%d")})
            events = r.json().get("events", [])
    except Exception as e:
        print(f"[Fixtures] fetch failed: {e}")
        return []

    out = []
    for e in events:
        comp = (e.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = sides.get("home", {}), sides.get("away", {})
        try:
            ko = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(SAST)
        except Exception:
            ko = None
        st = (e.get("status") or {}).get("type", {})
        out.append({
            "id": str(e.get("id", "")),
            "home_key": _key_for(home.get("team", {})),
            "away_key": _key_for(away.get("team", {})),
            "home": home.get("team", {}).get("displayName", ""),
            "away": away.get("team", {}).get("displayName", ""),
            "kickoff_sast": ko.strftime("%a %H:%M") if ko else "",
            "kickoff_iso": ko.isoformat() if ko else "",
            "status": st.get("state", ""),            # pre | in | post
            "completed": bool(st.get("completed")),
            "home_score": home.get("score", ""),
            "away_score": away.get("score", ""),
            "venue": (comp.get("venue") or {}).get("fullName", ""),
        })
    return out


async def todays_fixtures() -> list[dict]:
    return await fixtures_for(datetime.now(SAST))


async def next_fixture(club_key: str, days_ahead: int = 21) -> dict | None:
    """The club's NEXT fixture — never one already played.

    Owner rule 2026-08-24: "we must always use the upcoming game not past
    games". A predicted XI or preview built against a finished match is worse
    than no post: it tells the reader we are not watching. Callers that need a
    fixture must resolve it here rather than carrying a hard-coded opponent,
    which is how a line-up video went out on 24 Aug advertising Chiefs vs
    Sundowns — a game played on the 15th.

    Returns the fixture dict from fixtures_for(), or None when the club has
    nothing scheduled inside the window.
    """
    now = datetime.now(SAST)
    for i in range(days_ahead + 1):
        day = now + timedelta(days=i)
        for f in await fixtures_for(day):
            if club_key not in (f.get("home_key"), f.get("away_key")):
                continue
            # today's list can still hold a finished match
            if f.get("completed") or f.get("status") == "post":
                continue
            return f
    return None


SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/summary"


async def official_lineups(event_id: str) -> dict:
    """
    The CONFIRMED starting XI from the match summary feed, once the clubs
    announce their team sheets (usually ~60-75 min before kickoff).

    Returns {club_key: {"formation": "4-3-3", "players": ["32 Petersen", ...]}}
    — empty dict until the lineups are actually published.
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(SUMMARY, params={"event": event_id})
            rosters = r.json().get("rosters", [])
    except Exception as e:
        print(f"[Fixtures] summary fetch failed: {e}")
        return {}

    out = {}
    for side in rosters:
        key = _ID_TO_KEY.get(str((side.get("team") or {}).get("id", "")), "")
        entries = side.get("roster", [])
        starters = [p for p in entries if p.get("starter")]
        if not key or len(starters) < 11:
            continue
        # order: GK first, then by ESPN's formation place when present
        def _ord(p):
            fp = p.get("formationPlace")
            return int(fp) if str(fp).isdigit() else 99
        starters.sort(key=_ord)
        players = []
        for p in starters[:11]:
            ath = p.get("athlete") or {}
            no = str(p.get("jersey") or ath.get("jersey") or "").strip()
            from modules.psl_squads import fix_name
            nm = fix_name((ath.get("displayName") or "").strip()).split()
            surname = " ".join(nm[-2:]) if len(nm) > 1 and nm[-2].lower() in \
                ("du", "de", "van", "von", "le", "da", "dos") else (nm[-1] if nm else "")
            players.append(f"{no} {surname}".strip())
        out[key] = {"formation": side.get("formation") or "4-3-3",
                    "players": players}
    return out


BIG_THREE = ("chiefs", "pirates", "sundowns")


def priority(fx: dict) -> int:
    """Rank fixtures: big-three derby > big-three game > any PSL game."""
    n = sum(1 for k in (fx["home_key"], fx["away_key"]) if k in BIG_THREE)
    return n


if __name__ == "__main__":
    import asyncio

    async def _t():
        for d in range(3):
            day = datetime.now(SAST) + timedelta(days=d)
            fx = await fixtures_for(day)
            print(f"\n{day.strftime('%Y-%m-%d')}: {len(fx)} fixture(s)")
            for f in sorted(fx, key=priority, reverse=True):
                print(f"  [{priority(f)}] {f['home']} vs {f['away']} "
                      f"{f['kickoff_sast']} ({f['status']}) {f['venue']}")
    asyncio.run(_t())
