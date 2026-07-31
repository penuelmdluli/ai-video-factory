"""
AI Video Factory — Telegram Remote Control

Control the whole factory from your phone. This is a zero-infrastructure
Telegram bot (long-polling, no public URL needed, no extra dependencies
beyond `requests`) that lets an authorised owner:

  • /run [full|morning|evening|trends-only|post-only]
        Trigger the Genesis Content Engine (the real production pipeline that
        runs in GitHub Actions) via workflow_dispatch.
  • /status     Show the latest Genesis workflow run (status + conclusion).
  • /runs       List the last few workflow runs with links.
  • /id         Show your Telegram chat id (use it to fill ALLOWED_CHAT_IDS).
  • /help       Show the command list.

Setup (see REMOTE_CONTROL.md for the full walk-through):
  1. Create a bot with @BotFather → copy the token.
  2. Create a GitHub Personal Access Token with `actions:write` (fine-grained)
     or classic `repo` scope.
  3. Put these in your .env (or environment):

        TELEGRAM_BOT_TOKEN=123456:ABC...
        TELEGRAM_ALLOWED_CHAT_IDS=            # leave blank first run
        GITHUB_TOKEN=ghp_...
        GITHUB_REPO=penuelmdluli/ai-video-factory

  4. Run `python remote_control.py`, message your bot, send /id, copy the id
     into TELEGRAM_ALLOWED_CHAT_IDS, restart. Done.

The module also exposes `notify(text)` / `send_message(...)` so the rest of
the pipeline (or the GitHub Actions workflow) can push status updates to your
phone.

Usage:
    python remote_control.py            # run the bot (long-polling)
    python remote_control.py --notify "Batch finished ✅"   # send one message and exit
"""
import os
import sys
import time
import argparse

import requests

try:
    # Match the rest of the codebase: load .env if python-dotenv is present.
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


# ── Configuration ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "penuelmdluli/ai-video-factory").strip()
GENESIS_WORKFLOW_FILE = os.getenv("GENESIS_WORKFLOW_FILE", "genesis-content-engine.yml").strip()
GENESIS_WORKFLOW_REF = os.getenv("GENESIS_WORKFLOW_REF", "main").strip()

# Valid batch options — must match the workflow_dispatch inputs in
# .github/workflows/genesis-content-engine.yml
VALID_BATCHES = ["full", "morning", "evening", "trends-only", "post-only"]

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
GITHUB_API = "https://api.github.com"


def _allowed_chat_ids():
    """Parse TELEGRAM_ALLOWED_CHAT_IDS (comma-separated) into a set of strings."""
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    return {c.strip() for c in raw.split(",") if c.strip()}


