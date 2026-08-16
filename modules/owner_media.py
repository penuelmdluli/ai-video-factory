"""
Owner media vault — the owner's own footage, top priority everywhere.

Photos and videos the owner sends to the WhatsApp bot land in
assets/owner_media/inbox with a caption sidecar. This module serves them to
the pipeline ABOVE every other source: their footage is fully licensed, real,
and exactly what the page should look like. Credit line: "Genesis News".

Filing: the caption ("Chiefs vs Sundowns") resolves clubs; uncaptioned media
is served for any club (better real than blurry).

Usage:
    from modules.owner_media import pick_owner_video, owner_images, mark_used
"""
import json
import time
from pathlib import Path

VAULT = Path(__file__).parent.parent / "assets" / "owner_media"
INBOX = VAULT / "inbox"
USAGE = VAULT / "usage.json"


def _meta(p: Path) -> dict:
    try:
        return json.loads((p.parent / (p.name + ".json")).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _clubs_for(p: Path) -> list[str]:
    cap = _meta(p).get("caption", "")
    try:
        from modules.club_brand import resolve_clubs
        return resolve_clubs(cap)
    except Exception:
        return []


def _matches(p: Path, club: str | None) -> bool:
    if not club:
        return True
    clubs = _clubs_for(p)
    return (not clubs) or (club in clubs)     # uncaptioned = usable anywhere


def owner_videos(club: str | None = None) -> list[dict]:
    """Newest-first owner videos (optionally club-filtered via caption)."""
    if not INBOX.exists():
        return []
    out = []
    for p in sorted(INBOX.glob("*.mp4"), key=lambda x: x.stat().st_mtime,
                    reverse=True):
        if _matches(p, club):
            out.append({"path": str(p), "caption": _meta(p).get("caption", ""),
                        "credit": "Genesis News footage", "channel": "Genesis News",
                        "title": _meta(p).get("caption") or p.stem,
                        "owner": True})
    return out


def owner_images(club: str | None = None, limit: int = 2) -> list[dict]:
    """Newest-first owner photos as gather_images-shaped dicts."""
    if not INBOX.exists():
        return []
    out = []
    for p in sorted(INBOX.glob("*.jpg"), key=lambda x: x.stat().st_mtime,
                    reverse=True):
        if _matches(p, club):
            out.append({"path": str(p), "credit": "Genesis News",
                        "archive_year": "", "club": club or "", "real": True,
                        "owner": True})
        if len(out) >= limit:
            break
    return out


def pick_owner_video(club: str | None = None) -> dict | None:
    """Least-recently-used owner video for the live window (rotation)."""
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
    return chosen
