"""Kie.ai Veo 3 client — cheapest access to Google Veo 3 (cinematic video WITH native audio:
dialogue, ambient, music, all generated together). Async createTask -> poll -> download.

Setup: create an account at https://kie.ai, add a few dollars of credit, copy your API key,
and put it in .env as  KIE_API_KEY=xxxxx

    from modules.veo_kie import generate_veo
    generate_veo("A lion and a tiger talking in a jungle...", "clip.mp4",
                 model="veo3_fast", aspect="9:16", resolution="720p", duration=8)
"""
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://api.kie.ai/api/v1/veo"
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"


def _key():
    k = os.getenv("KIE_API_KEY", "")
    if not k:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("KIE_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"')
                    break
    return k


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def _post(url, payload, key):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": _UA}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def _get(url, key):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": _UA},
                                 method="GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def upload_image(path, upload_path="wildminds"):
    """Base64-upload a local image to Kie's file host; return its public fileUrl (expires ~3 days)."""
    import base64
    import mimetypes
    key = _key()
    if not key:
        raise RuntimeError("KIE_API_KEY not set")
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    payload = {"base64Data": f"data:{mime};base64,{b64}",
               "uploadPath": upload_path, "fileName": Path(path).name}
    r = _post(UPLOAD_URL, payload, key)
    d = r.get("data") if isinstance(r.get("data"), dict) else r
    url = (d or {}).get("fileUrl") or (d or {}).get("downloadUrl")
    if not url:
        raise RuntimeError(f"image upload failed: {r}")
    print(f"[Veo] uploaded reference -> {url}", flush=True)
    return url


def estimate_cost(model, duration, resolution="720p"):
    per_sec = {"veo3_fast": 0.15, "veo3_lite": 0.10, "veo3": 0.40}.get(model, 0.15)
    return per_sec * duration


def generate_veo(prompt, out_path, model="veo3_fast", aspect="9:16", resolution="720p",
                 duration=8, image_urls=None, generation_type=None, timeout=900, poll=12):
    """Generate one Veo 3 clip and download it. Returns out_path. Raises on failure.
    Pass image_urls + generation_type='REFERENCE_2_VIDEO' to lock characters to a reference image."""
    key = _key()
    if not key:
        raise RuntimeError("KIE_API_KEY not set — add it to .env (sign up + add credit at https://kie.ai)")
    body = {"prompt": prompt, "model": model, "aspect_ratio": aspect,
            "resolution": resolution, "duration": duration}
    if image_urls:
        body["imageUrls"] = image_urls if isinstance(image_urls, list) else [image_urls]
    if generation_type:
        body["generationType"] = generation_type
    r = _post(f"{BASE}/generate", body, key)
    if r.get("code") != 200:
        raise RuntimeError(f"Veo create failed: code={r.get('code')} msg={r.get('msg')}")
    task = r["data"]["taskId"]
    print(f"[Veo] task {task} submitted ({model}, {resolution}, {duration}s, {aspect}) "
          f"~${estimate_cost(model, duration):.2f}", flush=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll)
        s = _get(f"{BASE}/record-info?taskId={task}", key)
        d = s.get("data") or {}
        flag = d.get("successFlag")
        if flag == 1:
            resp = d.get("response") or {}
            urls = resp.get("resultUrls") or d.get("resultUrls")
            if isinstance(urls, str):
                urls = json.loads(urls)
            if not urls:
                raise RuntimeError(f"Veo completed but no result URL: {d}")
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            _ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120 Safari/537.36")
            dl = urllib.request.Request(urls[0], headers={"User-Agent": _ua})
            with urllib.request.urlopen(dl, timeout=180) as resp, open(out_path, "wb") as f:
                f.write(resp.read())
            print(f"[Veo] done ({time.time()-t0:.0f}s) -> {out_path}", flush=True)
            return str(out_path)
        if flag in (2, 3):
            raise RuntimeError(f"Veo generation failed: {d.get('errorMessage') or d}")
        print(f"[Veo] ...still rendering ({time.time()-t0:.0f}s)", flush=True)
    raise RuntimeError("Veo timed out")


def check_key():
    """Quick sanity: is the key present? (Does not spend credit.)"""
    return bool(_key())
