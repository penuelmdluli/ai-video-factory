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


def check_email_alerts():
    """The inbox is a monitoring channel too — RunPod, Meta, TikTok, YouTube
    and billing all warn by email before anything visibly breaks."""
    try:
        from modules.gmail_alerts import find_alerts
    except Exception:
        return
    for tag, msg in find_alerts():
        PROBLEMS.append((tag, msg))


def check_orphaned_builds():
    """A batch build that outlives its scheduled window and keeps the GPU.

    2026-08-23: the music task hit its 3h Task Scheduler limit at 18:00, the
    scheduler killed the wrapper but not the python child, and the orphan held
    10.9GB of an 11GB card until 20:50. The 19:00 PSL evening build reached TTS,
    found no VRAM, and sat frozen for 1h49m — nothing posted, and check_posting
    stayed quiet because its log was only two hours stale.

    Long-lived pm2 services (matchday live, vault, agent) are excluded: they are
    supposed to run for days. One-shot builds are not.
    """
    LIMIT_H = {"make_music.py": 3.5, "build_psl_news.py": 1.5,
               "build_careers_daily.py": 1.5, "main.py": 2.0}
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
             "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate.ToString('o'))|$($_.CommandLine)\" }"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return

    now = datetime.now()
    for line in out.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) != 3:
            continue
        pid, started, cmd = parts
        if "matchday.py" in cmd or "vault-bot" in cmd or "shopmo" in cmd:
            continue          # pm2 services, legitimately long-lived
        script = next((k for k in LIMIT_H if k in cmd), "")
        if not script:
            continue
        try:
            age_h = (now - datetime.fromisoformat(started).replace(tzinfo=None)).total_seconds() / 3600
        except Exception:
            continue
        if age_h > LIMIT_H[script]:
            PROBLEMS.append((f"orphan-{script.replace('.py','')}",
                             f"{script} (pid {pid}) has run {age_h:.1f}h, past its "
                             f"{LIMIT_H[script]}h ceiling — likely orphaned and "
                             f"holding the GPU. Kill it or the next build starves."))


def main():
    check_pm2()
    check_whatsapp_logout()
    check_posting()
    check_data_feeds()
    check_email_alerts()
    check_orphaned_builds()
    if not PROBLEMS:
        print(f"[Health] {datetime.now():%H:%M} all green")
        return
    for tag, msg in PROBLEMS:
        print(f"[Health] PROBLEM {tag}: {msg}")
        notify_failure(f"health-{tag}", msg, cooldown_h=6)


if __name__ == "__main__":
    main()
