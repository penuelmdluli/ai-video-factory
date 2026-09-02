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

import asyncio
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


class FixtureFetchError(RuntimeError):
    """We could not read a day. NOT the same as 'that day has no matches'."""


async def fixtures_for(day: datetime, strict: bool = False) -> list[dict]:
    """All PSL fixtures on a calendar day (SAST).

    strict=True raises FixtureFetchError instead of returning an empty list
    when the request fails.

    This distinction is not academic. The old version returned [] for both
    'no matches' and 'the request failed', so on 2026-08-27 a single transient
    failure while scanning 6 September made next_fixture skip straight past
    Chiefs v Siwelele and report Polokwane on the 12th - a different opponent,
    a week later. Every reel, caption and countdown downstream would have
    carried that wrong fixture, and nothing anywhere would have looked broken.
    A silent empty list is the most dangerous value this function can return.
    """
    attempts = 3 if strict else 1
    last = None
    for i in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=30,
                                         follow_redirects=True) as client:
                r = await client.get(SCOREBOARD,
                                     params={"dates": day.strftime("%Y%m%d")})
                r.raise_for_status()
                events = r.json().get("events", [])
            break
        except Exception as e:
            last = e
            if i == attempts - 1:
                print(f"[Fixtures] fetch failed: {e}")
                if strict:
                    raise FixtureFetchError(
                        f"{day:%Y-%m-%d}: {e}") from e
                return []
            await asyncio.sleep(1.5 * (i + 1))

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

    Reads each day strictly: a day we could not fetch is NOT treated as a day
    with no matches. Skipping an unreadable day is how the wrong opponent gets
    onto a reel - the scan sails past the real next fixture and returns one a
    week later, with nothing in any log looking wrong.
    """
    now = datetime.now(SAST)
    for i in range(days_ahead + 1):
        day = now + timedelta(days=i)
        try:
            fixtures = await fixtures_for(day, strict=True)
        except FixtureFetchError as e:
            print(f"[Fixtures] cannot read {day:%Y-%m-%d} ({e}) - refusing to "
                  f"guess a later fixture for {club_key}")
            return None
        for f in fixtures:
            if club_key not in (f.get("home_key"), f.get("away_key")):
                continue
            # today's list can still hold a finished match
            if f.get("completed") or f.get("status") == "post":
                continue
            return f
    return None


SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/summary"


async def last_lineup(club_key: str, lookback_days: int = 45) -> dict | None:
    """The club's most recent REAL starting XI, straight off the team sheet.

    Owner call 2026-08-24: "I think we gave them a weak team, give them the
    best, one no one can deny". The predicted XI was being assembled by taking
    the first players of each position out of the squad cache — squad-list
    order, which is not merit and is not form. It left out Phili, Monyane,
    Mmodi, Moloisane and Mthethwa, every one of whom had STARTED the previous
    match, and it guessed 4-3-3 when Chiefs had lined up 5-3-2.

    A predicted XI that starts from who actually played is one nobody can argue
    is invented. Returns {formation, players, date, match} or None when ESPN
    has published no team sheet inside the window.
    """
    now = datetime.now(SAST)
    for i in range(1, lookback_days + 1):
        day = now - timedelta(days=i)
        for f in await fixtures_for(day):
            if club_key not in (f.get("home_key"), f.get("away_key")):
                continue
            sheets = await official_lineups(f["id"])
            sheet = sheets.get(club_key)
            if sheet and len(sheet.get("players", [])) >= 11:
                return {"formation": sheet.get("formation") or "4-3-3",
                        "players": sheet["players"][:11],
                        "bench": sheet.get("bench", [])[:9],
                        "date": day.strftime("%Y-%m-%d"),
                        "match": f"{f.get('home')} v {f.get('away')}"}
    return None


def _display(player_line: str) -> str:
    """Apply owner name fixes to a "7 Surname" team-sheet entry."""
    try:
        from modules.psl_squads import fix_name, fix_surname
    except Exception:
        return player_line
    no, _, nm = player_line.partition(" ")
    if not nm:
        return fix_name(player_line)
    return f"{no} {fix_surname(nm.strip()) if ' ' not in nm.strip() else fix_name(nm.strip())}"


def side_of(pos: str) -> int:
    """How far across the pitch a published ESPN position sits.

        LB -3 | CD-L -1 | CD 0 | CD-R +1 | RB +3

    Hoisted out of official_lineups so the PREDICTED XI can order its lines the
    same way the OFFICIAL one already does. It could not before: predict_xi2
    rebuilds the side from the squad cache, where every defender is just "DF",
    so the side information ESPN publishes was thrown away and Monyane - who is
    always at one end of his line on the real sheets - landed wherever the sort
    happened to put him. Two cards of the same club in the same week disagreed
    about which flank he plays.
    """
    pos = (pos or "").upper()
    if pos.startswith(("LB", "LWB", "LM", "LW")):
        return -3
    if pos.startswith(("RB", "RWB", "RM", "RW")):
        return 3
    if pos.endswith("-L"):
        return -1
    if pos.endswith("-R"):
        return 1
    return 0


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

        # Order each line LEFT TO RIGHT by the position ESPN publishes, not by
        # formationPlace. Owner caught this on 2026-08-24: place-ordering put
        # Monyane (RB) on the left of the back five and Mmodi (LB) second, and
        # pushed Zitha Macheke — a centre-back, CD-R — out to the touchline.
        # The abbreviations carry the side explicitly: LB, CD-L, CD, CD-R, RB.
        def _ord(p):
            pos = ((p.get("position") or {}).get("abbreviation")
                   or (p.get("athlete") or {}).get("position", {}).get("abbreviation")
                   or "").upper()
            depth = (0 if pos.startswith("G") else
                     1 if pos.startswith(("D", "CD", "LB", "RB", "LWB", "RWB")) else
                     3 if pos.startswith(("F", "CF", "ST", "LW", "RW")) else 2)
            # A full-back (LB/RB) stands WIDER than a shaded centre-back
            # (CD-L/CD-R), so they cannot share a rank or Monyane ends up
            # inside Macheke. Order across the pitch:
            #   LB -3 | CD-L -1 | CD 0 | CD-R +1 | RB +3
            side = side_of(pos)
            fp = p.get("formationPlace")
            return (depth, side, int(fp) if str(fp).isdigit() else 99)
        starters.sort(key=_ord)
        players = []
        for p in starters[:11]:
            ath = p.get("athlete") or {}
            no = str(p.get("jersey") or ath.get("jersey") or "").strip()
            from modules.psl_squads import fix_name
            nm = fix_name((ath.get("displayName") or "").strip()).split()
            surname = " ".join(nm[-2:]) if len(nm) > 1 and nm[-2].lower() in \
                ("du", "de", "van", "von", "le", "da", "dos") else (nm[-1] if nm else "")
            # owner name fixes apply here so every board, card and reel
            # shows the name the fans actually use
            players.append(_display(f"{no} {surname}".strip()))
        # The bench is published too and was simply never read. Fans argue
        # about the subs as much as the XI.
        bench = []
        for p in entries:
            if p.get("starter"):
                continue
            ath = p.get("athlete") or {}
            from modules.psl_squads import fix_name
            nm = fix_name((ath.get("displayName") or "").strip()).split()
            if not nm:
                continue
            no = str(p.get("jersey") or ath.get("jersey") or "").strip()
            bench.append(f"{no} {nm[-1]}".strip())

        # The side data ESPN publishes, kept rather than consumed and dropped.
        # This is the only place in the repo that knows Monyane is a right back
        # and Mmodi a left back; the squad cache says "DF" for both.
        positions = {}
        for p in starters[:11]:
            ath = p.get("athlete") or {}
            from modules.psl_squads import fix_name
            nm = fix_name((ath.get("displayName") or "").strip()).split()
            if not nm:
                continue
            sur = (" ".join(nm[-2:]) if len(nm) > 1 and nm[-2].lower() in
                   ("du", "de", "van", "von", "le", "da", "dos") else nm[-1]).lower()
            abbr = ((p.get("position") or {}).get("abbreviation")
                    or (ath.get("position", {}) or {}).get("abbreviation") or "")
            if abbr:
                positions[sur] = abbr.upper()

        out[key] = {"positions": positions,
                    "formation": side.get("formation") or "4-3-3",
                    "players": players, "bench": bench}
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
