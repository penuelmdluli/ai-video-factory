"""WAR action reel — LTX combat stress test. New cheap setup: NO foley, smooth
zoom, music from library. Build only (review before posting)."""
import asyncio, base64, subprocess, time, sys
from pathlib import Path
import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
OUTC = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\reel_war"); OUTC.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "output" / "reel_war"; OUT.mkdir(parents=True, exist_ok=True)
KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
EP_LTX = "https://api.runpod.ai/v2/mp2awqavthuc2b"
EP_WHISPER = "https://api.runpod.ai/v2/5r88ueysbd8tm8"
W, HGT, FPS = 704, 1280, 24
NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted, warped faces, extra limbs, "
       "text artifacts, watermark, low resolution, flickering, morphing")

SHOTS = [
    ("01_squad", "A squad of soldiers sprinting through thick smoke and firing rifles, bright muzzle flashes, "
                 "chaos, handheld shaky cam, photorealistic, dynamic motion, cinematic, 4k"),
    ("02_tank", "A battle tank firing its main cannon, huge muzzle blast and shockwave, debris flying, fast "
                "tracking shot, photorealistic, dynamic motion, cinematic, 4k"),
    ("03_blast", "A massive explosion erupting across a battlefield at dusk, fireball and flying debris, "
                 "shockwave rippling, photorealistic, dynamic motion, cinematic, 4k"),
    ("04_jet", "A fighter jet screaming low over a warzone firing missiles, banking hard, afterburner glow, "
               "fast, photorealistic, dynamic motion, cinematic, 4k"),
    ("05_heli", "A military helicopter swooping low over a desert warzone kicking up a dust storm, fast, "
                "photorealistic, dynamic motion, handheld, cinematic, 4k"),
    ("06_convoy", "An armored convoy speeding through a war-torn city street, smoke and rubble everywhere, "
                  "fast tracking shot, photorealistic, dynamic motion, cinematic, 4k"),
    ("07_tracers", "A night battlefield with streaking tracer fire and flashing explosions lighting the sky, "
                   "chaotic, photorealistic, dynamic motion, cinematic, 4k"),
    ("08_trench", "A lone soldier running through a muddy trench under fire, dirt kicking up around him, "
                  "handheld shaky cam, intense, photorealistic, dynamic motion, cinematic, 4k"),
]
NARRATION = ("Breaking tonight. Fierce fighting has erupted as forces clash on multiple fronts. Explosions light "
             "the night sky while troops advance under heavy fire. Civilians flee as the conflict escalates by the "
             "hour. World leaders scramble for calm, but on the ground, the battle rages on.")
TICKER = "Fierce fighting erupts on multiple fronts  \u2022  forces clash as the conflict escalates by the hour"


def _sub(ep, p):
    return requests.post(f"{ep}/run", headers=H, json={"input": p}, timeout=90).json().get("id")


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


def main():
    print("=== WAR REEL (LTX combat test) ===", flush=True)
    print("[1] shots", flush=True)
    paths = []
    for name, prompt in SHOTS:
        f = OUTC / f"{name}.mp4"
        if f.exists() and f.stat().st_size > 50_000:
            print(f"  {name} reuse", flush=True); paths.append(f); continue
        print(f"  {name}", flush=True)
        job = _sub(EP_LTX, {"prompt": prompt, "negative_prompt": NEG, "width": W, "height": HGT,
                            "num_frames": 97, "seed": 7})
        res = _poll(EP_LTX, job, 3000, f"{name} ") if job else None
        if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("video_base64"):
            f.write_bytes(base64.b64decode(res["output"]["video_base64"])); paths.append(f)
        else:
            paths.append(None)

    print("[2] voice (Kokoro am_onyx)", flush=True)
    from modules.voice_generator import generate_voice_kokoro
    wav = OUT / "narration.wav"; mp3 = OUT / "narration.mp3"
    asyncio.run(generate_voice_kokoro(NARRATION, mp3, voice="am_onyx", speed=1.0))
    subprocess.run([_ff(), "-y", "-i", str(mp3), str(wav)], capture_output=True)

    print("[3] music (library — free)", flush=True)
    from music_library import get_music_bed
    music = get_music_bed()

    print("[4] captions", flush=True)
    wj = _sub(EP_WHISPER, {"audio_base64": base64.b64encode(wav.read_bytes()).decode()})
    wres = _poll(EP_WHISPER, wj, 400, "whisper ") if wj else None
    words = (wres.get("output") or {}).get("words") or [] if wres and wres.get("status") == "COMPLETED" else []

    print("[5] assemble (no foley, smooth zoom)", flush=True)
    from assemble_full import assemble
    clips = [p for p in paths if p]
    final = assemble(clips, str(wav), str(music) if music else None, words, NARRATION, OUT, W, HGT, FPS,
                     target=28.0, flags=("US", "RU"), lowerthird_label="Conflict escalates",
                     ticker=TICKER, live=True, tag_text="AI", shot_audios=None)
    dest = Path(r"C:\Users\PenuelM\Desktop\AI_Videos\reel_war_test.mp4")
    subprocess.run([_ff(), "-y", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(dest)], capture_output=True)
    print(f"DONE -> {dest}", flush=True)


if __name__ == "__main__":
    main()
