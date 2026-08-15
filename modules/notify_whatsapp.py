"""
WhatsApp notifications — via the ShopMO agent's outbox.

The always-on shopmo-whatsapp agent (SELLBOT project, PM2) polls its
data/outbox.json and sends anything queued there from the connected WhatsApp
number. We just append a message addressed to the admin — no second WhatsApp
connection, no API fees.

Usage:
    from modules.notify_whatsapp import notify
    notify("⚽ FT posted: Chiefs 1-1 Sundowns")
"""
import json
from pathlib import Path

AGENT_DATA = Path(r"C:\Users\PenuelM\Documents\SELLBOT\shopmo-whatsapp\data")
OUTBOX = AGENT_DATA / "outbox.json"
ADMINS = AGENT_DATA / "admins.json"


def notify(text: str) -> bool:
    """Queue a WhatsApp message to the owner/admin. True if queued."""
    try:
        admins = json.loads(ADMINS.read_text(encoding="utf-8"))
        if not admins:
            print("[WhatsApp] no admin jid configured")
            return False
        try:
            items = json.loads(OUTBOX.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
        items.append({"jid": admins[0], "text": f"🟡 GENESIS NEWS\n{text}"})
        OUTBOX.write_text(json.dumps(items, indent=2), encoding="utf-8")
        print(f"[WhatsApp] queued: {text[:60]}")
        return True
    except Exception as e:
        print(f"[WhatsApp] queue failed: {e}")
        return False


if __name__ == "__main__":
    notify("Test — Genesis News is now wired to your WhatsApp. "
           "You'll get matchday results, posted reels and the Sunday scorecard here. ⚽")
