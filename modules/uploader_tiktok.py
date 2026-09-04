"""
TikTok Uploader — Posts videos to TikTok via browser automation (Playwright).

Supports staggered scheduling: post the first video immediately,
schedule subsequent ones 2 hours apart so TikTok's algorithm treats
each one as a fresh upload (better reach than dumping all at once).

Authentication priority:
  1. TIKTOK_SESSION_ID env var  (most reliable — single cookie value)
  2. tokens/tiktok_cookies.json (JSON list from browser extension export)
  3. tokens/tiktok_cookies.txt  (Netscape format)

To get your session ID:
  1. Open https://www.tiktok.com in Chrome and log in
  2. Press F12 -> Application -> Cookies -> https://www.tiktok.com
  3. Find the cookie named "sessionid" and copy its Value
  4. Add to .env:  TIKTOK_SESSION_ID=<paste_value_here>
"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from config import TOKENS_DIR

COOKIES_JSON = TOKENS_DIR / "tiktok_cookies.json"
COOKIES_TXT  = TOKENS_DIR / "tiktok_cookies.txt"

# ---------------------------------------------------------------------------
# Subprocess script — runs tiktok_uploader in a CLEAN Python process.
# Avoids Playwright Sync API / asyncio event-loop conflict.
# Dismisses TikTok's joyride/tutorial overlay that blocks headless uploads.
# NOTE: uses single-quote r-string r'''...''' so inner triple-double-quotes
#       don't terminate the string early.
# ---------------------------------------------------------------------------
_UPLOAD_SCRIPT = r'''
import json, sys, os, time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv(override=True)

args        = json.loads(sys.argv[1])
video_path  = args["video_path"]
description = args["description"]
auth        = args["auth"]
schedule_iso = args.get("schedule_time")  # ISO format or None


def dismiss_joyride(page):
    # Force-remove TikTok joyride/tutorial overlay via JS (always safe to run)
    time.sleep(1.5)
    try:
        page.evaluate("document.querySelectorAll('[data-test-id=overlay],.react-joyride__overlay').forEach(function(e){e.remove()})")
    except Exception:
        pass
    # Also try clicking Skip/Close buttons if overlay still visible
    try:
        for sel in ["button:has-text('Skip')", "button:has-text('Got it')", "[data-e2e='joyride-close']"]:
            try:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    time.sleep(0.3)
                    break
            except Exception:
                pass
    except Exception:
        pass


# Patch _go_to_upload so joyride is dismissed immediately after navigation.
import tiktok_uploader.upload as _tu
from tiktok_uploader.upload import config as _tt_cfg

_orig_go_to_upload = _tu._go_to_upload
def _patched_go_to_upload(page):
    _orig_go_to_upload(page)
    dismiss_joyride(page)
_tu._go_to_upload = _patched_go_to_upload


# Replace _post_video entirely.
# The joyride overlay reappears DURING the upload-wait loop and blocks the post button.
# This version: keeps overlay removed every 2 seconds AND force-clicks the button.
def _patched_post_video(page):
    JS_REMOVE = "document.querySelectorAll('[data-test-id=overlay],.react-joyride__overlay').forEach(function(e){e.remove()})"
    btn_xpath = "//button[@data-e2e='post_video_button']"
    btn = page.locator("xpath=" + btn_xpath)

    # Wait for button to be enabled, removing overlay on every tick
    for _ in range(int(_tt_cfg.uploading_wait / 2)):
        try:
            page.evaluate(JS_REMOVE)
        except Exception:
            pass
        try:
            if btn.get_attribute("data-disabled", timeout=1500) == "false":
                break
        except Exception:
            pass
        time.sleep(2)

    # One final overlay removal before clicking
    try:
        page.evaluate(JS_REMOVE)
    except Exception:
        pass
    time.sleep(0.5)

    # Force-click (bypasses pointer-events from any remaining overlay)
    clicked = False
    try:
        btn.scroll_into_view_if_needed()
        btn.click(force=True, timeout=10000)
        clicked = True
    except Exception:
        pass

    if not clicked:
        # JS dispatch as last resort
        try:
            page.evaluate(
                "var b=document.querySelector('[data-e2e=\"post_video_button\"]');"
                "if(b){b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))}"
            )
            clicked = True
        except Exception:
            pass

    if not clicked:
        raise Exception("Could not click post button after overlay removal")

    # Check for post_now button (schedule flow)
    try:
        pn = page.locator("xpath=//button[.//div[text()='Post now']]")
        if pn.is_visible(timeout=4000):
            pn.click()
    except Exception:
        pass

    # Wait for post confirmation
    time.sleep(5)

_tu._post_video = _patched_post_video


# Replace _set_interactivity entirely.
#
# The library hunts for three controls - Comment, Duet and Stitch - with
#     //label[.='Comment']/following-sibling::div/input
# and on the current TikTok Web Studio page not one of those resolves. A DOM
# probe of the live upload form on 2026-08-30 found this instead:
#
#     Comment              input.Checkbox__input   (nested inside the label)
#     Reuse of content     input.Checkbox__input
#     Disclose post content / AI-generated content / Audience control  (switches)
#
# Duet and Stitch are GONE as separate toggles - TikTok folded them into
# "Reuse of content" - and Comment moved inside its label rather than sitting
# in a following sibling. So every lookup ran to the full 30s Playwright
# timeout, the whole thing died on the first one, and the library logged a
# flat "Failed to set interactivity settings" with the real cause swallowed by
# a bare except. Thirty seconds of every upload, and any interactivity choice
# we made was silently discarded.
#
# What this does NOT do is change what has been going out: the page defaults
# are Comment on and Reuse of content on, which is what we were asking for
# anyway. The win is that the setting is honoured instead of ignored, the
# stall is gone, and a control that disappears next time TikTok reshuffles the
# page says WHICH one rather than failing blind.
def _patched_set_interactivity(page, comment=True, stitch=True, duet=True,
                               *args, **kwargs):
    def _toggle(label_text, want):
        # The input is appearance:none and effectively unclickable; the label
        # is the control a person actually hits, so click that.
        lab = page.locator(
            "label.Checkbox__root:has(span:text-is(\"%s\"))" % label_text)
        try:
            if not lab.count():
                print("[TikTok] interactivity: no '%s' control on this page "
                      "- skipped" % label_text, flush=True)
                return
            box = lab.locator("input.Checkbox__input").first
            now = box.is_checked(timeout=4000)
            if now != want:
                lab.first.click(timeout=4000)
                print("[TikTok] interactivity: %s %s -> %s"
                      % (label_text, now, want), flush=True)
            else:
                print("[TikTok] interactivity: %s already %s"
                      % (label_text, want), flush=True)
        except Exception as e:
            # One control we cannot set must not cost the upload. The video
            # going out matters more than who is allowed to duet it.
            print("[TikTok] interactivity: '%s' failed (%s)"
                  % (label_text, str(e)[:120]), flush=True)

    _toggle("Comment", bool(comment))
    # duet and stitch no longer have their own toggles. "Reuse of content" is
    # the permission that replaced both, so it stays on unless the caller has
    # asked for BOTH to be off - turning it off on a request for one of them
    # would withdraw the other silently.
    _toggle("Reuse of content", bool(duet or stitch))

_tu._set_interactivity = _patched_set_interactivity


# CAPTURE THE REAL REASON. complete_upload_form runs _go_to_upload,
# _set_video, _remove_split_window, _set_interactivity and _post_video in a
# chain, and the library catches ANY exception from it, appends the video to
# `failed`, and moves on. Our layer then reported a flat "post button click
# failed" - which named the last step in the chain rather than the one that
# actually broke, and was wrong every time the failure was earlier.
#
# This wrapper lets the step run, records what really went wrong, and re-raises
# so the library still behaves normally.
_REAL_ERROR = {"why": ""}
_orig_complete = _tu.complete_upload_form


def _complete_with_reason(*args, **kwargs):
    try:
        return _orig_complete(*args, **kwargs)
    except Exception as e:
        _REAL_ERROR["why"] = f"{type(e).__name__}: {str(e)[:200]}"
        raise


_tu.complete_upload_form = _complete_with_reason

from tiktok_uploader.upload import upload_video

# Parse schedule time if provided
schedule_dt = None
if schedule_iso:
    try:
        schedule_dt = datetime.fromisoformat(schedule_iso)
    except Exception:
        pass

try:
    upload_kwargs = {
        "filename": video_path,
        "description": description,
        **{k: v for k, v in auth.items()},
        "headless": True,
        "num_retries": 2,
    }
    if schedule_dt:
        upload_kwargs["schedule"] = schedule_dt

    # ONE FRESH ATTEMPT ON FAILURE. num_retries inside the library retries
    # within the SAME page state, so a stuck overlay or a half-loaded form is
    # retried in the condition that caused it. This throws the browser away and
    # starts again, which is the difference that matters: the roll call failed
    # at 16:20 and the role analysis went through minutes later on identical
    # code, so the fault is transient page state, not our video.
    failed = upload_video(**upload_kwargs)
    if failed:
        why1 = _REAL_ERROR.get("why") or "unknown"
        print("[TikTok] attempt 1 failed (%s) - retrying with a fresh session"
              % why1, flush=True)
        _REAL_ERROR["why"] = ""
        time.sleep(4)
        failed = upload_video(**upload_kwargs)

    if not failed:
        status_msg = "scheduled" if schedule_dt else "uploaded"
        result = {"status": status_msg}
        if schedule_dt:
            result["scheduled_for"] = schedule_iso
        print(json.dumps(result))
    else:
        # Name the step that broke, not the last step in the chain.
        print(json.dumps({"status": "failed",
                          "error": _REAL_ERROR.get("why")
                                   or "upload failed with no captured reason"}))
except Exception as e:
    print(json.dumps({"status": "failed", "error": str(e)}))
'''


def _get_auth() -> dict:
    """
    Return the best available TikTok auth kwargs for tiktok_uploader.
    Reloads .env on every call so a running pipeline picks up new session IDs.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    # 1. Session ID from env — pass as cookies_list with full domain/path.
    # The library's sessionid= param omits domain/path, which Playwright rejects.
    session_id = os.getenv("TIKTOK_SESSION_ID", "").strip()
    if session_id:
        return {
            "cookies_list": [
                {
                    "name": "sessionid",
                    "value": session_id,
                    "domain": ".tiktok.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "expiry": 9999999999,
                }
            ]
        }

    # 2. JSON cookie list (from browser extension export)
    if COOKIES_JSON.exists():
        try:
            cookies = json.loads(COOKIES_JSON.read_text())
            if cookies:
                normalized = [
                    {
                        "name":     c.get("name", ""),
                        "value":    c.get("value", ""),
                        "domain":   c.get("domain", ".tiktok.com"),
                        "path":     c.get("path", "/"),
                        "secure":   c.get("secure", True),
                        "httpOnly": c.get("httpOnly", False),
                        "expiry":   c.get("expiry", c.get("expirationDate", 0)),
                    }
                    for c in cookies
                ]
                return {"cookies_list": normalized}
        except Exception:
            pass

    # 3. Netscape .txt fallback
    if COOKIES_TXT.exists():
        return {"cookies": str(COOKIES_TXT)}

    return {}


