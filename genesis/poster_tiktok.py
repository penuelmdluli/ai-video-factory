"""
Genesis Content Engine — TikTok Poster

Posts branded videos to TikTok using the existing Playwright-based uploader.
Reuses session cookies from ai-video-factory/tokens/.
"""
import asyncio
import json
import sys
import os
import subprocess
import tempfile
import time
from pathlib import Path

from genesis.genesis_config import BRANDS, TOKENS_DIR
from genesis.db import save_post, update_post, log_pipeline

FACTORY_DIR = Path(__file__).parent.parent


# The upload script runs in a subprocess to avoid async/sync conflicts with Playwright
_TIKTOK_UPLOAD_SCRIPT = r'''
import json, sys, os, time
from dotenv import load_dotenv
load_dotenv(override=True)

args = json.loads(sys.argv[1])
video_path = args["video_path"]
description = args["description"]
cookies_file = args.get("cookies_file", "")
session_id = args.get("session_id", "")


def dismiss_joyride(page):
    time.sleep(1.5)
    try:
        page.evaluate("document.querySelectorAll('[data-test-id=overlay],.react-joyride__overlay').forEach(function(e){e.remove()})")
    except Exception:
        pass
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


try:
    from tiktok_uploader.upload import upload_video
    from tiktok_uploader.auth import AuthBackend

    # Determine auth method
    if session_id:
        auth = AuthBackend(cookies=f"sessionid={session_id}")
    elif cookies_file and os.path.exists(cookies_file):
        auth = AuthBackend(cookies=cookies_file)
    else:
        print(json.dumps({"error": "No TikTok auth available"}))
        sys.exit(1)

    # Upload
    result = upload_video(
        video_path,
        description=description[:150],  # TikTok caption limit
        cookies=auth.cookies if hasattr(auth, 'cookies') else session_id,
        headless=True,
        on_page_load=dismiss_joyride,
    )

    print(json.dumps({"success": True, "result": str(result)}))

except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
'''


async def post_to_tiktok(brand: str, video_data: dict) -> dict | None:
    """Post a branded video to TikTok."""
    start = time.time()

    config = BRANDS[brand]
    tt = config["tiktok"]

    video_path = Path(video_data.get("branded_path", ""))
    if not video_path.exists():
        log_pipeline("post_tiktok", brand, "failed", f"Video file not found: {video_path}")
        return None

    caption = video_data.get("script_data", {}).get("caption", "")
    # TikTok: shorter caption
    caption_short = caption.split("\n")[0][:150] if caption else ""

    post_id = save_post(video_data["video_id"], brand, "tiktok", caption_short)

    try:
        # Write upload script to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(FACTORY_DIR)) as f:
            f.write(_TIKTOK_UPLOAD_SCRIPT)
            script_path = f.name

        args = {
            "video_path": str(video_path),
            "description": caption_short,
            "cookies_file": str(tt.get("cookies_file", "")),
            "session_id": tt.get("session_id", ""),
        }

        result = subprocess.run(
            [sys.executable, script_path, json.dumps(args)],
            capture_output=True,
            text=True,
            timeout=180,  # 3 min max
            cwd=str(FACTORY_DIR),
        )

        # Clean up temp file
        try:
            os.unlink(script_path)
        except Exception:
            pass

        if result.returncode != 0:
            stderr = result.stderr[-300:] if result.stderr else ""
            stdout = result.stdout[-300:] if result.stdout else ""
            raise Exception(f"TikTok upload failed: {stderr or stdout}")

        # Parse output
        output_lines = result.stdout.strip().split("\n")
        last_line = output_lines[-1] if output_lines else "{}"

        try:
            output = json.loads(last_line)
        except json.JSONDecodeError:
            output = {"success": True, "result": result.stdout[-200:]}

        if output.get("error"):
            raise Exception(output["error"])

        update_post(post_id,
            status="posted",
            posted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        duration = time.time() - start
        log_pipeline("post_tiktok", brand, "success", "Posted to TikTok", duration)

        return {
            "post_id": post_id,
            "platform": "tiktok",
        }

    except subprocess.TimeoutExpired:
        update_post(post_id, status="failed", error_message="TikTok upload timed out (3 min)")
        log_pipeline("post_tiktok", brand, "failed", "Timed out", time.time() - start)
        return None
    except Exception as e:
        update_post(post_id, status="failed", error_message=str(e))
        log_pipeline("post_tiktok", brand, "failed", str(e), time.time() - start)
        print(f"  ❌ TikTok post failed for {brand}: {e}")
        return None
