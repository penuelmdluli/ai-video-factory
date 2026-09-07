"""
Comment on a post on the owner's personal Facebook timeline.

WHY THIS IS NOT modules/community_manager.py
--------------------------------------------
community_manager posts comments through the Graph API: POST to
/{comment_id}/comments with a PAGE access token. That works, and all seven
page tokens are live — but only for Pages. A personal timeline post has no
page token and no Graph post id, because Facebook removed publish_actions in
2018 and never replaced it. The same wall that forces uploader_fb_profile to
drive a browser forces this to.

So: Pages get the API, the profile gets Playwright. Two mechanisms for one
idea, because Facebook offers exactly one of them for each surface.

SAME SAFETY CONTRACT AS THE UPLOADER
------------------------------------
  * No password is handled. Auth is the same FB_PROFILE_C_USER / FB_PROFILE_XS
    session cookie pair the uploader reads from .env.
  * post=False is the default. The box is filled and left alone unless the
    caller explicitly asks to submit.
  * One comment per call, no batching, no retry. A failed comment is reported
    and abandoned — hammering is what gets an account flagged.
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_COMMENT_SCRIPT = r'''
import json, sys, time
from playwright.sync_api import sync_playwright

args     = json.loads(sys.argv[1])
url      = args["url"]
text     = args["text"]
cookies  = args["cookies"]
do_post  = args.get("do_post", False)
headless = args.get("headless", True)

def out(status, **kw):
    print(json.dumps(dict(status=status, **kw)), flush=True)

def log(m):
    print("  [FBComment] %s" % m, flush=True, file=sys.stderr)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"))
    ctx.add_cookies(cookies)
    page = ctx.new_page()

    log("opening post")
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    time.sleep(6)

    if "login" in page.url or "checkpoint" in page.url:
        out("failed", error="session is not logged in")
        browser.close(); sys.exit(0)

    # The comment box is a contenteditable textbox. Facebook labels it
    # "Write a comment..." / "Comment as ...". Match on role plus an aria-label
    # that starts with either, never on a loose substring: the page also holds
    # the post's own message box and every reply box under existing comments.
    box = None
    for _ in range(12):
        loc = page.locator("div[role='textbox'][aria-label*='omment']")
        if loc.count():
            for i in range(loc.count()):
                b = loc.nth(i)
                try:
                    if b.is_visible():
                        box = b
                        break
                except Exception:
                    pass
        if box:
            break
        # Reels open in a viewer that hides comments until asked.
        for label in ("Comment", "View comments"):
            btn = page.locator("div[role='button'][aria-label='%s']" % label)
            if btn.count() and btn.first.is_visible():
                log("opening comments panel")
                btn.first.click()
                break
        time.sleep(2.5)

    if box is None:
        out("failed", error="no comment box found on this post")
        browser.close(); sys.exit(0)

    log("typing comment")
    box.click()
    time.sleep(1)

    # insert_text, NOT type().
    #
    # type() simulates keystrokes, and a keystroke cannot carry an astral-plane
    # character — so every emoji was silently dropped and the comment posted as
    # plain text (verified on a live comment, 2026-08-31: the em-dash survived,
    # the fire emoji did not). insert_text dispatches one insertText input
    # event with the whole string, which is the same path a paste takes, and
    # emoji arrive intact.
    page.keyboard.insert_text(text)
    time.sleep(1.5)

    # Confirm the box really holds what we meant to say. A React editor can
    # ignore an inserted event, and posting a half-written comment is worse
    # than posting none.
    try:
        got = box.inner_text().strip()
    except Exception:
        got = ""
    if not got:
        out("failed", error="comment box stayed empty after insert_text")
        browser.close(); sys.exit(0)

    if not do_post:
        out("ok", dry=True, composed=True,
            note="comment box filled; nothing submitted")
        browser.close(); sys.exit(0)

    log("submitting")
    box.press("Enter")
    time.sleep(6)

    # The box emptying is the signal it went. Reading the feed back is
    # unreliable — Facebook renders the new comment asynchronously and
    # sometimes not at all until reload.
    try:
        left = box.inner_text().strip()
    except Exception:
        left = ""
    if left and left[:20] == text[:20]:
        out("failed", error="comment text still in the box after Enter")
    else:
        out("ok", posted=True)
    browser.close()
'''


def _get_auth() -> list:
    from dotenv import load_dotenv
    load_dotenv()
    c_user = os.getenv("FB_PROFILE_C_USER", "").strip()
    xs = os.getenv("FB_PROFILE_XS", "").strip()
    if not (c_user and xs):
        return []
    return [
        {"name": "c_user", "value": c_user, "domain": ".facebook.com", "path": "/"},
        {"name": "xs", "value": xs, "domain": ".facebook.com", "path": "/"},
    ]


async def comment_on_post(url: str, text: str, post: bool = False,
                          headless: bool = True, timeout: int = 240) -> dict:
    """
    Leave one comment on a personal-timeline post.

    post=False fills the box and stops, which is how you check a comment
    before it is public.
    """
    cookies = _get_auth()
    if not cookies:
        return {"platform": "fb_profile_comment", "status": "skipped",
                "error": "No profile session — add FB_PROFILE_C_USER and FB_PROFILE_XS to .env."}

    print(f"[FBComment] {'POST' if post else 'dry'} | {len(text)} chars | {url}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(_COMMENT_SCRIPT)
        script_path = f.name

    payload = json.dumps({"url": url, "text": text, "cookies": cookies,
                          "do_post": bool(post), "headless": bool(headless)})
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path, payload,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        so, se = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if se:
            print(se.decode("utf-8", "replace").rstrip())
        line = (so.decode("utf-8", "replace").strip().splitlines() or ["{}"])[-1]
        result = json.loads(line)
    except asyncio.TimeoutError:
        return {"platform": "fb_profile_comment", "status": "failed",
                "error": f"timed out after {timeout}s"}
    except Exception as e:
        return {"platform": "fb_profile_comment", "status": "failed", "error": str(e)[:300]}
    finally:
        Path(script_path).unlink(missing_ok=True)

    result["platform"] = "fb_profile_comment"
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Comment on a personal-profile post")
    ap.add_argument("--url", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--post", action="store_true", help="actually submit")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    print(json.dumps(asyncio.run(
        comment_on_post(a.url, a.text, post=a.post, headless=not a.show)), indent=2))
