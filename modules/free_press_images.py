"""
Free, properly-licensed REAL football photos for the PSL page.

Why not just take the pictures off Goal.com / Soccer Laduma: those photos are
not the outlets' to give away — PSL match photography is Gallo Images,
BackpagePix and Getty, licensed to the publisher. Re-uploading them into
monetised reels is the one thing on this page with automated enforcement behind
it (Meta and YouTube both run rights matching on stills and video), and a new
page does not survive repeat strikes.

Wikimedia Commons gets the same thing legally: real, named PSL players, real
FNB Stadium, under CC-BY / CC-BY-SA / public domain. The licence requires
credit, so every result carries the author + licence string and the caller
burns it into the frame.

Usage:
    from modules.free_press_images import search_free_photos
    hits = await search_free_photos("Kaizer Chiefs", limit=3)
    # -> [{url, title, author, license, credit, width, height}, ...]
"""
import asyncio
import re
from typing import Optional

import httpx

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Licences we will actually publish. Anything else (non-commercial, no-derivs,
# "fair use") is dropped — a licence we cannot comply with is worth nothing.
ALLOWED_LICENSE = re.compile(
    r"(cc[- ]by([- ]sa)?([- ]\d(\.\d)?)?|public domain|cc0|pd-)", re.IGNORECASE
)
BLOCKED_LICENSE = re.compile(r"(non[- ]?commercial|\bnc\b|no[- ]?deriv|\bnd\b|fair use)", re.IGNORECASE)

# Search terms that reliably return SA football imagery on Commons.
# Phrase-quoted on purpose. A bare "Chiefs" search returns Edward Curtis
# portraits of Native American chiefs, and a bare "soccer" search returned
# Iranian beach football — neither is usable and both looked like a hit.
CLUB_QUERIES = {
    "chiefs": ['"Kaizer Chiefs"', '"Kaizer Chiefs" football', '"FNB Stadium"'],
    "pirates": ['"Orlando Pirates"', '"Orlando Pirates" football', '"Orlando Stadium"'],
    "sundowns": ['"Mamelodi Sundowns"', '"Mamelodi Sundowns" football', '"Loftus Versfeld"'],
    "generic": ['"Premier Soccer League" South Africa', '"FNB Stadium"',
                '"Soccer City"', '"Orlando Stadium"', '"Loftus Versfeld"'],
}

# A result must look like South African football, or it is dropped. This is the
# guard that kills the Curtis portraits and the beach-soccer set.
RELEVANT = re.compile(
    r"(kaizer chiefs|orlando pirates|mamelodi sundowns|premier soccer league|"
    r"fnb stadium|soccer city|orlando stadium|loftus|moses mabhida|"
    r"south africa|psl|bafana|soweto)",
    re.IGNORECASE,
)
IRRELEVANT = re.compile(
    r"(native american|indian chief|chief joseph|red cloud|curtis|"
    r"beach soccer|tribal|headdress)",
    re.IGNORECASE,
)


def _clean_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


async def _search_titles(client: httpx.AsyncClient, query: str, limit: int) -> list[str]:
    """Find file titles matching a query."""
    try:
        r = await client.get(COMMONS_API, params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": "6",
            "gsrlimit": str(limit * 3),
        })
        data = r.json()
        return [p["title"] for p in (data.get("query", {}).get("pages", {}) or {}).values()]
    except Exception as e:
        print(f"[FreeImages] search failed for '{query}': {e}")
        return []


