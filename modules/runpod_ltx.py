"""RunPod LTX image-to-video client (endpoint mp2awqavthuc2b).

The cheap video rail: FLUX/SDXL still -> sharp animated clip for ~$0.02-0.05
vs WaveSpeed's ~$0.15. Same endpoint the Zuzu pipeline uses. Send an image and
it does i2v; returns the saved mp4 path or None.
"""
import os, base64, time, requests
from pathlib import Path

EP = "https://api.runpod.ai/v2/mp2awqavthuc2b"

def _key():
    k = os.getenv("RUNPOD_API_KEY", "")
    if k:
        return k
    try:
        for line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
            if line.startswith("RUNPOD_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'").strip('"')
    except Exception:
        pass
    return ""

def generate(image_path, output_path, prompt, width=832, height=480,
             num_frames=97, steps=40, seed=7, timeout=900):
    # SPEND GATE. The RunPod credit is dedicated to the 85K profile's dancing
    # pipeline (owner call 2026-08-30); everything else degrades to its local
    # path rather than billing against it. See modules/runpod_guard.py.
    from modules.runpod_guard import is_allowed
    if not is_allowed():
        print("[RunPodLTX] blocked - RunPod credit is reserved for the profile "
              "dancing pipeline (set RUNPOD_PURPOSE=dance to allow)")
        return None

    key = _key()
    if not key:
        print("[RunPodLTX] no RUNPOD_API_KEY"); return None
    H = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    payload = {"image": b64, "prompt": prompt,
               "negative_prompt": "blurry, distortion, warping, morphing, deformed, static, frozen",
               "width": int(width), "height": int(height),
               "num_frames": int(num_frames), "fps": 24, "steps": int(steps), "seed": int(seed)}
    try:
        jid = requests.post(f"{EP}/run", headers=H, json={"input": payload}, timeout=90).json().get("id")
    except Exception as e:
        print(f"[RunPodLTX] submit error: {e}"); return None
    if not jid:
        return None
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(10)
        try:
            s = requests.get(f"{EP}/status/{jid}", headers=H, timeout=30).json()
        except Exception:
            continue
        st = s.get("status")
        if st == "COMPLETED":
            o = s.get("output") or {}
            if o.get("video_base64"):
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(base64.b64decode(o["video_base64"]))
                return str(output_path)
            return None
        if st in ("FAILED", "TIMED_OUT", "CANCELLED"):
            print(f"[RunPodLTX] job {st}"); return None
    print("[RunPodLTX] timeout"); return None
