#!/usr/bin/env python
"""Autonomous top-up builder for SAGA OF THE NORTH.

Keeps a buffer of READY (built-but-unposted) episodes on disk so the 3x/day poster
(post_next_viking.py) never runs dry. It builds only what is missing, in strict season order, and
stops on its own once every episode in viking_saga.py is built — so cost is bounded to the season
and drops to $0 when the bank is exhausted. Add Season 2 episodes to viking_saga.py and it resumes
building them automatically.

Run daily by the SagaOfTheNorth_Build scheduled task (06:00, before the 08:00 post). Safe to run by
hand too:

  python auto_viking_build.py            # top the buffer up to BUFFER
  python auto_viking_build.py --buffer 5 # keep a bigger cushion
  python auto_viking_build.py --status   # show ready/unbuilt and what it WOULD build, build nothing
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Keep at least this many episodes built-but-unposted. With posting at 3x/day and this task at 1x/day
# a buffer of 4 leaves a one-post cushion each morning after the day's three posts drain it.
BUFFER = int(os.getenv("VIKING_BUILD_BUFFER", "4"))
POSTED = ROOT / "logs" / "viking_posted.json"

import viking_saga as saga


def _posted():
    try:
        return set(json.loads(POSTED.read_text()))
    except Exception:
        return set()


def _built():
    """Newest final.mp4 per episode number, series naming only (viking_epNN_slug)."""
    best = {}
    for f in ROOT.glob("output/viking_ep*_*/final.mp4"):
        m = re.match(r"viking_ep(\d{2})_", f.parent.name)
        if not m:
            continue
        n = int(m.group(1))
        if n not in best or f.stat().st_mtime > best[n].stat().st_mtime:
            best[n] = f
    return best


def plan(buffer):
    posted = _posted()
    built = _built()
    ready = sorted(n for n, f in built.items() if str(f) not in posted)
    unbuilt = [e["ep"] for e in saga.EPISODES if e["ep"] not in built]
    need = max(0, buffer - len(ready))
    count = min(need, len(unbuilt))
    return ready, unbuilt, count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buffer", type=int, default=BUFFER, help="ready episodes to keep on hand")
    ap.add_argument("--status", action="store_true", help="show the plan and build nothing")
    args = ap.parse_args()

    ready, unbuilt, count = plan(args.buffer)
    print(f"[auto-build] ready={ready} ({len(ready)}) unbuilt={unbuilt} buffer_target={args.buffer}",
          flush=True)

    if count <= 0:
        if not unbuilt:
            print("[auto-build] season fully built — add episodes to viking_saga.py for more.",
                  flush=True)
        else:
            print(f"[auto-build] buffer OK ({len(ready)} ready) — nothing to build.", flush=True)
        return

    if args.status:
        print(f"[auto-build] WOULD build the next {count} unbuilt episode(s).", flush=True)
        return

    print(f"[auto-build] building {count} episode(s) to refill the buffer...", flush=True)
    # Force the tech-news female narrator; finish_short.py already defaults to it, belt-and-braces.
    env = dict(os.environ, SAGA_NARRATOR="kokoro")
    r = subprocess.run([sys.executable, str(ROOT / "build_viking_batch.py"), "--count", str(count)],
                       env=env)
    print(f"[auto-build] build_viking_batch exited {r.returncode}", flush=True)


if __name__ == "__main__":
    main()
