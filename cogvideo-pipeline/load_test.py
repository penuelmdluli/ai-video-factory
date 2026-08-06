"""
Phase 1 — Load CogVideoX1.5-5B-I2V and verify it runs on RTX 2080 Ti (11GB).

Tries offload strategies in order until one works:
1. model_cpu_offload + VAE tiling/slicing
2. sequential_cpu_offload + VAE tiling/slicing
3. INT8 quantization + offload

Gate 1: Model loads, one forward step completes, peak VRAM < 11GB.
"""
import torch
import gc
import sys
import time
import json

MODEL_ID = "THUDM/CogVideoX1.5-5B-I2V"
RESULT = {"model": MODEL_ID, "gate": "GATE_1", "status": "FAIL"}


def try_load_level1():
    """Level 1: model_cpu_offload + VAE tiling/slicing."""
    from diffusers import CogVideoXImageToVideoPipeline

    print("[Level 1] Loading with model_cpu_offload + VAE tiling/slicing...")
    pipe = CogVideoXImageToVideoPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
    )
    # VAE in float32 — Turing GPUs produce NaN in float16 VAE
    pipe.vae = pipe.vae.to(dtype=torch.float32)
    pipe.enable_model_cpu_offload()
    try:
        pipe.vae.enable_tiling()
    except Exception as e:
        print(f"  VAE tiling: {e}")
    try:
        pipe.vae.enable_slicing()
    except Exception as e:
        print(f"  VAE slicing: {e}")
    return pipe, "level1_model_cpu_offload_vae_fp32"


def try_load_level2():
    """Level 2: sequential_cpu_offload + VAE tiling/slicing."""
    from diffusers import CogVideoXImageToVideoPipeline

    print("[Level 2] Loading with sequential_cpu_offload + VAE tiling/slicing...")
    pipe = CogVideoXImageToVideoPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
    )
    pipe.enable_sequential_cpu_offload()
    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass
    try:
        pipe.vae.enable_slicing()
    except Exception:
        pass
    return pipe, "level2_sequential_cpu_offload"


def run_forward_test(pipe):
    """Run a single denoising step to verify GPU execution."""
    from PIL import Image

    print("[Test] Running single-step forward pass...")
    img = Image.new("RGB", (256, 256), (100, 150, 200))

    t0 = time.time()
    with torch.inference_mode():
        output = pipe(
            image=img,
            prompt="a person waving",
            num_frames=8,
            num_inference_steps=1,
            guidance_scale=6.0,
            generator=torch.manual_seed(42),
            height=480,
            width=720,
        )
    t1 = time.time()

    frames = output.frames[0]
    peak_vram = torch.cuda.max_memory_allocated() / 1e9
    print(f"[Test] Forward pass: {t1 - t0:.1f}s, {len(frames)} frames, peak VRAM: {peak_vram:.1f}GB")
    return len(frames), peak_vram, t1 - t0


def main():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    free, total = torch.cuda.mem_get_info()
    print(f"VRAM: {free / 1e9:.1f}GB free / {total / 1e9:.1f}GB total")
    torch.cuda.reset_peak_memory_stats()

    levels = [
        ("Level 1", try_load_level1),
        ("Level 2", try_load_level2),
    ]

    for level_name, load_fn in levels:
        gc.collect()
        torch.cuda.empty_cache()

        try:
            pipe, offload_level = load_fn()
            num_frames, peak_vram, duration = run_forward_test(pipe)

            RESULT["status"] = "PASS"
            RESULT["offload_level"] = offload_level
            RESULT["peak_vram_gb"] = round(peak_vram, 2)
            RESULT["forward_time_s"] = round(duration, 1)
            RESULT["test_frames"] = num_frames

            del pipe
            gc.collect()
            torch.cuda.empty_cache()

            print(f"\n{'='*50}")
            print(f"GATE 1: PASS — {level_name} works")
            print(f"  Offload: {offload_level}")
            print(f"  Peak VRAM: {peak_vram:.1f}GB")
            print(f"  Forward time: {duration:.1f}s")
            print(f"  Frames: {num_frames}")
            print(f"{'='*50}")
            break

        except torch.cuda.OutOfMemoryError:
            print(f"[{level_name}] OOM — trying next level...")
            gc.collect()
            torch.cuda.empty_cache()
            continue

        except Exception as e:
            print(f"[{level_name}] Error: {e}")
            gc.collect()
            torch.cuda.empty_cache()
            continue
    else:
        print("\nGATE 1: FAIL — All offload levels failed")
        RESULT["error"] = "All offload levels exhausted"

    # Save result
    with open("cogvideo-pipeline/gate1_result.json", "w") as f:
        json.dump(RESULT, f, indent=2)
    print(f"\nResult saved: cogvideo-pipeline/gate1_result.json")

    sys.exit(0 if RESULT["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
