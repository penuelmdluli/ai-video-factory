"""
WaveSpeed AI — serverless image-to-video (sharp, cloud GPU).

Solves the Turing/2080-Ti problem: clips render on WaveSpeed's cloud GPUs with
top models (Wan 2.2, Seedance 2.0), then we download the finished MP4.

Models (endpoint after /api/v3/):
  wan22-i2v-720p  : wavespeed-ai/wan-2.2/image-to-video  (720p 5s ~$0.30, 480p ~$0.15)
  seedance-i2v    : bytedance/seedance-2.0/image-to-video (premium, ~$0.70/5s 720p)

Docs: base https://api.wavespeed.ai/api/v3 ; Bearer auth ; POST model -> poll
      /predictions/{id}/result until status=completed -> data.outputs[0] is the mp4 URL.
"""
import base64
import os
import time
from pathlib import Path

import requests

BASE = "https://api.wavespeed.ai/api/v3"

MODELS = {
    "wan22": "wavespeed-ai/wan-2.2/image-to-video",
    "seedance": "bytedance/seedance-2.0/image-to-video",
}

# USD cost per 5s clip by model+resolution (WaveSpeed published rates).
COST = {
    ("wan22", "480p"): 0.15, ("wan22", "720p"): 0.30,
    ("seedance", "720p"): 0.70, ("seedance", "1080p"): 0.75,
}

# ── Monthly budget cap (spend tracked in output/wavespeed_spend.json) ──
_SPEND_FILE = Path("output/wavespeed_spend.json")


def _month_key(ts_iso: str = "") -> str:
    # YYYY-MM — pass an ISO timestamp; caller supplies it (no Date.now in scripts).
    return (ts_iso or "")[:7]


def monthly_budget() -> float:
    return float(os.getenv("WAVESPEED_MONTHLY_BUDGET", "60"))


def spent_this_month(now_iso: str) -> float:
    try:
        import json
        data = json.loads(_SPEND_FILE.read_text())
        return float(data.get(_month_key(now_iso), 0.0))
    except Exception:
        return 0.0


def _record_spend(cost: float, now_iso: str):
    import json
    try:
        data = json.loads(_SPEND_FILE.read_text()) if _SPEND_FILE.exists() else {}
    except Exception:
        data = {}
    mk = _month_key(now_iso)
    data[mk] = round(float(data.get(mk, 0.0)) + cost, 4)
    _SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SPEND_FILE.write_text(json.dumps(data, indent=2))


def can_afford(model: str, resolution: str, now_iso: str) -> bool:
    cost = COST.get((model, resolution), 0.30)
    return spent_this_month(now_iso) + cost <= monthly_budget()


def _key() -> str:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    return os.getenv("WAVESPEED_API_KEY", "")


def _image_to_data_uri(image_path: str) -> str:
    p = Path(image_path)
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def generate(
    image_path: str,
    output_path: str,
    prompt: str = "",
    model: str = "wan22",
    resolution: str = "720p",
    duration: int = 5,
    poll_timeout: int = 300,
) -> str | None:
    """Generate one i2v clip on WaveSpeed. Returns output path or None."""
    # Spend gate. The budget is reserved for the Penuel Mdluli profile's dance
    # pipeline (owner call 2026-09-02); everything else must fall back to stock.
    # This sits ABOVE the budget check on purpose - "can we afford it" is the
    # wrong question when the money is not ours to spend.
    from modules.wavespeed_guard import check as _spend_check
    _spend_check(f"i2v clip -> {output_path}")

    key = _key()
    if not key:
        print("[WaveSpeed] WAVESPEED_API_KEY not set")
        return None

    from datetime import datetime
    now_iso = datetime.now().isoformat()
    if not can_afford(model, resolution, now_iso):
        print(f"[WaveSpeed] Monthly budget ${monthly_budget():.0f} reached "
              f"(spent ${spent_this_month(now_iso):.2f}) — falling back to stock")
        return None

    endpoint = f"{BASE}/{MODELS.get(model, MODELS['wan22'])}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "prompt": prompt or "cinematic real footage, natural motion, sharp focus",
        "image": _image_to_data_uri(image_path),
        "resolution": resolution,
        "duration": duration,
        "seed": -1,
    }

    # ── Submit ──
    r = requests.post(endpoint, headers=headers, json=body, timeout=60)
    if r.status_code != 200:
        print(f"[WaveSpeed] Submit failed {r.status_code}: {r.text[:300]}")
        return None
    data = r.json().get("data", {})
    task_id = data.get("id")
    get_url = data.get("urls", {}).get("get") or f"{BASE}/predictions/{task_id}/result"
    print(f"[WaveSpeed] Submitted {model} {resolution} {duration}s — task {task_id}")

    # ── Poll ──
    t0 = time.time()
    while time.time() - t0 < poll_timeout:
        time.sleep(3)
        pr = requests.get(get_url, headers=headers, timeout=30)
        if pr.status_code != 200:
            continue
        pdata = pr.json().get("data", {})
        status = pdata.get("status")
        if status == "completed":
            outputs = pdata.get("outputs") or []
            if not outputs:
                print("[WaveSpeed] Completed but no outputs")
                return None
            video_url = outputs[0]
            # ── Download ──
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            dl = requests.get(video_url, timeout=120)
            if dl.status_code == 200:
                out.write_bytes(dl.content)
                mb = out.stat().st_size / 1e6
                _record_spend(COST.get((model, resolution), 0.30), now_iso)
                print(f"[WaveSpeed] Done in {time.time()-t0:.0f}s -> {out.name} ({mb:.1f}MB) "
                      f"| month spend ${spent_this_month(now_iso):.2f}/${monthly_budget():.0f}")
                return str(out)
            print(f"[WaveSpeed] Download failed {dl.status_code}")
            return None
        if status in ("failed", "error"):
            print(f"[WaveSpeed] Job failed: {pdata.get('error') or pdata}")
            return None
    print("[WaveSpeed] Poll timeout")
    return None


if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else "cogvideo-pipeline/test_input.png"
    mdl = sys.argv[2] if len(sys.argv) > 2 else "wan22"
    out = Path("logs") / f"wavespeed_{mdl}_test.mp4"
    print(f"WaveSpeed test: {img} via {mdl} -> {out}")
    r = generate(img, str(out),
                 prompt="handheld war footage, soldiers moving through smoke, explosions, drifting camera, real combat",
                 model=mdl, resolution="720p", duration=5)
    print("RESULT:", r)
