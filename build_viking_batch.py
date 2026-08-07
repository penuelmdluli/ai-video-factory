#!/usr/bin/env python
"""Crank out a BATCH of SAGA OF THE NORTH shorts — distinct epic Viking moments, same locked hero,
each ~16s and ~$0.80, with the full pack (narrator + score + subtitles + follow + comment)."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from modules.veo_kie import generate_veo, upload_image, check_key, estimate_cost
from build_viking_ep1 import STYLE, concat_uniform
from finish_short import finish

HERO = ROOT / "assets" / "viking" / "hero.png"

SHORTS = [
    {
        "slug": "oath",
        "shots": [
            "Night, firelight. LOW-ANGLE PUSH-IN on the warrior kneeling before a roaring bonfire, "
            "raising his axe; around him warriors kneel, firelight flickering on their faces, chanting low.",
            "The warrior RISES and ROARS, thrusting his axe to the black sky; his warband erupts, "
            "pounding shields, sparks and embers whirling up into the night.",
        ],
        "saga": ("Before the blood, there is the oath. By fire and by iron, the Northmen swear: we "
                 "will not kneel, we will not break. We will see Valhalla, or we will burn."),
        "comment": "Would you take the oath?",
    },
    {
        "slug": "pyre",
        "shots": [
            "Dawn over a misty fjord. SLOW DOLLY over a burning longship drifting out to sea, a fallen "
            "warrior laid upon it wrapped in furs as flames rise; the warrior stands on the shore, "
            "grief on his face.",
            "CRANE-UP as the warrior raises his axe in salute; his warband on the shore lift their "
            "weapons; the burning ship glows against the grey dawn as ravens circle overhead.",
        ],
        "saga": ("When a great one falls, the North does not weep for long. They give him to the sea "
                 "and the fire, and send him home. Farewell, brother. We drink again in Valhalla."),
        "comment": "Rest in Valhalla.",
    },
    {
        "slug": "shieldwall",
        "shots": [
            "Grey muddy battlefield. LOW TRACKING SHOT along a Viking shield wall locking together, the "
            "warrior at the center bracing hard, as a thunderous enemy charge storms toward them.",
            "Kinetic HANDHELD SHOT as the charge SLAMS into the shield wall — a brutal crush of shields, "
            "spears and bodies, the warrior roaring and heaving forward, mud and blood flying.",
        ],
        "saga": ("Hold the wall. One shield is a man. A thousand shields is a storm. Let them come. "
                 "The North does not break."),
        "comment": "Could you hold the line?",
    },
]


def main():
    if not check_key():
        print("KIE_API_KEY not set.", flush=True)
        return
    if not HERO.exists():
        print("hero missing.", flush=True)
        return
    hero_url = upload_image(str(HERO))
    total_shots = sum(len(s["shots"]) for s in SHORTS)
    print(f"=== VIKING BATCH — {len(SHORTS)} shorts / {total_shots} shots "
          f"~${estimate_cost('veo3_lite', 8) * total_shots:.2f} ===", flush=True)

    done = []
    for sh in SHORTS:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = ROOT / "output" / f"viking_{sh['slug']}_{stamp}"
        out.mkdir(parents=True, exist_ok=True)
        print(f"\n--- {sh['slug'].upper()} ---", flush=True)
        clips = []
        for i, p in enumerate(sh["shots"]):
            c = out / f"shot_{i}.mp4"
            try:
                generate_veo(STYLE + p, str(c), model="veo3_lite", aspect="9:16", resolution="1080p",
                             duration=8, image_urls=[hero_url], generation_type="REFERENCE_2_VIDEO")
                clips.append(str(c))
            except Exception as e:
                print(f"  {sh['slug']} shot {i} FAILED: {e}", flush=True)
        if not clips:
            continue
        concat_uniform(clips, str(out / "visuals.mp4"))
        final = finish(str(out), saga=sh["saga"], comment=sh["comment"], voiceover=False)
        if final:
            done.append(str(final))
            print(f"  DONE -> {final}", flush=True)
    print(f"\n=== BATCH COMPLETE — {len(done)} shorts ===", flush=True)
    for f in done:
        print(f, flush=True)


if __name__ == "__main__":
    main()
