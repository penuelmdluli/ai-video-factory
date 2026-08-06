"""FULL vertical REEL (no presenter) with REAL per-shot foley, then post to FB.

Vertical 704x1280. 8 generic/illustrative war-politics shots, each with its own
HunyuanVideo-Foley synced sound. + Kokoro voice + music + captions + broadcast
graphics. Posts as a Reel to Tech Pulse Africa.
"""
import asyncio, base64, subprocess, time, sys
from pathlib import Path
import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
OUTC = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\reel"); OUTC.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "output" / "reel"; OUT.mkdir(parents=True, exist_ok=True)

KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
EP_LTX = "https://api.runpod.ai/v2/mp2awqavthuc2b"
EP_MUSIC = "https://api.runpod.ai/v2/b13hwup9d6179v"
EP_WHISPER = "https://api.runpod.ai/v2/5r88ueysbd8tm8"
EP_FOLEY = "https://api.runpod.ai/v2/5arzy0p1wnm229"

W, HGT, FPS = 704, 1280, 24
NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted, warped faces, extra limbs, "
       "text artifacts, watermark, low resolution, flickering, morphing")

SHOTS = [
    ("01_soldier", "A lone soldier silhouette standing on a hilltop at dawn, mist rolling, dramatic orange sky, "
                   "slow push-in, vertical cinematic, shot on 35mm film, highly detailed, 4k",
     "cold wind, distant gunfire, boots on gravel"),
    ("02_tank", "A single military tank rolling across a vast desert at dusk, thick dust trail behind it, "
                "low golden light, vertical cinematic, highly detailed, 4k",
     "heavy tank engine, metal treads, desert wind"),
    ("03_jet", "A fighter jet streaking low across a dramatic cloudy sky, condensation vapor trail, "
               "dynamic low angle, vertical cinematic, highly detailed, 4k",
     "loud jet engine roar passing overhead, wind"),
    ("04_flag", "A weathered national flag waving on a pole against a smoky orange sky at dusk, embers drifting, "
                "vertical cinematic, shallow depth of field, 4k",
     "wind, fabric flag flapping, distant sirens"),
    ("05_convoy", "An aerial vertical shot of a military convoy of armored vehicles moving along a desert road at "
                  "dusk, long shadows, dust, cinematic, highly detailed, 4k",
     "diesel engines, gravel crunch, wind"),
    ("06_radar", "Close-up of a glowing green radar sweep on a dark command-room screen, blips pulsing, "
                 "reflections, tense, vertical cinematic, 4k",
     "radar beeps, low electronic hum, distant radio chatter"),
    ("07_smoke", "A distant city skyline at dusk under a deep red sky with columns of smoke rising on the horizon, "
                 "vertical wide cinematic, highly detailed, 4k",
     "distant rumble, wind, faint sirens"),
    ("08_map", "A glowing tactical world map on a dark briefing-room table, moving light markers, dramatic, "
               "vertical cinematic close-up, 4k",
     "electronic hum, soft beeps, muffled voices"),
]

NARRATION = ("Tonight, the world holds its breath. Military forces are mobilizing across multiple fronts as "
             "diplomatic tensions reach a breaking point. Analysts warn the coming days could reshape the global "
             "balance of power. Governments urge calm, but the drums of conflict grow louder. Stay with us as this "
             "story develops.")

TICKER = "Global military tensions escalate across multiple fronts  \u2022  diplomats scramble as forces mobilize"


def _submit(ep, payload):
    r = requests.post(f"{ep}/run", headers=H, json={"input": payload}, timeout=90)
    return r.json().get("id")


def _poll(ep, job, budget, label=""):
    t0 = time.time(); last = None
    while time.time() - t0 < budget:
        time.sleep(12)
        s = requests.get(f"{ep}/status/{job}", headers=H, timeout=30).json()
        st = s.get("status")
        if st != last:
            print(f"    {label}[{int(time.time()-t0)}s] {st}", flush=True); last = st
        if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
            return s
    return None


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def gen_shots():
    paths = []
    for name, prompt, _ in SHOTS:
        f = OUTC / f"{name}.mp4"
        if f.exists() and f.stat().st_size > 50_000:
            print(f"  [{name}] reuse", flush=True); paths.append(f); continue
        print(f"  [{name}] LTX generating", flush=True)
        job = _submit(EP_LTX, {"prompt": prompt, "negative_prompt": NEG, "width": W, "height": HGT,
                               "num_frames": 97, "seed": 7})
        res = _poll(EP_LTX, job, 3000, f"{name} ") if job else None
        if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("video_base64"):
            f.write_bytes(base64.b64decode(res["output"]["video_base64"]))
            print(f"    saved {name} ({f.stat().st_size/1e6:.2f}MB)", flush=True); paths.append(f)
        else:
            print(f"    {name} FAILED: {res.get('status') if res else 'timeout'}", flush=True); paths.append(None)
    return paths


