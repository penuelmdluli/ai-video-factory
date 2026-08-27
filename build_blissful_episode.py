"""
BLISSFUL MOMENTS — episode 1. Blender scene, voiced, scored, end to end.

The revival candidate is chosen from the audit, not from taste: Blissful
Moments holds 57,831 followers - thirty-five times Genesis - and returns 0.9
engagement per post. That audience is not gone, it is unserved.

The pipeline, all of it already built except the scene:

    blender/blissful_scene.py   headless render, no GUI, fully parametric
    modules/voice_generator     the same Kokoro voice the football uses
    modules/sound_kit           the same synthesised score
    ffmpeg                      mux and loudness

The render is timed to the narration rather than the other way round, which
is the lesson from the football reels: build the picture to a fixed length and
the words land in the wrong place.

    python build_blissful_episode.py                # build only
    python build_blissful_episode.py --post         # blocked while paused
"""
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

NICHE = "blissful_moments"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe")
FPS = 30

# Written to be read slowly, and to be true. No promises, no instructions to
# feel better - the page's job here is a held breath, not advice.
EPISODES = [
    {
        "key": "ep01-the-day-is-done",
        "title": "The Day Is Done",
        "seed": 0.0,
        "lines": [
            "The day is done.",
            "Whatever it asked of you, you carried it.",
            "The sun does not ask if you finished everything. "
            "It just goes down, and comes back.",
            "Sit here a moment. Let the light change without you.",
            "Tomorrow will want things from you too. Not yet.",
        ],
        "closing": "BREATHE. THE DAY IS DONE.",
    },
]


def narration(ep):
    return " ".join(ep["lines"])


async def make_voice(text, work):
    from modules.voice_generator import generate_voice
    vw = work / "voicework"
    vw.mkdir(parents=True, exist_ok=True)
    v = await generate_voice(text, vw, "blissful", "short", NICHE)
    p = (v or {}).get("audio_path")
    if not p:
        return None, 0.0
    from moviepy import AudioFileClip
    a = AudioFileClip(p)
    d = a.duration
    a.close()
    return p, d


def render_scene(out_stem, frames, seed):
    """Headless Blender. Returns the mp4 path, or None."""
    if not BLENDER.exists():
        print("[Blissful] Blender not found at " + str(BLENDER))
        return None
    cmd = [str(BLENDER), "--background", "--python",
           str(ROOT / "blender" / "blissful_scene.py"), "--",
           "--out", str(out_stem), "--frames", str(frames),
           "--seed", str(seed)]
    print(f"[Blissful] rendering {frames} frames in Blender…")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    if r.returncode != 0:
        print("[Blissful] blender failed: " + (r.stderr or "")[-400:])
        return None
    # Blender writes <stem>0001-NNNN.mp4 for an animation range
    hits = sorted(Path(out_stem).parent.glob(Path(out_stem).name + "*.mp4"))
    return str(hits[-1]) if hits else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int, default=0)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    ep = EPISODES[a.episode]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"blissful_{ep['key']}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    text = narration(ep)
    audio, vdur = await make_voice(text, work)
    if not audio:
        print("[Blissful] voice failed — refusing to build a silent episode")
        return 1
    # a beat of quiet at each end: this format is the opposite of urgent
    total = vdur + 3.4
    frames = int(total * FPS)
    print(f"[Blissful] voice {vdur:.1f}s -> episode {total:.1f}s ({frames}f)")

    silent = render_scene(work / "scene", frames, ep["seed"])
    if not silent:
        return 1
    print("[Blissful] scene: " + silent)

    # Score: the music bed only. No risers, no impacts - the football palette
    # is built to create tension and this format exists to remove it.
    from modules.sound_kit import music_bed, write_wav
    score = write_wav(music_bed(total, bpm=54, root=110.0) * 0.85,
                      work / "score.wav")

    # voice in, 1.7s after the picture starts, so the scene lands first
    out = work / "final.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", silent, "-i", audio, "-i", score,
           "-filter_complex",
           "[1:a]adelay=1700|1700,volume=1.0[v];"
           "[2:a]volume=-16dB[m];"
           "[v][m]amix=inputs=2:duration=longest:normalize=0[x];"
           "[x]loudnorm=I=-16:TP=-1.5:LRA=11[a]",
           "-map", "0:v", "-map", "[a]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-shortest", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print("[Blissful] mux failed: " + (r.stderr or "")[-300:])
        return 1
    print("[Blissful] BUILD COMPLETE: " + str(out))

    cover = work / "cover.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss",
                    f"{total*0.62:.2f}", "-i", str(out), "-frames:v", "1",
                    "-q:v", "2", str(cover)], timeout=300)

    caption = ("🌅 " + ep["title"].upper() + "\n\n"
               + "\n".join(ep["lines"][:3]) + "\n\n"
               "Take a minute. That is the whole post.\n\n"
               "#BlissfulMoments #Calm #Mindfulness #SouthAfrica")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(out), "thumbnail": str(cover),
         "title": ep["title"], "description": caption,
         "narration": text, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")

    if a.post:
        # The page is in PAUSED_PAGES from the audit. That guard is doing its
        # job here, and it should NOT be worked around from inside a builder -
        # unpausing is an owner decision, made once, in one place.
        from modules.uploader_facebook import PAUSED_PAGES
        if NICHE in PAUSED_PAGES:
            print("[Blissful] page is PAUSED — not posting. Remove "
                  "blissful_moments from GENESIS_PAUSED_PAGES to publish.")
            return 0
        from modules.publish_reel import publish
        r2 = await publish(str(out), ep["title"], caption, cover, niche=NICHE)
        print("published: " + str(r2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
