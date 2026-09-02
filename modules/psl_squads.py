"""
Live PSL squads — the CURRENT first-team list for each club.

A predicted XI is only credible if every name on it actually plays for the club
THIS season. Model memory goes stale the moment a transfer window opens, so
lineups must come from a live source.

PRIMARY: ESPN's South African Premiership API (site.api.espn.com, league rsa.1)
— maintained rosters that caught Ashley du Preez leaving Chiefs while the
Wikipedia squad template still listed him, and that carry the promoted clubs
(Kruger United, Milford) the day the league changed. FALLBACK: Wikipedia's
{{fs player}} squad templates.

Usage:
    from modules.psl_squads import get_squad, predict_xi
    squad = await get_squad("chiefs")          # [{"no": "32", "pos": "GK", "name": "..."}, ...]
    xi    = await predict_xi("chiefs", "4-3-3")  # 11 players honouring the formation
"""
import json
import re
import time
from pathlib import Path

import httpx

CACHE = Path(__file__).parent.parent / "data" / "psl_squads_cache.json"

# ── Fan-name normalisation ─────────────────────────────────────────────────
# ESPN uses legal names; SA fans use match names. "Inácio Santos" (full name
# Inácio Miguel dos Santos) went out in a post and the owner rightly asked
# "who is that?" — every surface must print the name the league knows.
NAME_FIX = {
    "Inácio Santos": "Inácio Miguel",
    "Inacio Santos": "Inácio Miguel",
    "Inácio Miguel dos Santos": "Inácio Miguel",
    "Inacio Miguel dos Santos": "Inácio Miguel",
    "Brandon Peterson": "Brandon Petersen",
    # ESPN lists him as Macheke; every Chiefs fan knows him as Kwinika, and a
    # graphic that uses the name the crowd does not use reads as an outsider's
    # feed (owner, 2026-08-26).
    "Macheke": "Kwinika",
    "Given Macheke": "Given Kwinika",
    "Sibongiseni Macheke": "Sibongiseni Kwinika",
}


def fix_surname(token: str) -> str:
    """Fix a bare surname as it appears on a team sheet or a board chip."""
    return NAME_FIX.get(token, token)


def fix_name(name: str) -> str:
    return NAME_FIX.get(name, name)


# Confirmed departures ESPN still lists (owner + news verified 2026-08-17).
# NEVER let these appear in squads, XIs or posts.
DEPARTED = {
    "chiefs": {"Thabo Cele", "Thatayaone Ditlhokwe", "Ashley Du Preez"},
}


def is_departed(club_key: str, name: str) -> bool:
    return name in DEPARTED.get(club_key, set())
CACHE_TTL = 24 * 3600              # 1 day — rosters move mid-window

WIKI_API = "https://en.wikipedia.org/w/api.php"
ESPN_ROSTER = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/teams/{tid}/roster"
HDRS = {"User-Agent": "GenesisNewsPSL/1.0 (contact: mdlulipenuel@gmail.com)"}

# club key -> ESPN team id (league rsa.1, 2026-27 season)
ESPN_TEAMS = {
    "amazulu": 7079, "chippa": 11913, "durban_city": 22348, "arrows": 7077,
    "chiefs": 7081, "kruger": 22350, "sundowns": 7084, "gallants": 13317,
    "milford": 21990, "pirates": 7085, "polokwane": 7099, "richards_bay": 18825,
    "sekhukhune": 20814, "siwelele": 131361, "stellenbosch": 18615, "galaxy": 19298,
}
_ESPN_POS = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}

