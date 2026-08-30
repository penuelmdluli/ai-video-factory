"""Reusable local MUSIC library — generate a few dramatic beds once, then REUSE
them across reels (rotating) instead of paying MusicGen every run.

Foley is NOT cached here: it's generated per-shot to match each specific clip,
so it can't be reused. Booms/whooshes are free local synth in assemble_full.
"""
import base64
import random
import time
from pathlib import Path

import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
LIB = ROOT / "assets" / "reel_music"
LIB.mkdir(parents=True, exist_ok=True)
EP_MUSIC = "https://api.runpod.ai/v2/b13hwup9d6179v"
TARGET_LIBRARY = 6   # grow up to this many beds, then always reuse

_KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        _KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"}

PROMPTS = [
    "epic tense afro-cinematic news underscore, deep drums, ominous strings, subtle african percussion, building, 92bpm",
    "dark dramatic breaking-news bed, pulsing sub bass, tense strings, ticking urgency, 100bpm",
    "cinematic geopolitical tension, low brass swells, driving percussion, ominous, 88bpm",
    "high-stakes documentary underscore, deep taiko drums, eerie synth pad, rising tension, 95bpm",
    "gritty conflict news bed, distorted low drone, martial snare, urgent, 105bpm",
    "sweeping orchestral tension, staccato strings, war drums, dramatic build, 90bpm",
]


def _generate_bed(prompt, name):
    r = requests.post(f"{EP_MUSIC}/run", headers=H, json={"input": {"prompt": prompt, "duration": 29}}, timeout=90)
    job = r.json().get("id")
    if not job:
        return None
    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(12)
        s = requests.get(f"{EP_MUSIC}/status/{job}", headers=H, timeout=30).json()
        if s.get("status") == "COMPLETED" and (s.get("output") or {}).get("audio_base64"):
            f = LIB / f"{name}.wav"
            f.write_bytes(base64.b64decode(s["output"]["audio_base64"]))
            return f
        if s.get("status") in ("FAILED", "TIMED_OUT", "CANCELLED"):
            return None
    return None


def get_music_bed():
    """Return a music bed path — REUSE a cached one when possible, only generate
    (and cache) to grow the library toward TARGET_LIBRARY."""
    beds = sorted(LIB.glob("*.wav"))
    # reuse if the library is full, or most of the time once we have a few
    if beds and (len(beds) >= TARGET_LIBRARY or random.random() > 0.30):
        pick = random.choice(beds)
        print(f"[MusicLib] REUSE {pick.name} ({len(beds)} in library) — $0 saved", flush=True)
        return pick
    # grow the library with a new bed
    used = {b.stem for b in beds}
    idx = len(beds) % len(PROMPTS)
    name = f"bed_{idx:02d}"
    if name in used:
        name = f"bed_{len(beds):02d}"
    print(f"[MusicLib] generating new bed {name} (library growing to {len(beds)+1})", flush=True)
    f = _generate_bed(PROMPTS[idx], name)
    if f:
        return f
    return random.choice(beds) if beds else None


def populate(n=4):
    for i in range(n):
        beds = sorted(LIB.glob("*.wav"))
        if len(beds) >= n:
            break
        name = f"bed_{len(beds):02d}"
        print(f"populate: {name}", flush=True)
        _generate_bed(PROMPTS[len(beds) % len(PROMPTS)], name)
    print(f"library now: {[b.name for b in sorted(LIB.glob('*.wav'))]}", flush=True)


if __name__ == "__main__":
    # SPEND GATE - see modules/runpod_guard.py. The credit belongs to the
    # 85K profile's dancing pipeline until the owner widens it.
    from modules.runpod_guard import is_allowed
    if not is_allowed():
        print("[MusicLibrary] stood down - RunPod credit is reserved for "
              "the profile dancing pipeline (set RUNPOD_PURPOSE=dance)")
        raise SystemExit(0)
    populate(4)
