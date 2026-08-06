#!/usr/bin/env python
"""Cross-promote the newest blog post to the matching Facebook page (link post).
Reads blog/state.json (newest post is posts[0]), maps its niche to an FB page,
and posts a link to /{page_id}/feed. Skips gracefully if the page isn't set up.
"""
import os, sys, json
from pathlib import Path
import urllib.request, urllib.parse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
try:
    import config  # loads .env
except Exception:
    pass

SITE_URL = os.getenv("BLOG_URL", "https://blog.genesisstudio.app")
GRAPH = "https://graph.facebook.com/v19.0"
# blog niche -> Facebook page niche key (FB_PAGE_ID_<key> / FB_PAGE_TOKEN_<key>)
FB_NICHE = {"kids": "blissful_moments", "news": "tech_news",
            "study": "limitless_you", "sleep": "limitless_you", "coding": "limitless_you",
            "wellness": "health_wellness", "sa": "sa_pulse"}
BLURB = {"kids": "New on our blog for parents 👶", "news": "Fresh explainer on our blog 🌍",
         "study": "New focus & study tips on our blog 🎧", "sleep": "Sleep better — new guide 🌙",
         "coding": "For the coders — new post 💻",
         "wellness": "New organic-living tips on our blog 🌿",
         "sa": "New on Genesis News — South Africa, explained 🇿🇦"}

def post_link(page_id, token, message, link):
    data = urllib.parse.urlencode({"message": message, "link": link, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{page_id}/feed", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def _is_live(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "genesis-blog"})
        urllib.request.urlopen(req, timeout=15); return True
    except Exception:
        return False

def promote(p):
    """Post one blog article to its matching Facebook page."""
    niche = p.get("niche", "")
    key = FB_NICHE.get(niche)
    if not key:
        print(f"[fb] no FB mapping for '{niche}' — skip"); return
    page_id = os.getenv(f"FB_PAGE_ID_{key}", ""); token = os.getenv(f"FB_PAGE_TOKEN_{key}", "")
    if not page_id or not token:
        print(f"[fb] page '{key}' not configured — skip"); return
    url = f"{SITE_URL}/posts/{p['slug']}"
    if not _is_live(url):
        print(f"[fb] {url} not live yet — skip"); return
    msg = f"{BLURB.get(niche, 'New on our blog')}\n\n{p['title']}\n\n{url}"
    try:
        res = post_link(page_id, token, msg, url)
        print(f"[fb] posted '{niche}' -> {key}: {res.get('id', res)}")
    except Exception as e:
        print(f"[fb] post failed ({key}): {str(e)[:160]}")

def main():
    import sys
    launch = "--launch" in sys.argv
    st = ROOT / "state.json"
    if not st.exists():
        print("[fb] no state.json"); return
    posts = json.loads(st.read_text()).get("posts", [])
    if not posts:
        print("[fb] no posts"); return
    if launch:
        # one representative article per page (first post of each mapped niche)
        seen = set()
        for p in posts:
            key = FB_NICHE.get(p.get("niche", ""))
            if key and key not in seen:
                seen.add(key); promote(p)
    else:
        promote(posts[0])  # daily: newest post

if __name__ == "__main__":
    main()
