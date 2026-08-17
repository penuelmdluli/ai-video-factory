"""
Owner media vault — the owner's own footage, top priority everywhere.

Photos and videos the owner sends to the WhatsApp bot land in
assets/owner_media/inbox with a caption sidecar. This module serves them to
the pipeline ABOVE every other source: their footage is fully licensed, real,
and exactly what the page should look like. Credit line: "Genesis News".

Filing: the caption ("Chiefs vs Sundowns") resolves clubs. Uncaptioned media
inherits the caption of the nearest captioned item sent in the same batch
(within 10 minutes) — a photo captioned "Pirates" followed seconds later by a
video files BOTH under Pirates. Media with no caption anywhere in its batch is
only served for club-less stories, never onto another club's news (2026-08-16:
Pirates footage landed on a Chiefs–Sundowns story this way).

Phone videos arrive VFR/120fps; MoviePy misreads those timestamps and the
clip plays fast. pick_owner_video() serves a cached constant-30fps re-encode
(timestamp-based, so real-world speed is preserved).

Usage:
    from modules.owner_media import pick_owner_video, owner_images
"""
import json
import subprocess
import time
from pathlib import Path

VAULT = Path(__file__).parent.parent / "assets" / "owner_media"
INBOX = VAULT / "inbox"
NORM = VAULT / "normalized"
USAGE = VAULT / "usage.json"
BATCH_MS = 10 * 60 * 1000        # caption inheritance window


def _meta(p: Path) -> dict:
    try:
        return json.loads((p.parent / (p.name + ".json")).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _caption(p: Path) -> str:
    """Own caption, else the nearest captioned sibling from the same send."""
    m = _meta(p)
    cap = (m.get("caption") or "").strip()
    if cap:
        return cap
    ts = m.get("ts") or int(p.stat().st_mtime * 1000)
    best, best_gap = "", BATCH_MS + 1
    for sc in INBOX.glob("*.json"):
        sm = _meta(INBOX / sc.stem)      # sc.stem strips ".json" -> media name
        sib_cap = (sm.get("caption") or "").strip()
        if not sib_cap or sm.get("from") != m.get("from"):
            continue
        gap = abs((sm.get("ts") or 0) - ts)
        if gap <= BATCH_MS and gap < best_gap:
            best, best_gap = sib_cap, gap
    return best


def _clubs_for(p: Path) -> list[str]:
    try:
        from modules.club_brand import resolve_clubs
        return resolve_clubs(_caption(p))
    except Exception:
        return []


def _matches(p: Path, club) -> bool:
    """club: None, a key, or a list of keys the story is about.

    Captioned (or batch-captioned) media must intersect the story's clubs.
    Media with no resolvable club is ONLY served when the story itself has
    no specific club — real footage of the wrong team is worse than stock.
    """
    wanted = {c for c in ([club] if isinstance(club, str) or club is None else club)
              if c and c != "generic"}
    clubs = _clubs_for(p)
    if not wanted:
        return True
    if not clubs:
        return False                     # unfiled media never rides club news
    return bool(set(clubs) & wanted)


def _playback_path(p: Path) -> str:
    """Constant-30fps re-encode for MoviePy (cached; falls back to original)."""
    out = NORM / p.name
    if out.exists() and out.stat().st_size > 10_000:
        return str(out)
    NORM.mkdir(parents=True, exist_ok=True)
    # clean the WhatsApp crush on the way through: deblock -> denoise ->
    # 2x lanczos upscale -> sharpen (then constant 30fps for real speed)
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(p),
         "-vf", ("deblock=filter=strong:block=8,hqdn3d=2:1:4:3,"
                 "scale=iw*2:ih*2:flags=lanczos,unsharp=5:5:0.5,cas=0.4,fps=30"),
         "-c:v", "libx264", "-preset", "fast", "-crf", "19",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)],
        capture_output=True)
    if r.returncode == 0 and out.exists() and out.stat().st_size > 10_000:
        return str(out)
    return str(p)


def owner_videos(club=None) -> list[dict]:
    """Newest-first owner videos (club: key, list of keys, or None)."""
    if not INBOX.exists():
        return []
    out = []
    for p in sorted(INBOX.glob("*.mp4"), key=lambda x: x.stat().st_mtime,
                    reverse=True):
        if _matches(p, club):
            out.append({"path": str(p), "caption": _caption(p),
                        "credit": "Genesis News footage", "channel": "Genesis News",
                        "title": _caption(p) or p.stem,
                        "owner": True})
    return out


def owner_images(club=None, limit: int = 2) -> list[dict]:
    """Owner photos as gather_images-shaped dicts, LEAST-RECENTLY-USED first —
    the same photo must not front every card and thumbnail (owner rule
    2026-08-17: 'always rotate the image used, even on the thumbnail')."""
    if not INBOX.exists():
        return []
    try:
        usage = json.loads(USAGE.read_text(encoding="utf-8"))
    except Exception:
        usage = {}
    out = []
    for p in sorted(INBOX.glob("*.jpg"),
                    key=lambda x: (usage.get(x.name, 0), -x.stat().st_mtime)):
        if _matches(p, club):
            # "club" must be a single key (cards hash it) — prefer the media's
            # own filing, else the first story club
            own = _clubs_for(p)
            wanted = [club] if isinstance(club, str) else list(club or [])
            key = own[0] if own else (wanted[0] if wanted else "")
            out.append({"path": str(p), "credit": "Genesis News",
                        "archive_year": "", "club": key or "", "real": True,
                        "owner": True})
        if len(out) >= limit:
            break
    if out:                               # stamp usage so the next build rotates
        for i in out:
            usage[Path(i["path"]).name] = time.time()
        USAGE.parent.mkdir(parents=True, exist_ok=True)
        USAGE.write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return out


def pick_owner_video(club=None) -> dict | None:
    """Least-recently-used owner video for the live window (rotation).

    Serves the constant-fps re-encode so playback speed is real.
    """
    vids = owner_videos(club)
    if not vids:
        return None
    try:
        usage = json.loads(USAGE.read_text(encoding="utf-8"))
    except Exception:
        usage = {}
    vids.sort(key=lambda v: usage.get(Path(v["path"]).name, 0))
    chosen = vids[0]
    usage[Path(chosen["path"]).name] = time.time()
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(usage, indent=2), encoding="utf-8")
    chosen["path"] = _playback_path(Path(chosen["path"]))
    return chosen
