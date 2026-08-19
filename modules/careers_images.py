"""
Backdrop photos for Mzansi Careers posts.

Government circular posts have no employer photo, so covers were rendering on
a flat brand backdrop — a green rectangle in the feed. These are real,
freely-licensed South African images, downloaded once and credited on the
card, chosen by what the department actually does.

Licences are recorded per image and printed with every post. Nothing here is
scraped from the open web.
"""
import json
import re
from pathlib import Path

import requests

DIR = Path(__file__).parent.parent / "assets" / "careers_bg"
INDEX = DIR / "index.json"
UA = "GenesisNews/1.0 (mdlulipenuel@gmail.com)"
API = "https://commons.wikimedia.org/w/api.php"

# theme -> (Commons file title, keywords that pick it)
LIBRARY = [
    ("government", "File:Union Buildings Pretoria 03.jpg",
     ["public service", "government", "presidency", "treasury", "home "
      "affairs", "cooperative governance", "parliament"]),
    ("city", "File:Cape Town City Hall, South Africa.jpg",
     ["municipal", "city", "local government", "tourism", "arts", "culture"]),
    ("work", "File:Office Cleaner.jpg",
     ["labour", "employment", "public works", "infrastructure", "services"]),
]
DEFAULT = "government"


def _meta_and_url(title: str):
    r = requests.get(API, headers={"User-Agent": UA}, timeout=60, params={
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600})
    pages = (r.json().get("query") or {}).get("pages") or {}
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))
        return (ii.get("thumburl") or ii.get("url"),
                " ".join(artist.split())[:60],
                em.get("LicenseShortName", {}).get("value", ""))
    return None, "", ""


def ensure_library() -> dict:
    """Download any missing backdrops. Returns {theme: {path, credit}}."""
    DIR.mkdir(parents=True, exist_ok=True)
    idx = {}
    if INDEX.exists():
        try:
            idx = json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            idx = {}
    for theme, title, _kw in LIBRARY:
        dest = DIR / f"{theme}.jpg"
        if dest.exists() and theme in idx:
            continue
        url, artist, lic = _meta_and_url(title)
        if not url:
            print(f"[CareersImages] {theme}: not found on Commons")
            continue
        try:
            img = requests.get(url, headers={"User-Agent": UA}, timeout=120)
            img.raise_for_status()
            dest.write_bytes(img.content)
            idx[theme] = {"path": str(dest),
                          "credit": f"photo: {artist} ({lic}, Wikimedia)"}
            print(f"[CareersImages] {theme}: {artist} — {lic}")
        except Exception as e:
            print(f"[CareersImages] {theme} download failed: {e}")
    INDEX.write_text(json.dumps(idx, indent=2), encoding="utf-8")
    return idx


def backdrop_for(employer: str, programme: str = "") -> tuple:
    """(path, credit) for this post, or (None, '') if nothing is available."""
    idx = ensure_library()
    text = f"{employer} {programme}".lower()
    for theme, _title, keywords in LIBRARY:
        if any(k in text for k in keywords) and theme in idx:
            return idx[theme]["path"], idx[theme]["credit"]
    d = idx.get(DEFAULT)
    return (d["path"], d["credit"]) if d else (None, "")
