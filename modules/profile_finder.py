"""
Find a post we just published on the personal timeline.

Posting through the composer returns no id and no url — Playwright clicks Post
and the dialog closes, and that is all we learn. So the only way to act on a
new post (comment on it, check it, link to it) is to go back to the profile and
identify it.

"Newest reel on the grid" is a guess, not an answer: if anything else posts to
that timeline the newest reel may not be ours. So a caption fragment is matched
against the candidates before a url is returned, and no match is reported as a
failure rather than falling back to the newest.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from modules.profile_commenter import _get_auth

_JS_COLLECT = (
    "() => { const seen = []; "
    "document.querySelectorAll('a[href*=\"/reel/\"]').forEach(a => { "
    "const m = a.href.match(/\\/reel\\/(\\d+)/); "
    "if (m && !seen.includes(m[1])) seen.push(m[1]); }); return seen; }"
)

_FIND_SCRIPT = '''
import json, sys, time
from playwright.sync_api import sync_playwright

args     = json.loads(sys.argv[1])
cookies  = args["cookies"]
match    = args.get("match", "")
js       = args["js"]
headless = args.get("headless", True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=headless,
                                args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"))
    ctx.add_cookies(cookies)
    page = ctx.new_page()
    page.goto("https://www.facebook.com/me/reels",
              wait_until="domcontentloaded", timeout=90000)
    time.sleep(7)

    ids = page.evaluate(js)
    if not ids:
        print(json.dumps({"status": "failed", "error": "no reels on the profile"}), flush=True)
        browser.close(); sys.exit(0)

    chosen = None
    for rid in ids[:4]:
        url = "https://www.facebook.com/reel/" + rid
        if not match:
            chosen = url
            break
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        time.sleep(5)
        body = page.inner_text("body")[:5000]
        if match[:28] in body:
            chosen = url
            break

    if chosen:
        print(json.dumps({"status": "ok", "url": chosen}), flush=True)
    else:
        print(json.dumps({"status": "failed",
                          "error": "no recent reel matched the caption",
                          "checked": ids[:4]}), flush=True)
    browser.close()
'''


# Every caption opens with the same hook, so the hook is useless for telling
# posts apart. Matching on it returned the 2.7M original instead of the reel
# posted ten minutes earlier (2026-08-31) — and the reels grid is not ordered
# newest-first, so there was no fallback that would have been right either.
GENERIC_OPENERS = ("wait for it", "wait for it...", "🔥", "👀")


def distinctive(caption: str) -> str:
    """The part of a caption that identifies THIS post and no other."""
    text = caption
    for opener in ("Wait for it...", "Wait for it"):
        if text.startswith(opener):
            text = text[len(opener):]
            break
    # Drop leading emoji and punctuation left behind by the hook.
    text = text.lstrip(" .🔥👀😭🙌—-")
    return text.strip()


async def find_recent_post(match: str = "", headless: bool = True,
                           timeout: int = 300) -> dict:
    """
    URL of our most recent reel, verified against a caption fragment.

    `match` must identify this post specifically — pass distinctive(caption),
    not the caption itself.
    """
    if match and match.strip().lower() in GENERIC_OPENERS:
        return {"status": "failed",
                "error": f"match {match!r} is the shared hook and identifies every post; "
                         "pass distinctive(caption)"}
    cookies = _get_auth()
    if not cookies:
        return {"status": "skipped", "error": "no profile session"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(_FIND_SCRIPT)
        script_path = f.name

    payload = json.dumps({"cookies": cookies, "match": match,
                          "js": _JS_COLLECT, "headless": bool(headless)})
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path, payload,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        so, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        line = (so.decode("utf-8", "replace").strip().splitlines() or ["{}"])[-1]
        return json.loads(line)
    except Exception as e:
        return {"status": "failed", "error": str(e)[:300]}
    finally:
        Path(script_path).unlink(missing_ok=True)


# Seed comments for the dance reels.
#
# Engagement bait, deliberately with no link in it. A first comment exists to
# open a thread and give the algorithm an early interaction; a link in that
# position suppresses reach, which is the opposite of why it is there.
DANCE_SEED_COMMENTS = [
    "Who did it better, them or the original? \U0001F440",
    "Tag someone who dances like this \U0001F602",
    "Watch it twice — the ending gets better \U0001F525",
    "Drop a \U0001F525 if this made your day",
    "Which one should we do next? \U0001F447",
    "The crowd's reaction says it all \U0001F602\U0001F64C",
]


def seed_comment() -> str:
    import random
    return random.choice(DANCE_SEED_COMMENTS)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Find our most recent reel")
    ap.add_argument("--match", default="", help="caption fragment to verify against")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    print(json.dumps(asyncio.run(
        find_recent_post(a.match, headless=not a.show)), indent=2))
