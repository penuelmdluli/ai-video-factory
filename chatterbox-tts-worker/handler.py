"""
RunPod Serverless handler for Chatterbox-TTS (Resemble AI) — warm, expressive TTS.

Serves the AI Video Factory's self-hosted voices. The niche→voice mapping in
modules/voice_generator.py sends voice="warm_teacher" (kids) or "news_anchor"
(news); this worker turns those preset names into Chatterbox emotion/pacing
settings, and — if a matching reference clip exists in /app/voices — clones a
fixed character voice so it stays consistent across every video.

ONE worker serves every preset: point RUNPOD_TTS_ENDPOINT_KIDS,
RUNPOD_TTS_ENDPOINT_NEWS (and/or the generic RUNPOD_TTS_ENDPOINT) at this
endpoint; the `voice` field selects the preset.

Contract (matches our other workers + modules/voice_runpod.py):
  event["input"]:
    text          REQUIRED  the words to speak
    voice         optional  preset: "warm_teacher" | "news_anchor" | "default"
    exaggeration  optional  float 0..1 override (emotion intensity)
    cfg_weight    optional  float 0..1 override (pacing; lower = slower/steadier)
    seed          optional  int
  success -> {"audio_base64" (wav), "sample_rate", "duration", "seconds", "voice"}
  failure -> {"error", "trace"}
"""
import os
import sys
import time
import base64
import tempfile
import traceback

# Force model/cache onto the RunPod network volume BEFORE importing torch/hf.
os.environ.setdefault("HF_HOME", "/runpod-volume/hf")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", "/runpod-volume/hf/hub")
os.environ.setdefault("TORCH_HOME", "/runpod-volume/torch")
for _d in (os.environ["HF_HOME"], os.environ["HUGGINGFACE_HUB_CACHE"], os.environ["TORCH_HOME"]):
    os.makedirs(_d, exist_ok=True)

# Optional per-preset reference voices baked into the image (voice cloning) — drop
# warm_teacher.wav / news_anchor.wav here for a consistent character. Missing = the
# model's built-in voice with the preset's emotion (still warm via `exaggeration`).
VOICE_REF_DIR = os.environ.get("VOICE_REF_DIR", "/app/voices")

import runpod
import torch
import torchaudio

# Loaded ONCE per warm worker.
_MODEL = None

# Emotion + pacing presets. Higher exaggeration = more expressive/warm; lower
# cfg_weight = slower, more deliberate delivery (good for kids call-and-response).
PRESETS = {
    "warm_teacher": {"exaggeration": 0.65, "cfg_weight": 0.40},   # kids — warm, slow, expressive
    "news_anchor":  {"exaggeration": 0.35, "cfg_weight": 0.50},   # news — measured, authoritative
    "default":      {"exaggeration": 0.50, "cfg_weight": 0.50},
}


def _get_model():
    global _MODEL
    if _MODEL is None:
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[chatterbox] loading model on {device} ...", flush=True)
        _MODEL = ChatterboxTTS.from_pretrained(device=device)
        print("[chatterbox] ready.", flush=True)
    return _MODEL


def _ref_for(voice):
    """Reference clip for voice cloning, if one was baked into the image."""
    path = os.path.join(VOICE_REF_DIR, f"{voice}.wav")
    return path if os.path.exists(path) else None


def handler(event):
    t0 = time.time()
    workdir = tempfile.mkdtemp(prefix="cbx_")
    try:
        inp = event.get("input") or {}
        text = (inp.get("text") or "").strip()
        if not text:
            return {"error": "Missing required field 'text'."}

        voice = str(inp.get("voice") or "default")
        preset = PRESETS.get(voice, PRESETS["default"])
        exaggeration = float(inp.get("exaggeration", preset["exaggeration"]))
        cfg_weight = float(inp.get("cfg_weight", preset["cfg_weight"]))
        seed = inp.get("seed")
        if seed is not None:
            torch.manual_seed(int(seed))

        model = _get_model()
        gen_kwargs = {"exaggeration": exaggeration, "cfg_weight": cfg_weight}
        ref = _ref_for(voice)
        if ref:
            gen_kwargs["audio_prompt_path"] = ref

        wav = model.generate(text, **gen_kwargs)

        # Normalize to [channels, samples] for torchaudio.save.
        wav = wav.detach().to("cpu").float()
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        elif wav.dim() == 3:
            wav = wav[0]
        sr = int(getattr(model, "sr", 24000))

        wav_path = os.path.join(workdir, "out.wav")
        torchaudio.save(wav_path, wav, sr)
        with open(wav_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        duration = float(wav.shape[-1]) / float(sr)
        return {
            "audio_base64": audio_b64,   # WAV — the client transcodes to mp3
            "sample_rate": sr,
            "duration": round(duration, 3),
            "seconds": round(time.time() - t0, 2),
            "voice": voice,
        }

    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
    finally:
        try:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass


runpod.serverless.start({"handler": handler})
