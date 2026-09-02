"""The owner's own tracks, rotating — the only music our videos use.

Owner 2026-09-02: "here is my sound music, please remove all the vuvuzela sound
and all you have used and only use [file]"... then "here is another one. From
now on all our videos should use this music, both, change it around always."

So this is a LIBRARY, not a setting. Drop an audio file in assets/owner_audio/
and it joins the rotation; nothing else needs editing. Tracks are chosen
least-recently-used first, the same rule that already governs the formations,
the eleven, the fan prompts and the cabinet seats - a page that repeats itself
is the one complaint that has come back more than any other today.

WHEN A TRACK IS PLAYING, EVERY GENERATED SOUND IS OFF. Not ducked - off. The
owner asked for his music and named the vuvuzelas specifically; a kick sample
landing over a song he chose is the opposite of what he asked for.

He supplied both files himself and confirmed them as his. Worth recording
plainly, because the filenames are Facebook CDN downloads (AQO.../AQP...) and
the licence that covers music inside Facebook's own editor does not cover audio
re-uploaded through the API. I raised that before he sent them; he sent them
anyway, which is his call on his pages. If a post is ever muted or pulled, this
is the first thing to look at.

    from modules.owner_music import next_track, record_used
    path = next_track()          # least-recently-used
    ...
    record_used(path)            # after a confirmed post
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MUSIC_DIR = ROOT / "assets" / "owner_audio"
STATE = ROOT / "data" / "owner_music.json"
EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".mp4"}


def tracks() -> list[Path]:
    """Every track in the library, sorted so the order is stable."""
    if not MUSIC_DIR.exists():
        return []
    return sorted(p for p in MUSIC_DIR.iterdir()
                  if p.suffix.lower() in EXTS and p.stat().st_size > 1024)


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"used": []}


def _save(d: dict):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Music] state write failed (non-critical): {e}")


def next_track() -> str:
    """The least-used track, or "" if the library is empty."""
    lib = tracks()
    if not lib:
        return ""
    used = _load().get("used", [])
    counts = {p.name: used.count(p.name) for p in lib}
    pick = min(lib, key=lambda p: (counts[p.name], p.name))
    return str(pick)


def record_used(path: str) -> bool:
    """Log a track that actually went out, so the next build picks another."""
    name = Path(path).name
    if not name:
        return False
    d = _load()
    d["used"] = (d.get("used", []) + [name])[-60:]
    d["last"] = datetime.now().isoformat(timespec="seconds")
    _save(d)
    print(f"[Music] used {name}")
    return True


if __name__ == "__main__":
    lib = tracks()
    print(f"{len(lib)} track(s) in {MUSIC_DIR}:")
    used = _load().get("used", [])
    for p in lib:
        print(f"  {used.count(p.name):>3} plays  {p.name}")
    print("next:", Path(next_track()).name if next_track() else "(none)")
