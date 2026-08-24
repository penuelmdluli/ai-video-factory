"""
Club media library — real, properly-licensed photos of a club's people.

Owner call 2026-08-24: post more about Chiefs PLAYERS, the coach and the fans,
and use those faces for goal and line-up analysis. That needs a standing
library rather than a scramble at build time, because the good photo is rarely
there the moment a goal goes in.

Everything here goes through modules.free_press_images, so the licence rules
are not re-implemented: Wikimedia Commons only, CC-BY / CC-BY-SA / public
domain only, non-commercial and no-derivatives and fair-use rejected outright.
Every file is stored with the author and licence that came with it, and the
manifest is the only permitted source of a credit line. A photo whose credit
we cannot reproduce is not saved.

    python -m modules.club_media chiefs           # harvest / refresh
    python -m modules.club_media chiefs --report  # what we hold

    from modules.club_media import photo_for
    hit = photo_for("chiefs", "Ranga Chivaviro")  # -> {path, credit, ...}
"""
import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEDIA = ROOT / "assets" / "club_media"
SQUADS = ROOT / "data" / "psl_squads_cache.json"

# Non-player subjects worth holding: the coach is named per club, the rest are
# crowd and stadium texture for cards that have no single face to show.
CLUB_EXTRAS = {
    "chiefs": {
        "coach": ["Fernando Da Cruz"],
        "scenes": ["Kaizer Chiefs supporters", "Kaizer Chiefs fans",
                   "FNB Stadium crowd", "Kaizer Chiefs match"],
    },
    "pirates": {
        "coach": ["Nasreddine Ouaddou"],
        "scenes": ["Orlando Pirates supporters", "Orlando Stadium crowd"],
    },
    "sundowns": {
        "coach": ["Miguel Cardoso"],
        "scenes": ["Mamelodi Sundowns supporters", "Loftus Versfeld crowd"],
    },
}


def _slug(s):
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")


def manifest_path(club):
    return MEDIA / club / "manifest.json"


def load_manifest(club):
    try:
        return json.loads(manifest_path(club).read_text(encoding="utf-8"))
    except Exception:
        return {"club": club, "updated": "", "people": {}, "scenes": {}}


def _save_manifest(club, man):
    p = manifest_path(club)
    p.parent.mkdir(parents=True, exist_ok=True)
    man["updated"] = datetime.now().isoformat()
    p.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")


def squad_for(club):
    try:
        d = json.loads(SQUADS.read_text(encoding="utf-8"))
        s = (d.get(club) or {}).get("squad") or []
        return [p if isinstance(p, str) else p.get("name", "") for p in s]
    except Exception:
        return []


async def _grab(hits, out_dir, key, download):
    """Download the usable hits, keeping the credit that came with each."""
    shots = []
    for i, h in enumerate(hits):
        # No credit, no file — we cannot honour the licence without it.
        if not h.get("credit"):
            continue
        dest = out_dir / f"{key}_{i}.jpg"
        try:
            got = await download(h, dest)
        except Exception:
            got = None
        if got:
            shots.append({
                "path": str(Path(got).relative_to(ROOT)),
                "credit": h.get("credit", ""),
                "license": h.get("license", ""),
                "author": h.get("author", ""),
                "title": h.get("title", ""),
            })
    return shots


async def harvest(club="chiefs", per_person=2, refresh=False):
    """Fetch and cache licensed photos for the squad, the coach and scenes."""
    from modules.free_press_images import (photos_for_player, search_free_photos,
                                           download)

    man = load_manifest(club)
    people = man.setdefault("people", {})
    scenes = man.setdefault("scenes", {})
    extras = CLUB_EXTRAS.get(club, {})
    names = squad_for(club) + extras.get("coach", [])
    out_dir = MEDIA / club
    (out_dir / "people").mkdir(parents=True, exist_ok=True)
    (out_dir / "scenes").mkdir(parents=True, exist_ok=True)

    added = 0
    for name in names:
        if not name:
            continue
        key = _slug(name)
        if people.get(key, {}).get("shots") and not refresh:
            continue
        try:
            hits = await photos_for_player(name, limit=per_person)
        except Exception as e:
            print(f"[ClubMedia] {name}: lookup failed ({str(e)[:50]})")
            continue
        shots = await _grab(hits, out_dir / "people", key, download)
        if shots:
            people[key] = {"name": name, "shots": shots}
            added += len(shots)
            print(f"[ClubMedia] {name}: {len(shots)} licensed photo(s)")
        else:
            people.setdefault(key, {"name": name, "shots": []})

    for q in extras.get("scenes", []):
        key = _slug(q)
        if scenes.get(key, {}).get("shots") and not refresh:
            continue
        try:
            hits = await search_free_photos(q, limit=3)
        except Exception:
            hits = []
        shots = await _grab(hits, out_dir / "scenes", key, download)
        if shots:
            scenes[key] = {"query": q, "shots": shots}
            added += len(shots)
            print(f"[ClubMedia] scene '{q}': {len(shots)} licensed photo(s)")

    _save_manifest(club, man)
    print(f"[ClubMedia] {club}: +{added} new files")
    return man


def photo_for(club, name):
    """A licensed photo of this person, or None. Never invent a face."""
    man = load_manifest(club)
    rec = man.get("people", {}).get(_slug(name))
    if not rec or not rec.get("shots"):
        return None
    shot = rec["shots"][0]
    p = ROOT / shot["path"]
    if not p.exists():
        return None
    return dict(shot, path=str(p), name=rec["name"])


def scene_photo(club):
    """Crowd / stadium texture when there is no single face to show."""
    man = load_manifest(club)
    pool = [s for rec in man.get("scenes", {}).values() for s in rec.get("shots", [])]
    pool = [s for s in pool if (ROOT / s["path"]).exists()]
    if not pool:
        return None
    s = random.choice(pool)
    return dict(s, path=str(ROOT / s["path"]))


def have_photo(club, name):
    return photo_for(club, name) is not None


def report(club):
    man = load_manifest(club)
    people = man.get("people", {})
    have = {k: v for k, v in people.items() if v.get("shots")}
    n_scene = sum(len(r.get("shots", [])) for r in man.get("scenes", {}).values())
    print(f"[ClubMedia] {club} — updated {man.get('updated', 'never')[:19]}")
    print(f"  people with photos : {len(have)} / {len(people)}")
    print(f"  scene photos       : {n_scene}")
    for v in list(have.values())[:12]:
        lic = (v["shots"][0].get("license") or "")[:30]
        print(f"    {v['name']:<26} {len(v['shots'])} shot(s)  [{lic}]")
    missing = [v["name"] for v in people.values() if not v.get("shots")]
    if missing:
        tail = " ..." if len(missing) > 6 else ""
        print(f"  no free photo found: {len(missing)} — {', '.join(missing[:6])}{tail}")


if __name__ == "__main__":
    club = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "chiefs"
    if "--report" in sys.argv:
        report(club)
    else:
        asyncio.run(harvest(club, refresh="--refresh" in sys.argv))
        report(club)
