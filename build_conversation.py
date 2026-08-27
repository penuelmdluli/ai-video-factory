"""
Two characters having an argument. Voices, lip sync, eyelines and a cut.

A conversation is not two monologues. Four things separate one from the other,
and all four are missing from a scene that just plays two clips:

  1. DIFFERENT VOICES. Kokoro ships 54; one per character, chosen once and
     kept, because a voice IS a character.
  2. EYELINES. They look at EACH OTHER, not at the camera. The listener's
     head turns to whoever is talking. This is the single strongest cue that
     two people are in a conversation rather than in the same shot.
  3. SHOT / REVERSE-SHOT. The camera cuts to whoever is speaking. It is the
     oldest grammar in film and it is what makes dialogue readable - a locked
     wide of two people talking reads as security footage.
  4. ONLY THE SPEAKER'S MOUTH MOVES. Obvious, and the thing that ruins a
     scene fastest if you get it wrong.

Consistency comes from the spec: the same cast, the same world seed and the
same deterministic keyframes mean episode 12 sits in the same street as
episode 1, with the same two people, and no frame is ever re-rolled.

    python build_conversation.py --script convo.json
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
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe")
FPS = 30

# The argument. Written so each line is a REACTION to the last - an exchange,
# not two people taking turns to state opinions.
DEFAULT = {
    "world": "street",
    "seed": 5,
    "cars": 11,
    "cast": [
        {"name": "sharp", "voice": "af_bella",
         "fbx": "C:/Users/PenuelM/Documents/AI-Avatar-Pipeline/temp/"
                "browser_downloads/Shoved Reaction With Spin (2).fbx",
         "at": [-7.9, -3.4], "facing": 62, "lift": 0.30},
        {"name": "cap", "voice": "am_onyx",
         "fbx": "C:/Users/PenuelM/Documents/AI-Avatar-Pipeline/temp/"
                "browser_downloads/Shoved Reaction With Spin.fbx",
         "at": [-6.4, -5.0], "facing": -118, "lift": 0.30},
    ],
    "lines": [
        {"who": 0, "text": "You are not seriously telling me that was a foul."},
        {"who": 1, "text": "He went down. The referee gave it. That is a foul."},
        {"who": 0, "text": "He went down because he wanted to go down!"},
        {"who": 1, "text": "Oh, so now you are the referee."},
        {"who": 0, "text": "I am the only one here who was actually watching."},
        {"who": 1, "text": "Fine. Then tell me what you saw. Slowly."},
    ],
}


async def voice_line(text, voice, work, tag):
    from modules.voice_generator import generate_voice_kokoro
    audio = work / f"{tag}.mp3"
    subs = work / f"{tag}.srt"
    r = await generate_voice_kokoro(text, audio, voice=voice, output_subs=subs)
    if not r:
        return None
    from moviepy import AudioFileClip
    a = AudioFileClip(str(audio))
    d = a.duration
    a.close()
    return {"audio": str(audio), "srt": str(subs) if subs.exists() else "",
            "dur": d, "voice": voice, "text": text}


def render_shot(spec_path, out_stem):
    cmd = [str(BLENDER), "--background", "--python",
           str(ROOT / "blender" / "story.py"), "--",
           "--spec", str(spec_path), "--out", str(out_stem)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    if r.returncode != 0:
        print("  render failed: " + (r.stderr or "")[-300:])
        return None
    hits = sorted(Path(out_stem).parent.glob(Path(out_stem).name + "*.mp4"))
    return str(hits[-1]) if hits else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--write", action="store_true",
                    help="let the model write the scene")
    ap.add_argument("--premise", default="")
    ap.add_argument("--cast", default="Thandi,Sipho")
    a = ap.parse_args()

    story = (json.loads(Path(a.script).read_text(encoding="utf-8"))
             if a.script else json.loads(json.dumps(DEFAULT)))

    # The model writes the scene; the spec supplies the cast, the world and
    # the voices. Keeping those apart means a new episode is a new SCRIPT in
    # the same street with the same two people - which is what makes a series
    # feel like a series rather than a set of unrelated clips.
    if a.write:
        from modules.scene_writer import write_scene
        names = [x.strip() for x in a.cast.split(",")][:2]
        scene = await write_scene(a.premise, cast=tuple(names))
        if not scene:
            print("[Convo] the writer produced nothing usable — stopping")
            return 1
        story["lines"] = scene["lines"]
        story["title"] = scene.get("title", "")
        story["premise"] = scene.get("premise", "")
        for i, n in enumerate(names):
            if i < len(story["cast"]):
                story["cast"][i]["name"] = n
        print(f"[Convo] '{story['title']}' — {story['premise']}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / (a.out or f"output/convo_{stamp}")
    work.mkdir(parents=True, exist_ok=True)
    vwork = work / "voice"
    vwork.mkdir(exist_ok=True)

    # ── 1. every line gets its own voice and its own timings ──────────────
    takes = []
    for i, ln in enumerate(story["lines"]):
        who = int(ln["who"])
        v = story["cast"][who]["voice"]
        t = await voice_line(ln["text"], v, vwork, f"l{i:02d}")
        if not t:
            print(f"[Convo] line {i} voice failed — aborting")
            return 1
        t["who"] = who
        takes.append(t)
        print(f"[Convo] {i}: {story['cast'][who]['name']:6} ({v:9}) "
              f"{t['dur']:5.2f}s  \"{ln['text'][:44]}\"")

    # ── 2. one shot per line, cutting to the speaker ──────────────────────
    parts = []
    for i, t in enumerate(takes):
        frames = max(12, int(round(t["dur"] * FPS)) + 6)
        spec = {
            "frames": frames,
            "focus": t["who"],
            "speaker": t["who"],
            "srt": t["srt"],
            "shot": "close" if i % 2 == 0 else "medium",
            "world": story.get("world", "street"),
            "seed": story.get("seed", 5),
            "cars": story.get("cars", 11),
            "samples": 10,
            "cast": [],
        }
        # Eyelines: each character looks at the OTHER one, not the lens. The
        # look target is set per-cast-member below by index.
        for j, c in enumerate(story["cast"]):
            spec["cast"].append({
                "name": c["name"], "fbx": c["fbx"], "at": c["at"],
                "facing": c["facing"], "lift": c.get("lift", 0),
                "speed": 0.55 if j == t["who"] else 0.75,
                "offset": -18 * j - i * 11,
                "look_at_cast": 1 - j,
                "look": 0.45,
            })
        sp = work / f"shot{i:02d}.json"
        sp.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        print(f"[Convo] rendering shot {i+1}/{len(takes)} "
              f"({spec['shot']}, {frames}f)")
        p = render_shot(sp, work / f"shot{i:02d}")
        if p:
            parts.append((p, t))

    if not parts:
        print("[Convo] nothing rendered")
        return 1

    # ── 3. join picture, then lay the dialogue over it in order ───────────
    from modules.ffmpeg_ops import concat
    silent = concat([p for p, _ in parts], work / "silent.mp4")
    if not silent:
        return 1

    # audio: each line starts where the previous shot ended
    filters, inputs, at = [], ["-i", silent], 0.0
    for idx, (p, t) in enumerate(parts):
        inputs += ["-i", t["audio"]]
        filters.append(f"[{idx+1}:a]adelay={int(at*1000)}|{int(at*1000)}"
                       f"[a{idx}]")
        at += t["dur"] + 0.20        # a beat between lines
    mixchain = "".join(f"[a{i}]" for i in range(len(parts)))
    filters.append(f"{mixchain}amix=inputs={len(parts)}:normalize=0[dry]")
    filters.append("[dry]loudnorm=I=-15:TP=-1.5:LRA=11[aout]")

    out = work / "conversation.mp4"
    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inputs
           + ["-filter_complex", ";".join(filters),
              "-map", "0:v", "-map", "[aout]",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
              "-shortest", str(out)])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print("[Convo] mux failed: " + (r.stderr or "")[-300:])
        return 1

    (work / "script.json").write_text(
        json.dumps(story, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[Convo] COMPLETE: " + str(out))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
