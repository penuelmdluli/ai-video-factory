"""Live South African news feed for Tech Pulse Africa.

The page went quiet because it had nothing real to say. Its topic bank holds
ANGLES ("the big South African story everyone is talking about today") and the
model was left to fill in the story itself, so it reached for whatever was
safely evergreen: Home Affairs queues, a Cape Town water tariff, a Zimbabwean
e-visa. All true, none of them what anyone was actually talking about that day.
A page of timeless service journalism is a page nobody has a reason to open.

So this module supplies the story instead of the model inventing it, the same
contract modules/psl_news.py already gives Genesis: the headlines are THE ONLY
FACTS the script may use.

The ranking is the point. One outlet's front page is one editor's opinion; a
story that five newsrooms all ran today is the story the country is having an
argument about. So headlines are clustered across outlets and ranked by how
many DISTINCT publishers carry them - corroboration as the heat signal, rather
than trusting whichever feed answered first. That also happens to be the
cheapest fact-check available: a single-source claim never leads.

PSL football is excluded on purpose. Genesis News owns that beat and two of the
owner's pages competing for the same story helps neither.
"""
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import httpx

CACHE_PATH = Path(__file__).parent.parent / "data" / "sa_news_cache.json"
# 40 min. The three build slots are hours apart, so each gets a genuinely fresh
# read, while a retry inside the same slot reuses the fetch instead of hammering
# fourteen feeds again.
CACHE_TTL_SECONDS = 60 * 40

# ── Feeds ──────────────────────────────────────────────────────
# Broad enough that a big story cannot slip through a topical gap: the first
# two are undirected ("what is South Africa reading right now"), the rest are
# the beats this audience has shown up for. The point is coverage, not depth -
# depth comes from the same story appearing across several of them.
QUERIES = [
    "South Africa",
    "South Africa breaking news",
    "South Africa protest march",
    "South Africa politics government",
    "Ramaphosa",
    "parliament South Africa",
    "load shedding Eskom",
    "rand petrol price South Africa",
    "SASSA grant South Africa",
    "South Africa crime police",
    "South Africa immigration border",
    "South Africa jobs unemployment",
    "Johannesburg Durban Cape Town municipality",
    "South Africa court ruling",
]

# Running stories the page tracks even on the days they are not the loudest.
#
# The general queries above answer "what broke today". They do NOT reliably
# reach a story that is BUILDING - measured on 2 Sep 2026, the fourteen broad
# queries returned 153 headlines and not one of them mentioned March and March,
# while a direct query found the AfriForum alliance and the Steinberg piece
# immediately. A national day of action four weeks out is invisible to a
# 2-day news window right up until it isn't.
#
# These are pooled with everything else and ranked identically - a watchlist
# subject with one sleepy outlet still loses to a five-outlet story. The
# watchlist buys visibility, not priority.
WATCHLIST = [
    "March and March Ngobese-Zuma",
    "South Africa immigration policy debate",
    "Operation Dudula",
    "AfriForum South Africa",
    "national shutdown South Africa",
    "ANC GNU coalition",
    "MK Party Zuma",
    "EFF Malema",
    "service delivery protest South Africa",
]

# Outlets whose byline is worth naming on screen. Untrusted sources are not
# dropped - they still count towards how loud a story is - but a cluster is
# only ever attributed to a trusted outlet, so the page never cites a
# content farm as its authority.
TRUSTED_SOURCES = [
    "News24", "IOL", "EWN", "Eyewitness News", "TimesLIVE", "Times LIVE",
    "SowetanLIVE", "Sowetan", "The Citizen", "BusinessTech", "Business Day",
    "Daily Maverick", "Mail & Guardian", "SABC News", "SABC", "BusinessLIVE",
    "Moneyweb", "The South African", "Briefly", "Independent Online",
    "Reuters", "AP", "Associated Press", "BBC", "Al Jazeera", "Bloomberg",
    "GroundUp", "Daily Sun", "City Press", "Sunday Times", "Newzroom Afrika",
]