CLUB_PAGES = {
    "chiefs":       "Kaizer Chiefs F.C.",
    "pirates":      "Orlando Pirates F.C.",
    "sundowns":     "Mamelodi Sundowns F.C.",
    "amazulu":      "AmaZulu F.C.",
    "chippa":       "Chippa United F.C.",
    "durban_city":  "Durban City F.C. (2024)",
    "arrows":       "Lamontville Golden Arrows F.C.",
    "magesi":       "Magesi F.C.",
    "gallants":     "Marumo Gallants F.C.",
    "orbit":        "Orbit College F.C.",
    "polokwane":    "Polokwane City F.C.",
    "richards_bay": "Richards Bay F.C.",
    "sekhukhune":   "Sekhukhune United F.C.",
    "siwelele":     "Siwelele F.C.",
    "stellenbosch": "Stellenbosch F.C.",
    "galaxy":       "TS Galaxy F.C.",
    "kruger":       "Kruger United F.C.",
    "milford":      "Milford F.C. (South Africa)",
}

# {{fs player|no=32|nat=RSA|pos=GK|name=[[Brandon Petersen]]}} and variants
_PLAYER_RE = re.compile(
    r"\{\{(?:fs|football squad) player\s*\|([^}]+)\}\}", re.IGNORECASE)


def _field(body: str, key: str) -> str:
    m = re.search(rf"\b{key}\s*=\s*([^|}}]+)", body)
    return (m.group(1) if m else "").strip()


def _clean_name(raw: str) -> str:
    # [[Brandon Petersen]] / [[Miguel Timm|Timm]] / [[X (footballer, born 1997)]]
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", raw)
    name = (m.group(2) or m.group(1)) if m else re.sub(r"[\[\]{}']", "", raw)
    # drop disambiguators — "(soccer)", "(footballer, born 1997)" are not names
    return re.sub(r"\s*\([^)]*\)?", "", name).strip()


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


async def _espn_squad(club_key: str) -> list[dict]:
    """Current roster from ESPN — the primary source."""
    tid = ESPN_TEAMS.get(club_key)
    if not tid:
        return []
    try:
        # NOTE: default client headers on purpose — ESPN's edge returns an empty
        # body for unknown User-Agent strings.
        # (name normalisation happens below via fix_name)
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(ESPN_ROSTER.format(tid=tid))
            athletes = r.json().get("athletes", [])
    except Exception as e:
        print(f"[Squads] ESPN fetch failed for {club_key}: {e}")
        return []
    squad = []
    for a in athletes:
        pos = _ESPN_POS.get((a.get("position") or {}).get("abbreviation", ""), "")
        name = (a.get("fullName") or a.get("displayName") or "").strip()
        if not name or not pos:
            continue
        no = str(a.get("jersey") or "").strip()
        squad.append({"no": no if no.isdigit() else "", "pos": pos,
                      "name": fix_name(name)})
    return squad


async def get_squad(club_key: str, force_refresh: bool = False) -> list[dict]:
    """Current first-team squad: [{"no","pos","name"}, ...]. Empty on failure."""
    cache = _load_cache()
    ent = cache.get(club_key)
    if ent and not force_refresh and time.time() - ent.get("at", 0) < CACHE_TTL:
        return [p for p in ent["squad"]
                if not is_departed(club_key, p["name"])]

    # ESPN first — it tracks transfers and promotions faster than Wikipedia.
    squad = await _espn_squad(club_key)
    if squad:
        squad = [p for p in squad if not is_departed(club_key, p["name"])]
        cache[club_key] = {"at": time.time(), "squad": squad, "source": "espn"}
        _save_cache(cache)
        print(f"[Squads] {club_key}: {len(squad)} current players from ESPN")
        return squad

    page = CLUB_PAGES.get(club_key)
    if not page:
        return ent["squad"] if ent else []
    try:
        async with httpx.AsyncClient(timeout=30, headers=HDRS,
                                     follow_redirects=True) as client:
            r = await client.get(WIKI_API, params={
                "action": "parse", "page": page, "prop": "wikitext",
                "format": "json", "redirects": 1})
            wt = r.json()["parse"]["wikitext"]["*"]
    except Exception as e:
        print(f"[Squads] fetch failed for {club_key}: {e}")
        return ent["squad"] if ent else []

    # Only read the current-squad section — "Notable former players" also uses
    # the same template family further down the page.
    sec = re.search(r"==\s*(?:Current squad|First-team squad|Players)\s*==(.*?)(?:\n==[^=])",
                    wt, re.S | re.IGNORECASE)
    body = sec.group(1) if sec else wt

    squad = []
    for m in _PLAYER_RE.finditer(body):
        f = m.group(1)
        name = _clean_name(_field(f, "name"))
        pos = _field(f, "pos").upper()[:2]
        if not name or pos not in ("GK", "DF", "MF", "FW"):
            continue
        squad.append({"no": re.sub(r"\D", "", _field(f, "no")),
                      "pos": pos, "name": name})

    if squad:
        cache[club_key] = {"at": time.time(), "squad": squad}
        _save_cache(cache)
        print(f"[Squads] {club_key}: {len(squad)} current players from Wikipedia")
    else:
        print(f"[Squads] {club_key}: no squad parsed — page layout may have changed")
    return squad or (ent["squad"] if ent else [])


