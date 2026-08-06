"""Test EchoMimicV3: anchor image + Kokoro voice -> gesturing talking presenter."""
import base64, time, json, subprocess
from pathlib import Path
import requests, imageio_ffmpeg

key = ""
for line in open(r"C:\Users\PenuelM\Documents\ai-video-factory\.env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        key = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
BASE = "https://api.runpod.ai/v2/k526wl5smcg7h5"
IMG = Path(r"C:\Users\PenuelM\Documents\ai-video-factory\assets\presenters\anchor_halfbody.png")
AUD_SRC = Path(r"C:\Users\PenuelM\Documents\ai-video-factory\output\full_video\narration_cbox.wav")
OUT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory\output\presenter"); OUT.mkdir(parents=True, exist_ok=True)

# trim audio to ~6s for a fast first validation (avoids long-clip RIFLEx uncertainty)
ff = imageio_ffmpeg.get_ffmpeg_exe()
AUD = OUT / "voice_6s.wav"
subprocess.run([ff, "-y", "-i", str(AUD_SRC), "-t", "6", str(AUD)], capture_output=True)

payload = {"input": {
    "image": base64.b64encode(IMG.read_bytes()).decode(),
    "audio": base64.b64encode(AUD.read_bytes()).decode(),
    "prompt": "A professional news anchor speaking to camera, natural hand gestures",
}}
print("submitting presenter job (first run downloads ~24GB model to volume)...", flush=True)
r = requests.post(f"{BASE}/run", headers=H, json=payload, timeout=90)
job = r.json().get("id")
if not job:
    print("submit fail:", r.text[:300], flush=True); raise SystemExit
print("job:", job, flush=True)
t0 = time.time(); last = None
while time.time() - t0 < 1800:
    time.sleep(15)
    s = requests.get(f"{BASE}/status/{job}", headers=H, timeout=30).json()
    st = s.get("status")
    if st != last: print(f"[{int(time.time()-t0)}s] {st}", flush=True); last = st
    if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
        gpu = (s.get("executionTime") or 0)/1000
        out = s.get("output") or {}
        if st == "COMPLETED" and out.get("video_base64"):
            f = OUT / "presenter_test.mp4"
            f.write_bytes(base64.b64decode(out["video_base64"]))
            print(f"SAVED {f} ({f.stat().st_size/1e6:.2f}MB) gpu={gpu:.0f}s => PRESENTER WORKS", flush=True)
        else:
            print(f"{st} gpu={gpu:.0f}s: {json.dumps(out)[:1200]}", flush=True)
        break
print("done", flush=True)
