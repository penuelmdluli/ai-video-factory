"""FULL end-to-end 30s video — EVERYTHING in it.

Pipeline (all on our own RunPod workers + local assembly):
  1. AI shot list  (video_prompt_enhancer: Gemini->Claude)
  2. Video         -> LTX worker (8 cinematic shots, reuses output/warpost/ if present)
  3. Narration     -> edge-tts (Chatterbox voice worker when its build is fixed)
  4. Music bed     -> MusicGen worker
  5. Captions      -> Whisper worker (word-level) -> burned karaoke (PIL)
  6. Sound FX      -> local assets/sfx whooshes at cuts (best-effort)
  7. AI tag        -> "AI VISUALIZATION" overlay throughout
  8. Assemble      -> MoviePy v2 -> output/full_video/final_30s.mp4

Run:  python make_full_video.py
"""
import asyncio
import base64
import glob
import os
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
LTX_CLIPS = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\warpost")
OUT = ROOT / "output" / "full_video"
OUT.mkdir(parents=True, exist_ok=True)

KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
EP_LTX = "https://api.runpod.ai/v2/mp2awqavthuc2b"
EP_MUSIC = "https://api.runpod.ai/v2/b13hwup9d6179v"
EP_WHISPER = "https://api.runpod.ai/v2/5r88ueysbd8tm8"

NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted, warped faces, "
       "extra limbs, text artifacts, watermark, low resolution, flickering, morphing")

W, HGT, FPS = 1216, 704, 24

# 8 coherent, GENERIC, illustrative naval/Red-Sea shots (no real people or events).
# First 4 names match the test angles so they get reused from output/warpost/.
SHOTS = [
    ("01_wide", "Wide cinematic establishing shot: a lone grey naval patrol vessel silhouetted on a vast "
                "choppy sea at dusk, deep crimson and orange sky, slow aerial drift, volumetric haze, "
                "shot on 35mm film, highly detailed, 4k, cinematic color grade"),
    ("02_tracking", "Low-angle tracking shot skimming just above the dark water alongside a fast-moving grey "
                    "patrol vessel cutting through spray at twilight, ominous crimson light, motion blur, "
                    "cinematic, anamorphic, highly detailed, 4k"),
    ("03_aerial", "Top-down aerial drone shot slowly descending over a single naval vessel carving a white wake "
                  "across deep blue-black ocean at dusk, dramatic god rays, cinematic, highly detailed, 4k"),
    ("04_detail", "Slow cinematic push-in on the bow of a weathered grey patrol vessel slicing through crimson-lit "
                  "water at twilight, sea spray catching the last light, shallow depth of field, film grain, 4k"),
    ("05_radar", "Close-up of a glowing green radar sweep on a dark control-room screen, blips pulsing, "
                 "reflections on glass, tense atmosphere, cinematic, highly detailed, 4k"),
    ("06_tanker", "A massive oil tanker silhouette on the horizon at dusk, still water, distant haze, "
                  "ominous orange sky, slow cinematic pan, highly detailed, 4k"),
    ("07_watch", "Silhouette of a lone naval officer from behind watching a wall of glowing monitors in a dim "
                 "command room, cool blue light, cinematic, shallow depth of field, 4k"),
    ("08_horizon", "Distant warship silhouettes on the horizon under a blood-red sunset over open sea, "
                   "long lens, shimmering water, epic cinematic wide shot, highly detailed, 4k"),
]

NARRATION_FALLBACK = (
    "Tonight, all eyes turn to the Red Sea. Naval forces are moving into position "
    "as tensions between global powers reach a boiling point. The shipping lanes that "
    "carry the world's oil now sit at the center of a dangerous standoff. Analysts warn "
    "that a single misstep could ignite a far wider conflict. For now, the world watches, and waits."
)


def _submit(ep, payload):
    r = requests.post(f"{ep}/run", headers=H, json={"input": payload}, timeout=60)
    return r.json().get("id")


def _poll(ep, job, budget=800, label=""):
    t0 = time.time(); last = None
    while time.time() - t0 < budget:
        time.sleep(10)
        s = requests.get(f"{ep}/status/{job}", headers=H, timeout=30).json()
        st = s.get("status")
        if st != last:
            print(f"    {label}[{int(time.time()-t0)}s] {st}", flush=True); last = st
        if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
            return s
    return None


# ---------------- 1. narration script (Gemini -> Claude -> fallback) --------------
def make_narration_text():
    try:
        import sys
        sys.path.insert(0, str(ROOT))
        from modules.video_prompt_enhancer import _try_gemini  # reuse the AI client
        # Ask Gemini for a ~30s news brief; reuse the enhancer's client via a direct call
        from config import GEMINI_API_KEY
        if GEMINI_API_KEY:
            from google import genai
            c = genai.Client(api_key=GEMINI_API_KEY)
            p = ("Write a tense 30-second breaking-news voiceover script (about 70 words) for a war/geopolitics "
                 "video about rising Red Sea naval tensions and threatened oil shipping lanes. Generic, no real "
                 "names, no specific claimed events. Punchy news-anchor tone. Return ONLY the script text.")
            for m in ("gemini-2.5-flash", "gemini-2.0-flash"):
                try:
                    r = c.models.generate_content(model=m, contents=p)
                    if r and r.text and len(r.text.strip()) > 40:
                        return r.text.strip().replace("\n", " ")
                except Exception:
                    continue
    except Exception as e:
        print(f"  narration AI failed ({e}); using fallback", flush=True)
    return NARRATION_FALLBACK