_INJURY_RE = re.compile(
    r"(injur\w*|ruled out|sidelined|out for|surgery|torn|fracture|hamstring|"
    r"knee|ankle|recovery|doubt\w*|stretchered|suspended|red card)", re.IGNORECASE)


async def injured_players(club_key: str) -> set[str]:
    """
    Surnames to EXCLUDE from a predicted XI, from live injury/suspension
    headlines. A predicted lineup showing a player the whole country knows is
    out reads as lazy — this is the guard against that.
    """
    try:
        from modules.club_brand import CLUB_BRAND
        name = CLUB_BRAND.get(club_key, {}).get("name", club_key)
        import feedparser
        from urllib.parse import quote
        q = quote(f'"{name}" (injury OR injured OR "ruled out" OR suspended)')
        url = (f"https://news.google.com/rss/search?q={q}+when:14d"
               f"&hl=en-ZA&gl=ZA&ceid=ZA:en")
        async with httpx.AsyncClient(timeout=20, headers=HDRS,
                                     follow_redirects=True) as client:
            r = await client.get(url)
        feed = feedparser.parse(r.text)
        titles = [e.get("title", "") for e in feed.entries[:25]]
    except Exception as e:
        print(f"[Squads] injury feed failed for {club_key}: {e}")
        return set()

    squad = await get_squad(club_key)
    out = set()
    for t in titles:
        if not _INJURY_RE.search(t):
            continue
        tl = t.lower()
        for p in squad:
            sn = p["name"].split()[-1].lower()
            if len(sn) >= 4 and sn in tl:
                out.add(p["name"])
    if out:
        print(f"[Squads] {club_key} injury/suspension exclusions: {sorted(out)}")
    return out


SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/teams/{tid}/schedule"


async def recent_starts(club_key: str, matches: int = 4) -> tuple[dict, str | None]:
    """
    Who has ACTUALLY been starting: {surname_lower: starts} counted from the
    club's last completed matches (real ESPN team sheets), plus the formation
    they most recently used. This is what makes a predicted XI credible —
    recent selection beats shirt-number guesswork.
    """
    tid = ESPN_TEAMS.get(club_key)
    if not tid:
        return {}, None
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(SCHEDULE.format(tid=tid))
            events = r.json().get("events", [])
    except Exception as e:
        print(f"[Squads] schedule fetch failed: {e}")
        return {}, None
    done = [e for e in events
            if (e.get("competitions") or [{}])[0].get("status", {})
            .get("type", {}).get("completed")]
    done.sort(key=lambda e: e.get("date", ""), reverse=True)

    from modules.psl_fixtures import official_lineups
    counts, formation = {}, None
    for e in done[:matches]:
        sheet = (await official_lineups(str(e["id"]))).get(club_key)
        if not sheet:
            continue
        if formation is None:
            formation = sheet.get("formation")
        for p in sheet["players"]:
            sur = " ".join(p.split()[1:]).lower() or p.lower()
            counts[sur] = counts.get(sur, 0) + 1
    if counts:
        print(f"[Squads] {club_key}: starts counted over {min(len(done), matches)} "
              f"recent match(es), last formation {formation}")
    return counts, formation


