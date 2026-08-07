#!/usr/bin/env python
"""$0 finisher for a Veo short: take the existing visuals + a narration script, add a deep
saga-teller narrator (Kokoro) + score bed, brand it, then burn synced subtitles + a follow
prompt + comment-bait. No Veo re-generation.

  python finish_short.py <dir_with_visuals.mp4>
"""
import asyncio
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import imageio_ffmpeg

from modules.wild_brand import brand_video
from modules.subtitles import add_subs_and_follow
from modules.voice_generator import generate_voice_kokoro

SAGA = ("They came from the cold north, where the sea itself screams. And when the storm broke... "
        "the Northmen did not pray. They attacked.")
NAME, EMOJI, HANDLE = "SAGA OF THE NORTH", "\U0001FA93", "@SagaOfTheNorth"
COMMENT = "Would you sail with him?"
MUSIC = ROOT / "assets" / "ai_music_cache" / "bgm_tech_news.mp3"
GOLD = (224, 164, 0)


def _dur(p):
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", p], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 16.0


def finish(dir_, saga=SAGA, comment=COMMENT, name=NAME, emoji=EMOJI, handle=HANDLE):
    d = Path(dir_)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    visuals = d / "visuals.mp4"
    if not visuals.exists():
        print(f"no visuals.mp4 in {d}", flush=True)
        return
    narr, srt = d / "narr.mp3", d / "narr.srt"
    print("  narrating (am_onyx)...", flush=True)
    asyncio.run(generate_voice_kokoro(saga, narr, voice="am_onyx", speed=1.0, output_subs=srt))
    if not narr.exists():
        print("  narration failed", flush=True)
        return
    dur = _dur(str(visuals))

    mixed = d / "mixed.mp4"
    ins = ["-i", str(visuals), "-i", str(narr)]
    fc = "[0:a]volume=0.35[a0];[1:a]volume=1.3,adelay=500|500[a1];"
    amix, n = "[a0][a1]", 2
    if MUSIC.exists():
        ins += ["-i", str(MUSIC)]
        fc += (f"[2:a]volume=0.16,aloop=loop=-1:size=200000000,atrim=0:{dur:.2f},"
               f"afade=t=out:st={max(0, dur-1):.2f}:d=1[a2];")
        amix += "[a2]"
        n = 3
    fc += f"{amix}amix=inputs={n}:normalize=0:duration=first[a]"
    subprocess.run([ff, "-y", *ins, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", str(mixed)], capture_output=True)

    branded = d / "branded.mp4"
    brand_video(str(mixed), str(branded), name=name, emoji=emoji, follow=False)
    final = d / "final.mp4"
    add_subs_and_follow(str(branded), str(srt), str(final), handle=handle, accent=GOLD, comment=comment)
    print(f"FINAL -> {final}", flush=True)
    return final


if __name__ == "__main__":
    finish(sys.argv[1] if len(sys.argv) > 1 else max(
        (p for p in (ROOT / "output").glob("viking_ep1_*")), key=lambda p: p.stat().st_mtime))
