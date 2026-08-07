#!/usr/bin/env python
"""WILD MINDS — "The Borders". Full-body, wide, cinematic Veo 3 shots: the animals, who cross
every frontier freely, baffled by human walls and 'foreigners'. Clever, unifying, shareable.
Generates each shot, stitches, brands. Review before posting.
"""
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from modules.veo_kie import generate_veo, check_key, estimate_cost
from make_animal_movie import stitch
from modules.wild_brand import brand_video

STYLE = ("Epic cinematic wildlife documentary, shot on ARRI, wide sweeping FULL-BODY shot, "
         "golden-hour light over the vast open African savanna, dust drifting in the air, shallow "
         "depth of field, gentle film grain, natural ambient plains sounds, photorealistic 4k. ")

SHOTS = [
    STYLE + ('A majestic lion walks slowly across the open savanna toward a tiger and a small rabbit '
             'resting under a lone acacia tree; a long low stone wall runs across the plain far behind '
             'them. Full body, wide cinematic shot. The lion says in a deep rumbling voice: "I saw '
             'something strange at the human place today. A wall. A great long wall, cutting the land in two."'),
    STYLE + ('Wide full-body shot of the three animals together on the golden plain, the distant wall '
             'behind them. The tiger rises and stretches, then says in a smooth low voice: "A wall? What '
             'for? To stop the grass from growing on the other side?"'),
    STYLE + ('Wide low-angle shot, the little rabbit hops forward through the tall golden grass, ears up, '
             'full body. It squeaks nervously: "And they call the ones on the other side foreigners. As if '
             'the wind needs a passport!"'),
    STYLE + ('Epic wide shot at sunset: the lion, tiger and rabbit stand together on a ridge watching a '
             'great flock of birds cross freely over the distant wall, full-body silhouettes against the '
             'burning orange sky. The lion says softly and gravely: "We cross every border on Earth. And '
             'not one of us has ever asked another... where are you from?"'),
]


def main():
    if not check_key():
        print("KIE_API_KEY not set — add it to .env (https://kie.ai).", flush=True)
        return
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"borders_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    est = sum(estimate_cost("veo3_fast", 8) for _ in SHOTS)
    print(f"=== THE BORDERS — {len(SHOTS)} full-body Veo shots ~${est:.2f} ===", flush=True)
    clips = []
    for i, p in enumerate(SHOTS):
        c = out / f"shot_{i}.mp4"
        try:
            generate_veo(p, str(c), model="veo3_fast", aspect="9:16", resolution="720p", duration=8)
            clips.append(str(c))
        except Exception as e:
            print(f"shot {i} FAILED: {e}", flush=True)
    if not clips:
        print("no clips generated.", flush=True)
        return
    stitched = out / "stitched.mp4"
    if len(clips) == 1:
        shutil.copy(clips[0], stitched)
    else:
        stitch(clips, str(stitched))
    final = out / "the_borders.mp4"
    brand_video(str(stitched), str(final))
    print(f"EPISODE -> {final}  ({len(clips)} shots)", flush=True)


if __name__ == "__main__":
    main()
