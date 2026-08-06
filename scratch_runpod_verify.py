"""Autonomous RunPod verification with the corrected workflow.
Un-pauses, WAITS for propagation (retries submit on 409), polls, downloads,
and ALWAYS re-pauses (finally) so a failure can't leave a worker billing.
"""
import os, time, base64, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)
K = os.getenv("RUNPOD_API_KEY"); E = os.getenv("RUNPOD_ENDPOINT_ID")
RH = {"Authorization": f"Bearer {K}", "Content-Type": "application/json"}
REST = f"https://rest.runpod.io/v1/endpoints/{E}"
V2 = f"https://api.runpod.ai/v2/{E}"

def set_max(n):
    r = requests.patch(REST, headers=RH, json={"workersMax": n}, timeout=30)
    now = requests.get(REST, headers=RH, timeout=20).json().get("workersMax")
    print(f"[endpoint] set workersMax={n} -> now {now} (http {r.status_code})", flush=True)

try:
    set_max(1)
    from modules.runpod_video import _build_workflow, _extract_output
    neg = "blurry, low quality, deformed, watermark, text, ugly, static, still"
    wf = _build_workflow("intense war action, soldiers running and firing through smoke, "
                         "an explosion erupting with flying debris, vehicles speeding, jets "
                         "overhead, fast handheld camera, cinematic, everything moving",
                         neg, 424242, 480, 832, 80)

    # Submit with retry until the run-queue sees the un-pause (409 propagation lag).
    job = None
    for i in range(30):  # up to ~5 min of retries
        r = requests.post(f"{V2}/run", headers=RH, json={"input": {"workflow": wf}}, timeout=60)
        if r.status_code == 200:
            job = r.json().get("id"); print(f"[submit] accepted job {job}", flush=True); break
        print(f"[submit] attempt {i+1}: {r.status_code} {r.text[:120]}", flush=True)
        time.sleep(10)
    if not job:
        raise SystemExit("submit never accepted")

    t0 = time.time(); last = None
    while time.time() - t0 < 900:
        time.sleep(8)
        s = requests.get(f"{V2}/status/{job}", headers=RH, timeout=30).json()
        st = s.get("status")
        if st != last:
            print(f"[{int(time.time()-t0):>3}s] status={st}", flush=True); last = st
        if st == "COMPLETED":
            url, b64 = _extract_output(s.get("output"))
            out = Path("logs/runpod_verify.mp4"); out.parent.mkdir(parents=True, exist_ok=True)
            if url:
                out.write_bytes(requests.get(url, timeout=120).content)
            elif b64:
                out.write_bytes(base64.b64decode(b64))
            else:
                print("COMPLETED but no output:", str(s.get("output"))[:400], flush=True); break
            print(f"SUCCESS: {out} ({out.stat().st_size} bytes, execTime {s.get('executionTime')}ms)", flush=True)
            break
        if st in ("FAILED", "CANCELLED", "TIMED_OUT"):
            print("FAILED:", str(s.get("error"))[:600], flush=True); break
    else:
        print("poll timeout (still running/queued at 900s)", flush=True)
finally:
    set_max(0)
    print("[cleanup] endpoint re-paused (workersMax=0)", flush=True)
