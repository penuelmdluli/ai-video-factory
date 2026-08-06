"""
AI Video Generator — Converts AI images into cinematic video clips.

Primary model: Stable Video Diffusion XT (SVD-XT), run GPU-direct.
- Fits in 11GB VRAM at 576x1024, fp16-safe on Turing (RTX 2080 Ti)
- ~2.5 min/clip, up to 25 frames (~1.6s) with natural camera motion
- Loaded ONCE per batch (see convert_images_to_videos)

Fallback: Ken Burns zoom/pan effect (always works, no GPU needed)

Rejected for local use: Wan-14B and CogVideoX-5B require bf16 (no Turing HW
support) and >11GB VRAM — they produce black frames and ~2.7 hr/clip under
CPU offload. Reserve those for a hosted GPU.
"""
import asyncio
import gc
import os
import torch
from pathlib import Path

try:
    from config import (
        ENABLE_IMG2VID, IMG2VID_FPS, IMG2VID_NUM_FRAMES,
        IMG2VID_MIN_DURATION, IMG2VID_SMOOTH_FPS,
    )
except ImportError:
    ENABLE_IMG2VID = os.getenv("ENABLE_IMG2VID", "true").lower() in ("true", "1", "yes")
    IMG2VID_FPS = int(os.getenv("IMG2VID_FPS", "16"))
    IMG2VID_NUM_FRAMES = int(os.getenv("IMG2VID_NUM_FRAMES", "33"))
    IMG2VID_MIN_DURATION = float(os.getenv("IMG2VID_MIN_DURATION", "3.0"))
    IMG2VID_SMOOTH_FPS = int(os.getenv("IMG2VID_SMOOTH_FPS", "24"))

# Wan 2.1 settings
WAN_MODEL_ID = "Wan-AI/Wan2.1-I2V-14B-480P-Diffusers"  # 14B (1.3B removed from HuggingFace)
# Note: 14B requires CPU offload on 11GB VRAM — SVD-XT is primary fallback
WAN_STEPS = int(os.getenv("WAN_STEPS", "20"))  # 20 steps = good quality + speed
WAN_GUIDANCE = float(os.getenv("WAN_GUIDANCE", "5.0"))

# SVD-XT denoise steps. Was hard-capped at 8 (fast but undercooked/soft frames).
# 15 ~doubles motion coherence/sharpness; the GFPGAN+ESRGAN enhance pass handles
# the rest of the clarity, so we don't pay for 22+ steps (~19 min/clip on 2080 Ti).
SVD_STEPS = int(os.getenv("SVD_STEPS", "15"))

# Clip enhancement: GFPGAN face-restore + Real-ESRGAN upscale to clean up soft
# AI frames and fix melty faces. Applied per-clip after interpolation.
ENABLE_CLIP_ENHANCE = os.getenv("ENABLE_CLIP_ENHANCE", "true").lower() in ("true", "1", "yes")
CLIP_ENHANCE_WIDTH = int(os.getenv("CLIP_ENHANCE_WIDTH", "1080"))
CLIP_ENHANCE_HEIGHT = int(os.getenv("CLIP_ENHANCE_HEIGHT", "1920"))

# Global pipeline (lazy-loaded, unloaded after batch)
_wan_pipe = None
_pipe_type = None  # Track which pipeline is loaded


def _load_wan_pipeline():
    """Load I2V pipeline. Wan 14B too large for 11GB VRAM — use SVD-XT on GPU directly."""
    global _wan_pipe, _pipe_type

    if _wan_pipe is not None:
        return _wan_pipe

    # Free any existing pipeline first
    unload_pipeline()

    # Skip Wan 14B — requires 28GB+ VRAM, won't fit on RTX 2080 Ti (11GB)
    # Go straight to SVD-XT which runs great on GPU at ~45s/clip
    print("[AI-Video] Loading SVD-XT (GPU-direct, ~45s/clip)...")
    return _load_svd_fallback()


