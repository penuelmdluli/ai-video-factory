"""Proves two overlapping builds cannot fight over one temp audio file.

Incident 2026-09-02 21:54 - the role slot exited 1 and posted nothing, dying
in MoviePy's cleanup after the video was already encoded:

    File ".../moviepy/video/VideoClip.py", line 411, in write_videofile
        os.remove(audiofile)
    PermissionError: [WinError 32] The process cannot access the file because
    it is being used by another process: 'finalTEMP_MPY_wvf_snd.mp4'

modules/safe_render.py explains the cause and carries the fix. This is the
proof, and it is a real one: --race actually renders two clips concurrently,
a long one and a short one, so the short build finishes while the long build
still holds the temp audio open. That is the exact shape of the failure, and
before the fix it reproduced it every time.

    python check_render_safety.py            # patch + scoping + coverage
    python check_render_safety.py --race     # the above, plus the live race
    python check_render_safety.py --audit    # also list every covered call
"""
import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Vendored trees and virtualenvs - not ours to fix. Matched as whole path
# PARTS, never as substrings: the first cut of this list held "build", which
# is a substring of every build_*.py in the repo root, so the audit skipped
# the twenty-two builders it was written to find and called them clean.
#
# echomimic-presenter-worker is a RunPod container: it ships without this
# repo's modules/, and one job runs per container, so there is nothing for it
# to collide with. It is skipped deliberately, not overlooked.
SKIP = {"site-packages", "node_modules", ".git", "venv", ".venv", "output",
        "zuzu_engine", "acestep_venv", "cogvideo-pipeline", "dist",
        "__pycache__", "echomimic-presenter-worker"}


def check_patch():
    """The patch is installed by importing modules, and only once."""
    import modules  # noqa: F401  - installs on import
    from moviepy.video.VideoClip import VideoClip
    from modules.safe_render import _MARK, install

    live = getattr(VideoClip.write_videofile, _MARK, False)
    print("  patch installed by 'import modules': " + str(bool(live)))
    print("  install() is idempotent: " + str(install() is False))
    return bool(live)


def check_paths():
    """Two different builds must no longer name the same temp file."""
    from modules.safe_render import temp_audio_path_for

    builds = ["output/role_chiefs_A/final.mp4",
              "output/lineup_chiefs_B/final.mp4"]
    paths = [temp_audio_path_for(b) for b in builds]
    for b, p in zip(builds, paths):
        print("  " + b + "\n     -> " + p)
    ok = len(set(paths)) == len(builds)
    print("  distinct temp paths for " + str(len(builds)) + " builds: "
          + str(len(set(paths))))
    return ok


_RACE_CHILD = """
import sys
from pathlib import Path
sys.path.insert(0, r"{root}")
import modules  # noqa: F401  - installs the temp-audio scoping
import numpy as np
from moviepy import ColorClip, AudioArrayClip

tag, dur = sys.argv[1], float(sys.argv[2])
work = Path(r"{root}") / "output" / ("_render_safety_" + tag)
work.mkdir(parents=True, exist_ok=True)
v = ColorClip((1080, 1920), color=(20, 20, 20), duration=dur)
t = np.linspace(0, dur, int(44100 * dur))
wave = np.sin(2 * np.pi * 220 * t) * 0.2
v = v.with_audio(AudioArrayClip(np.c_[wave, wave], fps=44100))
v.write_videofile(str(work / "final.mp4"), fps=24, codec="libx264",
                  audio_codec="aac", logger=None, preset="medium", threads=4)
print(tag + ": OK")
"""


def check_race():
    """Render two builds at once, as the slot runner and scheduler do.

    Long and short on purpose: the short one finishes while the long one is
    still encoding, which is when the deletion used to land.
    """
    script = ROOT / "_render_safety_child.py"
    script.write_text(_RACE_CHILD.format(root=str(ROOT)), encoding="utf-8")
    # Only NEW strays count. Two 2026-04 orphans have sat in the repo root
    # since a killed build, and counting them would fail a passing run.
    before = set(Path(ROOT).glob("*TEMP_MPY_wvf_snd.*"))
    try:
        procs = [(tag, subprocess.Popen(
            [sys.executable, str(script), tag, dur], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
            for tag, dur in (("long", "70"), ("short", "5"))]
        ok = True
        for tag, p in procs:
            out = p.communicate()[0]
            good = p.returncode == 0
            ok = ok and good
            print("  " + tag + " build exit " + str(p.returncode)
                  + ("" if good else " <-- FAILED"))
            if not good:
                for ln in [x for x in out.splitlines() if x.strip()][-4:]:
                    print("      " + ln)
        stray = sorted(set(Path(ROOT).glob("*TEMP_MPY_wvf_snd.*")) - before)
        print("  NEW temp audio in repo root: " + str(len(stray))
              + " (pre-existing orphans: " + str(len(before)) + ")")
        for s in stray:
            print("      ! " + s.name)
        return ok and not stray
    finally:
        script.unlink(missing_ok=True)


def _modules_import_lines(tree):
    """Line numbers where this file first pulls in modules.* (any form)."""
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(n.name == "modules" or n.name.startswith("modules.")
                   for n in node.names):
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "modules" or mod.startswith("modules."):
                lines.append(node.lineno)
    return lines


def coverage(verbose=False):
    """Every render must scope its temp audio, one way or the other.

    A call is safe if it either names a temp path itself, or sits in a file
    that has already imported modules.* - which installs the patch. Anything
    else renders with MoviePy's default and can collide in the repo root,
    which is the 2026-09-02 failure. This is the check that catches the next
    builder somebody adds.
    """
    relies, unsafe, explicit = [], [], []
    for p in sorted(ROOT.rglob("*.py")):
        if SKIP.intersection(p.parts):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        # Anything inside modules/ is covered by construction: importing it
        # at all runs modules/__init__.py.
        in_package = "modules" in p.parts
        imports = _modules_import_lines(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "write_videofile"):
                continue
            where = (str(p.relative_to(ROOT)), node.lineno)
            if any(k.arg is None for k in node.keywords):
                continue  # **kwargs forwarding - the caller decides
            if any(k.arg in ("temp_audiofile", "temp_audiofile_path")
                   for k in node.keywords):
                explicit.append(where)
            elif in_package or any(ln < node.lineno for ln in imports):
                relies.append(where)
            else:
                unsafe.append(where)

    print("  " + str(len(explicit)) + " call(s) name a temp path themselves")
    print("  " + str(len(relies)) + " call(s) covered by the patch")
    if verbose:
        for rel, line in relies:
            print("      " + rel + ":" + str(line))
    print("  " + str(len(unsafe)) + " call(s) UNCOVERED")
    for rel, line in unsafe:
        print("      ! " + rel + ":" + str(line)
              + "  - imports no modules.*; pass temp_audiofile_path")
    return not unsafe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--race", action="store_true",
                    help="also run two real renders concurrently (~2 min)")
    ap.add_argument("--audit", action="store_true",
                    help="also list every call the patch covers")
    a = ap.parse_args()

    print("[RenderSafety] patch")
    results = [check_patch()]
    print("[RenderSafety] temp audio path per build")
    results.append(check_paths())
    print("[RenderSafety] coverage")
    results.append(coverage(verbose=a.audit))
    if a.race:
        print("[RenderSafety] live race - two builds at once")
        results.append(check_race())

    ok = all(results)
    print("[RenderSafety] " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
