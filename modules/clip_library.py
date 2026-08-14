"""
Local clip library — recent, licensed, REAL match footage, always on disk.

A daily sweep pulls the newest CC-BY YouTube videos for every PSL club (the
fan-shot kind that clears modules/cc_clips' licence + ownership filters),
trims to short segments and stores them under assets/clip_library/<club>/ with
credit metadata. Builders then grab footage instantly — no network fetch at
render time — for highlight reels, analysis videos and the live-video window
on news cards.

Facebook is deliberately NOT a source: FB video carries no licence signal, so
every download would be unlicensed third-party property. YouTube CC-BY is the
legal version of the same footage.

Usage:
    python modules/clip_library.py --sweep      # refresh the library (scheduled daily)
    from modules.clip_library import get_clips
    clips = get_clips("chiefs", limit=2)   # newest first, with credits
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

LIB = Path(__file__).parent.parent / "assets" / "clip_library"
MAX_PER_CLUB = 4
MAX_AGE_DAYS = 30


def _meta_path(club: str) -> Path:
    return LIB / club / "meta.json"


def _load_meta(club: str) -> dict:
    try:
        return json.loads(_meta_path(club).read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_clips(club: str, limit: int = 2) -> list[dict]:
    """Newest local clips for a club: [{"path","credit","title","published"}]."""
    meta = _load_meta(club)
    out = []
    for vid, m in sorted(meta.items(), key=lambda kv: kv[1].get("published", ""),
                         reverse=True):
        p = LIB / club / f"{vid}.mp4"
        if p.exists():
            out.append({"path": str(p), **m})
        if len(out) >= limit:
            break
    return out


async def sweep(clubs: list[str] | None = None):
    """Refresh the library: fetch new CC clips, prune stale ones."""
    from modules.cc_clips import search_cc_videos, _download
    from modules.club_brand import CLUB_BRAND
    from modules.psl_squads import ESPN_TEAMS

    clubs = clubs or list(ESPN_TEAMS.keys())
    total_new = 0
    for club in clubs:
        name = CLUB_BRAND.get(club, {}).get("name", club)
        meta = _load_meta(club)
        try:
            hits = await search_cc_videos(f"{name} highlights", limit=MAX_PER_CLUB,
                                          days=MAX_AGE_DAYS)
        except Exception as e:
            print(f"[ClipLib] {club}: search failed ({e})")
            continue
        # a clip only belongs in this club's folder if the title actually
        # names the club — search relevance alone filed a Chiefs video
        # under Sekhukhune on the first sweep
        club_words = [w.lower() for w in name.split() if len(w) > 3] or [name.lower()]
        for h in hits:
            if not any(w in h["title"].lower() for w in club_words):
                continue
            vid = h["video_id"]
            dest = LIB / club / f"{vid}.mp4"
            if vid in meta and dest.exists():
                continue
            got = await asyncio.to_thread(_download, vid, dest)
            if got:
                meta[vid] = {"credit": h["credit"], "title": h["title"],
                             "channel": h["channel"], "published": h["published"],
                             "added": time.time()}
                total_new += 1
                print(f"[ClipLib] + {club}: {h['title'][:50]}")
        # prune: keep newest MAX_PER_CLUB, drop older than MAX_AGE_DAYS
        cutoff = time.time() - MAX_AGE_DAYS * 86400
        keep = dict(sorted(meta.items(), key=lambda kv: kv[1].get("published", ""),
                           reverse=True)[:MAX_PER_CLUB])
        for vid in list(meta):
            if vid not in keep or meta[vid].get("added", 0) < cutoff:
                (LIB / club / f"{vid}.mp4").unlink(missing_ok=True)
                meta.pop(vid, None)
        if meta:
            _meta_path(club).parent.mkdir(parents=True, exist_ok=True)
            _meta_path(club).write_text(json.dumps(meta, indent=2,
                                                   ensure_ascii=False),
                                        encoding="utf-8")
    print(f"[ClipLib] sweep done — {total_new} new clip(s)")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    import modules.cc_clips as cc
    import os
    cc.KEY = os.getenv("YOUTUBE_API_KEY", "")
    if "--sweep" in sys.argv:
        asyncio.run(sweep())
    else:
        for c in ("chiefs", "pirates", "sundowns"):
            print(c, "->", [x["title"][:40] for x in get_clips(c)])
