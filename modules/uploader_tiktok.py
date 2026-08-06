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

    failed = upload_video(**upload_kwargs)
    if not failed:
        status_msg = "scheduled" if schedule_dt else "uploaded"
        result = {"status": status_msg}
        if schedule_dt:
            result["scheduled_for"] = schedule_iso
        print(json.dumps(result))
    else:
        print(json.dumps({"status": "failed", "error": "post button click failed"}))
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
