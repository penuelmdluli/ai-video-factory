"""
Health check — the watchdog that tells the owner when the machine skips a beat.

Runs every 2h from Task Scheduler. Checks the things that have actually
broken before (2026-08: WhatsApp logouts, silent build crashes, dead PM2
processes) and WhatsApps the owner ONCE per problem (cooldowns in
notify_failure — no alert storms).

Usage: python build_health_check.py
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

from modules.notify_whatsapp import notify_failure

ROOT = Path(__file__).parent
PROBLEMS = []


def check_pm2():
    """genesis-vault / shopmo-agent / genesis-live must be online."""
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True,
                           timeout=60, shell=True)
        procs = {p["name"]: p["pm2_env"]["status"]
                 for p in json.loads(r.stdout or "[]")}
    except Exception as e:
        PROBLEMS.append(("pm2", f"PM2 unreachable: {str(e)[:80]}"))
        return
    for name in ("genesis-vault", "shopmo-agent", "genesis-live"):
        st = procs.get(name, "missing")
        if st != "online":
            PROBLEMS.append((f"pm2-{name}", f"{name} is {st} — bots down"))


def check_whatsapp_logout():
    """A LOGGED OUT storm in the vault log means media stops arriving."""
    for name, log in (("vault", Path.home() / ".pm2/logs/genesis-vault-out.log"),
                      ("agent", Path.home() / ".pm2/logs/shopmo-agent-error-0.log")):
        try:
            if time.time() - log.stat().st_mtime > 3600:
                continue                      # nothing recent, fine
            tail = log.read_text(encoding="utf-8", errors="ignore")[-3000:]
            recent_logout = "LOGGED OUT" in tail.rsplit("connected", 1)[-1]
            if recent_logout:
                PROBLEMS.append((f"wa-{name}",
                                 f"WhatsApp {name} LOGGED OUT — re-scan needed "
                                 "(ask Claude for the QR)"))
        except Exception:
            pass


def check_posting():
    """Three reels post daily; a >9h silence during the day means a dead slot."""
    log = ROOT / "logs" / "psl_news.log"
    try:
        age_h = (time.time() - log.stat().st_mtime) / 3600
    except Exception:
        return
    hour = datetime.now().hour
    if age_h > 9 and 8 <= hour <= 23:
        PROBLEMS.append(("posting",
                         f"No reel activity for {age_h:.0f}h — check the "
                         "scheduled builds"))


def check_data_feeds():
    """Standings/fixtures caches should refresh at least daily."""
    for name, f in (("standings", ROOT / "data" / "psl_standings_cache.json"),
                    ("squads", ROOT / "data" / "psl_squads_cache.json")):
        try:
            age_h = (time.time() - f.stat().st_mtime) / 3600
            if age_h > 48:
                PROBLEMS.append((f"feed-{name}",
                                 f"{name} cache is {age_h:.0f}h old — ESPN "
                                 "feed may be failing"))
        except Exception:
            pass


def main():
    check_pm2()
    check_whatsapp_logout()
    check_posting()
    check_data_feeds()
    if not PROBLEMS:
        print(f"[Health] {datetime.now():%H:%M} all green")
        return
    for tag, msg in PROBLEMS:
        print(f"[Health] PROBLEM {tag}: {msg}")
        notify_failure(f"health-{tag}", msg, cooldown_h=6)


if __name__ == "__main__":
    main()