async def recent_positions(club_key: str, matches: int = 4,
                           mode: str = "latest") -> dict:
    """{surname: ESPN position abbreviation} from recent real team sheets.

    Separate from recent_starts() rather than bolted onto its return value,
    because four callers unpack that as a two-tuple and a third element would
    break every one of them.

    This is the ONLY source of side information in the pipeline. The squad
    cache from Wikipedia/ESPN says "DF" for Monyane and "DF" for Mmodi, so a
    predicted XI built from it cannot tell a right back from a left back - it
    put whoever the sort ranked higher on whichever flank came first. The match
    feed is explicit: Monyane RB/RM, Mmodi LB/LM, Macheke CD-R.

    Most recent match wins, so a player who has switched flanks is placed where
    he last actually played rather than where he once did.
    """
    tid = ESPN_TEAMS.get(club_key)
    if not tid:
        return {}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(SCHEDULE.format(tid=tid))
            events = r.json().get("events", [])
    except Exception as e:
        print(f"[Squads] schedule fetch failed for positions: {e}")
        return {}
    done = [e for e in events
            if (e.get("competitions") or [{}])[0].get("status", {})
            .get("type", {}).get("completed")]
    done.sort(key=lambda e: e.get("date", ""), reverse=True)

    from modules.psl_fixtures import official_lineups
    out: dict = {}
    tally: dict = {}
    # Oldest first so the most recent sheet overwrites, not the other way round.
    for e in reversed(done[:matches]):
        sheet = (await official_lineups(str(e["id"]))).get(club_key)
        if sheet and sheet.get("positions"):
            out.update(sheet["positions"])
            for sur, abbr in sheet["positions"].items():
                tally.setdefault(sur, {})
                tally[sur][abbr] = tally[sur].get(abbr, 0) + 1

    if mode == "frequent":
        # Where a man USUALLY plays, not where he played once.
        #
        # "latest" is right for a line-up card - it places him where the coach
        # last put him. It is wrong for a role analysis: Monyane was RM in one
        # 3-4-3 and RB in the match before, so latest-wins would teach "how a
        # modern right winger plays" about a full back, which is precisely the
        # wrong-position complaint this data was added to fix.
        # Ties break towards the most recent, since `out` already holds it.
        for sur, counts in tally.items():
            best = max(counts.values())
            if counts.get(out.get(sur, ""), 0) == best:
                continue                      # latest is already a top choice
            out[sur] = max(counts, key=lambda a: (counts[a], a == out.get(sur)))
    if out:
        print(f"[Squads] {club_key}: side data for {len(out)} players from real sheets")
    return out


async def predict_xi(club_key: str, formation: str | None = None,
                     force_refresh: bool = False) -> list[str]:
    players, _f = await predict_xi2(club_key, formation, force_refresh)
    return players


