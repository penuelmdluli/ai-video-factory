"""
Gmail as a monitoring channel — reads the few senders that mean the machine
is actually broken.

Why this exists: RunPod deleted the network volume on 2026-08-18 and the
warning sat unread for four days, because it landed in an inbox carrying
63,000 unread messages. Task Scheduler can't see a mailbox, so the health
check now reads it directly.

Read-only. Never sends, never deletes, never labels.

Setup once:  python auth_gmail.py
Standalone:  python modules/gmail_alerts.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TOKEN_PATH = ROOT / "tokens" / "gmail_token.json"
CLIENT_SECRET_PATH = ROOT / "tokens" / "youtube_client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# (tag, gmail query, human prefix). Tag drives the WhatsApp cooldown, so keep
# them stable — renaming a tag re-pages the owner for an old problem.
RULES = [
    ("runpod",
     'from:runpod.io (subject:"low balance" OR subject:"past due" '
     'OR subject:"volume deleted" OR subject:"payment failed")',
     "RunPod"),
    ("billing",
     'subject:("payment declined" OR "payment failed" OR "past due" '
     'OR "will be cancelled" OR "insufficient funds" OR "card declined")',
     "Billing"),
    ("fb-page",
     'from:(facebookmail.com OR facebook.com OR meta.com) '
     'subject:(violat OR restrict OR disabled OR removed OR appeal OR suspend)',
     "Facebook page"),
    ("tiktok-auth",
     'from:tiktok.com subject:("new device login" OR "password" '
     'OR "suspicious" OR "unusual activity")',
     "TikTok"),
    ("youtube",
     'from:youtube.com subject:(strike OR copyright OR violat '
     'OR suspended OR "removed your")',
     "YouTube"),
    ("api-quota",
     'from:(elevenlabs.io OR openai.com OR anthropic.com OR huggingface.co '
     'OR googleapis.com) subject:(quota OR "rate limit" OR credits '
     'OR "limit reached" OR expired)',
     "API provider"),
]


def _service():
    """None if Gmail was never authorised — the health check must survive that."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return None
    if not TOKEN_PATH.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        print(f"[Gmail] auth failed: {str(e)[:100]}")
        return None


def _newest(svc, query, window_days=2):
    """Subject + date of the most recent match, or None."""
    q = f"({query}) newer_than:{window_days}d -in:spam -in:trash"
    try:
        res = svc.users().messages().list(
            userId="me", q=q, maxResults=3).execute()
    except Exception as e:
        print(f"[Gmail] query failed: {str(e)[:100]}")
        return None
    msgs = res.get("messages", [])
    if not msgs:
        return None
    try:
        m = svc.users().messages().get(
            userId="me", id=msgs[0]["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]).execute()
    except Exception:
        return None
    hdrs = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
    return {
        "subject": hdrs.get("Subject", "(no subject)")[:110],
        "from": hdrs.get("From", "")[:60],
        "count": len(msgs),
    }


def find_alerts(window_days=2):
    """[(tag, message)] for build_health_check. Empty list = all clear."""
    svc = _service()
    if svc is None:
        return []
    problems = []
    for tag, query, prefix in RULES:
        hit = _newest(svc, query, window_days)
        if hit:
            more = f" (+{hit['count'] - 1} more)" if hit["count"] > 1 else ""
            problems.append((f"mail-{tag}",
                             f"{prefix} email: \"{hit['subject']}\"{more}"))
    return problems


def main():
    if not TOKEN_PATH.exists():
        print("[Gmail] not authorised yet — run: python auth_gmail.py")
        return 1
    alerts = find_alerts()
    if not alerts:
        print("[Gmail] no operational alerts in the last 2 days")
        return 0
    for tag, msg in alerts:
        print(f"[Gmail] {tag}: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
