"""An expired TikTok cookie must fail once, clearly — not twice, confusingly.

Between 27 Aug and 06 Oct 2026 every TikTok upload failed (171 of them) and the
logs blamed "Playwright Sync API inside the asyncio loop". That was attempt 2
talking. Attempt 1 had been bounced to tiktok.com/login because the sessionid
was dead, and the retry overwrote that diagnosis with its own unrelated error —
so the one actionable fact (refresh the cookie) never reached the log, and the
parent's "Session expired" hint never fired because the reported message
contained neither "login" nor "session".

This runs the REAL generated upload script against a stub tiktok_uploader, so
it checks the subprocess contract too: what lands on stdout, and the exit code.

Run:  python tests/test_tiktok_dead_session.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.uploader_tiktok import _UPLOAD_SCRIPT

FAILS = []

LOGIN_REDIRECT = (
    'Page.wait_for_selector: Timeout 60000ms exceeded.\n'
    'Call log:\n  - waiting for locator("#root") to be visible\n'
    '  - navigated to "https://www.tiktok.com/login?redirect_url='
    'https%3A%2F%2Fwww.tiktok.com%2Fcreator-center%2Fupload"\n'
)
STALE_FORM = 'TimeoutError: post button never became enabled'

STUB = '''
import json, sys
from pathlib import Path

COUNTER = Path(__file__).parent / "calls.txt"
FAILURE = Path(__file__).parent / "failure.txt"


class config:
    uploading_wait = 4


def _go_to_upload(page):
    pass


def _set_video(*a, **k):
    pass


def _remove_split_window(*a, **k):
    pass


def _set_interactivity(*a, **k):
    pass


def _post_video(page):
    pass


def complete_upload_form(*a, **k):
    raise RuntimeError(FAILURE.read_text(encoding="utf-8"))


def upload_video(filename=None, **kwargs):
    n = int(COUNTER.read_text() or 0) if COUNTER.exists() else 0
    COUNTER.write_text(str(n + 1))
    # the real library funnels every step through complete_upload_form and
    # swallows whatever it raises, returning the videos that did not post
    try:
        complete_upload_form(None, None)
    except Exception:
        return [{"video": filename}]
    return []
'''


def check(name, cond):
    print(("  ok   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def run_script(failure_text):
    """Run the generated upload script with a stubbed library.

    Returns (exit_code, parsed_json_result, upload_video_call_count).
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        pkg = d / "tiktok_uploader"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "upload.py").write_text(STUB, encoding="utf-8")
        (pkg / "failure.txt").write_text(failure_text, encoding="utf-8")

        script = d / "upload_script.py"
        script.write_text(_UPLOAD_SCRIPT, encoding="utf-8")

        payload = json.dumps({
            "video_path": str(d / "final.mp4"),
            "description": "roll call",
            "auth": {"cookies_list": [{"name": "sessionid", "value": "dead"}]},
            "schedule_time": None,
        })
        # PYTHONPATH is searched before site-packages, so the stub shadows the
        # real tiktok_uploader while everything else (dotenv, stdlib) stays put.
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), payload],
            capture_output=True, text=True, cwd=str(d), timeout=120,
            env={**os.environ, "PYTHONPATH": str(d),
                 "PYTHONIOENCODING": "utf-8"},
        )
        result = None
        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    break
                except Exception:
                    pass
        counter = pkg / "calls.txt"
        calls = int(counter.read_text()) if counter.exists() else 0
        if result is None:
            print("    stdout:", proc.stdout[-400:])
            print("    stderr:", proc.stderr[-400:])
        return proc.returncode, result, calls


def test_dead_session_fails_once():
    print("a login redirect is reported, and not retried")
    code, result, calls = run_script(LOGIN_REDIRECT)

    check("the script exits cleanly so the parent can read its verdict",
          code == 0)
    check("it reports a failure", result and result.get("status") == "failed")
    err = ((result or {}).get("error") or "").lower()
    check("the reason names the expired session", "session expired" in err)
    check("the reason tells the owner which cookie to refresh",
          "tiktok_session_id" in err)
    check("the parent's 'Session expired' hint will now fire",
          "login" in err or "session" in err)
    check("the browser is launched ONCE, not twice", calls == 1)
    check("the Playwright asyncio error no longer masks the real cause",
          "sync api" not in err and "asyncio" not in err)


def test_transient_failure_still_retries():
    """The retry is still right for the thing it was written for."""
    print("a stale form is still retried with a fresh browser")
    code, result, calls = run_script(STALE_FORM)

    check("still reports a failure after both attempts",
          result and result.get("status") == "failed")
    check("a transient fault gets its second attempt", calls == 2)
    check("the reason is not mislabelled as an expired session",
          "session expired" not in ((result or {}).get("error") or "").lower())


if __name__ == "__main__":
    test_dead_session_fails_once()
    test_transient_failure_still_retries()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: " + "; ".join(FAILS))
        sys.exit(1)
    print("all green")
