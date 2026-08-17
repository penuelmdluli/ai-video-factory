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


def _owner_phone() -> str:
    """OWNER_WA_NUMBER from the agent's .env — a stable phone-number JID.
    (@lid ids die when the session is re-linked; error 463 on send.)"""
    try:
        for line in (AGENT_DATA.parent / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("OWNER_WA_NUMBER="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def notify(text: str) -> bool:
    """Message the owner. Official Cloud API first (never logs out);
    Baileys agent outbox as fallback. True if either path took it."""
    try:
        from modules.notify_wa_cloud import send as _cloud_send
        if _cloud_send(f"🟡 GENESIS NEWS\n{text}"):
            return True
    except Exception:
        pass
    try:
        try:
            items = json.loads(OUTBOX.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
        phone = _owner_phone()
        msg = {"text": f"🟡 GENESIS NEWS\n{text}"}
        if phone:
            msg["phone"] = phone
        else:
            admins = json.loads(ADMINS.read_text(encoding="utf-8"))
            if not admins:
                print("[WhatsApp] no destination configured")
                return False
            msg["jid"] = admins[0]
        items.append(msg)
        OUTBOX.write_text(json.dumps(items, indent=2), encoding="utf-8")
        print(f"[WhatsApp] queued to {phone or 'admin jid'}: {text[:50]}")
        return True
    except Exception as e:
        print(f"[WhatsApp] queue failed: {e}")
        return False


STAMPS = Path(__file__).parent.parent / "data" / "fail_alerts.json"


def notify_failure(tag: str, text: str, cooldown_h: float = 6.0) -> bool:
    """Failure alert with a per-tag cooldown — a task that crashes every
    5 minutes must page the owner ONCE, not forty times a night."""
    import time
    try:
        stamps = json.loads(STAMPS.read_text(encoding="utf-8"))
    except Exception:
        stamps = {}
    now = time.time()
    if now - stamps.get(tag, 0) < cooldown_h * 3600:
        print(f"[WhatsApp] '{tag}' alert suppressed (cooldown)")
        return False
    stamps[tag] = now
    STAMPS.parent.mkdir(parents=True, exist_ok=True)
    STAMPS.write_text(json.dumps(stamps, indent=2), encoding="utf-8")
    return notify(f"⚠️ {text}")


if __name__ == "__main__":
    notify("Test — Genesis News is now wired to your WhatsApp. "
           "You'll get matchday results, posted reels and the Sunday scorecard here. ⚽")
