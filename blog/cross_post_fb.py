#!/usr/bin/env python
"""Cross-promote blog posts to the matching Facebook page (link post) to drive site traffic.

Reads blog/state.json (newest post is posts[0]), maps each post's niche to an FB page, and posts a
link to /{page_id}/feed. The daily run promotes the NEWEST post that hasn't been cross-posted yet
AND maps to a live, unlocked page — so a day whose newest post is 'kids' (mapped to the now-locked
Viking page) still pushes the next valid post instead of silently doing nothing. A slug is recorded
in blog/fb_crossposted.json once handled so it never double-posts.

  python cross_post_fb.py            # daily: newest un-promoted post to a live page
  python cross_post_fb.py --dry-run  # show what WOULD post, post nothing
  python cross_post_fb.py --launch   # one representative article per page (backfill)
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
DONE_FILE = ROOT / "fb_crossposted.json"
# blog niche -> Facebook page niche key (FB_PAGE_ID_<key> / FB_PAGE_TOKEN_<key>)
FB_NICHE = {"kids": "blissful_moments", "news": "tech_news",
            "study": "limitless_you", "sleep": "limitless_you", "coding": "limitless_you",
            "wellness": "health_wellness", "sa": "sa_pulse"}
BLURB = {"kids": "New on our blog for parents 👶", "news": "Fresh explainer on our blog 🌍",
         "study": "New focus & study tips on our blog 🎧", "sleep": "Sleep better — new guide 🌙",
         "coding": "For the coders — new post 💻",
         "wellness": "New organic-living tips on our blog 🌿",
         "sa": "New on Genesis News — South Africa, explained 🇿🇦"}


def _done():
    try:
        return set(json.loads(DONE_FILE.read_text()))
    except Exception:
        return set()


def _mark_done(slug):
    s = _done(); s.add(slug)
    DONE_FILE.write_text(json.dumps(sorted(s), indent=2))


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


def _page_for(niche):
    """Return (key, page_id, token) for a postable page, or None with a printed reason."""
    key = FB_NICHE.get(niche)
    if not key:
        print(f"[fb] '{niche}': no FB mapping — skip"); return None
    try:
        from config import page_locked
        if page_locked(key):
            print(f"[fb] '{niche}' -> {key}: page locked to its own poster — skip"); return None
    except Exception:
        pass
    page_id = os.getenv(f"FB_PAGE_ID_{key}", ""); token = os.getenv(f"FB_PAGE_TOKEN_{key}", "")
    if not page_id or not token:
        print(f"[fb] '{niche}' -> {key}: page not configured — skip"); return None
    return key, page_id, token


def promote(p, dry_run=False):
    """Post one blog article to its matching Facebook page. Returns True only if it actually posted."""
    niche = p.get("niche", "")
    pg = _page_for(niche)
    if not pg:
        return False
    key, page_id, token = pg
    url = f"{SITE_URL}/posts/{p['slug']}"
    if not _is_live(url):
        print(f"[fb] {url} not live yet — skip"); return False
    msg = f"{BLURB.get(niche, 'New on our blog')}\n\n{p['title']}\n\n{url}"
    if dry_run:
        print(f"[fb] DRY-RUN would post '{niche}' -> {key}: {url}"); return True
    try:
        res = post_link(page_id, token, msg, url)
        print(f"[fb] posted '{niche}' -> {key}: {res.get('id', res)}")
        return True
    except Exception as e:
        print(f"[fb] post failed ({key}): {str(e)[:160]}")
        return False


def main():
    launch = "--launch" in sys.argv
    dry = "--dry-run" in sys.argv
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
                seen.add(key)
                if promote(p, dry_run=dry) and not dry:
                    _mark_done(p["slug"])
        return

    # Daily: newest post not yet cross-posted that maps to a live, unlocked page. Fall through the
    # (few) most recent so a 'kids'-newest day still pushes the next valid post instead of no-op'ing.
    done = _done()
    for p in posts[:8]:
        slug = p.get("slug", "")
        if slug in done:
            continue
        pg = _page_for(p.get("niche", ""))
        if not pg:
            if not dry:
                _mark_done(slug)  # unpostable (locked/unmapped) — retire it so we don't re-check forever
            continue
        if promote(p, dry_run=dry):
            if not dry:
                _mark_done(slug)
            return
    print("[fb] nothing new to cross-post (all recent posts already promoted or unpostable)")


if __name__ == "__main__":
    main()
