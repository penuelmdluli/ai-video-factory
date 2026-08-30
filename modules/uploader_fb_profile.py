"""
Facebook PERSONAL PROFILE poster — browser automation (Playwright).

WHY THIS EXISTS, AND WHAT IT COSTS
----------------------------------
There is no API for this. Facebook removed `publish_actions` in April 2018
and never replaced it: Pages publish through the Graph API, personal
timelines cannot, at any app-review tier. So the only route to a profile is
to drive a logged-in browser the way a person would.

That route is not free. Facebook actively detects automation, and the account
it penalises is the personal one — the thing you cannot rebuild. Owner call
2026-08-30: proceed anyway. The mitigations below are therefore not
decoration, they are the whole safety margin:

  * No password is handled here, ever. Auth is a session cookie the owner
    exports themselves; this module only reads it from .env.
  * One post per call, no batching, no retry storm. A failed post is
    reported and abandoned — hammering the composer is what gets an account
    flagged.
  * post=False is the default. Nothing reaches the timeline unless the
    caller explicitly asks, so an accidental import cannot publish.
  * check_only verifies the session and prints whose account it is WITHOUT
    composing anything.

AUTHENTICATION
--------------
Two cookies identify a Facebook session: `c_user` (your numeric id) and `xs`
(the session secret). Get them yourself — these should never be sent to
another person:

  1. Open https://www.facebook.com in Chrome, logged in as yourself
  2. F12 -> Application -> Cookies -> https://www.facebook.com
  3. Copy the Value of `c_user` and of `xs`
  4. Add to .env:
         FB_PROFILE_C_USER=<c_user value>
         FB_PROFILE_XS=<xs value>

`xs` is a live key to the account. Treat it like the password it stands in
for: .env only, never a commit, and rotate it by logging that browser session
out if it ever leaks.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Subprocess script — runs Playwright in a CLEAN Python process.
# Same reason as the TikTok uploader: the Playwright sync API cannot run
# inside a live asyncio event loop, and this pipeline is async end to end.
# NOTE: single-quote r-string so inner triple-double-quotes do not close it.
# ---------------------------------------------------------------------------
_POST_SCRIPT = r'''
import json, sys, time
from playwright.sync_api import sync_playwright

args     = json.loads(sys.argv[1])
message  = args["message"]
media    = args.get("media_path") or ""
cookies  = args["cookies"]
do_post  = args.get("do_post", False)
check    = args.get("check_only", False)
headless = args.get("headless", True)

def out(status, **kw):
    print(json.dumps(dict(status=status, **kw)), flush=True)

def log(m):
    print("[FBProfile] " + m, file=sys.stderr, flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=headless, args=[
        "--disable-blink-features=AutomationControlled",
    ])
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="en-GB",
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"),
    )
    ctx.add_cookies(cookies)
    page = ctx.new_page()

    try:
        log("opening facebook")
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded",
                  timeout=60000)
        time.sleep(3)

        # A dead cookie does not error - it silently serves the logged-out
        # page, and every selector below would then fail for the wrong
        # reason. Establish identity FIRST so the error names the real cause.
        if "login" in page.url or page.locator("input[name='pass']").count():
            out("failed", error=("session cookie is not valid (Facebook served "
                                 "the login page). Refresh FB_PROFILE_C_USER "
                                 "and FB_PROFILE_XS from your browser."))
            browser.close(); sys.exit(0)

        who = ""
        for sel in ["[aria-label='Your profile']",
                    "div[role='banner'] [aria-label*='profile' i]",
                    "div[role='navigation'] image"]:
            try:
                el = page.locator(sel).first
                if el.count():
                    who = (el.get_attribute("aria-label")
                           or el.get_attribute("alt") or "")
                    if who:
                        break
            except Exception:
                pass
        log("session live" + (" as " + who if who else ""))

        if check:
            out("ok", checked=True, account=who or "(name not read)",
                url=page.url)
            browser.close(); sys.exit(0)

        # COMPOSER
        #
        # Every selector below was read off the live page on 2026-08-30, not
        # guessed. A DOM probe found FOUR div[role=dialog] on this account
        # with the composer open:
        #
        #     0  aria="Notifications"    (already open on load)
        #     1  aria="Messenger"        (already open on load)
        #     2  aria=null               <- THE COMPOSER: the textbox, the
        #                                   file input and Photo/video are
        #                                   all in here
        #     3  aria="Create post"      an empty shell with nothing in it
        #
        # So the two obvious handles are both wrong, in ways that fail
        # differently: div[role=dialog] grabs Notifications, and
        # [aria-label='Create post'] grabs the empty shell 3. Scoping by
        # CONTENT - the one dialog that owns a textbox - resolves to exactly
        # one element, and it is the right one.
        SCOPE = "div[role='dialog']:has(div[role='textbox'])"

        def first_hit(selectors, what, timeout=8000):
            for s in selectors:
                try:
                    loc = page.locator(s).first
                    if loc.count():
                        loc.wait_for(state="visible", timeout=timeout)
                        return loc
                except Exception:
                    continue
            raise Exception("could not find " + what)

        log("opening composer")
        first_hit([
            "div[role='button']:has-text(\"What's on your mind\")",
            "div[role='button']:has-text('mind')",
            "[aria-label*=\"What's on your mind\" i]",
        ], "the composer button").click()
        time.sleep(3)

        composer = first_hit([SCOPE], "the composer dialog")

        log("typing message")
        box = composer.locator("div[role='textbox']").first
        box.click()
        box.type(message, delay=18)     # a human cadence, not a paste
        time.sleep(1.5)

        if media:
            log("attaching media")
            # The file input is already in the composer (accept covers
            # image/* and video/*), so setting it directly beats driving the
            # Photo/video button into an OS file dialog we cannot answer.
            fi = composer.locator("input[type='file']").first
            if not fi.count():
                try:
                    composer.locator("div[aria-label='Photo/video']").first.click()
                    time.sleep(2)
                    fi = composer.locator("input[type='file']").first
                except Exception:
                    pass
            if not fi.count():
                raise Exception("no file input in the composer")
            fi.set_input_files(media)
            log("waiting for media to process")
            time.sleep(15)

        # THIS COMPOSER HAS NO POST BUTTON.
        #
        # The probe found its submit control is aria="Next" - Facebook's
        # two-step composer - and Post only exists on the step after it. A
        # single "click Post" would have failed here every time. Next itself
        # publishes nothing, so the dry run is allowed to reach it and stop.
        submit = None
        for aria in ("Next", "Post"):
            loc = composer.locator("div[role='button'][aria-label='%s']" % aria)
            if loc.count():
                submit = (aria, loc.first)
                break
        if submit is None:
            raise Exception("composer has neither a Next nor a Post button")
        log("submit control is '%s'" % submit[0])

        if not do_post:
            out("ok", dry=True, composed=True, submit=submit[0],
                note=("composer filled and the '%s' control located; "
                      "nothing clicked" % submit[0]))
            browser.close(); sys.exit(0)

        log("clicking " + submit[0])
        submit[1].click()
        time.sleep(3)

        if submit[0] == "Next":
            # Step two. Post may take a moment to render.
            log("looking for Post on step two")
            posted_btn = None
            for _ in range(10):
                loc = page.locator(
                    "%s div[role='button'][aria-label='Post'], "
                    "%s div[role='button']:has-text('Post')" % (SCOPE, SCOPE))
                if loc.count():
                    posted_btn = loc.first
                    break
                time.sleep(1.5)
            if posted_btn is None:
                out("failed", error=("clicked Next but no Post button "
                                     "appeared - nothing was published"))
                browser.close(); sys.exit(0)
            log("clicking Post")
            posted_btn.click()

        # The COMPOSER closing is the signal it went. Counting all dialogs
        # would never reach zero - Notifications and Messenger stay open for
        # the whole session - so this would report "unconfirmed" on every
        # successful post and invite a double-post on the retry.
        posted = False
        for _ in range(40):
            time.sleep(1.5)
            if not page.locator(SCOPE).count():
                posted = True
                break
        out("uploaded" if posted else "unconfirmed",
            note=("posted" if posted else
                  "composer never closed - check the profile by hand before "
                  "re-running, so this does not double-post"))
    except Exception as e:
        out("failed", error=(type(e).__name__ + ": " + str(e))[:400])
    finally:
        try:
            browser.close()
        except Exception:
            pass
'''


def _get_auth() -> list:
    """Session cookies from .env, or [] if the owner has not supplied them."""
    from dotenv import load_dotenv
    load_dotenv(override=True)

    c_user = os.getenv("FB_PROFILE_C_USER", "").strip()
    xs = os.getenv("FB_PROFILE_XS", "").strip()
    if not (c_user and xs):
        return []
    base = {"domain": ".facebook.com", "path": "/", "secure": True}
    return [
        {"name": "c_user", "value": c_user, "httpOnly": False, **base},
        {"name": "xs", "value": xs, "httpOnly": True, **base},
    ]


async def post_to_profile(
    message: str,
    media_path: str | None = None,
    post: bool = False,
    check_only: bool = False,
    headless: bool = True,
    timeout: int = 300,
) -> dict:
    """
    Put one post on the owner's personal Facebook timeline.

    post=False is deliberate. This drives a real logged-in session on an
    account that cannot be replaced, so publishing is opt-in per call and
    there is no batch entry point.

    Args:
        message:    the post text.
        media_path: optional image or video to attach.
        post:       True actually clicks Post. False fills the composer and
                    stops, which is how you check a post before it is public.
        check_only: verify the session only; compose nothing.
    """
    cookies = _get_auth()
    if not cookies:
        return {
            "platform": "fb_profile",
            "status": "skipped",
            "error": ("No profile session. Add FB_PROFILE_C_USER and "
                      "FB_PROFILE_XS to .env — F12 -> Application -> Cookies "
                      "-> facebook.com -> c_user and xs."),
        }

    if media_path and not Path(media_path).exists():
        return {"platform": "fb_profile", "status": "failed",
                "error": f"media not found: {media_path}"}

    mode = ("check" if check_only else "POST" if post else "dry")
    print(f"[FBProfile] {mode} | {len(message)} chars"
          + (f" | {Path(media_path).name}" if media_path else ""))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(_POST_SCRIPT)
        script_path = f.name

    payload = json.dumps({
        "message": message,
        "media_path": str(Path(media_path).resolve()) if media_path else "",
        "cookies": cookies,
        "do_post": bool(post),
        "check_only": bool(check_only),
        "headless": bool(headless),
    })

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path, payload,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(),
                                                timeout=timeout)
        for line in stderr.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                print("  " + line)

        result = {"status": "failed", "error": "no output from subprocess"}
        for line in reversed(stdout.decode("utf-8", errors="replace").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    break
                except Exception:
                    pass
        result["platform"] = "fb_profile"
        return result
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"platform": "fb_profile", "status": "failed",
                "error": f"timed out after {timeout}s"}
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Post to your personal Facebook profile")
    ap.add_argument("--message", default="")
    ap.add_argument("--media", default=None)
    ap.add_argument("--post", action="store_true",
                    help="actually publish (default fills the composer only)")
    ap.add_argument("--check", action="store_true",
                    help="verify the session and exit — composes nothing")
    ap.add_argument("--show", action="store_true",
                    help="run headed so you can watch it")
    a = ap.parse_args()
    if not a.check and not a.message:
        ap.error("--message is required unless you pass --check")
    r = asyncio.run(post_to_profile(a.message, a.media, post=a.post,
                                    check_only=a.check, headless=not a.show))
    print(json.dumps(r, indent=2))