def _load_svd_fallback():
    """Fallback to SVD-XT if Wan isn't available."""
    global _wan_pipe, _pipe_type

    try:
        from diffusers import StableVideoDiffusionPipeline

        model_id = "stabilityai/stable-video-diffusion-img2vid-xt"
        print(f"[AI-Video] Loading SVD-XT fallback ({model_id})...")

        pipe = StableVideoDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            variant="fp16",
        )
        pipe.to("cuda")  # GPU-direct — 45s/clip vs 19min/step with CPU offload
        pipe.unet.enable_forward_chunking()

        _wan_pipe = pipe
        _pipe_type = "svd"
        print("[AI-Video] SVD-XT loaded as fallback")
        return _wan_pipe

    except Exception as e:
        print(f"[AI-Video] SVD-XT also failed: {e}")
        return None


def unload_pipeline():
    """Free VRAM by unloading the video pipeline."""
    global _wan_pipe, _pipe_type

    if _wan_pipe is not None:
        del _wan_pipe
        _wan_pipe = None
        _pipe_type = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[AI-Video] Pipeline unloaded, VRAM freed")


def _generate_wan_video_sync(
    image_path: str,
    output_path: str,
    prompt: str = "",
    num_frames: int = 33,
    guidance_scale: float = 5.0,
    num_inference_steps: int = 20,
) -> str | None:
    """Generate video using Wan 2.1 I2V (synchronous, runs in thread)."""
    from PIL import Image
    from diffusers.utils import export_to_video

    pipe = _load_wan_pipeline()
    if pipe is None:
        return None

    # Load and resize image
    img = Image.open(image_path).convert("RGB")

    if _pipe_type == "wan":
        # Wan expects specific resolutions
        # 480P mode: 832x480 landscape or 480x832 portrait
        w, h = img.size
        if w > h:
            img = img.resize((832, 480), Image.LANCZOS)
        else:
            img = img.resize((480, 832), Image.LANCZOS)

        # Generate with Wan 2.1
        if not prompt:
            prompt = "cinematic camera movement, smooth motion, high quality"

        with torch.inference_mode():
            output = pipe(
                image=img,
                prompt=prompt,
                num_frames=num_frames,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
            )
            frames = output.frames[0]

    elif _pipe_type == "svd":
        # SVD-XT on GPU — full 576x1024 resolution
        w, h = img.size
        if w > h:
            img = img.resize((1024, 576), Image.LANCZOS)
        else:
            img = img.resize((576, 1024), Image.LANCZOS)

        generator = torch.manual_seed(42)
        with torch.inference_mode():
            frames = pipe(
                img,
                decode_chunk_size=2,
                generator=generator,
                num_frames=min(num_frames, 25),  # SVD-XT native max = 25 (~1.6s @16fps)
                num_inference_steps=SVD_STEPS,  # 22 = sharp; was capped at 8 (soft)
                motion_bucket_id=100,
                noise_aug_strength=0.02,
                height=img.size[1],
                width=img.size[0],
            ).frames[0]
    else:
        return None

    # Export to MP4
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_to_video(frames, str(output_path), fps=IMG2VID_FPS)

    duration = len(frames) / IMG2VID_FPS

    # Extend short clips to a usable length with smooth motion interpolation.
    # SVD-XT caps at 25 frames (~1.6s); the assembler would otherwise loop the
    # clip to fill a scene, which reads as a stutter. minterpolate retimes +
    # generates in-between frames so the motion stays fluid at the new length.
    if IMG2VID_MIN_DURATION and duration < IMG2VID_MIN_DURATION:
        extended = _extend_clip_min_duration(output_path, IMG2VID_MIN_DURATION, IMG2VID_SMOOTH_FPS)
        if extended:
            duration = IMG2VID_MIN_DURATION

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[AI-Video] {_pipe_type.upper()}: {output_path.name} ({duration:.1f}s, {size_mb:.1f}MB, {len(frames)}f src@{IMG2VID_FPS}fps)")
    return str(output_path)


