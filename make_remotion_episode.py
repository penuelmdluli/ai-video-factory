#!/usr/bin/env python
"""Bridge: turn a Zuzu lesson (dict) into an animated MP4 via the Remotion project.

This is the programmatic spine for the kids channel — feed a lesson (scenes,
counting, karaoke lyrics, optional character clip + song) and it renders an
episode. Character clips can come from your RunPod wan-animate / i2v step and
the song from ACE-Step; drop them in via `assets`.

Usage:
  python make_remotion_episode.py                 # render the built-in demo lesson
  python make_remotion_episode.py lesson.json out.mp4
As a lib:
  from make_remotion_episode import render_episode
  render_episode(lesson_dict, "output/zuzu/ep1.mp4", assets={"audio":"song.mp3","clip":"zuzu.mp4"})
"""
import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / "remotion-zuzu"
PUBLIC = PROJ / "public"
INPUT = PROJ / "input"


def _ensure_installed():
    if not (PROJ / "node_modules").exists():
        print("[remotion] installing deps (first run, ~1-2 min)…")
        subprocess.run(["npm", "install"], cwd=str(PROJ), check=True, shell=(sys.platform == "win32"))


def render_episode(lesson: dict, out_path: str, assets: dict | None = None) -> str | None:
    """lesson: the JSON described in remotion-zuzu/src/schema.ts.
    assets: {"audio": <path>, and any character clip paths} — copied into public/
    and referenced by basename so Remotion's staticFile() finds them."""
    lesson = json.loads(json.dumps(lesson))  # shallow copy
    PUBLIC.mkdir(parents=True, exist_ok=True); INPUT.mkdir(parents=True, exist_ok=True)

    # stage audio
    if assets and assets.get("audio"):
        src = Path(assets["audio"])
        if src.exists():
            shutil.copy(src, PUBLIC / src.name); lesson["audio"] = src.name
    # stage the Zuzu character image (shown/animated across scenes)
    if lesson.get("characterImg"):
        src = Path(lesson["characterImg"])
        if src.exists():
            shutil.copy(src, PUBLIC / src.name); lesson["characterImg"] = src.name
    # stage rotating pose images (title / character / outro use different stills)
    if lesson.get("characterImgs"):
        staged = []
        for p in lesson["characterImgs"]:
            src = Path(p)
            if src.exists():
                shutil.copy(src, PUBLIC / src.name); staged.append(src.name)
            else:
                staged.append(p)
        lesson["characterImgs"] = staged
    # stage character clips referenced by scenes (copy + rewrite to basename)
    for sc in lesson.get("scenes", []):
        if sc.get("type") == "character" and sc.get("clip"):
            src = Path(sc["clip"])
            if src.exists():
                shutil.copy(src, PUBLIC / src.name); sc["clip"] = src.name

    lesson_file = INPUT / "lesson.json"
    lesson_file.write_text(json.dumps(lesson, indent=2), encoding="utf-8")

    try:
        _ensure_installed()
        out = Path(out_path).resolve()
        # NOTE: on Windows, headless Chromium can throw a late "Target closed" AFTER the
        # mp4 is fully written. So don't trust the exit code — trust the output file.
        subprocess.run(["node", "render.mjs", str(lesson_file), str(out)],
                       cwd=str(PROJ), check=False, shell=(sys.platform == "win32"))
        ok = out.exists() and out.stat().st_size > 100_000
        if not ok:
            print("[remotion] render produced no valid output")
        return str(out) if ok else None
    except Exception as e:
        print(f"[remotion] render failed: {e}")
        return None


def _demo_lesson() -> dict:
    return json.loads((INPUT / "lesson.example.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        lesson = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = sys.argv[2] if len(sys.argv) > 2 else "output/zuzu_remotion/episode.mp4"
    else:
        lesson = _demo_lesson()
        out = "output/zuzu_remotion/demo.mp4"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    print("RESULT:", render_episode(lesson, out))
