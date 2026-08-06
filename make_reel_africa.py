"""Vertical REEL — Africa's pressing issues linked to global powers (SA focus).
Reuses the improved assembler (voice-forward mix, boom, Ken Burns, subtle tag).
"""
import asyncio, base64, subprocess, time, sys
from pathlib import Path
import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
OUTC = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\reel_africa"); OUTC.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "output" / "reel_africa"; OUT.mkdir(parents=True, exist_ok=True)

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
    ("01_map", "A glowing map of the African continent on a dark tactical table, pulsing light markers spreading, "
               "dramatic, vertical cinematic close-up, highly detailed, 4k",
     "deep electronic hum, soft data beeps"),
    ("02_mine", "A vast open-pit mine at dusk, terraced walls, heavy haul trucks, dust haze, golden light, "
                "vertical cinematic aerial, highly detailed, 4k",
     "heavy mining machinery, rock crushing, wind"),
    ("03_port", "A massive container port at dusk, towering cranes loading a cargo ship, stacked containers, "
                "vertical cinematic wide, highly detailed, 4k",
     "port cranes, distant ship horn, machinery"),
    ("04_skyline", "A modern African city skyline at dusk, glowing towers, busy highways, dramatic orange sky, "
                   "vertical cinematic, highly detailed, 4k",
     "city ambience, distant traffic, wind"),
    ("05_flags", "Several national flags on tall poles waving against a dramatic stormy sky at dusk, "
                 "vertical cinematic, shallow depth of field, 4k",
     "strong wind, fabric flags flapping"),
    ("06_oil", "An oil refinery with pipelines and a glowing flare stack at dusk, industrial sprawl, "
               "vertical cinematic, highly detailed, 4k",
     "industrial hum, roaring gas flare, machinery"),
    ("07_summit", "Silhouettes of figures seated around a summit table in a dim room, dramatic backlight through "
                  "large windows, vertical cinematic, highly detailed, 4k",
     "muffled voices, quiet room tone"),
    ("08_handshake", "Two silhouetted figures shaking hands in front of a large glowing world map, dramatic rim "
                     "light, vertical cinematic, highly detailed, 4k",
     "quiet room, soft ambience, single camera shutter"),
]

NARRATION = ("Across Africa, a new struggle is unfolding. The world's great powers, from Washington to Beijing to "
             "Moscow, are racing for the continent's minerals, its markets, and its loyalty. South Africa sits at "
             "the center, balancing old alliances against a shifting global order. The choices made here could tip "
             "the balance of power for decades. Africa is no longer the periphery. It is the prize.")

TICKER = "Global powers compete for Africa's minerals and influence  \u2022  South Africa balances a shifting world order"


def _submit(ep, p):
    r = requests.post(f"{ep}/run", headers=H, json={"input": p}, timeout=90); return r.json().get("id")


def _poll(ep, job, budget, label=""):
    t0 = time.time(); last = None
    while time.time() - t0 < budget:
        time.sleep(12)
        s = requests.get(f"{ep}/status/{job}", headers=H, timeout=30).json(); st = s.get("status")
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
        print(f"  [{name}] LTX", flush=True)
        job = _submit(EP_LTX, {"prompt": prompt, "negative_prompt": NEG, "width": W, "height": HGT,
                               "num_frames": 97, "seed": 7})
        res = _poll(EP_LTX, job, 3000, f"{name} ") if job else None
        if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("video_base64"):
            f.write_bytes(base64.b64decode(res["output"]["video_base64"])); paths.append(f)
            print(f"    saved {name}", flush=True)
        else:
            print(f"    {name} FAILED", flush=True); paths.append(None)
    return paths


def gen_foley(paths):
    out = []
    for (name, _, fp), p in zip(SHOTS, paths):
        if not p:
            out.append(None); continue
        print(f"  [{name}] foley", flush=True)
        try:
            job = _submit(EP_FOLEY, {"video": base64.b64encode(Path(p).read_bytes()).decode(), "prompt": fp})
            res = _poll(EP_FOLEY, job, 1200, f"{name} ") if job else None
            if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("audio_base64"):
                a = OUT / f"foley_{name}.wav"; a.write_bytes(base64.b64decode(res["output"]["audio_base64"]))
                out.append(str(a)); print(f"    ok {name}", flush=True)
            else:
                out.append(None); print(f"    {name} foley failed", flush=True)
        except Exception as e:
            out.append(None); print(f"    {name} err {e}", flush=True)
    return out


def gen_music():
    job = _submit(EP_MUSIC, {"prompt": "epic tense afro-cinematic news underscore, deep drums, ominous strings, "
                                       "subtle african percussion, building, 92bpm", "duration": 29})
    res = _poll(EP_MUSIC, job, 600, "music ") if job else None
    if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("audio_base64"):
        f = OUT / "music.wav"; f.write_bytes(base64.b64decode(res["output"]["audio_base64"])); return f
    return None


def gen_caps(wav):
    job = _submit(EP_WHISPER, {"audio_base64": base64.b64encode(Path(wav).read_bytes()).decode()})
    res = _poll(EP_WHISPER, job, 400, "whisper ") if job else None
    return (res.get("output") or {}).get("words") or [] if res and res.get("status") == "COMPLETED" else []


async def kokoro(text, wav):
    from modules.voice_generator import generate_voice_kokoro
    mp3 = OUT / "narration.mp3"
    await generate_voice_kokoro(text, mp3, voice="am_onyx", speed=1.0)
    subprocess.run([_ff(), "-y", "-i", str(mp3), str(wav)], capture_output=True)


def main():
    print("=== AFRICA REEL ===", flush=True)
    print("[1] shots", flush=True); paths = gen_shots()
    print("[2] foley", flush=True); audios = gen_foley(paths)
    print("[3] voice", flush=True); wav = OUT / "narration.wav"; asyncio.run(kokoro(NARRATION, wav))
    print("[4] music", flush=True); music = gen_music()
    print("[5] captions", flush=True); words = gen_caps(wav)
    print("[6] assemble", flush=True)
    from assemble_full import assemble
    clips = [p for p in paths if p]
    shot_aud = [a for a, p in zip(audios, paths) if p]
    final = assemble(clips, str(wav), music, words, NARRATION, OUT, W, HGT, FPS, target=30.0,
                     flags=("ZA", "CN"), lowerthird_label="South Africa at the crossroads",
                     ticker=TICKER, live=True, tag_text="AI", shot_audios=shot_aud)
    dest = Path(r"C:\Users\PenuelM\Desktop\AI_Videos\reel_africa.mp4")
    subprocess.run([_ff(), "-y", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(dest)], capture_output=True)
    print(f"DONE -> {dest}", flush=True)


if __name__ == "__main__":
    main()