# ---------------- 2. narration audio (edge-tts) ----------------------------------
async def make_narration_audio(text, wav_path):
    import edge_tts
    mp3 = str(OUT / "narration.mp3")
    await edge_tts.Communicate(text, "en-US-GuyNeural", rate="+6%").save(mp3)
    ff = _ffmpeg()
    subprocess.run([ff, "-y", "-i", mp3, wav_path], capture_output=True)
    return wav_path


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _audio_dur(path):
    ff = _ffmpeg()
    r = subprocess.run([ff, "-i", path], capture_output=True, text=True)
    for l in r.stderr.splitlines():
        if "Duration" in l:
            hh, mm, ss = l.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
    return 0.0


# ---------------- 3. video shots (LTX, reuse if present) -------------------------
def make_shots():
    LTX_CLIPS.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, prompt in SHOTS:
        existing = LTX_CLIPS / f"{name}.mp4"
        if existing.exists() and existing.stat().st_size > 50_000:
            print(f"  [{name}] reuse existing ({existing.stat().st_size/1e6:.2f}MB)", flush=True)
            paths.append(existing); continue
        print(f"  [{name}] generating", flush=True)
        job = _submit(EP_LTX, {"prompt": prompt, "negative_prompt": NEG,
                               "width": W, "height": HGT, "num_frames": 97, "seed": 7})
        if not job:
            print(f"    {name} submit failed", flush=True); continue
        res = _poll(EP_LTX, job, budget=3000, label=f"{name} ")  # patient: wait through capacity crunch
        if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("video_base64"):
            existing.write_bytes(base64.b64decode(res["output"]["video_base64"]))
            print(f"    SAVED {name} ({existing.stat().st_size/1e6:.2f}MB)", flush=True)
            paths.append(existing)
        else:
            print(f"    {name} -> {res.get('status') if res else 'TIMEOUT'}", flush=True)
    return paths


# ---------------- 4. music (MusicGen) --------------------------------------------
def make_music(seconds):
    print("  music: generating bed", flush=True)
    job = _submit(EP_MUSIC, {"prompt": "tense cinematic geopolitical news underscore, low pulsing strings, "
                                        "deep drums, ominous, building tension, 90bpm",
                             "duration": min(30, max(12, int(seconds) + 1))})
    if not job:
        print("    music submit failed", flush=True); return None
    res = _poll(EP_MUSIC, job, budget=500, label="music ")
    if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("audio_base64"):
        f = OUT / "music.wav"
        f.write_bytes(base64.b64decode(res["output"]["audio_base64"]))
        print(f"    SAVED music ({f.stat().st_size/1e6:.2f}MB)", flush=True)
        return f
    print("    music failed", flush=True); return None


# ---------------- 5. captions (Whisper worker -> segments) -----------------------
def make_captions(wav_path):
    try:
        b64 = base64.b64encode(Path(wav_path).read_bytes()).decode()
        job = _submit(EP_WHISPER, {"audio_base64": b64})
        if not job:
            return []
        res = _poll(EP_WHISPER, job, budget=400, label="whisper ")
        if res and res.get("status") == "COMPLETED":
            out = res.get("output") or {}
            words = out.get("words") or []
            print(f"    whisper: {len(words)} words", flush=True)
            return words
    except Exception as e:
        print(f"    whisper failed: {e}", flush=True)
    return []


def main():
    print("=== FULL 30s VIDEO BUILD ===", flush=True)

    print("\n[1/6] narration script", flush=True)
    text = make_narration_text()
    print("  script:", text[:120], "...", flush=True)

    print("\n[2/6] narration audio (edge-tts)", flush=True)
    wav = str(OUT / "narration.wav")
    asyncio.run(make_narration_audio(text, wav))
    ndur = _audio_dur(wav)
    print(f"  narration duration: {ndur:.1f}s", flush=True)

    print("\n[3/6] video shots (LTX)", flush=True)
    clips = make_shots()
    print(f"  {len(clips)} shots ready", flush=True)

    print("\n[4/6] music (MusicGen)", flush=True)
    music = make_music(ndur)

    print("\n[5/6] captions (Whisper)", flush=True)
    words = make_captions(wav)

    print("\n[6/6] assemble", flush=True)
    from assemble_full import assemble
    final = assemble(clips, wav, music, words, text, OUT, W, HGT, FPS, target=max(28.0, ndur))
    print(f"\nDONE -> {final}", flush=True)


if __name__ == "__main__":
    main()
