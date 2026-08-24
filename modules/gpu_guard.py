"""
Preflight guard: never start a build behind a dead one.

2026-08-23 and again 2026-08-24: the music task hit its 3h Task Scheduler
ceiling, the scheduler killed the wrapper but NOT the python child, and the
orphan held ~10.8GB of an 11GB card. Both times the next PSL build reached TTS,
found no VRAM, and froze — 1h49m the first night, 2h17m the second. Two slots
lost to a process that had already been told to stop.

The health check alerts on this every 2h, but an alert does not free a card.
This reaps first and then waits, and every build calls it before it starts.

    from modules.gpu_guard import preflight
    preflight("build_psl_news.py")
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Hours after which a one-shot build is certainly dead. A normal PSL build is
# 11-15 min, careers similar, music is capped at 3h by Task Scheduler itself.
CEILING_H = {
    "make_music.py": 3.5,
    "make_zuzu.py": 2.5,
    "build_psl_news.py": 1.5,
    "build_careers_daily.py": 1.5,
    "build_log_card.py": 1.0,
    "main.py": 2.0,
}
# pm2 services and long-lived feeds — never touch these.
PROTECTED = ("matchday.py", "vault-bot", "shopmo", "scheduler.py")

# A build past its ceiling may still be alive — just slow, or recovering after
# the card was freed. Age alone cannot tell a hang from slow progress, so a
# process whose log moved recently is left alone no matter how old it is.
LOG_FOR = {
    "build_psl_news.py": "logs/psl_news.log",
    "build_careers_daily.py": "logs/careers_daily.log",
    "build_log_card.py": "logs/log_card.log",
    "make_music.py": "logs/music.log",
    "make_zuzu.py": "logs/zuzu.log",
}
ALIVE_WINDOW_S = 600      # log written in the last 10 min = still working

VRAM_FLOOR_MIB = 2500      # TTS + video needs roughly this much headroom
WAIT_SECONDS = 300         # how long to wait for a busy card before giving up


def _ps(cmd: str) -> str:
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                              capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ""


def _log_is_moving(script: str) -> bool:
    """True if this build's log was written to very recently."""
    rel = LOG_FOR.get(script)
    if not rel:
        return False
    f = ROOT / rel
    try:
        return (time.time() - f.stat().st_mtime) < ALIVE_WINDOW_S
    except Exception:
        return False


def find_orphans(exclude_pid: int | None = None) -> list[tuple[int, str, float]]:
    """[(pid, script, age_hours)] for one-shot builds that are past their
    ceiling AND have stopped writing to their log."""
    out = _ps("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
              "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate.ToString('o'))|$($_.CommandLine)\" }")
    found, now = [], datetime.now()
    for line in out.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) != 3:
            continue
        pid_s, started, cmd = parts
        if any(p in cmd for p in PROTECTED):
            continue
        script = next((k for k in CEILING_H if k in cmd), "")
        if not script:
            continue
        try:
            pid = int(pid_s)
            age = (now - datetime.fromisoformat(started).replace(tzinfo=None)).total_seconds() / 3600
        except Exception:
            continue
        if pid == exclude_pid or age <= CEILING_H[script]:
            continue
        if _log_is_moving(script):
            print(f"[GPUGuard] {script} (pid {pid}) is {age:.1f}h old but its log "
                  f"is still moving — leaving it alone")
            continue
        found.append((pid, script, age))
    return found


def reap(exclude_pid: int | None = None) -> list[str]:
    """Kill every orphan past its ceiling. Returns what was killed."""
    killed = []
    for pid, script, age in find_orphans(exclude_pid):
        _ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
        msg = f"{script} (pid {pid}, {age:.1f}h old)"
        killed.append(msg)
        print(f"[GPUGuard] reaped orphan: {msg}")
    return killed


def free_vram_mib() -> int:
    out = _ps("nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits")
    try:
        used, total = [int(x.strip()) for x in out.strip().splitlines()[0].split(",")]
        return total - used
    except Exception:
        return VRAM_FLOOR_MIB      # no GPU info — do not block the build


def preflight(script_name: str = "", wait: int = WAIT_SECONDS) -> bool:
    """Reap dead builds, then wait for enough VRAM. True if clear to build."""
    import os
    reap(exclude_pid=os.getpid())
    deadline = time.time() + wait
    while True:
        free = free_vram_mib()
        if free >= VRAM_FLOOR_MIB:
            print(f"[GPUGuard] {free} MiB free — clear to build {script_name}")
            return True
        if time.time() >= deadline:
            print(f"[GPUGuard] only {free} MiB free after {wait}s — building anyway, "
                  f"expect it to be slow")
            return False
        print(f"[GPUGuard] {free} MiB free, need {VRAM_FLOOR_MIB} — waiting…")
        time.sleep(20)


if __name__ == "__main__":
    k = reap()
    print(f"[GPUGuard] reaped {len(k)}" if k else "[GPUGuard] no orphans")
    print(f"[GPUGuard] free VRAM: {free_vram_mib()} MiB")
    sys.exit(0)
