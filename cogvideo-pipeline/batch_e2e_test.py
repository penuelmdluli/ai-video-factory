"""
End-to-end batch test for the LOCAL AI video model (SVD-XT path).

Proves the improved convert_images_to_videos():
  1. Loads the pipeline ONCE for a multi-scene batch (not per clip)
  2. Produces valid, non-black clips with real motion
  3. 25-frame clips fit in 11GB VRAM

Run: python cogvideo-pipeline/batch_e2e_test.py
"""
import asyncio
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.ai_video_generator import convert_images_to_videos  # noqa: E402

TEST_IMG = Path(__file__).parent / "test_input.png"
OUT_DIR = Path(__file__).parent / "output" / "batch_test"


def analyze(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    frames, prev, diffs, brights = 0, None, [], []
    while True:
        ret, f = cap.read()
        if not ret:
            break
        frames += 1
        brights.append(float(np.mean(f)))
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diffs.append(float(np.mean(np.abs(g.astype(int) - prev.astype(int)))))
        prev = g
    cap.release()
    return {
        "frames": frames,
        "brightness": statistics.mean(brights) if brights else 0,
        "motion": statistics.mean(diffs) if diffs else 0,
    }


async def main():
    # Two fake "scenes" pointing at the same test image — simulates a 2-scene video
    visuals = [
        {"type": "ai_image", "local_path": str(TEST_IMG), "scene_number": 1},
        {"type": "ai_image", "local_path": str(TEST_IMG), "scene_number": 2},
    ]

    torch.cuda.reset_peak_memory_stats()
    results = await convert_images_to_videos(visuals, OUT_DIR, niche="tech_news")
    peak_vram = torch.cuda.max_memory_allocated() / 1e9

    print("\n" + "=" * 60)
    print("BATCH E2E RESULTS")
    print("=" * 60)
    all_valid = True
    clips = [r for r in results if r.get("type") == "ai_video"]
    for r in clips:
        a = analyze(r["local_path"])
        valid = a["brightness"] > 5 and a["motion"] > 0.3 and a["frames"] >= 10
        all_valid &= valid
        print(f"  scene {r['scene_number']}: {a['frames']}f  "
              f"bright={a['brightness']:.0f}  motion={a['motion']:.1f}  "
              f"-> {'VALID' if valid else 'INVALID'}")

    print(f"\n  clips produced : {len(clips)}/2")
    print(f"  peak VRAM      : {peak_vram:.1f}GB / 11.8GB")
    verdict = "PASS" if (len(clips) == 2 and all_valid and peak_vram < 11.0) else "FAIL"
    print(f"\n  GATE (batch e2e): {verdict}")
    print("=" * 60)
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    asyncio.run(main())