def _extend_clip_min_duration(clip_path: Path, min_duration: float, smooth_fps: int) -> bool:
    """
    Retime a short clip up to `min_duration` seconds with motion-compensated
    frame interpolation (ffmpeg minterpolate). Overwrites clip_path in place.
    Returns True on success.
    """
    import subprocess

    clip_path = Path(clip_path)
    try:
        # Current duration
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(clip_path)],
            capture_output=True, text=True,
        )
        cur = float(probe.stdout.strip() or 0)
        if cur <= 0 or cur >= min_duration:
            return False

        # Overshoot ~12%: minterpolate drops a few tail frames, so aim a little
        # past the target to reliably clear min_duration.
        factor = (min_duration / cur) * 1.12  # slow-down factor (PTS multiplier)
        tmp_path = clip_path.with_suffix(".ext.mp4")
        vf = (
            f"setpts={factor:.4f}*PTS,"
            f"minterpolate=fps={smooth_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        )
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(clip_path), "-vf", vf,
             "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-preset", "veryfast", "-crf", "18", str(tmp_path)],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 0:
            tmp_path.replace(clip_path)
            return True
        print(f"[AI-Video] Interpolation failed (kept original): {r.stderr[-200:]}")
        return False
    except Exception as e:
        print(f"[AI-Video] Interpolation error (kept original): {e}")
        return False


async def generate_video_from_image(
    image_path: str,
    output_path: str,
    prompt: str = "",
    motion_bucket_id: int | None = None,
) -> str | None:
    """
    Convert a single AI image into a cinematic video clip.

    Uses Wan 2.1 I2V (primary) → SVD-XT (fallback) → None (Ken Burns).
    """
    if not ENABLE_IMG2VID:
        return None

    try:
        if not torch.cuda.is_available():
            print("[AI-Video] Skipped: CUDA not available")
            return None
    except Exception:
        return None

    try:
        result = await asyncio.to_thread(
            _generate_wan_video_sync,
            image_path,
            output_path,
            prompt=prompt,
            num_frames=IMG2VID_NUM_FRAMES,
            guidance_scale=WAN_GUIDANCE,
            num_inference_steps=WAN_STEPS,
        )
        return result

    except Exception as e:
        err_msg = str(e)
        if "out of memory" in err_msg.lower():
            print("[AI-Video] GPU OOM — falling back to Ken Burns.")
            unload_pipeline()
        else:
            print(f"[AI-Video] Generation failed: {err_msg[:150]}")
        return None


