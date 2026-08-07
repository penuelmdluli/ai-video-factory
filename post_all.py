#!/usr/bin/env python
"""Post one $0 beat-synced reel to each channel in a single warm process (Kokoro loads once).
Usage: python post_all.py [niche1 niche2 ...]   (default: tech_news ai_money motivation)
"""
import sys
import traceback

from make_graphic_reel import run

NICHES = sys.argv[1:] or ["tech_news", "ai_money", "motivation", "health_wellness", "blissful_moments"]
DRY = "--dry-run" in NICHES
NICHES = [n for n in NICHES if not n.startswith("--")]

for n in NICHES:
    print(f"\n############ {n} ############", flush=True)
    try:
        run(n, dry_run=DRY)
    except Exception:
        print(f"{n} FAILED:\n" + traceback.format_exc(), flush=True)
print("\n==== post_all complete ====", flush=True)
