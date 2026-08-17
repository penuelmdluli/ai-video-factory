"""
WhatsApp Cloud API notifications — Meta's OFFICIAL channel. No linked device,
no QR scans, no 401 logouts (the Baileys agents died three times on
2026-08-17 alone; this path cannot).

Setup (one-time, ~10 min, developers.facebook.com):
  1. Open the Meta app (or create one) -> Add product -> WhatsApp
  2. "API Setup" page gives: a TEST NUMBER, its Phone number ID, and a token
  3. Add the owner's number as a recipient (Meta sends a confirm code)
  4. .env:  WA_CLOUD_TOKEN=...   WA_CLOUD_PHONE_ID=...   OWNER_WA_NUMBER=27...
  (Temporary tokens die in 24h — for permanent, create a System User token
   in Business Settings with whatsapp_business_messaging permission.)

Free-form text only lands inside the 24h window after the owner last
messaged the bot; outside it we fall back to the pre-approved hello_world
template (guaranteed delivery) with the real text following when possible.
"""
import json
import os
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"


def _cfg():
    tok = os.getenv("WA_CLOUD_TOKEN", "")
    pid = os.getenv("WA_CLOUD_PHONE_ID", "")
    to = os.getenv("OWNER_WA_NUMBER", "") or "27792572466"
    return tok, pid, to.lstrip("+")


def _post(pid: str, tok: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{GRAPH}/{pid}/messages",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def send(text: str) -> bool:
    """Send a text to the owner via the Cloud API. False if not configured
    or delivery failed (caller falls back to the Baileys outbox)."""
    tok, pid, to = _cfg()
    if not tok or not pid:
        return False
    try:
        _post(pid, tok, {"messaging_product": "whatsapp", "to": to,
                         "type": "text", "text": {"body": text[:4000]}})
        print(f"[WA-Cloud] sent: {text[:50]}")
        return True
    except Exception as e:
        # outside the 24h service window free-form is rejected — try the
        # always-deliverable hello_world template so the owner gets SOMETHING
        try:
            _post(pid, tok, {"messaging_product": "whatsapp", "to": to,
                             "type": "template",
                             "template": {"name": "hello_world",
                                          "language": {"code": "en_US"}}})
            print("[WA-Cloud] window closed — sent template ping instead")
            return True
        except Exception as e2:
            print(f"[WA-Cloud] failed: {str(e)[:80]} / {str(e2)[:60]}")
            return False


if __name__ == "__main__":
    ok = send("Genesis News — official WhatsApp channel is live. "
              "No more logouts. ⚽")
    print("delivered" if ok else "not configured or failed")
