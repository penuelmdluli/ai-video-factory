"""
RunPod serverless video generation — reuses the EXISTING proven Wan 2.2 endpoint
(dm5mng5h7034q7, "Wan2.2 ksampler", 784 completed runs, RTX 4090 flex, FlashBoot).

This is TEXT-to-video (Wan 2.2 14B fp8) — generates a clip straight from the scene
prompt, no input image. Much cheaper than WaveSpeed: ~$0.02-0.05/clip on a 4090
(billed per GPU-second, scale-to-zero) vs WaveSpeed's $0.15.

Workflow ported from genesis-studio/src/lib/runpod-comfyui.ts (kijai WanVideoWrapper).
Kept as an ALTERNATE backend — WaveSpeed stays default until this is approved.
"""
import base64
import os
import time
from datetime import datetime
from pathlib import Path

import requests

API_BASE = "https://api.runpod.ai/v2"
DEFAULT_ENDPOINT = "dm5mng5h7034q7"          # proven Wan 2.2 T2V endpoint
GPU_RATE_PER_HR = float(os.getenv("RUNPOD_GPU_RATE", "1.10"))  # RTX 4090 flex ~$1.10/hr
_SPEND_FILE = Path("output/runpod_spend.json")


def _cfg():
    from dotenv import load_dotenv
    load_dotenv(override=True)
    return (os.getenv("RUNPOD_API_KEY", ""),
            os.getenv("RUNPOD_ENDPOINT_ID", DEFAULT_ENDPOINT))


def _record_spend(cost: float):
    import json
    mk = datetime.now().isoformat()[:7]
    try:
        data = json.loads(_SPEND_FILE.read_text()) if _SPEND_FILE.exists() else {}
    except Exception:
        data = {}
    data[mk] = round(float(data.get(mk, 0.0)) + cost, 4)
    _SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SPEND_FILE.write_text(json.dumps(data, indent=2))
    return data[mk]


def _build_workflow(prompt, negative_prompt, seed, width, height, frames):
    """kijai WanVideoWrapper Wan 2.2 T2V workflow (ComfyUI API format)."""
    return {
        "1": {"class_type": "WanVideoModelLoader", "inputs": {
            "model": "wan2.1_t2v_14B_fp8.safetensors", "base_precision": "fp16",
            "quantization": "fp8_e4m3fn", "load_device": "offload_device", "attention_mode": "sdpa"}},
        "2": {"class_type": "LoadWanVideoT5TextEncoder", "inputs": {
            "model_name": "umt5-xxl-enc-bf16.safetensors", "precision": "bf16",
            "load_device": "offload_device", "quantization": "disabled"}},
        "3": {"class_type": "WanVideoTextEncode", "inputs": {
            "positive_prompt": prompt, "negative_prompt": negative_prompt,
            "t5": ["2", 0], "force_offload": True, "model_to_offload": ["1", 0]}},
        "4": {"class_type": "WanVideoEmptyEmbeds", "inputs": {
            "width": width, "height": height, "num_frames": frames}},
        "5": {"class_type": "WanVideoSampler", "inputs": {
            "cfg": 6, "shift": 5.0, "steps": 30, "seed": seed,
            "force_offload": True, "scheduler": "unipc", "riflex_freq_index": 0,
            "model": ["1", 0], "text_embeds": ["3", 0], "image_embeds": ["4", 0]}},
        "6": {"class_type": "WanVideoVAELoader", "inputs": {
            "model_name": "Wan2_1_VAE_bf16.safetensors", "precision": "bf16"}},
        "7": {"class_type": "WanVideoDecode", "inputs": {
            "samples": ["5", 0], "vae": ["6", 0], "enable_vae_tiling": False,
            "tile_x": 272, "tile_y": 272,
            "tile_stride_x": 144, "tile_stride_y": 128}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["7", 0], "frame_rate": 16, "loop_count": 0,
            "filename_prefix": "genesis_wan22", "format": "video/h264-mp4",
            "pix_fmt": "yuv420p", "crf": 19, "save_output": True,
            "pingpong": False, "save_metadata": False}},
    }