async def convert_images_to_videos(
    image_paths: list[dict],
    output_dir: Path,
    niche: str = "",
) -> list[dict]:
    """
    Convert a batch of AI images into video clips.

    Loads pipeline once, converts all images, then unloads to free VRAM.
    Images that fail keep their original path (Ken Burns fallback in assembler).
    """
    if not ENABLE_IMG2VID:
        print("[AI-Video] Image-to-video disabled (ENABLE_IMG2VID=false)")
        return image_paths

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Niche-specific prompts for Wan 2.1 (guides the motion style)
    niche_prompts = {
        "ai_money": "smooth camera pan, professional corporate footage, money and technology",
        "tech_news": "handheld war footage, shaky frontline camera, smoke drifting, explosions and debris in motion, soldiers moving, chaotic combat energy",
        "motivation": "powerful cinematic camera push, dramatic lighting, epic atmosphere",
        "health_wellness": "gentle slow motion, nature and wellness, warm sunlight",
        "blissful_moments": "dreamy slow camera drift, peaceful atmosphere, soft bokeh",
        "daily_breakdown": "steady news camera, professional studio lighting",
        "limitless_you": "energetic camera movement, dynamic angles, inspiring atmosphere",
        "shopmo_products": "smooth product showcase rotation, clean studio lighting",
    }
    prompt = niche_prompts.get(niche, "cinematic camera movement, high quality, smooth motion")

    converted = 0
    failed = 0
    total_images = sum(1 for p in image_paths if p.get("type") == "ai_image")

    if total_images == 0:
        return image_paths

    print(f"[AI-Video] Converting {total_images} AI images to video clips...")
    print(f"[AI-Video] Niche: {niche} | Prompt: {prompt[:60]}...")

    # Load the pipeline ONCE for the whole batch. SVD-XT runs GPU-direct and
    # fits comfortably in 11GB, so there's no need to reload per clip — doing so
    # paid the ~10-60s model-load cost N times for an N-scene video.
    import time as _time
    _batch_start = _time.time()

    results = []
    for item in image_paths:
        if item.get("type") != "ai_image" or not item.get("local_path"):
            results.append(item)
            continue

        scene_num = item.get("scene_number", 0)
        video_path = output_dir / f"scene_{scene_num:02d}_video.mp4"

        result = await generate_video_from_image(
            item["local_path"],
            str(video_path),
            prompt=prompt,
        )

        if result:
            item_copy = dict(item)
            item_copy["local_path"] = result
            item_copy["type"] = "ai_video"
            item_copy["source_image"] = item["local_path"]
            results.append(item_copy)
            converted += 1
        else:
            results.append(item)
            failed += 1

    # Final cleanup — unload SVD once, after the whole batch (frees VRAM for the
    # enhancer, so the two models never overlap in 11GB).
    unload_pipeline()

    elapsed = _time.time() - _batch_start
    per_clip = elapsed / converted if converted else 0
    print(f"[AI-Video] Converted {converted}/{total_images} images to video "
          f"({failed} kept as Ken Burns) in {elapsed:.0f}s ({per_clip:.0f}s/clip)")

    # ── Enhancement pass: GFPGAN face-restore + Real-ESRGAN upscale ──
    # Runs on the interpolated clips so the melty faces from SVD + minterpolate
    # get restored, and every frame is upscaled to the final render resolution.
    if ENABLE_CLIP_ENHANCE and converted:
        # Only enhance clips that haven't been through GFPGAN/ESRGAN already.
        # convert_images_to_videos can run twice per video (visual_fetcher, then
        # main.py step 4.1 for any scene that failed the first time) — a second
        # enhance pass on the same clip over-smooths faces into a plastic look.
        pending = [r for r in results
                   if r.get("type") == "ai_video" and not r.get("enhanced")]
        clip_paths = [r["local_path"] for r in pending]
        if clip_paths:
            try:
                from modules.clip_enhancer import enhance_clips
                _e0 = _time.time()
                print(f"[AI-Video] Enhancing {len(clip_paths)} clips (GFPGAN + Real-ESRGAN -> "
                      f"{CLIP_ENHANCE_WIDTH}x{CLIP_ENHANCE_HEIGHT})...")
                n = await asyncio.to_thread(
                    enhance_clips, clip_paths, CLIP_ENHANCE_WIDTH, CLIP_ENHANCE_HEIGHT
                )
                for r in pending:
                    r["enhanced"] = True
                print(f"[AI-Video] Enhanced {n}/{len(clip_paths)} clips in {_time.time() - _e0:.0f}s")
            except Exception as e:
                print(f"[AI-Video] Enhancement skipped ({str(e)[:100]})")

    return results


# Backward compatibility alias
unload_svd = unload_pipeline


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    async def test():
        if len(sys.argv) < 2:
            print("Usage: python -m modules.ai_video_generator <image_path>")
            return

        image_path = sys.argv[1]
        output_path = Path(image_path).parent / "test_wan_video.mp4"

        print(f"Converting {image_path} to video with SVD-XT...")
        result = await generate_video_from_image(image_path, str(output_path))

        if result:
            print(f"Success: {result}")
        else:
            print("Failed — check GPU memory and model availability")

        unload_pipeline()

    asyncio.run(test())
