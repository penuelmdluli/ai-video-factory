"""
PSL News — real South African football headlines for the Genesis News page.

Why this exists
---------------
The `sa_pulse` page is now a PSL football channel built around the big three:
Kaizer Chiefs, Orlando Pirates and Mamelodi Sundowns. Football news is
check-able — a fan spots a fake score, a fake signing or an invented quote
instantly, and the page loses all credibility. So scripts must NEVER be
invented by the model: they are grounded in headlines that real, named South
African football outlets actually published.

Sources (all free, no API key): Google News RSS scoped to South Africa
(gl=ZA, ceid=ZA:en), which aggregates Soccer Laduma, KickOff, iDiski Times,
FARPost, SABC Sport, TimesLIVE, Sowetan and the official club sites. Every
headline keeps its publisher name so the video and blog can credit the source.

Usage
-----
    from modules.psl_news import get_psl_briefing, headlines_for_prompt

    briefing = await get_psl_briefing()          # structured, per-club
    context  = await headlines_for_prompt()      # string for the topic generator
"""
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import feedparser
import httpx

CACHE_PATH = Path(__file__).parent.parent / "data" / "psl_news_cache.json"
CACHE_TTL_SECONDS = 60 * 45  # 45 min — three daily slots stay fresh, no feed hammering

# ── The big three + the competitions they play in ─────────────────────────
# key -> (display name, nickname, Google News query)
# Betting promos and affiliate spam ride in on the league's sponsor name
# ("Betway Premiership"), and read exactly like a headline. Never a story.
JUNK_MARKERS = re.compile(
    r"\b(sign[- ]?up offer|free bets?|bet £|bet \$|bet r\d|odds|betting tips|"
    r"promo code|bonus code|predictions? and odds|casino|how to bet|"
    r"deposit bonus|acca|accumulator)\b", re.I)

CLUBS = {
    "chiefs": ("Kaizer Chiefs", "Amakhosi", "Kaizer Chiefs"),
    "pirates": ("Orlando Pirates", "Buccaneers", "Orlando Pirates"),
    "sundowns": ("Mamelodi Sundowns", "Masandawana", "Mamelodi Sundowns"),
}

# CHIEFS BIAS — Amakhosi are the biggest-engagement club in SA football, so the
# page deliberately over-indexes on Kaizer Chiefs: more headlines pulled, more
# kept, and Chiefs lead every briefing. Pirates and Sundowns stay strong
# secondary coverage (they are also what Chiefs fans argue about).
FEED_LIMITS = {"chiefs": 14, "pirates": 10, "sundowns": 10,
               "premiership": 10, "cups": 6, "continental": 5,
               "transfers": 8, "bafana": 6, "weekend": 8, "others": 8}
KEEP_LIMITS = {"chiefs": 8, "pirates": 6, "sundowns": 6,
               "premiership": 7, "cups": 4, "continental": 3,
               "transfers": 6, "bafana": 4, "weekend": 6, "others": 6}

# Extra Chiefs-only sweeps. Amakhosi stay the priority club — the owner wants
# MORE Chiefs, just not the same story twice. Two queries only ever surfaced
# the one running storyline, so these widen the angles Chiefs news can arrive
# from: squad, youth, individual players, the next opponent, the club off the
# pitch. Three are used per run, rotating, so the Chiefs section is deep AND
# varied.
CHIEFS_ANGLE_QUERIES = [
    "Kaizer Chiefs transfer news signing",
    "Kaizer Chiefs coach Fernando Da Cruz team news",
    "Kaizer Chiefs next match preview fixture",
    "Kaizer Chiefs player interview reaction",
    "Kaizer Chiefs youth academy development player",
    "Kaizer Chiefs injury return fitness update",
    "Kaizer Chiefs fans supporters Amakhosi reaction",
    "Kaizer Chiefs log position table Betway Premiership",
    "Kaizer Chiefs Nedbank Cup MTN8 Carling Knockout",
    "Kaizer Chiefs contract renewal squad depth",
]


def rotating_chiefs_queries(day_index: int, n: int = 4) -> list[str]:
    """Walk the Chiefs angle list so every run pulls a different mix."""
    start = (day_index * n) % len(CHIEFS_ANGLE_QUERIES)
    return [CHIEFS_ANGLE_QUERIES[(start + i) % len(CHIEFS_ANGLE_QUERIES)]
            for i in range(n)]


# kept for callers/back-compat
CHIEFS_EXTRA_QUERIES = CHIEFS_ANGLE_QUERIES[:2]

