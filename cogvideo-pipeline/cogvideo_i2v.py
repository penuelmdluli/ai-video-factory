"""
Phase 2 — CogVideoX1.5-5B-I2V: Generate real video from image.

Usage:
    python cogvideo_i2v.py --image <path> --prompt "motion description" --output-dir output/
"""
import torch
import gc
import sys
import time
import json
import argparse
from pathlib import Path

MODEL_ID = "THUDM/CogVideoX1.5-5B-I2V"


def generate_video(
    image_path: str,
    prompt: str,
    output_dir: str = "output",
    num_frames: int = 49,  # CogVideoX default
    num_steps: int = 30,
    fps: int = 16,
    height: int = 480,
    width: int = 720,
    seed: int = 42,
    guidance_scale: float = 6.0,
):
    from diffusers import CogVideoXImageToVideoPipeline
    from diffusers.utils import export_to_video
    from PIL import Image

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load image
    print(f"[CogVideo] Loading image: {image_path}")
    img = Image.open(image_path).convert("RGB")
    img = img.resize((width, height), Image.LANCZOS)

    # Load pipeline
    print(f"[CogVideo] Loading model: {MODEL_ID}")
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    pipe = CogVideoXImageToVideoPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
    )
    pipe.enable_model_cpu_offload()

    # ── CRITICAL FIX for Turing GPUs (RTX 2080 Ti) ──────────
    # CogVideoX VAE produces NaN in float16 → black frames.
    # Fix: upcast ENTIRE VAE to float32, AND patch decode_latents
    # to cast the latents to float32 before decoding.
    pipe.vae = pipe.vae.to(dtype=torch.float32)

    # Patch decode_latents to upcast latents before VAE
    _orig_decode = pipe.decode_latents
    def _fp32_decode_latents(latents, *args, **kwargs):
        latents = latents.to(dtype=torch.float32)
        return _orig_decode(latents, *args, **kwargs)
    pipe.decode_latents = _fp32_decode_latents

    # Patch prepare_latents to handle VAE encode in float32
    _orig_prepare = pipe.prepare_latents
    def _fp32_prepare_latents(*args, **kwargs):
        # Temporarily cast VAE input to float32
        result = _orig_prepare(*args, **kwargs)
        return result
    pipe.prepare_latents = _fp32_prepare_latents

    # Force the image encoding to use float32
    _orig_vae_encode = pipe.vae.encode
    def _safe_encode(x, *args, **kwargs):
        return _orig_vae_encode(x.to(dtype=torch.float32), *args, **kwargs)
    pipe.vae.encode = _safe_encode
    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass
    try:
        pipe.vae.enable_slicing()
    except Exception:
        pass

    free, total = torch.cuda.mem_get_info()
    print(f"[CogVideo] VRAM: {free / 1e9:.1f}GB free / {total / 1e9:.1f}GB")
    print(f"[CogVideo] Generating: {width}x{height}, {num_frames} frames, {num_steps} steps...")

    t0 = time.time()
    generator = torch.manual_seed(seed)
    with torch.inference_mode():
        output = pipe(
            image=img,
            prompt=prompt,
            num_frames=num_frames,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            height=height,
            width=width,
        )
    t1 = time.time()

    frames = output.frames[0]
    peak_vram = torch.cuda.max_memory_allocated() / 1e9
    duration = len(frames) / fps

    print(f"[CogVideo] Done: {len(frames)} frames in {t1 - t0:.0f}s")
    print(f"[CogVideo] Duration: {duration:.1f}s at {fps}fps")
    print(f"[CogVideo] Peak VRAM: {peak_vram:.1f}GB")

    # Save video
    output_path = output_dir / "cogvideo_output.mp4"
    export_to_video(frames, str(output_path), fps=fps)
    size_mb = output_path.stat().st_size / 1e6
    print(f"[CogVideo] Saved: {output_path} ({size_mb:.1f}MB)")

    # Save run log
    run_log = {
        "image": image_path,
        "prompt": prompt,
        "num_frames": len(frames),
        "num_steps": num_steps,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "duration_s": round(duration, 1),
        "wall_clock_s": round(t1 - t0, 1),
        "peak_vram_gb": round(peak_vram, 2),
        "output_path": str(output_path),
        "size_mb": round(size_mb, 2),
        "offload": "model_cpu_offload",
    }
    log_path = output_dir / "cogvideo_run_log.json"
    with open(log_path, "w") as f:
        json.dump(run_log, f, indent=2)
    print(f"[CogVideo] Log: {log_path}")

    # Cleanup
    del pipe, frames, output
    gc.collect()
    torch.cuda.empty_cache()

    return str(output_path), run_log


def main():
    parser = argparse.ArgumentParser(description="CogVideoX Image-to-Video")
    parser.add_argument("--image", required=True, help="Input image path")
    parser.add_argument("--prompt", required=True, help="Motion/action prompt")
    parser.add_argument("--output-dir", default="cogvideo-pipeline/output", help="Output directory")
    parser.add_argument("--frames", type=int, default=49, help="Number of frames")
    parser.add_argument("--steps", type=int, default=30, help="Inference steps")
    parser.add_argument("--fps", type=int, default=16, help="Output FPS")
    parser.add_argument("--height", type=int, default=480, help="Video height")
    parser.add_argument("--width", type=int, default=720, help="Video width")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    output_path, run_log = generate_video(
        image_path=args.image,
        prompt=args.prompt,
        output_dir=args.output_dir,
        num_frames=args.frames,
        num_steps=args.steps,
        fps=args.fps,
        height=args.height,
        width=args.width,
        seed=args.seed,
    )

    # Gate 2 verification
    import subprocess
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-show_entries", "stream=width,height,nb_frames",
         "-of", "csv=p=0", output_path],
        capture_output=True, text=True,
    )
    print(f"\n[Gate 2] ffprobe: {r.stdout.strip()}")

    # Check frames aren't blank
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(output_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    check_points = [0, total_frames // 4, total_frames // 2, 3 * total_frames // 4]
    all_valid = True
    for idx in check_points:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            print(f"[Gate 2] FAIL: Could not read frame {idx}")
            all_valid = False
            continue
        variance = np.var(frame)
        mean_val = np.mean(frame)
        print(f"[Gate 2] Frame {idx}: mean={mean_val:.0f}, variance={variance:.0f}")
        if variance < 10:
            print(f"[Gate 2] FAIL: Frame {idx} appears blank/noise")
            all_valid = False
    cap.release()

    duration = float(r.stdout.strip().split("\n")[-1]) if r.stdout.strip() else 0
    if duration >= 3.0 and all_valid:
        print(f"\n{'='*50}")
        print(f"GATE 2: PASS")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Generation time: {run_log['wall_clock_s']:.0f}s")
        print(f"  Peak VRAM: {run_log['peak_vram_gb']:.1f}GB")
        print(f"  Output: {output_path}")
        print(f"{'='*50}")
    else:
        print(f"\nGATE 2: FAIL — duration={duration:.1f}s, valid_frames={all_valid}")
        sys.exit(1)


if __name__ == "__main__":
    main()