# Genesis News owns football. A Chiefs story reaching this page is a bug, not
# a bonus, so it is dropped before ranking rather than argued with in a prompt.
FOOTBALL_MARKERS = re.compile(
    # BARE CLUB NAMES TOO. The list held only the full names, so "Chiefs
    # drop points: Da Cruz on injuries and Petersen" walked onto Tech Pulse
    # Africa on 2 Sep - a football story on the page explicitly walled off
    # from football, and the owner had to ask for it to be deleted.
    # Newsrooms write "Kaizer Chiefs" once and then Chiefs, Pirates,
    # Sundowns for the rest of the piece.
    r"\b(chiefs|pirates|sundowns|amakhosi|buccaneers|masandawana|"
    r"psl|premier soccer league|betway premiership|kaizer chiefs|orlando "
    r"pirates|mamelodi sundowns|bafana|banyana|caf|afcon|nedbank cup|carling "
    r"knockout|soccer|striker|midfielder|goalkeeper|transfer window|"
    r"stellenbosch fc|supersport united|sekhukhune|richards bay|"
    r"marumo gallants|golden arrows|amazulu|chippa|magesi|polokwane city)\b",
    re.IGNORECASE,
)

# Aggregator sludge, live-blog stubs and SEO filler.
JUNK_MARKERS = re.compile(
    r"(^live[: ]|liveblog|live blog|^watch:? *$|^recap|^photos?:|"
    r"horoscope|lotto results|weather forecast|^opinion *\| *$|"
    r"betting|casino|odds|coupon|discount code|^sponsored)",
    re.IGNORECASE,
)

# Claims a headline is only REPORTING, not establishing. Flagged so narration
# says "reports say" - the same guard psl_news uses for transfer rumours, and
# it matters far more here: this page names real, living people.
CLAIM_MARKERS = re.compile(
    r"\b(alleged|allegedly|reportedly|claims?|accused|denies|denied|"
    r"rumour|rumor|speculation|said to be|set to|expected to|"
    r"could|may |might |investigating|probe)\b",
    re.IGNORECASE,
)

# South-African relevance. Google News honours hl=en-ZA for RANKING, not for
# subject: "national shutdown South Africa" returned the US House passing a
# funding bill, carried by four Midwestern local papers, and it ranked FIRST on
# corroboration alone. A page for 10,442 South Africans led by a story about
# Wisconsin is the exact failure this module exists to end, so relevance is
# checked rather than assumed.
#
# An item qualifies on EITHER axis - a South African newsroom, or South African
# subject matter - because both single-axis tests fail in practice: Reuters and
# Bloomberg file the biggest SA business stories (foreign outlet, SA subject),
# and a local paper's headline often names only "Eskom" or "the Reserve Bank"
# with the country left implied.
SA_OUTLET_MARKERS = re.compile(
    r"(\.co\.za|\.za\b|news24|iol\b|ewn\b|eyewitness|timeslive|times live|"
    r"sowetan|citizen|businesstech|business day|daily maverick|mail & guardian|"
    r"sabc|moneyweb|briefly|groundup|city press|sunday times|daily sun|"
    r"newzroom|enca|scrolla|joburg|south african government news)",
    re.IGNORECASE,
)

SA_SUBJECT_MARKERS = re.compile(
    r"\b(south africa\w*|mzansi|\bsa\b|eskom|sassa|\brand\b|rands|load ?shedding|"
    r"johannesburg|joburg|jozi|cape town|durban|pretoria|tshwane|ekurhuleni|"
    r"soweto|gauteng|kwazulu|natal|limpopo|mpumalanga|free state|"
    r"north west|northern cape|eastern cape|western cape|bloemfontein|"
    r"port elizabeth|gqeberha|polokwane|nelspruit|mbombela|kimberley|"
    r"\banc\b|\beff\b|\bda\b|\bmk party\b|ifp|ramaphosa|zuma|malema|mashatile|"
    r"steenhuisen|mbeki|union buildings|luthuli house|parliament of south|"
    r"transnet|prasa|sars|sarb|reserve bank|nersa|prasa|denel|"
    r"home affairs|hawks|saps|nprosecut|npa\b|zondo|phala phala|"
    r"matric|nsfas|bela|afriforum|dudula|march and march|"
    r"taxi|spaza|township|shack|amapiano)\b",
    re.IGNORECASE,
)


def _is_sa(item: dict) -> bool:
    return bool(
        SA_OUTLET_MARKERS.search(item.get("source", ""))
        or SA_SUBJECT_MARKERS.search(item.get("title", ""))
    )


# Words that would otherwise cluster the entire feed into one lump: every
# headline here says "South Africa" somewhere.
STOPWORDS = {
    "south", "africa", "african", "africans", "sa", "news", "says", "said",
    "after", "over", "with", "from", "that", "this", "will", "have", "has",
    "been", "into", "more", "than", "what", "when", "where", "which", "who",
    "about", "amid", "back", "calls", "call", "could", "does", "down", "first",
    "here", "how", "its", "just", "last", "like", "make", "makes", "many",
    "may", "new", "not", "now", "off", "one", "only", "out", "own", "part",
    "past", "plans", "plan", "post", "read", "report", "reports", "set",
    "should", "still", "take", "takes", "their", "there", "these", "they",
    "those", "time", "top", "two", "under", "until", "video", "watch", "way",
    "week", "were", "why", "year", "years", "your", "day", "days", "get",
    "gets", "big",
}