async def _image_info(client: httpx.AsyncClient, titles: list[str],
                      require: str | None = None) -> list[dict]:
    """Pull URL + licence metadata for a batch of file titles.

    require: text that MUST appear in the title/description (used for player
    searches, where the SA-football keyword guard would reject valid portraits).
    """
    if not titles:
        return []
    try:
        r = await client.get(COMMONS_API, params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "titles": "|".join(titles[:40]),
            "iiprop": "url|extmetadata|size",
            "iiurlwidth": "1280",
        })
        pages = (r.json().get("query", {}).get("pages", {}) or {}).values()
    except Exception as e:
        print(f"[FreeImages] imageinfo failed: {e}")
        return []

    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {}) or {}
        lic = _clean_html(meta.get("LicenseShortName", {}).get("value", ""))
        author = _clean_html(meta.get("Artist", {}).get("value", "")) or "Wikimedia Commons"
        if not lic or BLOCKED_LICENSE.search(lic) or not ALLOWED_LICENSE.search(lic):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        # Skip tiny/graphic assets — logos and icons make poor b-roll and are
        # usually the club marks we deliberately avoid.
        if (info.get("width") or 0) < 640:
            continue
        title = p.get("title", "").replace("File:", "")
        if re.search(r"(logo|crest|badge|\.svg)", title, re.IGNORECASE):
            continue
        # Relevance: the file must read as SA football, and must not match the
        # known false-positive families.
        haystack = f"{title} {_clean_html(meta.get('ImageDescription', {}).get('value', ''))}"
        if IRRELEVANT.search(haystack) or not RELEVANT.search(haystack):
            # Even player-name searches must read as SA football: a namesake in
            # a Dutch youth match passed the name check and made a PSL card.
            continue
        if require is not None and require.lower() not in haystack.lower():
            continue
        # When the photo was taken — recency is relevance for a news page.
        when = _clean_html(meta.get("DateTimeOriginal", {}).get("value", "")) or \
               _clean_html(meta.get("DateTime", {}).get("value", ""))
        ym = re.search(r"(19|20)\d{2}", f"{when} {title}")
        out.append({
            "url": url,
            "title": title,
            "author": author[:80],
            "license": lic,
            "credit": f"{author[:60]} / Wikimedia Commons ({lic})",
            "width": info.get("width"),
            "height": info.get("height"),
            "year": int(ym.group(0)) if ym else 0,
        })
    # Newest first — a 2024 photo of a player beats his 2012 one every time.
    out.sort(key=lambda h: h["year"], reverse=True)
    return out


async def search_free_photos(query: str, limit: int = 3) -> list[dict]:
    """Real, freely-licensed photos for a query. Empty list if nothing usable."""
    async with httpx.AsyncClient(
        timeout=25,
        headers={"User-Agent": "GenesisNewsPSL/1.0 (contact: mdlulipenuel@gmail.com)"},
        follow_redirects=True,
    ) as client:
        titles = await _search_titles(client, query, limit)
        hits = await _image_info(client, titles)
    return hits[:limit]


async def photos_for_player(name: str, limit: int = 2) -> list[dict]:
    """
    Recent, freely-licensed photos of a NAMED player — the most relevant image
    a football story can carry. The name must appear in the file's own
    title/description (no keyword-guard false negatives), results come newest
    first, and the same licence rules apply as everywhere else.
    """
    name = (name or "").strip()
    if len(name.split()) < 2:          # a bare surname matches too much junk
        return []
    async with httpx.AsyncClient(
        timeout=25,
        headers={"User-Agent": "GenesisNewsPSL/1.0 (contact: mdlulipenuel@gmail.com)"},
        follow_redirects=True,
    ) as client:
        titles = await _search_titles(client, f'"{name}"', limit)
        hits = await _image_info(client, titles, require=name)
    return hits[:limit]


async def photos_for_club(club_key: str, limit: int = 3) -> list[dict]:
    """Try each query for a club until enough usable photos are found."""
    seen, out = set(), []
    for q in CLUB_QUERIES.get(club_key, CLUB_QUERIES["generic"]):
        for hit in await search_free_photos(q, limit):
            if hit["url"] in seen:
                continue
            seen.add(hit["url"])
            out.append(hit)
            if len(out) >= limit:
                return out
    return out


async def download(hit: dict, dest) -> Optional[str]:
    from pathlib import Path
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(
            timeout=40,
            headers={"User-Agent": "GenesisNewsPSL/1.0 (contact: mdlulipenuel@gmail.com)"},
            follow_redirects=True,
        ) as client:
            r = await client.get(hit["url"])
            r.raise_for_status()
            dest.write_bytes(r.content)
        return str(dest)
    except Exception as e:
        print(f"[FreeImages] download failed: {e}")
        return None


if __name__ == "__main__":
    async def _test():
        for club in ("chiefs", "pirates", "sundowns", "generic"):
            hits = await photos_for_club(club, 3)
            print(f"\n{club}: {len(hits)} usable")
            for h in hits:
                print(f"  - {h['title'][:60]} | {h['license']} | {h['author'][:40]}")
    asyncio.run(_test())
