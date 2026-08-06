"""Re-assemble the reel from existing assets with the DRAMA + voice-forward fixes.
Reuses clips + foley + narration + music (no regeneration)."""
import base64, subprocess, sys
from pathlib import Path
import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
CLIPS = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\reel")
A = ROOT / "output" / "reel"
W, HGT, FPS = 704, 1280, 24
KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

ORDER = ["01_soldier", "02_tank", "03_jet", "04_flag", "05_convoy", "06_radar", "07_smoke", "08_map"]
NARRATION = ("Tonight, the world holds its breath. Military forces are mobilizing across multiple fronts as "
             "diplomatic tensions reach a breaking point. Analysts warn the coming days could reshape the global "
             "balance of power. Governments urge calm, but the drums of conflict grow louder. Stay with us as this "
             "story develops.")
TICKER = "Global military tensions escalate across multiple fronts  \u2022  diplomats scramble as forces mobilize"


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def captions(wav):
    b64 = base64.b64encode(Path(wav).read_bytes()).decode()
    r = requests.post("https://api.runpod.ai/v2/5r88ueysbd8tm8/run", headers=H,
                      json={"input": {"audio_base64": b64}}, timeout=60)
    job = r.json().get("id")
    import time
    t0 = time.time()
    while time.time() - t0 < 400:
        time.sleep(10)
        s = requests.get(f"https://api.runpod.ai/v2/5r88ueysbd8tm8/status/{job}", headers=H, timeout=30).json()
        if s.get("status") in ("COMPLETED", "FAILED", "TIMED_OUT"):
            return (s.get("output") or {}).get("words") or [] if s.get("status") == "COMPLETED" else []
    return []


def main():
    from assemble_full import assemble
    clips = [CLIPS / f"{n}.mp4" for n in ORDER if (CLIPS / f"{n}.mp4").exists()]
    foley = [str(A / f"foley_{n}.wav") if (A / f"foley_{n}.wav").exists() else None for n in ORDER]
    foley = [f for f, n in zip(foley, ORDER) if (CLIPS / f"{n}.mp4").exists()]
    wav = A / "narration.wav"
    music = A / "music.wav"
    print(f"{len(clips)} clips, {sum(1 for f in foley if f)} foley, music={'y' if music.exists() else 'n'}", flush=True)
    print("captions...", flush=True); words = captions(wav)
    print(f"{len(words)} words; assembling...", flush=True)
    final = assemble(clips, str(wav), music if music.exists() else None, words, NARRATION, A, W, HGT, FPS,
                     target=28.0, flags=("US", "RU"), lowerthird_label="Global forces on high alert",
                     ticker=TICKER, live=True, tag_text="AI", shot_audios=foley)
    dest = Path(r"C:\Users\PenuelM\Desktop\AI_Videos\reel_tensions_v2.mp4")
    subprocess.run([_ff(), "-y", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(dest)], capture_output=True)
    print(f"DONE -> {dest}", flush=True)


if __name__ == "__main__":
    main()