def gen_foley(paths):
    audios = []
    for (name, _, fprompt), p in zip(SHOTS, paths):
        if not p:
            audios.append(None); continue
        print(f"  [{name}] foley", flush=True)
        try:
            b64 = base64.b64encode(Path(p).read_bytes()).decode()
            job = _submit(EP_FOLEY, {"video": b64, "prompt": fprompt})
            res = _poll(EP_FOLEY, job, 1200, f"{name} ") if job else None
            if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("audio_base64"):
                a = OUT / f"foley_{name}.wav"
                a.write_bytes(base64.b64decode(res["output"]["audio_base64"]))
                print(f"    foley saved {name}", flush=True); audios.append(str(a))
            else:
                print(f"    foley {name} failed -> ambient fallback", flush=True); audios.append(None)
        except Exception as e:
            print(f"    foley {name} err: {e}", flush=True); audios.append(None)
    return audios


def gen_music(sec):
    print("  music", flush=True)
    job = _submit(EP_MUSIC, {"prompt": "tense cinematic military news underscore, deep drums, ominous strings, "
                                       "building urgency, 95bpm", "duration": min(30, int(sec) + 1)})
    res = _poll(EP_MUSIC, job, 600, "music ") if job else None
    if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("audio_base64"):
        f = OUT / "music.wav"; f.write_bytes(base64.b64decode(res["output"]["audio_base64"])); return f
    return None


def gen_captions(wav):
    try:
        b64 = base64.b64encode(Path(wav).read_bytes()).decode()
        job = _submit(EP_WHISPER, {"audio_base64": b64})
        res = _poll(EP_WHISPER, job, 400, "whisper ") if job else None
        if res and res.get("status") == "COMPLETED":
            return (res.get("output") or {}).get("words") or []
    except Exception as e:
        print("  whisper err", e, flush=True)
    return []


async def kokoro(text, wav):
    from modules.voice_generator import generate_voice_kokoro
    mp3 = OUT / "narration.mp3"
    await generate_voice_kokoro(text, mp3, voice="am_onyx", speed=1.0)
    subprocess.run([_ff(), "-y", "-i", str(mp3), str(wav)], capture_output=True)


def main():
    print("=== VERTICAL REEL BUILD ===", flush=True)
    print("[1] shots", flush=True); paths = gen_shots()
    good = [p for p in paths if p]
    print(f"  {len(good)}/8 shots ok", flush=True)
    print("[2] per-shot foley", flush=True); audios = gen_foley(paths)
    print("[3] narration (Kokoro am_onyx)", flush=True)
    wav = OUT / "narration.wav"; asyncio.run(kokoro(NARRATION, wav))
    print("[4] music", flush=True); music = gen_music(28)
    print("[5] captions", flush=True); words = gen_captions(wav)
    print("[6] assemble (vertical + per-shot foley)", flush=True)
    from assemble_full import assemble
    clips = [p for p in paths if p]
    shot_aud = [a for a, p in zip(audios, paths) if p]
    final = assemble(clips, str(wav), music, words, NARRATION, OUT, W, HGT, FPS, target=28.0,
                     flags=("US", "RU"), lowerthird_label="Global forces on high alert",
                     ticker=TICKER, live=True, tag_text="AI VISUALIZATION", shot_audios=shot_aud)
    # faststart reencode + move to desktop
    dest = Path(r"C:\Users\PenuelM\Desktop\AI_Videos\reel_tensions.mp4")
    subprocess.run([_ff(), "-y", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-c:a", "aac", str(dest)], capture_output=True)
    print(f"DONE -> {dest}", flush=True)


if __name__ == "__main__":
    main()