async def upload_to_tiktok(
    video_path: str,
    description: str,
    hashtags: list[str] | None = None,
    schedule_time: datetime | None = None,
    niche: str = "",
) -> dict:
    """
    Upload a video to TikTok via a subprocess (avoids asyncio/Playwright conflict).

    Args:
        video_path: Path to the video file.
        description: Post description text.
        hashtags: List of hashtags to append.
        schedule_time: If set, schedule the post for this datetime instead
                       of posting immediately. Must be at least 15 min in the future.
    """
    # ── WHOSE TIKTOK IS THIS? ────────────────────────────────────────────
    # There is one TIKTOK_SESSION_ID and it belongs to the Genesis News
    # (soccer) account. upload_to_tiktok already took a niche and then ignored
    # it for auth, so every page fanned out onto the same account — a Tech
    # Pulse geopolitics reel landed there on 21 Aug, which is why the owner
    # stopped the whole scheduler that morning. Stopping the scheduler stopped
    # the leak AND four pages with it.
    #
    # A niche may post to TikTok only if it has its own session, or if it is
    # the account's owner. Anything else skips with a reason instead of
    # quietly borrowing someone else's audience.
    owner = os.getenv("TIKTOK_OWNER_NICHE", "sa_pulse").strip()
    own_session = os.getenv(f"TIKTOK_SESSION_ID_{niche}", "").strip() if niche else ""
    if niche and niche != owner and not own_session:
        msg = (f"'{niche}' has no TikTok account of its own — refusing to post "
               f"it to the '{owner}' account. Add TIKTOK_SESSION_ID_{niche} to "
               f".env to give this page its own.")
        print(f"[TikTok] skipped: {msg}")
        return {"platform": "tiktok", "status": "skipped", "error": msg}
    if own_session:
        os.environ["TIKTOK_SESSION_ID"] = own_session

    auth = _get_auth()
    if not auth:
        return {
            "platform": "tiktok",
            "status": "skipped",
            "error": (
                "No TikTok auth. Add TIKTOK_SESSION_ID to .env — "
                "get it from: F12 -> Application -> Cookies -> tiktok.com -> sessionid"
            ),
        }

    # Build full description — pure content, no links
    full_description = description or ""
    if hashtags:
        tags_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
        full_description = f"{full_description}\n\n{tags_str}"
    full_description = full_description[:2200]

    auth_method = list(auth.keys())[0]
    schedule_str = ""
    if schedule_time:
        schedule_str = f" | scheduled for {schedule_time.strftime('%H:%M')}"
    print(f"[TikTok] Auth: {auth_method} | {Path(video_path).name}{schedule_str}")

    # Write upload script to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(_UPLOAD_SCRIPT)
        script_path = f.name

    payload = json.dumps({
        "video_path":  str(Path(video_path).resolve()),
        "description": full_description,
        "auth":        auth,
        "schedule_time": schedule_time.isoformat() if schedule_time else None,
    })

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path, payload,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        output    = stdout.decode("utf-8", errors="replace").strip()
        err_lines = stderr.decode("utf-8", errors="replace").strip()

        for line in err_lines.splitlines():
            try:
                print(f"  {line}")
            except UnicodeEncodeError:
                print(f"  {line.encode('ascii', errors='replace').decode('ascii')}")

        result = {"status": "failed", "error": "No output from subprocess"}
        for line in reversed(output.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    break
                except Exception:
                    pass

        if result.get("status") in ("uploaded", "scheduled"):
            if result.get("status") == "scheduled":
                sched_for = result.get("scheduled_for", "")
                print(f"[TikTok] Scheduled: {Path(video_path).name} → {sched_for}")
            else:
                print(f"[TikTok] Posted: {Path(video_path).name}")
        else:
            err = result.get("error", "unknown")
            print(f"[TikTok] Failed: {err[:120]}")
            if "login" in err.lower() or "session" in err.lower():
                print("[TikTok] Hint: Session expired — refresh TIKTOK_SESSION_ID in .env")
            # the owner must hear about a dead session, once — not per reel
            try:
                from modules.notify_whatsapp import notify_failure
                notify_failure("tiktok-upload",
                               "TikTok upload failing — session likely expired. "
                               "Fix: tiktok.com logged in > F12 > Application > "
                               "Cookies > copy 'sessionid', send it to Claude.",
                               cooldown_h=12)
            except Exception:
                pass

        result["platform"]    = "tiktok"
        result["auth_method"] = auth_method
        return result

    except asyncio.TimeoutError:
        print("[TikTok] Timed out after 5 minutes")
        return {"platform": "tiktok", "status": "failed", "error": "timeout"}
    except Exception as e:
        print(f"[TikTok] Subprocess error: {e}")
        return {"platform": "tiktok", "status": "failed", "error": str(e)}
    finally:
        try:
            Path(script_path).unlink()
        except Exception:
            pass


async def upload_batch_to_tiktok(
    videos: list[dict],
    stagger_hours: float = 2.0,
) -> list[dict]:
    """
    Upload multiple videos to TikTok with staggered scheduling.

    First video posts immediately. Subsequent videos are scheduled
    at `stagger_hours` intervals to maximize TikTok algorithm reach.

    Args:
        videos: List of dicts with 'path', 'description', optional 'hashtags'.
        stagger_hours: Hours between each scheduled post (default: 2).

    Returns:
        List of upload result dicts.
    """
    results = []
    now = datetime.now()

    for idx, v in enumerate(videos):
        # First video: post immediately. Rest: schedule stagger_hours apart
        if idx == 0:
            schedule_time = None
            print(f"[TikTok] Video {idx + 1}/{len(videos)}: posting NOW")
        else:
            schedule_time = now + timedelta(hours=stagger_hours * idx)
            # TikTok requires schedule at least 15 min in the future
            min_future = now + timedelta(minutes=20)
            if schedule_time < min_future:
                schedule_time = min_future
            print(f"[TikTok] Video {idx + 1}/{len(videos)}: scheduling for {schedule_time.strftime('%Y-%m-%d %H:%M')}")

        r = await upload_to_tiktok(
            video_path=v["path"],
            description=v.get("description", ""),
            hashtags=v.get("hashtags"),
            schedule_time=schedule_time,
        )
        results.append(r)
    return results
