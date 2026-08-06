"""
RunPod Serverless handler for HunyuanVideo-Foley (Tencent).

Video-to-audio / neural Foley: takes a short mp4 clip (+ optional text hint)
and generates a realistic, temporally-synchronized soundtrack (gunshot on the
muzzle flash, engine hum, footsteps, ocean waves ...).

Contract (matches our other workers):
  event["input"]:
    video        REQUIRED  base64 / data-uri / http(s) url of an mp4 clip
    prompt       optional  positive text hint ("gunshot, ship engine, waves")
    neg_prompt   optional  negative text hint
    guidance     optional  CFG scale (repo default 4.5, range ~1-10)
    steps        optional  diffusion steps (repo default 50, range ~10-100)
    seed         optional  int; default 1 (repo default)
    model_size   optional  "xxl" (default) or "xl"
    return_video optional  bool; if true also return muxed mp4 (video+audio)

  success -> {"audio_base64", "sample_rate", "duration", "seconds"[, "video_base64"]}
  failure -> {"error", "trace"}
"""

import os
import sys
import time
import base64
import tempfile
import traceback
import subprocess

# --- Force every cache onto the network volume BEFORE importing torch/transformers.
# (Dockerfile already sets these; we re-assert in case the worker overrides env.)
os.environ.setdefault("HF_HOME", "/runpod-volume/hf")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", "/runpod-volume/hf/hub")
os.environ.setdefault("TORCH_HOME", "/runpod-volume/torch")

MODEL_DIR = os.environ.get("FOLEY_MODEL_DIR", "/runpod-volume/models/hunyuanvideo-foley")
REPO_DIR = os.environ.get("FOLEY_REPO_DIR", "/app/HunyuanVideo-Foley")

# Make the repo importable (belt-and-suspenders; PYTHONPATH is set in Dockerfile).
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

for _d in (os.environ["HF_HOME"], os.environ["HUGGINGFACE_HUB_CACHE"],
           os.environ["TORCH_HOME"], MODEL_DIR):
    os.makedirs(_d, exist_ok=True)

import runpod
import torch
import torchaudio
import urllib.request

# Lazily-initialized globals so the model is loaded ONCE per warm worker.
_MODEL = None            # (model_dict, cfg)
_MODEL_SIZE = None       # which variant is currently loaded
_SAMPLE_RATE = None      # cached from first denoise (48000 for this model)


