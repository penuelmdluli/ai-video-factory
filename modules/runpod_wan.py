"""RunPod serverless Wan 2.2 IMAGE-TO-VIDEO client.

Targets the RunPod Hub template `wlsdml1114/generate_video` (Wan 2.2 with LoRA) —
a simple, self-contained i2v worker (weights bundled, ComfyUI under the hood).
Same public signature as modules/runpod_ltx.generate so the visual_fetcher router
calls it positionally and swaps LTX -> Wan across every channel.

Contract (per the template's API reference):
    POST {EP}/run  {"input": {"prompt","negative_prompt","image_base64",
                              "width","height","length","steps","seed","cfg"}}
    -> COMPLETED output {"video": "data:video/mp4;base64,...."}

Returns the saved mp4 path, or None so the router falls back to LTX -> WaveSpeed
-> stock. Set RUNPOD_WAN_ENDPOINT_ID in .env after deploy; empty = safe no-op.
"""
import os, json, base64, time
from pathlib import Path
from datetime import datetime

import requests

API_BASE = "https://api.runpod.ai/v2"
GPU_RATE_PER_HR = float(os.getenv("RUNPOD_WAN_GPU_RATE", "0.86"))  # L40S flex ~ $0.86/hr
_SPEND_FILE = Path("output/runpod_wan_spend.json")
NEG = "blurry, low quality, deformed, morphing, warping, fog, haze, watermark, text, static, frozen, distorted"


def _env(name):
    v = os.getenv(name, "")
    if v:
        return v
    try:
        for line in (Path(__file__).resolve().parent.parent / ".env").read_text(
                encoding="utf-8", errors="replace").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip("'").strip('"')
    except Exception:
        pass
    return ""


def _record_spend(cost):
    mk = datetime.now().isoformat()[:7]
    try:
        data = json.loads(_SPEND_FILE.read_text()) if _SPEND_FILE.exists() else {}
    except Exception:
        data = {}
    data[mk] = round(float(data.get(mk, 0.0)) + cost, 4)
    _SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SPEND_FILE.write_text(json.dumps(data, indent=2))
    return data[mk]


def _extract_video(output):
    """Template returns {"video": "data:video/mp4;base64,..."} (or a url)."""
    if isinstance(output, dict):
        v = output.get("video") or output.get("mp4")
        if isinstance(v, str):
            if v.startswith("http"):
                return v, None
            if "base64," in v:            # strip data-uri prefix
                v = v.split("base64,", 1)[1]
            if len(v) > 100:
                return None, v
        # some builds nest under images[]
        imgs = output.get("images")
        if isinstance(imgs, list) and imgs and isinstance(imgs[0], dict):
            it = imgs[0]
            if isinstance(it.get("url"), str):
                return it["url"], None
            data = it.get("data") or it.get("image")
            if isinstance(data, str) and len(data) > 100:
                return None, data.split("base64,", 1)[-1]
    return None, None


def generate(image_path, output_path, prompt, width=832, height=480,
             num_frames=81, steps=10, seed=7, timeout=900, cfg=2.0):
    """Animate a still on the Wan 2.2 i2v endpoint. Returns mp4 path or None.
    Signature-compatible with runpod_ltx.generate. `steps` is clamped to >=8
    because this template is NOT the 4-step Lightning build by default."""
    key = _env("RUNPOD_API_KEY")
    ep = _env("RUNPOD_WAN_ENDPOINT_ID")
    if not key or not ep:
        return None                       # not provisioned -> safe no-op, router falls back
    steps = max(8, int(steps))
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    H = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    base = f"{API_BASE}/{ep}"
    body = {"input": {
        "prompt": prompt or "cinematic scene, natural motion",
        "negative_prompt": NEG,
        "image_base64": b64,   # raw base64 — this handler b64decodes it directly (no data-uri prefix)
        "width": int(width), "height": int(height), "length": int(num_frames),
        "steps": int(steps), "seed": int(seed), "cfg": float(cfg)}}
    try:
        r = requests.post(f"{base}/run", headers=H, json=body, timeout=90)
    except Exception as e:
        print(f"[RunPodWan] submit error: {e}"); return None
    if r.status_code != 200:
        print(f"[RunPodWan] submit {r.status_code}: {r.text[:200]}"); return None
    jid = r.json().get("id")
    if not jid:
        print("[RunPodWan] no job id"); return None
    print(f"[RunPodWan] job {jid} submitted ({width}x{height}, {num_frames}f, {steps} steps)")

    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(10)
        try:
            s = requests.get(f"{base}/status/{jid}", headers=H, timeout=30).json()
        except Exception:
            continue
        st = s.get("status")
        if st == "COMPLETED":
            url, vb64 = _extract_video(s.get("output"))
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            if url:
                dl = requests.get(url, timeout=180)
                if dl.status_code != 200:
                    print(f"[RunPodWan] download {dl.status_code}"); return None
                out.write_bytes(dl.content)
            elif vb64:
                try:
                    out.write_bytes(base64.b64decode(vb64))
                except Exception as e:
                    print(f"[RunPodWan] decode error: {e}"); return None
            else:
                print(f"[RunPodWan] COMPLETED but no video in output: {str(s.get('output'))[:300]}")
                return None
            exec_ms = s.get("executionTime") or (time.time() - t0) * 1000
            cost = (exec_ms / 1000 / 3600) * GPU_RATE_PER_HR
            month = _record_spend(cost)
            print(f"[RunPodWan] done: {out.name} ({out.stat().st_size/1e6:.1f}MB, "
                  f"GPU {exec_ms/1000:.0f}s, ${cost:.4f}) | month ${month:.2f}")
            return str(out)
        if st in ("FAILED", "TIMED_OUT", "CANCELLED"):
            print(f"[RunPodWan] job {st}: {str(s.get('error'))[:200]}"); return None
    print("[RunPodWan] poll timeout"); return None


if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else "test.png"
    out = sys.argv[2] if len(sys.argv) > 2 else "logs/runpod_wan_test.mp4"
    print("RESULT:", generate(img, out, "a cinematic scene, camera slowly pushing in, natural motion",
                              640, 1152, 81, 10))
