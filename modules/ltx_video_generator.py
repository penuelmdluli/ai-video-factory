"""
LTX-Video Image-to-Video generator (sharper replacement for SVD-XT).

Why LTX over SVD-XT:
- Crisp video at higher native resolution, long clips (~4s) at 24fps NATIVELY —
  no minterpolate slow-mo, which was the biggest blur source in the SVD path.

Turing (RTX 2080 Ti) handling — the tricky part:
- LTX's VAE overflows in fp16 on Turing (no bf16) → washed-out frames, so the
  VAE must run in fp32. But model_cpu_offload re-casts the VAE to fp16 and its
  hook chain conflicts with pinning it. So instead of offload we PHASE it:
    1. Encode the prompt with the big T5 text encoder on GPU, then move T5 to CPU.
    2. Run the transformer (fp16) + VAE (fp32) together on GPU (~10.4GB) — fits 11GB.
  Needs ~24GB system RAM to hold the idle components (machine has 128GB).
"""
import gc
import os
from pathlib import Path

import torch

MODEL_ID = "Lightricks/LTX-Video"

# width/height divisible by 32; frames = 8n+1. Cropped to 1080x1920 by enhancer.
LTX_WIDTH = int(os.getenv("LTX_WIDTH", "768"))
LTX_HEIGHT = int(os.getenv("LTX_HEIGHT", "1344"))
LTX_NUM_FRAMES = int(os.getenv("LTX_NUM_FRAMES", "97"))   # 8*12+1 -> ~4s @24fps
LTX_STEPS = int(os.getenv("LTX_STEPS", "40"))
LTX_FPS = int(os.getenv("LTX_FPS", "24"))
LTX_GUIDANCE = float(os.getenv("LTX_GUIDANCE", "3.0"))

_pipe = None

NEG_PROMPT = ("worst quality, blurry, jittery, distorted, low resolution, "
              "watermark, text, deformed, oversmoothed, plastic")


def _load():
    global _pipe
    if _pipe is not None:
        return _pipe
    from diffusers import LTXImageToVideoPipeline
    print(f"[LTX] Loading {MODEL_ID} (phased, VAE fp32 for Turing)...")
    pipe = LTXImageToVideoPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.float16)

    # VAE runs in fp32 (Turing fp16 overflow). Patch the encode/decode boundary so
    # tensors crossing into the VAE are fp32; hand fp16 latents back to the fp16
    # transformer path so nothing else changes.
    pipe.vae = pipe.vae.to(dtype=torch.float32)

    _orig_decode = pipe.vae.decode
    def _fp32_decode(z, *a, **k):
        z = z.to("cuda", dtype=torch.float32)
        a = tuple(
            (t.to("cuda", dtype=torch.float32) if t.is_floating_point() else t.to("cuda"))
            if torch.is_tensor(t) else t
            for t in a
        )
        return _orig_decode(z, *a, **k)
    pipe.vae.decode = _fp32_decode

    _orig_encode = pipe.vae.encode
    def _fp32_encode(x, *a, **k):
        out = _orig_encode(x.to("cuda", dtype=torch.float32), *a, **k)
        try:
            out.latent_dist.mean = out.latent_dist.mean.to(dtype=torch.float16)
            out.latent_dist.logvar = out.latent_dist.logvar.to(dtype=torch.float16)
        except Exception:
            pass
        return out
    pipe.vae.encode = _fp32_encode

    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass

    # Start everything on CPU; generate() moves components on/off GPU per phase.
    pipe.to("cpu")
    _pipe = pipe
    print("[LTX] Loaded")
    return _pipe


def unload():
    global _pipe
    if _pipe is not None:
        del _pipe
        _pipe = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[LTX] Unloaded, VRAM freed")


def generate(image_path: str, output_path: str, prompt: str = "") -> str | None:
    """Generate one crisp i2v clip with LTX (phased execution). Returns path or None."""
    from PIL import Image
    from diffusers.utils import export_to_video

    pipe = _load()
    img = Image.open(image_path).convert("RGB").resize((LTX_WIDTH, LTX_HEIGHT), Image.LANCZOS)
    if not prompt:
        prompt = "cinematic real footage, natural motion, sharp focus, documentary realism"

    # ── Phase 1: encode prompt with T5 on GPU, then evict T5 ──
    pipe.text_encoder.to("cuda")
    with torch.inference_mode():
        pe, pam, npe, npam = pipe.encode_prompt(
            prompt=prompt,
            negative_prompt=NEG_PROMPT,
            do_classifier_free_guidance=True,
            num_videos_per_prompt=1,
            device="cuda",
        )
    pipe.text_encoder.to("cpu")
    gc.collect(); torch.cuda.empty_cache()

    # ── Phase 2: transformer (fp16) + VAE (fp32) on GPU ──
    pipe.transformer.to("cuda")
    pipe.vae.to("cuda")

    torch.cuda.reset_peak_memory_stats()
    generator = torch.manual_seed(42)
    with torch.inference_mode():
        frames = pipe(
            image=img,
            prompt_embeds=pe,
            prompt_attention_mask=pam,
            negative_prompt_embeds=npe,
            negative_prompt_attention_mask=npam,
            width=LTX_WIDTH,
            height=LTX_HEIGHT,
            num_frames=LTX_NUM_FRAMES,
            num_inference_steps=LTX_STEPS,
            guidance_scale=LTX_GUIDANCE,
            generator=generator,
        ).frames[0]

    peak = torch.cuda.max_memory_allocated() / 1e9
    pipe.transformer.to("cpu")
    pipe.vae.to("cpu")
    gc.collect(); torch.cuda.empty_cache()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_to_video(frames, str(output_path), fps=LTX_FPS)

    dur = len(frames) / LTX_FPS
    size_mb = output_path.stat().st_size / 1e6
    print(f"[LTX] {output_path.name} ({dur:.1f}s, {size_mb:.1f}MB, {len(frames)}f@{LTX_FPS}fps, peak {peak:.1f}GB)")
    return str(output_path)


# ── CLI smoke test ───────────────────────────────────────────
if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else "cogvideo-pipeline/test_input.png"
    out = Path("logs/ltx_test.mp4")
    print(f"LTX test: {img} -> {out}")
    r = generate(img, str(out), prompt="soldiers moving through smoke and rubble, drifting handheld camera, real war footage")
    print("Result:", r)
    unload()
