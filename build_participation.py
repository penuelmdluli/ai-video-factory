"""
The participation slot — a reel that gives the fan a job.

The page's own numbers made this the default rather than the extra:

    MATCHDAY (crest + one question)   23,628 views   345 comments
    Predicted XI                      10,522 median  223 comments
    Strikers: who starts              33,747 best    138 comments
    Daily news reel                    1,164 median    4 comments

The news reels can spike — one hit 46,225 — but they leave nothing behind:
five comments on forty-six thousand views. The participation posts turn views
into hundreds of replies, and replies are what keep a page in front of the
same people. So two of the three daily slots come here, and news becomes the
exception for a genuinely new story.

Rotates position groups so the midfield, the defence and the keepers each get
their own week, and never repeats the same group twice running.

    python build_participation.py            # build + post the next in line
    python build_participation.py --dry-run
"""
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
STATE = ROOT / "data" / "participation_state.json"

# Each entry: (script, args, human label). Position debates carry the rotation
# because they are the format with real evidence behind them.
WHEEL = [
    ("build_debate_video.py", ["--group", "midfield"], "Midfield debate"),
    ("build_debate_video.py", ["--group", "defence"], "Defence debate"),
    ("build_debate_video.py", ["--group", "forwards"], "Striker debate"),
    ("build_debate_video.py", ["--group", "keepers"], "Keeper debate"),
    ("build_debate_video.py", ["--group", "attackers"], "Attack debate"),
]


def _next() -> int:
    try:
        return int(json.loads(STATE.read_text(encoding="utf-8"))["i"])
    except Exception:
        return 0


def _advance(i: int):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"i": (i + 1) % len(WHEEL),
                                 "at": datetime.now().isoformat()}),
                     encoding="utf-8")


def main(dry: bool, club: str):
    i = _next()
    script, extra, label = WHEEL[i % len(WHEEL)]
    cmd = [sys.executable, "-X", "utf8", script, "--club", club] + extra
    if not dry:
        cmd.append("--post")
    print(f"[Participation] {label} — {' '.join(cmd[3:])}", flush=True)
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       timeout=2700)
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines()[-6:]:
        print(f"  {line}", flush=True)
    if r.returncode == 0:
        _advance(i)
        print(f"[Participation] done — next up: "
              f"{WHEEL[(i + 1) % len(WHEEL)][2]}", flush=True)
        return 0
    print(f"[Participation] {label} failed (exit {r.returncode})", flush=True)
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--club", default="chiefs")
    a = ap.parse_args()
    sys.exit(main(a.dry_run, a.club))
