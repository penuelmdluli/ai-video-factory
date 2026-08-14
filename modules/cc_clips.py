"""
CC-licensed YouTube clips — recent, REAL football video we may legally reuse.

Credit is not a licence. A standard-licence YouTube video stays the creator's
property no matter how prominently we credit them — SuperSport/PSL run rights
matching and a new page does not survive the strikes. YouTube's own
**Creative Commons (CC-BY)** licence option is the exception: reuse is allowed,
including commercially, provided the creator is credited. So this module
searches ONLY videos whose licence field says creativeCommon, double-checks the
licence on the video itself, downloads a short piece, and hands back the credit
line the caller must burn into the frame.

Usage:
    from modules.cc_clips import fetch_cc_clip
    clip = await fetch_cc_clip("Kaizer Chiefs highlights", out_dir)
    # -> {"path", "credit", "title", "video_id"} or None
"""
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

API = "https://www.googleapis.com/youtube/v3"
KEY = os.getenv("YOUTUBE_API_KEY", "")
MAX_SECONDS = 12          # we only ever need a short flash of real footage

# A CC flag only covers what the uploader actually OWNS. A commentary/reaction
# channel showing SuperSport's broadcast on a screen cannot CC-license that
# footage — using it invites the same rights-matching a direct rip would.
# Fan-shot in-stadium video (their own camera) is the safe, real thing.
_BLOCK = re.compile(
    r"(reaction|review|watch ?along|debate|podcast|radio|analysis|prediction|"
    r"preview show|talk|breakdown|opinion|discussion)", re.IGNORECASE)
_PREFER = re.compile(
    r"(uncut|live|stadium|fans?|matchday|vlog|arrival|celebrat|atmosphere|"
    r"warm ?up|training|open day)", re.IGNORECASE)


async def search_cc_videos(query: str, limit: int = 5, days: int = 14,
                           strict_fanshot: bool = False) -> list[dict]:
    """Recent CC-BY YouTube videos for a query. Licence verified twice."""
    if not KEY:
        print("[CCClips] YOUTUBE_API_KEY not set")
        return []
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}/search", params={
                "part": "snippet", "q": query, "type": "video",
                "videoLicense": "creativeCommon", "publishedAfter": after,
                "maxResults": limit * 2, "relevanceLanguage": "en",
                "regionCode": "ZA", "key": KEY,
            })
            items = r.json().get("items", [])
            ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
            if not ids:
                return []
            # verify the licence on the video resource itself — search filters
            # have been wrong before, and this is the legal load-bearing part
            r2 = await client.get(f"{API}/videos", params={
                "part": "status,snippet,contentDetails", "id": ",".join(ids), "key": KEY,
            })
            out = []
            for v in r2.json().get("items", []):
                if v.get("status", {}).get("license") != "creativeCommon":
                    continue
                sn = v["snippet"]
                blob = f"{sn.get('title', '')} {sn.get('channelTitle', '')}"
                if _BLOCK.search(blob):
                    continue          # commentary over broadcast — not theirs to license
                out.append({
                    "video_id": v["id"],
                    "title": sn.get("title", ""),
                    "channel": sn.get("channelTitle", ""),
                    "published": sn.get("publishedAt", ""),
                    "credit": f"video: {sn.get('channelTitle', 'YouTube')} (CC BY, via YouTube)",
                    "score": 1 if _PREFER.search(blob) else 0,
                })
            if strict_fanshot:
                # library-grade: must SHOW fan-shot signals, not merely lack
                # commentary words — a presenter video slipped past the
                # blocklist with a clean title
                out = [h for h in out if h["score"] == 1]
            out.sort(key=lambda h: h["score"], reverse=True)
            return out[:limit]
    except Exception as e:
        print(f"[CCClips] search failed: {e}")
        return []


def _download(video_id: str, dest: Path) -> str | None:
    import yt_dlp
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _section(info, ydl):
        # Fan videos open with the walk to the seat — cut from 30% in, where
        # the actual match/stadium footage lives.
        dur = info.get("duration") or 0
        start = dur * 0.30 if dur > MAX_SECONDS * 2 else 0
        return [{"start_time": start, "end_time": start + MAX_SECONDS}]

    opts = {
        "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b",
        "outtmpl": str(dest),
        "quiet": True, "no_warnings": True,
        "download_ranges": _section,
        "force_keyframes_at_cuts": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        if dest.exists():
            return str(dest)
    except Exception as e:
        print(f"[CCClips] section download failed for {video_id}: {e}")
    # fallback: full download, trim locally — the section cutter's ffmpeg
    # invocation fails on some streams
    try:
        import subprocess
        full = dest.with_suffix(".full.mp4")
        opts2 = {"format": opts["format"], "outtmpl": str(full),
                 "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(opts2) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        if not full.exists():
            return None
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(full)],
                               capture_output=True, text=True)
        dur = float(probe.stdout.strip() or 0)
        start = dur * 0.30 if dur > MAX_SECONDS * 2 else 0
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-ss", f"{start:.1f}", "-i", str(full),
                            "-t", str(MAX_SECONDS), "-c:v", "libx264",
                            "-c:a", "aac", str(dest)], capture_output=True)
        full.unlink(missing_ok=True)
        return str(dest) if r.returncode == 0 and dest.exists() else None
    except Exception as e:
        print(f"[CCClips] fallback download failed for {video_id}: {e}")
        return None


async def fetch_cc_clip(query: str, out_dir: Path) -> dict | None:
    """Best recent CC clip for a query, downloaded and ready to composite."""
    hits = await search_cc_videos(query)
    for h in hits:
        p = Path(out_dir) / f"cc_{h['video_id']}.mp4"
        got = await asyncio.to_thread(_download, h["video_id"], p)
        if got:
            print(f"[CCClips] using: {h['title'][:60]} — {h['credit']}")
            return {**h, "path": got}
    if hits:
        print("[CCClips] found CC videos but none downloadable")
    else:
        print(f"[CCClips] no recent CC videos for '{query}'")
    return None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    KEY = os.getenv("YOUTUBE_API_KEY", "")

    async def _t():
        hits = await search_cc_videos("Kaizer Chiefs highlights", 5)
        for h in hits:
            print(f"  {h['published'][:10]} | {h['title'][:55]} | {h['channel']}")
    asyncio.run(_t())
