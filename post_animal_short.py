#!/usr/bin/env python
"""Finish the talking-animal short: reuse shot 0 (already generated) + 2 new Veo 3 shots,
stitched into one continuous scene."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from modules.veo_kie import generate_veo
from make_animal_movie import STYLE, SCENE, stitch

SHOT0 = ROOT / "output" / "veo_test_shot.mp4"   # the lion opener (already paid)

NEW = [
    STYLE + SCENE + ('The tiger smirks knowingly and says in a smooth low voice: "Every morning, '
                     'they wake and stare at a small glowing rectangle. Before water. Before anything."'),
    STYLE + SCENE + ('The tiny rabbit\'s eyes go wide with realization and it squeaks: "So the little '
                     'glowing rectangle... is their real king?" The lion and tiger slowly nod, amused.'),
]


def main():
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"animal_short_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== ANIMAL SHORT — reuse shot0 + {len(NEW)} new Veo shots (~${0.15*8*len(NEW):.2f}) ===", flush=True)
    clips = [str(SHOT0)] if SHOT0.exists() else []
    for i, p in enumerate(NEW, 1):
        c = out / f"shot_{i}.mp4"
        try:
            generate_veo(p, str(c), model="veo3_fast", aspect="9:16", resolution="720p", duration=8)
            clips.append(str(c))
        except Exception as e:
            print(f"shot {i} FAILED: {e}", flush=True)
    if len(clips) < 2:
        print("not enough clips to stitch", flush=True)
        return
    final = out / "short.mp4"
    stitch(clips, str(final))
    print(f"SHORT -> {final}  ({len(clips)} shots)", flush=True)


if __name__ == "__main__":
    main()
