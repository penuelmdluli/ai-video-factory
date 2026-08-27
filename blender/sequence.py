"""
One mocap take -> a multi-shot edit. Angles, speeds and behaviour per shot.

A single Mixamo clip is one performance from one angle, and cutting it
straight to camera gives you exactly one 4-second beat. But a performance is
not a shot: the same 137 frames seen wide, then close, then from the other
side, at different speeds, with the head holding eye contact in one and not
the next, is a SEQUENCE. That is the difference between owning one clip and
owning a scene.

Each shot is a dict, so an episode is a list and the renderer is a loop:

    {"shot": "wide", "trim": "10:60", "speed": 1.0}
    {"shot": "close", "trim": "58:96", "speed": 0.55, "look": 0.8}

Blender renders each shot to its own file and ffmpeg concatenates - which is
the fast path already benchmarked at 209x MoviePy for exactly this join.

    python blender/sequence.py --fbx X.fbx --out output/scene
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe")

# The default cut. Wide to establish, close for the reaction, a slowed
# reverse for the beat that lands - which is how any editor would cut a
# stumble, and none of it needs a second mocap file.
DEFAULT_SHOTS = [
    {"shot": "wide",   "trim": "1:44",   "speed": 1.0,  "look": 0.0, "lean": 0},
    {"shot": "close",  "trim": "45:78",  "speed": 0.6,  "look": 0.85, "lean": 0},
    {"shot": "medium", "trim": "79:120", "speed": 1.0,  "look": 0.0, "lean": 6,
     "mirror": True},
    {"shot": "close",  "trim": "108:137", "speed": 0.45, "look": 1.0, "lean": 0},
]


def render_shot(fbx, out_stem, spec):
    cmd = [str(BLENDER), "--background", "--python",
           str(ROOT / "blender" / "motion_control.py"), "--",
           "--fbx", fbx, "--out", str(out_stem),
           "--shot", spec.get("shot", "medium"),
           "--speed", str(spec.get("speed", 1.0))]
    if spec.get("trim"):
        cmd += ["--trim", spec["trim"]]
    if spec.get("look"):
        cmd += ["--look", str(spec["look"])]
    if spec.get("lean"):
        cmd += ["--lean", str(spec["lean"])]
    if spec.get("mirror"):
        cmd += ["--mirror"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    if r.returncode != 0:
        print("  FAILED: " + (r.stderr or "")[-300:])
        return None
    hits = sorted(Path(out_stem).parent.glob(Path(out_stem).name + "*.mp4"))
    return str(hits[-1]) if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbx", required=True)
    ap.add_argument("--out", default="output/sequence")
    ap.add_argument("--shots", default="")
    a = ap.parse_args()

    shots = json.loads(Path(a.shots).read_text()) if a.shots else DEFAULT_SHOTS
    work = ROOT / a.out
    work.mkdir(parents=True, exist_ok=True)

    parts = []
    for i, spec in enumerate(shots):
        print(f"[Seq] shot {i+1}/{len(shots)}: {spec}")
        p = render_shot(a.fbx, work / f"shot{i:02d}", spec)
        if p:
            parts.append(p)
            print("  -> " + Path(p).name)

    if not parts:
        print("[Seq] nothing rendered")
        return 1

    from modules.ffmpeg_ops import concat
    sys.path.insert(0, str(ROOT))
    out = work / "sequence.mp4"
    joined = concat(parts, out)
    print("[Seq] " + str(len(parts)) + " shots -> " + str(joined))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