COMPETITION_QUERIES = {
    "premiership": "Betway Premiership PSL",
    "cups": "MTN8 OR Nedbank Cup OR Carling Knockout South Africa football",
    "continental": "CAF Champions League South African club",
    # League-wide angles. Without these the pool is only ever the big three,
    # which is how the page ended up telling one fixture twenty times.
    "transfers": "Betway Premiership transfer signing South Africa football",
    "bafana": "Bafana Bafana South Africa national team squad",
    "weekend": "Betway Premiership fixtures preview this weekend",
}

# The other thirteen Premiership clubs. Three are swept per run, rotating by
# day, so the story pool always carries something that is not the big three.
OTHER_CLUBS = [
    "Stellenbosch FC", "SuperSport United", "Sekhukhune United",
    "AmaZulu FC", "Richards Bay FC", "Golden Arrows", "Polokwane City",
    "Chippa United", "Magesi FC", "Marumo Gallants", "TS Galaxy",
    "Durban City", "Orbit College",
]


def rotating_other_clubs(day_index: int, n: int = 3) -> list[str]:
    """Pick n other clubs for this run, walking the list so all get covered."""
    if not OTHER_CLUBS:
        return []
    start = (day_index * n) % len(OTHER_CLUBS)
    return [OTHER_CLUBS[(start + i) % len(OTHER_CLUBS)] for i in range(n)]

# Outlets we consider trustworthy SA football reporting. Headlines from other
# publishers are still kept, but these are surfaced first.
TRUSTED_SOURCES = [
    "Soccer Laduma", "KickOff", "iDiski Times", "FARPost", "SABC Sport",
    "TimesLIVE", "Sowetan", "SowetanLIVE", "The Citizen", "IOL",
    "Kaizer Chiefs", "Orlando Pirates", "Mamelodi Sundowns", "PSL",
    "Goal.com", "SuperSport",
]

# Headlines matching these are transfer/rumour talk — flagged so the script
# says "reports claim" instead of stating it as confirmed fact.
RUMOUR_MARKERS = re.compile(
    r"\b(rumour|rumor|linked|reportedly|set to|eyeing|target|talks|swoop|"
    r"could join|move for|interest in|speculation)\b",
    re.IGNORECASE,
)


def _google_news_rss(query: str) -> str:
    """South-Africa-scoped Google News RSS search URL."""
    from urllib.parse import quote_plus
    return (
        f"https://news.google.com/rss/search?q={quote_plus(query)}+when:2d"
        f"&hl=en-ZA&gl=ZA&ceid=ZA:en"
    )


def _normalise(title: str) -> str:
    """Key for de-duplicating the same story republished by several outlets."""
    t = re.sub(r"[^a-z0-9 ]", "", title.lower())
    return " ".join(sorted(t.split()))[:120]


def _source_of(entry) -> str:
    """Publisher name — Google News puts it in <source> and after the last ' - '."""
    src = ""
    try:
        src = (entry.get("source", {}) or {}).get("title", "") or ""
    except Exception:
        pass
    if not src and " - " in entry.get("title", ""):
        src = entry["title"].rsplit(" - ", 1)[-1].strip()
    return src.strip()


def _clean_title(title: str, source: str) -> str:
    """Google News appends ' - Publisher' to every title; strip it."""
    if source and title.endswith(f" - {source}"):
        return title[: -(len(source) + 3)].strip()
    return title.strip()


def _published_at(entry) -> str:
    try:
        p = entry.get("published_parsed")
        if p:
            return datetime(*p[:6], tzinfo=timezone.utc).isoformat()
    except Exception:
        pass
    return ""


async def _fetch_feed(client: httpx.AsyncClient, query: str, limit: int = 8) -> list[dict]:
    """Fetch one Google News query and return cleaned, attributed headlines."""
    try:
        resp = await client.get(
            _google_news_rss(query),
            headers={"User-Agent": "Mozilla/5.0 (compatible; GenesisNews/1.0)"},
        )
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"[PSLNews] feed failed for '{query}': {e}")
        return []

    items = []
    for entry in feed.entries[: limit * 2]:
        raw_title = entry.get("title", "").strip()
        if not raw_title:
            continue
        source = _source_of(entry)
        title = _clean_title(raw_title, source)
        if len(title) < 15:
            continue
        if JUNK_MARKERS.search(title):
            continue
        items.append({
            "title": title,
            "source": source or "unattributed",
            "url": entry.get("link", ""),
            "published": _published_at(entry),
            "trusted": any(s.lower() in source.lower() for s in TRUSTED_SOURCES),
            "is_rumour": bool(RUMOUR_MARKERS.search(title)),
        })
        if len(items) >= limit:
            break
    return items


