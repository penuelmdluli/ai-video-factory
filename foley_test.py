"""Test HunyuanVideo-Foley: send an LTX shot + text hint -> synced sound."""
import base64, time, json
from pathlib import Path
import requests

key = ""
for line in open(r"C:\Users\PenuelM\Documents\ai-video-factory\.env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        key = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
BASE = "https://api.runpod.ai/v2/5arzy0p1wnm229"
CLIP = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\warpost\02_tracking.mp4")
OUT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory\output\foley"); OUT.mkdir(parents=True, exist_ok=True)

vid_b64 = base64.b64encode(CLIP.read_bytes()).decode()
payload = {"input": {"video": vid_b64, "prompt": "naval ship engine rumble, ocean waves, water spray, wind"}}
print("submitting foley job (first run downloads ~13GB model to volume)...", flush=True)
r = requests.post(f"{BASE}/run", headers=H, json=payload, timeout=60)
job = r.json().get("id")
if not job:
    print("submit fail:", r.text[:300], flush=True); raise SystemExit
print("job:", job, flush=True)
t0 = time.time(); last = None
while time.time() - t0 < 1400:
    time.sleep(15)
    s = requests.get(f"{BASE}/status/{job}", headers=H, timeout=30).json()
    st = s.get("status")
    if st != last: print(f"[{int(time.time()-t0)}s] {st}", flush=True); last = st
    if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
        gpu = (s.get("executionTime") or 0)/1000
        out = s.get("output") or {}
        if st == "COMPLETED" and out.get("audio_base64"):
            f = OUT / "foley_02_tracking.wav"
            f.write_bytes(base64.b64decode(out["audio_base64"]))
            print(f"SAVED {f} ({f.stat().st_size/1e6:.2f}MB) sr={out.get('sample_rate')} dur={out.get('duration')} gpu={gpu:.0f}s => FOLEY WORKS", flush=True)
        else:
            print(f"{st} gpu={gpu:.0f}s: {json.dumps(out)[:900]}", flush=True)
        break
print("done", flush=True)