async def predict_xi2(club_key: str, formation: str | None = None,
                      force_refresh: bool = False,
                      force_in: list[str] | None = None) -> tuple[list[str], str]:
    """
    A plausible XI drawn ONLY from the current squad, ranked by RECENT REAL
    STARTS (last matches' team sheets), then shirt number. Injured/suspended
    players are excluded. formation=None auto-uses the club's latest real
    formation. Returns (["32 Petersen", ...], formation).
    """
    from modules.psl_fixtures import side_of as _side_of
    squad = await get_squad(club_key, force_refresh=force_refresh)
    if not squad:
        return [], formation or "4-3-3"
    hurt = await injured_players(club_key)
    if hurt:
        squad = [p for p in squad if p["name"] not in hurt]

    starts, recent_formation = await recent_starts(club_key)
    sides = await recent_positions(club_key)
    if not formation:
        formation = recent_formation or "4-3-3"

    # Bold calls from modules/lineup_variety.py. Ranking is by RECENT STARTS,
    # so a man who has not started cannot rise into the XI on merit - which is
    # precisely what makes him a bold call, and precisely why he never appeared
    # when the rotation asked for him. Promoting him here is the difference
    # between a rotation that changes the card and one that only changes a
    # label on it.
    forced = {str(n).strip().lower() for n in (force_in or []) if str(n).strip()}

    # Charge for over-exposure. Ranking on starts alone is a TOTAL ORDER over a
    # squad that barely changes, so it returns the same ten names forever - five
    # builds on 2 Sep differed by exactly one shirt despite five formations and
    # five bold calls. Subtracting a penalty per recent appearance lets a squad
    # man who has fronted nothing overtake a regular who has fronted everything,
    # without ever picking at random: every name is still ordered by form.
    try:
        from modules.player_rotation import exposure_penalty
        penalty = exposure_penalty(club_key)
    except Exception as e:
        print(f"[Squads] rotation penalty unavailable ({e}) — ranking on form only")
        penalty = {}
    need = {"GK": 1}
    lines = [int(n) for n in str(formation).split("-") if n.strip().isdigit()]
    if len(lines) == 3:
        need.update({"DF": lines[0], "MF": lines[1], "FW": lines[2]})
    elif len(lines) == 4:   # e.g. 4-2-3-1 — collapse the two middle bands to MF
        need.update({"DF": lines[0], "MF": lines[1] + lines[2], "FW": lines[3]})
    else:
        need.update({"DF": 4, "MF": 3, "FW": 3})

    _side = {k: _side_of(v) for k, v in sides.items()}

    def surname(n: str) -> str:
        w = n.split()
        if len(w) >= 2 and w[-2].lower() in ("du", "de", "van", "von", "le", "da", "dos"):
            return " ".join(w[-2:])          # Du Preez, Van Rooyen, De Reuck
        return w[-1] if w else n

    def _key(p):
        # forced picks first, then form MINUS recent exposure, then shirt number
        shirt = int(p["no"]) if p["no"].isdigit() else 99
        sn = surname(p["name"]).lower()
        score = starts.get(sn, 0) - penalty.get(sn, 0.0)
        return (0 if sn in forced else 1, -score, shirt)

    xi = []
    for pos in ("GK", "DF", "MF", "FW"):
        pool = sorted([p for p in squad if p["pos"] == pos], key=_key)
        take = pool[:need.get(pos, 0)]
        # short-handed line (injuries/registration gaps upstream) — pad from
        # the neighbouring lines so the card always shows 11
        if len(take) < need.get(pos, 0):
            extra = sorted([p for p in squad if p["pos"] != pos and p not in xi
                            and p not in take], key=_key)
            take += extra[:need[pos] - len(take)]

        # Lay the line out ACROSS the pitch before adding it. The card draws a
        # row in list order, so this ordering IS the player's position on the
        # graphic - until now the line came out in form order, which is why a
        # right back could appear at left back. Men with no published side sit
        # in the middle (0) and keep their form order, which is right: an
        # unknown is a centre-back or a central midfielder far more often
        # than a full-back.
        take.sort(key=lambda q: _side.get(surname(q["name"]).lower(), 0))
        xi += take
    xi = xi[:11]
    return [f"{p['no']} {surname(p['name'])}".strip() for p in xi], formation


if __name__ == "__main__":
    import asyncio

    async def _t():
        for club in ("chiefs", "sundowns", "pirates"):
            xi = await predict_xi(club, "4-3-3")
            print(f"\n{club} 4-3-3: {xi}")
    asyncio.run(_t())