def _load_cache() -> Optional[dict]:
    try:
        if not CACHE_PATH.exists():
            return None
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if time.time() - data.get("fetched_at", 0) < CACHE_TTL_SECONDS:
            return data
    except Exception:
        pass
    return None


def _save_cache(data: dict):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[PSLNews] cache write failed (non-critical): {e}")


async def get_psl_briefing(force_refresh: bool = False) -> dict:
    """
    Fetch the current PSL picture, grouped by club + competition.

    Returns:
        {
          "fetched_at": <epoch>, "fetched_human": "...",
          "chiefs":   [{title, source, url, published, trusted, is_rumour}, ...],
          "pirates":  [...], "sundowns": [...],
          "premiership": [...], "cups": [...], "continental": [...],
          "image_queries": ["Kaizer Chiefs vs ...", ...],
        }
    Never raises — an empty section just means nothing was published recently.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    briefing: dict = {}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        queries = {k: q for k, (_, _, q) in CLUBS.items()}
        queries.update(COMPETITION_QUERIES)
        results = await asyncio.gather(
            *[_fetch_feed(client, q, limit=FEED_LIMITS.get(k, 8))
              for k, q in queries.items()],
            return_exceptions=True,
        )

    # Extra Amakhosi-only sweeps so the Chiefs section is always the deepest,
    # plus a rotating sweep of three other Premiership clubs so the pool is
    # never only the big three.
    from datetime import date as _date
    others_q = rotating_other_clubs(_date.today().toordinal())
    _ = others_q
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        chiefs_qs = rotating_chiefs_queries(_date.today().toordinal())
        extra, other_res = await asyncio.gather(
            asyncio.gather(*[_fetch_feed(client, q, limit=6)
                             for q in chiefs_qs],
                           return_exceptions=True),
            asyncio.gather(*[_fetch_feed(client, f"{c} football news", limit=6)
                             for c in others_q],
                           return_exceptions=True),
        )
    others_items = []
    for r in other_res:
        if not isinstance(r, Exception) and r:
            others_items.extend(r)
    briefing["others_clubs"] = others_q

    seen: set[str] = set()
    # Chiefs are de-duped FIRST so a shared story (e.g. Chiefs vs Sundowns)
    # lands in the Chiefs section rather than being claimed by another club.
    pairs = list(zip(queries.keys(), results)) + [("others", others_items)]
    ordered = sorted(pairs, key=lambda kr: kr[0] != "chiefs")
    for key, result in ordered:
        items = list(result) if not isinstance(result, Exception) and result else []
        if key == "chiefs":
            for e in extra:
                if not isinstance(e, Exception) and e:
                    items.extend(e)
        if not items:
            briefing[key] = []
            continue
        # trusted outlets first, then de-dup the same story across publishers
        unique = []
        for item in sorted(items, key=lambda i: (not i["trusted"],)):
            k = _normalise(item["title"])
            if k in seen:
                continue
            seen.add(k)
            unique.append(item)
        briefing[key] = unique[: KEEP_LIMITS.get(key, 6)]

    briefing["fetched_at"] = time.time()
    briefing["fetched_human"] = datetime.now().strftime("%A %d %B %Y, %H:%M SAST")
    briefing["image_queries"] = _image_queries(briefing)
    _save_cache(briefing)
    return briefing


def _image_queries(briefing: dict) -> list[str]:
    """
    Search-engine-ready queries for REAL match/player photos.

    These are for finding properly credited press images — never for
    AI-generating a real player, which is misinformation.
    """
    year = datetime.now().year
    queries = [
        f"Kaizer Chiefs players celebrating Betway Premiership {year} press photo",
        f"Orlando Pirates squad match action {year} high resolution",
        f"Mamelodi Sundowns attack FNB Stadium {year} press photo",
        f"Soweto Derby Chiefs vs Pirates FNB Stadium crowd {year}",
    ]
    # Pull a specific subject out of the top trusted headline for each club
    for club_key, (display, _nick, _q) in CLUBS.items():
        items = briefing.get(club_key) or []
        if items:
            subject = re.sub(r"[^A-Za-z0-9 ]", "", items[0]["title"])[:60]
            queries.append(f"{display} {subject} photo")
    return queries[:6]


def _format_items(items: list[dict], limit: int = 4) -> str:
    lines = []
    for item in items[:limit]:
        tag = " [REPORT/RUMOUR — say 'reports claim']" if item["is_rumour"] else ""
        lines.append(f"  - {item['title']} (source: {item['source']}){tag}")
    return "\n".join(lines) if lines else "  - (nothing new published in the last 48h)"



# The slot's lead club, set by the builder before it asks for a topic. Keeps
# the rotation in one place so the topic generator and the script writer both
# lead with the same club.
_LEAD_CLUB = "chiefs"


def set_lead_club(club: str):
    global _LEAD_CLUB
    _LEAD_CLUB = (club or "chiefs").lower()


def get_lead_club() -> str:
    return _LEAD_CLUB


async def headlines_for_prompt(force_refresh: bool = False,
                               lead_club: str = "") -> str:
    """Real PSL headlines formatted for injection into an LLM prompt."""
    b = await get_psl_briefing(force_refresh=force_refresh)
    if not any(b.get(k) for k in list(CLUBS) + list(COMPETITION_QUERIES)):
        return ""

    # LEAD ROTATION. Chiefs used to be hard-wired as "lead with this section
    # whenever there is anything at all here", which is how twenty straight
    # reels came out of one Chiefs fixture. Chiefs still lead most slots —
    # they are the biggest audience — but not every slot.
    lead = (lead_club or _LEAD_CLUB or "chiefs").lower()
    if lead not in CLUBS:
        lead = "chiefs"
    labels = {
        "chiefs": "KAIZER CHIEFS (Amakhosi)",
        "pirates": "ORLANDO PIRATES (Buccaneers)",
        "sundowns": "MAMELODI SUNDOWNS (Masandawana)",
    }
    club_keys = [lead] + [k for k in CLUBS if k != lead]
    sections = [
        f"REAL PSL HEADLINES (fetched {b.get('fetched_human', 'just now')}) — "
        f"these are the ONLY facts you may use:",
        f"{labels[lead]} — LEAD CLUB FOR THIS SLOT. Take your story from this "
        f"section if it has anything usable:\n"
        f"{_format_items(b.get(lead, []), 8)}",
    ]
    for k in club_keys[1:]:
        sections.append(f"{labels[k]}:\n{_format_items(b.get(k, []))}")
    sections += [
        f"BETWAY PREMIERSHIP (league-wide):\n"
        f"{_format_items(b.get('premiership', []), 5)}",
        f"OTHER PREMIERSHIP CLUBS — "
        f"{', '.join(b.get('others_clubs', []) or [])}:\n"
        f"{_format_items(b.get('others', []), 5)}",
        f"TRANSFERS:\n{_format_items(b.get('transfers', []), 4)}",
        f"THIS WEEKEND'S FIXTURES:\n{_format_items(b.get('weekend', []), 4)}",
        f"BAFANA BAFANA:\n{_format_items(b.get('bafana', []), 3)}",
        f"CUPS (MTN8 / Nedbank / Carling):\n{_format_items(b.get('cups', []), 3)}",
        f"CONTINENTAL (CAF):\n{_format_items(b.get('continental', []), 2)}",
    ]
    return "\n\n".join(sections)


def briefing_to_markdown(briefing: dict, slot: str = "Update") -> str:
    """Human-readable briefing — used for the 3x daily Morning/Midday/Evening post."""
    out = [f"# PSL {slot} — {briefing.get('fetched_human', '')}", ""]
    for key, label in [
        ("chiefs", "Kaizer Chiefs (Amakhosi)"),
        ("pirates", "Orlando Pirates (Buccaneers)"),
        ("sundowns", "Mamelodi Sundowns (Masandawana)"),
        ("premiership", "Betway Premiership"),
        ("cups", "MTN8 / Nedbank Cup / Carling Knockout"),
        ("continental", "CAF Champions League"),
    ]:
        items = briefing.get(key) or []
        if not items:
            continue
        out.append(f"## {label}")
        for item in items:
            flag = " _(report/rumour — not confirmed)_" if item["is_rumour"] else ""
            out.append(f"- {item['title']} — **{item['source']}**{flag}")
            if item["url"]:
                out.append(f"  - {item['url']}")
        out.append("")
    if briefing.get("image_queries"):
        out.append("## Image search queries (real, credited photos only)")
        out += [f"- `{q}`" for q in briefing["image_queries"]]
    return "\n".join(out)


if __name__ == "__main__":
    async def _test():
        b = await get_psl_briefing(force_refresh=True)
        print(briefing_to_markdown(b, "Test"))
    asyncio.run(_test())