def _google_news_rss(query: str) -> str:
    """South-Africa-scoped Google News RSS search URL, last 2 days only."""
    return (
        f"https://news.google.com/rss/search?q={quote_plus(query)}+when:2d"
        f"&hl=en-ZA&gl=ZA&ceid=ZA:en"
    )


def _source_of(entry) -> str:
    """Publisher name - Google News puts it in <source> and after the last ' - '."""
    src = ""
    try:
        src = (entry.get("source", {}) or {}).get("title", "") or ""
    except Exception:
        pass
    if not src and " - " in entry.get("title", ""):
        src = entry["title"].rsplit(" - ", 1)[-1].strip()
    return src.strip()


# Newsroom CMSs emit curly quotes, en/em dashes and ellipses. They survive the
# feed fine, then land in an edge-tts prompt, a caption and a PIL-rendered
# on-screen card - three places that each mangle them differently. Flattening
# once, here, beats debugging a "cities? unpaid" card later.
_PUNCT = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    "…": "...", " ": " ", "​": "", "﻿": "",
}


def _ascii_punct(text: str) -> str:
    for bad, good in _PUNCT.items():
        text = text.replace(bad, good)
    return text


def _clean_title(title: str, source: str) -> str:
    """Google News appends ' - Publisher' to every title; strip it."""
    title = _ascii_punct(title)
    source = _ascii_punct(source)
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


def _age_hours(published: str) -> float:
    """Hours since publication; 999 when unknown so undated items never lead."""
    if not published:
        return 999.0
    try:
        dt = datetime.fromisoformat(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    except Exception:
        return 999.0


def _tokens(title: str) -> set:
    """Significant words - what two headlines about the same story share."""
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", title.lower())
    return {w for w in words if len(w) > 3 and w not in STOPWORDS}


async def _fetch_feed(client: httpx.AsyncClient, query: str, limit: int = 12) -> list[dict]:
    """Fetch one Google News query and return cleaned, attributed headlines."""
    try:
        resp = await client.get(
            _google_news_rss(query),
            headers={"User-Agent": "Mozilla/5.0 (compatible; TechPulseAfrica/1.0)"},
        )
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"[SANews] feed failed for '{query}': {e}")
        return []

    items = []
    for entry in feed.entries[: limit * 3]:
        raw_title = (entry.get("title") or "").strip()
        if not raw_title:
            continue
        source = _source_of(entry)
        title = _clean_title(raw_title, source)
        if len(title) < 20:
            continue
        if JUNK_MARKERS.search(title) or FOOTBALL_MARKERS.search(title):
            continue
        items.append({
            "title": title,
            "source": source or "unattributed",
            "url": entry.get("link", ""),
            "published": _published_at(entry),
            "trusted": any(s.lower() in source.lower() for s in TRUSTED_SOURCES),
            "is_claim": bool(CLAIM_MARKERS.search(title)),
        })
        if len(items) >= limit:
            break
    return items


def _cluster(items: list[dict]) -> list[dict]:
    """Group headlines that are the same story, told by different newsrooms.

    Greedy token overlap rather than exact-title dedup: outlets never word a
    headline identically, so matching on the words they DO share ("ngobese",
    "march", "immigrants") is what turns eight scattered feeds into one ranked
    story list. Three shared significant words is the bar - two produced
    clusters joined by nothing more than "eskom" and "tariff".
    """
    clusters: list[dict] = []
    for item in items:
        toks = _tokens(item["title"])
        if len(toks) < 3:
            continue
        placed = False
        for c in clusters:
            shared = toks & c["tokens"]
            if len(shared) >= 3 or (
                len(shared) >= 2 and len(shared) / max(1, len(toks | c["tokens"])) >= 0.35
            ):
                c["items"].append(item)
                # Intersect rather than union: a cluster's identity is the words
                # every member agrees on. Union lets one long headline drag in
                # unrelated stories on a word the others never used.
                c["tokens"] = shared if len(shared) >= 3 else c["tokens"]
                placed = True
                break
        if not placed:
            clusters.append({"tokens": toks, "items": [item]})

    ranked = []
    for c in clusters:
        sources = {i["source"] for i in c["items"] if i["source"] != "unattributed"}
        trusted = [i for i in c["items"] if i["trusted"]]
        # Lead with a trusted outlet's wording, and prefer the newest of those.
        pool = trusted or c["items"]
        lead = min(pool, key=lambda i: _age_hours(i["published"]))
        ranked.append({
            "headline": lead["title"],
            "url": lead["url"],
            "lead_source": lead["source"],
            "sources": sorted(sources),
            "outlet_count": len(sources),
            "item_count": len(c["items"]),
            "trusted_count": len(trusted),
            "age_hours": round(_age_hours(lead["published"]), 1),
            "is_claim": any(i["is_claim"] for i in c["items"]),
            "also": [i["title"] for i in c["items"] if i["title"] != lead["title"]][:3],
        })

    # Corroboration first, then trusted weight, then freshness. Outlet count is
    # deliberately the primary key: it is the only signal here that measures
    # what the country is talking about rather than what one desk published.
    ranked.sort(key=lambda s: (-s["outlet_count"], -s["trusted_count"], s["age_hours"]))
    return ranked


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
        print(f"[SANews] cache write failed (non-critical): {e}")


