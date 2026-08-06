"""Submit one RunPod job and watch status + worker health live to capture the failure reason."""
import os, sys, time, json
import requests
from dotenv import load_dotenv
load_dotenv(override=True)
K = os.getenv("RUNPOD_API_KEY"); E = os.getenv("RUNPOD_ENDPOINT_ID")
H = {"Authorization": f"Bearer {K}", "Content-Type": "application/json"}
base = f"https://api.runpod.ai/v2/{E}"

from modules.runpod_video import _build_workflow
wf = _build_workflow("intense war action, explosion, smoke, fast motion",
                     "blurry, low quality, static", 12345, 480, 832, 80)

r = requests.post(f"{base}/run", headers=H, json={"input": {"workflow": wf}}, timeout=60)
print("SUBMIT:", r.status_code, r.text[:300], flush=True)
if r.status_code != 200:
    sys.exit(1)
job = r.json().get("id")
print("JOB:", job, flush=True)

t0 = time.time()
last = None
while time.time() - t0 < 300:
    time.sleep(6)
    s = requests.get(f"{base}/status/{job}", headers=H, timeout=30).json()
    st = s.get("status")
    h = requests.get(f"{base}/health", headers=H, timeout=20).json().get("workers", {})
    line = f"[{int(time.time()-t0):>3}s] status={st} workers={h}"
    if line != last:
        print(line, flush=True)
        last = line
    if st in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
        print("FINAL:", json.dumps(s)[:1200], flush=True)
        break
else:
    print("Gave up after 300s (still queued/running)", flush=True)
