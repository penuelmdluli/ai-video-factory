"""
Bridge from the Python pipeline to Genesis Studio (Remotion).

Python stays the source of truth for data and for the verification gate.
This module only hands a JSON payload to the Node renderer and gets a PNG or
MP4 back. If Node is missing, the bundle fails, or the render times out, the
caller falls back to the PIL templates — a graphics upgrade must never be
able to stop a post going out.

    from modules.studio import render_still, available
    png = render_still("JobCard", props, "output/card.png")
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

STUDIO = Path(__file__).parent.parent / "genesis-studio"
PUBLIC = STUDIO / "public"
TIMEOUT = 240          # a still should take ~20s; this is the give-up line


def available() -> bool:
    """True when the studio can actually render."""
    return (STUDIO / "node_modules").is_dir() and bool(
        shutil.which("node") or shutil.which("node.exe"))


def stage_asset(path) -> str | None:
    """Copy a local image into the studio's public folder; return its name."""
    p = Path(path)
    if not p.exists():
        return None
    PUBLIC.mkdir(parents=True, exist_ok=True)
    name = f"asset_{abs(hash(str(p.resolve()))) % 10**10}{p.suffix.lower()}"
    dest = PUBLIC / name
    if not dest.exists() or dest.stat().st_mtime < p.stat().st_mtime:
        shutil.copy(p, dest)
    return name


def _run(script: str, props: dict, out_path, comp_id: str):
    if not available():
        print("[Studio] not available — falling back")
        return None
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(props, fh)
        props_path = fh.name
    try:
        r = subprocess.run(
            ["node", script, props_path, str(out), comp_id],
            cwd=str(STUDIO), capture_output=True, text=True, timeout=TIMEOUT)
        if r.returncode != 0 or not out.exists():
            print(f"[Studio] {comp_id} failed: "
                  f"{(r.stderr or r.stdout or '')[-300:]}")
            return None
        return str(out)
    except subprocess.TimeoutExpired:
        print(f"[Studio] {comp_id} timed out after {TIMEOUT}s")
        return None
    except Exception as e:
        print(f"[Studio] {comp_id} error: {e}")
        return None
    finally:
        try:
            os.unlink(props_path)
        except OSError:
            pass


def render_still(comp_id: str, props: dict, out_path):
    """Render a still (card, thumbnail). Returns path, or None to fall back."""
    return _run("render_still.mjs", props, out_path, comp_id)


def render_video(comp_id: str, props: dict, out_path):
    """Render a motion composition. Returns path, or None to fall back."""
    return _run("render.mjs", props, out_path, comp_id)
