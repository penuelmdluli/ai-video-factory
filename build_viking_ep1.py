#!/usr/bin/env python
"""Build a single SAGA OF THE NORTH episode (defaults to EP.1 — FIRST LIGHT).

Kept as a convenience entry point; the season builder is build_viking_batch.py.

  python build_viking_ep1.py          # EP.1
  python build_viking_ep1.py 5        # EP.5 — THE SHIELD WALL
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from build_viking_batch import build_episode, HERO
from modules.veo_kie import upload_image, check_key, estimate_cost
import viking_saga as saga

# Re-exported for anything that imported them from here before the series rewrite.
STYLE = saga.STYLE


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ep = saga.BY_EP.get(n)
    if not ep:
        print(f"no episode {n} — season 1 is 1..{len(saga.EPISODES)}", flush=True)
        return
    if not check_key():
        print("KIE_API_KEY not set.", flush=True)
        return
    if not HERO.exists():
        print(f"hero image missing: {HERO}", flush=True)
        return
    cost = estimate_cost("veo3_lite", 8) * len(ep["shots"])
    print(f"=== {saga.SERIES} EP.{ep['ep']} {ep['title']} — "
          f"{len(ep['shots'])} shots ~${cost:.2f} ===", flush=True)
    final = build_episode(ep, upload_image(str(HERO)))
    print(f"EPISODE -> {final}", flush=True)


if __name__ == "__main__":
    main()