async def get_sa_briefing(force_refresh: bool = False) -> dict:
    """Fetch, cluster and rank today's South African stories."""
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    # Watchlist feeds are fetched shallower: they exist so a building story is
    # FOUND, and pulling twelve deep on each would flood the pool with nine
    # subjects' worth of back-catalogue and skew the clustering.
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[_fetch_feed(client, q) for q in QUERIES],
            *[_fetch_feed(client, q, limit=5) for q in WATCHLIST],
            return_exceptions=True,
        )

    items: list[dict] = []
    seen_urls = set()
    for r in results:
        if isinstance(r, Exception):
            continue
        for item in r:
            # The same article is returned by several of our queries; count it
            # once, or a story wins purely for matching more search terms.
            key = item["url"] or item["title"]
            if key in seen_urls:
                continue
            seen_urls.add(key)
            items.append(item)

    sa_items = [i for i in items if _is_sa(i)]
    dropped = len(items) - len(sa_items)
    if dropped:
        print(f"[SANews] dropped {dropped} non-South-African headlines")

    stories = _cluster(sa_items)
    briefing = {
        "fetched_at": time.time(),
        "fetched_iso": datetime.now().isoformat(timespec="seconds"),
        "raw_count": len(items),
        "sa_count": len(sa_items),
        # 25, not 12. headlines_for_prompt only ever shows the top 8, but
        # modules/dream_cabinet.py mines this same list for WHO is in the news,
        # and a 12-cluster window on a day dominated by two big stories yielded
        # exactly two usable names. The tail costs nothing - it is already
        # fetched and clustered - and it is where everyone below the lead story
        # lives.
        "stories": stories[:25],
    }
    if stories:
        _save_cache(briefing)
    else:
        print("[SANews] no stories after filtering - not caching an empty read")
    return briefing


def _format_story(s: dict, rank: int) -> str:
    tag = "REPORTED CLAIM" if s["is_claim"] else "REPORTED"
    outlets = ", ".join(s["sources"][:4]) or s["lead_source"]
    line = (f"{rank}. [{tag} | {s['outlet_count']} outlets | {s['age_hours']}h ago] "
            f"{s['headline']}  (via {outlets})")
    if s["also"]:
        line += "\n   also reported as: " + " / ".join(s["also"][:2])
    return line


async def headlines_for_prompt(force_refresh: bool = False, limit: int = 8) -> str:
    """The block injected into the topic prompt as the only permitted facts."""
    briefing = await get_sa_briefing(force_refresh=force_refresh)
    stories = briefing.get("stories") or []
    if not stories:
        return ""
    lines = [_format_story(s, i + 1) for i, s in enumerate(stories[:limit])]
    return (f"(read {briefing.get('fetched_iso', '')}, ranked by how many "
            f"newsrooms are carrying each story)\n" + "\n".join(lines))


async def hot_story(force_refresh: bool = False) -> Optional[dict]:
    """The single most-corroborated story right now, or None if the feeds are dry."""
    briefing = await get_sa_briefing(force_refresh=force_refresh)
    stories = briefing.get("stories") or []
    return stories[0] if stories else None


if __name__ == "__main__":
    async def _main():
        b = await get_sa_briefing(force_refresh=True)
        print(f"raw headlines: {b['raw_count']}   clusters kept: {len(b['stories'])}\n")
        for i, s in enumerate(b["stories"], 1):
            print(_format_story(s, i))
            print()

    asyncio.run(_main())
