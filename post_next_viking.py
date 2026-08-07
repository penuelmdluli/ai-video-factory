#!/usr/bin/env python
"""Post the next unposted SAGA OF THE NORTH short to the page (blissful_moments page ID, now the
Viking channel). Rotates through the bank in output/viking_*/final.mp4; tracks posted ones in
logs/viking_posted.json so it never repeats. Run 3x/day by the scheduler.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "viking_posted.json"
LOG.parent.mkdir(exist_ok=True)

CAPTIONS = {
    "oath": "THE OATH ⚔️  By fire and iron, the Northmen swear. Would you take the oath?",
    "pyre": "THE FUNERAL PYRE \U0001F525  We give him to the sea and the fire. Rest in Valhalla.",
    "shieldwall": "THE SHIELD WALL \U0001F6E1️  Hold the line. The North does not break. Could you hold?",
    "ep1": "SAGA OF THE NORTH ⚔️  They came from the cold north. Would you sail with him?",
}
DEFAULT = "SAGA OF THE NORTH ⚔️\U0001FA93  Legends of the North. Follow for the saga."


def _posted():
    try:
        return set(json.loads(LOG.read_text()))
    except Exception:
        return set()


def _mark(p):
    s = _posted()
    s.add(p)
    LOG.write_text(json.dumps(sorted(s), indent=2))


def main():
    finals = sorted(ROOT.glob("output/viking_*/final.mp4"), key=lambda p: p.stat().st_mtime)
    done = _posted()
    nxt = next((f for f in finals if str(f) not in done), None)
    if not nxt:
        print("no unposted viking shorts left — run build_viking_batch.py to make more", flush=True)
        return
    slug = nxt.parent.name.split("_")[1] if "_" in nxt.parent.name else ""
    cap = CAPTIONS.get(slug, DEFAULT) + "\n\n#Vikings #Norse #SagaOfTheNorth #Shorts #Reels #AI"
    from modules.uploader_facebook import upload_to_facebook
    res = asyncio.run(upload_to_facebook(
        video_path=str(nxt), title="SAGA OF THE NORTH", description=cap, niche="blissful_moments",
        hashtags=["Vikings", "Norse", "SagaOfTheNorth", "Shorts", "Reels"], is_reel=True))
    print("POST:", res, flush=True)
    if isinstance(res, dict) and res.get("status") == "uploaded":
        _mark(str(nxt))
        print(f"posted + logged: {nxt.parent.name}", flush=True)


if __name__ == "__main__":
    main()