# ── Telegram helpers ──────────────────────────────────────────
def send_message(chat_id, text, parse_mode="Markdown", disable_preview=True):
    """Send a Telegram message. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN:
        print("[remote_control] TELEGRAM_BOT_TOKEN not set — cannot send message.")
        return False
    url = TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"[remote_control] sendMessage failed {r.status_code}: {r.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[remote_control] sendMessage error: {e}")
        return False


def notify(text, parse_mode="Markdown"):
    """
    Broadcast a message to every authorised chat id.

    Handy for the pipeline / workflow to ping the owner, e.g.
        from remote_control import notify
        notify("✅ Evening batch finished — 4 videos posted.")
    """
    ids = _allowed_chat_ids()
    if not ids:
        print("[remote_control] TELEGRAM_ALLOWED_CHAT_IDS not set — nothing to notify.")
        return False
    ok = True
    for chat_id in ids:
        ok = send_message(chat_id, text, parse_mode=parse_mode) and ok
    return ok


# ── GitHub Actions helpers ────────────────────────────────────
def _github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def dispatch_workflow(batch):
    """
    Trigger the Genesis workflow via workflow_dispatch.

    Returns (ok: bool, message: str).
    """
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is not set — cannot trigger the pipeline."
    if batch not in VALID_BATCHES:
        return False, f"Unknown batch `{batch}`. Choose one of: {', '.join(VALID_BATCHES)}."

    url = (
        f"{GITHUB_API}/repos/{GITHUB_REPO}/actions/workflows/"
        f"{GENESIS_WORKFLOW_FILE}/dispatches"
    )
    body = {"ref": GENESIS_WORKFLOW_REF, "inputs": {"batch": batch}}
    try:
        r = requests.post(url, headers=_github_headers(), json=body, timeout=30)
    except requests.RequestException as e:
        return False, f"Network error dispatching workflow: {e}"

    if r.status_code == 204:
        return True, (
            f"🚀 Triggered *{batch}* batch on `{GITHUB_REPO}` "
            f"(ref `{GENESIS_WORKFLOW_REF}`).\nUse /status in ~30s to watch it."
        )
    if r.status_code == 404:
        return False, (
            f"404 from GitHub. Check GITHUB_REPO (`{GITHUB_REPO}`), the workflow "
            f"file name (`{GENESIS_WORKFLOW_FILE}`), and that the token can see the repo."
        )
    if r.status_code in (401, 403):
        return False, (
            f"{r.status_code} from GitHub — the token is missing `actions:write` "
            f"(fine-grained) or `repo` (classic) scope."
        )
    return False, f"GitHub returned {r.status_code}: {r.text[:200]}"


def list_runs(limit=5):
    """
    Fetch the most recent runs of the Genesis workflow.

    Returns (ok: bool, runs: list | error_message: str).
    """
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is not set — cannot read run status."
    url = (
        f"{GITHUB_API}/repos/{GITHUB_REPO}/actions/workflows/"
        f"{GENESIS_WORKFLOW_FILE}/runs?per_page={limit}"
    )
    try:
        r = requests.get(url, headers=_github_headers(), timeout=30)
    except requests.RequestException as e:
        return False, f"Network error reading runs: {e}"
    if r.status_code != 200:
        return False, f"GitHub returned {r.status_code}: {r.text[:200]}"
    return True, r.json().get("workflow_runs", [])


_STATUS_EMOJI = {
    "completed": "",  # replaced by conclusion emoji below
    "in_progress": "⏳",
    "queued": "🕒",
    "waiting": "🕒",
    "requested": "🕒",
}
_CONCLUSION_EMOJI = {
    "success": "✅",
    "failure": "❌",
    "cancelled": "🚫",
    "skipped": "⏭️",
    "timed_out": "⌛",
    "startup_failure": "💥",
}


def _run_line(run):
    """Format a single workflow run as one line of Markdown."""
    status = run.get("status", "?")
    conclusion = run.get("conclusion")
    if status == "completed":
        emoji = _CONCLUSION_EMOJI.get(conclusion, "❓")
        state = conclusion or "completed"
    else:
        emoji = _STATUS_EMOJI.get(status, "•")
        state = status
    created = (run.get("created_at") or "").replace("T", " ").replace("Z", " UTC")
    number = run.get("run_number", "?")
    url = run.get("html_url", "")
    return f"{emoji} *#{number}* — {state} · {created}\n{url}"


def format_status():
    """Human-readable summary of the latest run for /status."""
    ok, runs = list_runs(limit=1)
    if not ok:
        return f"⚠️ {runs}"
    if not runs:
        return "No Genesis workflow runs found yet."
    return "📊 *Latest Genesis run:*\n\n" + _run_line(runs[0])


def format_runs(limit=5):
    """Human-readable list of recent runs for /runs."""
    ok, runs = list_runs(limit=limit)
    if not ok:
        return f"⚠️ {runs}"
    if not runs:
        return "No Genesis workflow runs found yet."
    lines = [f"📜 *Last {len(runs)} runs:*", ""]
    lines.extend(_run_line(r) for r in runs)
    return "\n".join(lines)


# ── Command handling ──────────────────────────────────────────
HELP_TEXT = (
    "🎬 *AI Video Factory — Remote Control*\n\n"
    "*/run* `[batch]` — trigger the Genesis pipeline\n"
    "    batches: `full` (default), `morning`, `evening`, `trends-only`, `post-only`\n"
    "*/status* — latest workflow run\n"
    "*/runs* — recent runs\n"
    "*/id* — show your chat id\n"
    "*/ping* — check the bot is alive\n"
    "*/help* — this message"
)


def _is_authorised(chat_id):
    allowed = _allowed_chat_ids()
    # If no allow-list is configured, only /id is useful (handled by caller).
    return str(chat_id) in allowed


def handle_command(text, chat_id):
    """
    Route one incoming message to a reply string.

    /id and /ping are available to everyone (so a new owner can bootstrap the
    allow-list). Everything else requires an authorised chat id.
    """
    parts = text.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower().lstrip("/")
    # Strip @BotName suffix that Telegram adds in groups (e.g. /run@MyBot).
    cmd = cmd.split("@", 1)[0]
    args = parts[1:]

    if cmd in ("id", "whoami"):
        return f"Your chat id is `{chat_id}`.\nAdd it to `TELEGRAM_ALLOWED_CHAT_IDS`."

    if cmd == "ping":
        return "pong 🏓"

    # ── Everything below requires authorisation ──
    if not _is_authorised(chat_id):
        return (
            "⛔ Not authorised. Send /id and add your chat id to "
            "`TELEGRAM_ALLOWED_CHAT_IDS`, then restart the bot."
        )

    if cmd in ("start", "help"):
        return HELP_TEXT

    if cmd == "status":
        return format_status()

    if cmd == "runs":
        return format_runs()

    if cmd == "run":
        batch = args[0].lower() if args else "full"
        ok, msg = dispatch_workflow(batch)
        return msg

    return f"Unknown command `/{cmd}`. Try /help."


# ── Long-polling loop ─────────────────────────────────────────
def poll_loop():
    """Run the bot with getUpdates long-polling until interrupted."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set. See REMOTE_CONTROL.md.")
        sys.exit(1)

    allowed = _allowed_chat_ids()
    print("🎬 AI Video Factory — Remote Control")
    print(f"   repo:      {GITHUB_REPO}")
    print(f"   workflow:  {GENESIS_WORKFLOW_FILE} (ref {GENESIS_WORKFLOW_REF})")
    print(f"   github:    {'configured' if GITHUB_TOKEN else 'MISSING (set GITHUB_TOKEN)'}")
    if allowed:
        print(f"   owners:    {', '.join(sorted(allowed))}")
    else:
        print("   owners:    NONE — message the bot and send /id to get yours.")
    print("   Listening for messages... (Ctrl+C to stop)")

    get_updates = TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN, method="getUpdates")
    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            r = requests.get(get_updates, params=params, timeout=40)
            if r.status_code != 200:
                print(f"[getUpdates] {r.status_code}: {r.text[:200]}")
                time.sleep(3)
                continue
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                text = message.get("text")
                chat_id = message.get("chat", {}).get("id")
                if not text or chat_id is None:
                    continue
                print(f"[msg] {chat_id}: {text}")
                reply = handle_command(text, chat_id)
                if reply:
                    send_message(chat_id, reply)
        except requests.RequestException as e:
            print(f"[poll] network error: {e} — retrying in 5s")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


def main():
    parser = argparse.ArgumentParser(description="AI Video Factory — Telegram remote control")
    parser.add_argument("--notify", metavar="TEXT", help="Send one message to all owners and exit")
    args = parser.parse_args()

    if args.notify:
        ok = notify(args.notify)
        sys.exit(0 if ok else 1)

    poll_loop()


if __name__ == "__main__":
    main()