# --------------------------------------------------------------------------- #
# Input helpers (copied from our other handlers' _save style)                  #
# --------------------------------------------------------------------------- #
def _save(data_or_url, suffix, workdir):
    """Materialize base64 / data-uri / http(s) url into a temp file. Returns path."""
    path = os.path.join(workdir, f"input{suffix}")

    if isinstance(data_or_url, (bytes, bytearray)):
        with open(path, "wb") as f:
            f.write(data_or_url)
        return path

    s = str(data_or_url).strip()

    # http(s) url
    if s.startswith("http://") or s.startswith("https://"):
        req = urllib.request.Request(s, headers={"User-Agent": "foley-worker/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(path, "wb") as f:
            f.write(resp.read())
        return path

    # data-uri: strip the "data:...;base64," prefix
    if s.startswith("data:"):
        s = s.split(",", 1)[1]

    with open(path, "wb") as f:
        f.write(base64.b64decode(s))
    return path


def _b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _download_weights():
    """First-run download of the Tencent checkpoints to the network volume.

    Files pulled (tencent/HunyuanVideo-Foley, ~13GB total):
      hunyuanvideo_foley.pth        10.3 GB  (XXL DiT)
      hunyuanvideo_foley_xl.pth      5.85 GB (XL DiT)
      synchformer_state_dict.pth     950 MB  (visual sync encoder)
      vae_128d_48k.pth               1.49 GB (DAC 48kHz audio VAE)
      config.yaml / config_xl.yaml   (inference configs)
    SigLIP2 (google/siglip2-base-patch16-512) and CLAP
    (laion/larger_clap_general) auto-download into HF_HOME at load_model time.
    """
    from huggingface_hub import snapshot_download
    sentinel = os.path.join(MODEL_DIR, "hunyuanvideo_foley.pth")
    if os.path.exists(sentinel):
        return
    print(f"[foley] downloading weights -> {MODEL_DIR} (first run, ~13GB)...", flush=True)
    snapshot_download(
        repo_id="tencent/HunyuanVideo-Foley",
        local_dir=MODEL_DIR,
        allow_patterns=["*.pth", "*.yaml"],
    )
    print("[foley] weights ready.", flush=True)


def _get_model(model_size):
    """Load (and cache) the model. Reloads only if the requested size changes."""
    global _MODEL, _MODEL_SIZE
    if _MODEL is not None and _MODEL_SIZE == model_size:
        return _MODEL

    _download_weights()

    # Official inference API.
    from hunyuanvideo_foley.utils.model_utils import load_model

    device = "cuda" if torch.cuda.is_available() else "cpu"
    config_name = "config_xl.yaml" if model_size == "xl" else "config.yaml"
    config_path = os.path.join(MODEL_DIR, config_name)

    print(f"[foley] load_model(size={model_size}, config={config_name}, device={device})",
          flush=True)
    # load_model(model_path, config_path, device, enable_offload=False, model_size=None)
    # H100 80GB: no offload needed.
    model_dict, cfg = load_model(MODEL_DIR, config_path, device)

    _MODEL = (model_dict, cfg)
    _MODEL_SIZE = model_size
    return _MODEL


# --------------------------------------------------------------------------- #
# Handler                                                                      #
# --------------------------------------------------------------------------- #
def handler(event):
    t0 = time.time()
    workdir = tempfile.mkdtemp(prefix="foley_")
    try:
        inp = event.get("input") or {}

        video_in = inp.get("video")
        if not video_in:
            return {"error": "Missing required field 'video' (base64/data-uri/url of an mp4)."}

        prompt = inp.get("prompt", "") or ""
        neg_prompt = inp.get("neg_prompt", None)
        guidance = float(inp.get("guidance", 4.5))
        steps = int(inp.get("steps", 50))
        seed = int(inp.get("seed", 1))
        model_size = str(inp.get("model_size", "xxl")).lower()
        return_video = bool(inp.get("return_video", False))

        # 1) Materialize the input clip.
        video_path = _save(video_in, ".mp4", workdir)

        # 2) Load model + the official inference helpers.
        model_dict, cfg = _get_model(model_size)
        from hunyuanvideo_foley.utils.feature_utils import feature_process
        from hunyuanvideo_foley.utils.model_utils import denoise_process
        try:
            from hunyuanvideo_foley.utils.model_utils import set_manual_seed
            set_manual_seed(seed)
        except Exception:
            torch.manual_seed(seed)

        # 3) Extract visual (SigLIP2 @8fps + Synchformer @25fps) + text (CLAP)
        #    features. audio_len_in_s is DERIVED from the clip length
        #    (sync frame count / 25fps), capped at 15s by the model.
        # feature_process(video_path, prompt, model_dict, cfg, neg_prompt=None)
        visual_feats, text_feats, audio_len_in_s = feature_process(
            video_path, prompt, model_dict, cfg, neg_prompt=neg_prompt
        )

        # 4) Diffusion -> audio. Returns (audio_tensor_cpu_float32, sample_rate).
        # denoise_process(visual_feats, text_feats, audio_len_in_s, model_dict, cfg,
        #                 guidance_scale=4.5, num_inference_steps=50, batch_size=1)
        audio, sample_rate = denoise_process(
            visual_feats, text_feats, audio_len_in_s, model_dict, cfg,
            guidance_scale=guidance, num_inference_steps=steps, batch_size=1,
        )

        # 5) Normalize tensor to [channels, samples] for torchaudio.save.
        audio = audio.detach().to("cpu").float()
        if audio.dim() == 3:      # [batch, channels, samples]
            audio = audio[0]
        elif audio.dim() == 1:    # [samples]
            audio = audio.unsqueeze(0)

        wav_path = os.path.join(workdir, "foley.wav")
        torchaudio.save(wav_path, audio, sample_rate)

        n_samples = audio.shape[-1]
        duration = float(n_samples) / float(sample_rate)

        result = {
            "audio_base64": _b64_file(wav_path),
            "sample_rate": int(sample_rate),
            "duration": round(duration, 3),
            "seconds": round(time.time() - t0, 2),
        }

        # 6) Optional: mux the generated audio back onto the input video.
        if return_video:
            muxed = os.path.join(workdir, "foley.mp4")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", video_path, "-i", wav_path,
                     "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
                     "-shortest", muxed],
                    check=True, capture_output=True,
                )
                result["video_base64"] = _b64_file(muxed)
            except Exception as mux_err:  # audio still returned; report mux issue
                result["video_error"] = str(mux_err)

        return result

    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
    finally:
        try:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass


runpod.serverless.start({"handler": handler})