def _extract_output(output):
    """Return (url, base64) from the worker output."""
    if not isinstance(output, dict):
        return None, None
    # This worker returns {"video": "<base64 mp4>"} (or a URL).
    vid = output.get("video")
    if isinstance(vid, str):
        if vid.startswith("http"):
            return vid, None
        if len(vid) > 100:
            return None, vid
    if isinstance(vid, dict) and isinstance(vid.get("url"), str):
        return vid["url"], None
    imgs = output.get("images")
    if isinstance(imgs, list) and imgs:
        it = imgs[0]
        if isinstance(it, dict):
            if isinstance(it.get("url"), str):
                return it["url"], None
            if isinstance(it.get("data"), str) and len(it["data"]) > 100:
                return None, it["data"]
    msg = output.get("message")
    if isinstance(msg, str) and msg.startswith("http"):
        return msg, None
    return None, None


def generate(output_path, prompt="", width=480, height=832, duration=5,
             seed=None, poll_timeout=600):
    """Generate one T2V clip on RunPod. Returns output path or None.

    poll_timeout defaults to 600s: with scale-to-zero (workersMin=0) the first
    clip of a batch cold-starts the worker, and the current image downloads its
    ~26GB of weights at boot — that alone can take 5-8 min. Warm clips finish in
    ~60-120s. (A models-baked-in image would make cold starts near-instant.)
    """
    key, endpoint = _cfg()
    if not key:
        print("[RunPod] RUNPOD_API_KEY not set")
        return None
    if seed is None:
        seed = int(datetime.now().timestamp()) % 1_000_000
    frames = int(duration) * 16
    neg = "blurry, low quality, deformed, watermark, text, ugly, static, still"
    workflow = _build_workflow(prompt or "cinematic war action, intense motion",
                               neg, seed, width, height, frames)
    H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = f"{API_BASE}/{endpoint}"

    r = requests.post(f"{base}/run", headers=H, json={"input": {"workflow": workflow}}, timeout=60)
    if r.status_code != 200:
        print(f"[RunPod] Submit failed {r.status_code}: {r.text[:300]}")
        return None
    job_id = r.json().get("id")
    print(f"[RunPod] Job {job_id} submitted ({width}x{height}, {frames}f)")

    t0 = time.time()
    while time.time() - t0 < poll_timeout:
        time.sleep(3)
        pr = requests.get(f"{base}/status/{job_id}", headers=H, timeout=30)
        if pr.status_code != 200:
            continue
        d = pr.json()
        st = d.get("status")
        if st == "COMPLETED":
            url, b64 = _extract_output(d.get("output"))
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            if url:
                dl = requests.get(url, timeout=120)
                if dl.status_code != 200:
                    print(f"[RunPod] Download failed {dl.status_code}")
                    return None
                out.write_bytes(dl.content)
            elif b64:
                out.write_bytes(base64.b64decode(b64))
            else:
                print(f"[RunPod] Completed but no output: {str(d.get('output'))[:300]}")
                return None
            exec_ms = d.get("executionTime") or (time.time() - t0) * 1000
            cost = (exec_ms / 1000 / 3600) * GPU_RATE_PER_HR
            month = _record_spend(cost)
            print(f"[RunPod] Done: {out.name} ({out.stat().st_size/1e6:.1f}MB, "
                  f"GPU {exec_ms/1000:.0f}s, ${cost:.4f}) | month ${month:.2f}")
            return str(out)
        if st in ("FAILED", "CANCELLED", "TIMED_OUT"):
            print(f"[RunPod] Job {st}: {str(d.get('error'))[:200]}")
            return None
    print("[RunPod] Poll timeout")
    return None


if __name__ == "__main__":
    import sys
    out = Path("logs/runpod_test.mp4")
    p = sys.argv[1] if len(sys.argv) > 1 else ("intense war action, soldiers running and firing "
        "through smoke, an explosion erupting with flying debris, vehicles speeding, jets overhead, "
        "fast handheld camera, cinematic, everything moving")
    print(f"RunPod T2V test -> {out}")
    print("RESULT:", generate(str(out), prompt=p, duration=5))
