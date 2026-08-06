"""
AI Image Generator — Creates custom images using local + cloud AI.

Priority chain:
1. Local Stable Diffusion XL (best quality, free, unlimited — RTX 2080 Ti)
2. Gemini Flash Image (FREE — 500/day)
3. Cloudflare Workers AI FLUX (FREE — 100K/day)
4. DALL-E 3 (paid fallback — $0.04/image)

This replaces generic stock footage with exact custom visuals for each scene.
"""
import asyncio
import base64
import os
import requests
from pathlib import Path

from config import OPENAI_API_KEY, GEMINI_API_KEY


# ── Config ────────────────────────────────────────────────────
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")

ENABLE_LOCAL_SD = os.getenv("ENABLE_LOCAL_SD", "true").lower() in ("true", "1", "yes")
SD_STEPS = int(os.getenv("SD_STEPS", "20"))  # 20 steps = good quality + faster (was 30)
SD_CFG_SCALE = float(os.getenv("SD_CFG_SCALE", "7.5"))


# ── Global SDXL pipeline (lazy-loaded) ────────────────────────
_sdxl_pipe = None


# ── Niche-Specific Image Style Prompts (cloud generators) ────
NICHE_IMAGE_STYLES = {
    "ai_money": "RAW photograph of real person working intensely, dramatic natural window light, real office environment, sweat and focus visible, candid action moment, shot on Sony A7IV 85mm f1.4",
    "tech_news": "cinematic war ACTION, a few anonymous soldiers running through smoke, ONE clear military vehicle, an explosion in the background, dust and sparks, motion blur, dramatic light, photorealistic, sharp coherent subjects, one clear focal action not overcrowded, no real politicians, no static portrait",
    "motivation": "RAW photograph of real person pushing through struggle, sweat dripping, muscles tensed, golden hour backlight, genuine pain and determination on face, shot on Canon 5D 135mm f2",
    "health_wellness": "RAW photograph of real person preparing fresh food, steam rising, hands chopping vegetables, morning kitchen light, genuine lifestyle moment, extreme detail on textures, shot on Fuji XT5",
    "blissful_moments": "RAW photograph of real African mother holding baby, genuine laughter and tears of joy, warm golden backlight, intimate close-up of real emotion, shot on Sony A7III 50mm f1.2",
    "daily_breakdown": "RAW photograph of real South African scene, real people on streets of Johannesburg or Cape Town, SA flag visible, genuine emotion and pride, documentary street photography, shot on Leica Q3",
    "shopmo_products": "RAW photograph of real person unboxing product, genuine excitement on face, natural home lighting, real hands touching real product, authentic moment, shot on iPhone 15 Pro",
    "limitless_you": "RAW photograph of real young African entrepreneur in action, real African city background, genuine confidence, natural street lighting, documentary portrait, shot on Canon R5 85mm",
}


# ── Niche-Specific SDXL Style Prompts (local generator) ──────
NICHE_SDXL_STYLES = {
    "ai_money": "RAW photo, real person typing on laptop with intense focus, natural window light, real desk clutter, candid work moment, skin pores visible, 85mm f1.4 shallow DOF",
    "tech_news": "photorealistic cinematic war-news footage, dramatic natural light, film grain, shot on Canon EOS R3, ONE clear readable subject (not a chaotic jumble), sharp and coherent, real breaking-news look, anonymous figures with faces obscured, no real recognizable politician",
    "motivation": "RAW photo, real person mid-exercise with sweat visible, dramatic natural golden hour light, genuine struggle on face, outdoor environment, 135mm lens, film grain",
    "health_wellness": "RAW photo, real hands preparing fresh colorful food on wooden board, steam rising, morning sunlight through window, extreme texture detail, lifestyle documentary",
    "blissful_moments": "RAW photo, real African mother and baby sharing genuine laugh, warm natural backlight, real home environment, intimate portrait, soft bokeh, authentic emotion",
    "daily_breakdown": "RAW photo, real South African street scene with real people, vibrant colors, SA cultural elements, documentary photography, genuine daily life, Leica quality",
    "shopmo_products": "RAW photo, real person's hands opening a package with genuine excitement, natural home lighting, real product visible, authentic unboxing moment",
    "limitless_you": "RAW photo, real young African professional in modern office, genuine confidence, natural city light, real environment with depth, documentary portrait, 85mm",
}

SDXL_NEGATIVE_PROMPT = (
    "cartoon, illustration, anime, watermark, text, logo, blurry, low quality, "
    "deformed, ugly, disfigured, extra limbs, bad anatomy, CGI, 3D render, "
    "painting, drawing, AI generated look, smooth plastic skin, perfect symmetry, "
    "stock photo pose, empty background, no people, generic, boring, flat lighting, "
    "oversaturated, HDR look, digital art, concept art, studio backdrop"
)


def _enhance_prompt(prompt: str, niche: str = "", orientation: str = "landscape") -> str:
    """Create hyperrealistic photo prompts that look indistinguishable from real photos.

    Key: ALWAYS include real people doing real things. RAW photo look.
    The image should make viewers debate if it's real or AI.
    """
    style = NICHE_IMAGE_STYLES.get(niche, "RAW photograph of real person in action, natural lighting, candid moment, shot on Canon EOS R5 85mm f1.4")
    aspect = "wide 16:9 composition" if orientation == "landscape" else "vertical 9:16 portrait composition, showing full person"

    return (
        f"RAW photo, {aspect}. "
        f"{style}. "
        f"Scene: {prompt}. "
        f"Hyperrealistic, real skin texture with pores and imperfections, "
        f"natural film grain, real environment with depth, action happening, "
        f"people with genuine facial expressions, candid not posed. "
        f"No text, no watermarks, no logos, no CGI, no illustration."
    )


def _get_sdxl_prompt(prompt: str, niche: str = "", orientation: str = "landscape") -> str:
    """Create an optimized prompt specifically for Stable Diffusion XL.

    SDXL responds best to detailed photographic descriptions with camera/lens
    references, lighting details, and composition notes.
    """
    style = NICHE_SDXL_STYLES.get(
        niche,
        "professional photograph, natural lighting, shallow depth of field, "
        "shot on Canon EOS R5, 85mm lens, editorial photography"
    )
    aspect = "wide 16:9 horizontal composition" if orientation == "landscape" else "vertical 9:16 portrait composition"

    # SDXL CLIP tokenizer truncates at 77 tokens — keep prompt concise.
    # Lead with the SCENE SUBJECT (what THIS scene is actually about) so the
    # picture matches the story and varies per scene; style is a light modifier.
    scene_words = prompt.split()[:24]
    scene_desc = " ".join(scene_words)

    return (
        f"RAW photo, {aspect}. "
        f"{scene_desc}. "
        f"{style}."
    )


# ── Upscaling ─────────────────────────────────────────────────

def _upscale_image(image_path: str, target_w: int, target_h: int) -> str:
    """Upscale an image using PIL Lanczos resampling.

    Generates 20% larger than target for Ken Burns zoom headroom.
    For 1920x1080 target -> 2304x1296.
    For 1080x1920 target -> 1296x2304.
    """
    try:
        from PIL import Image

        # 20% larger for Ken Burns headroom
        final_w = int(target_w * 1.2)
        final_h = int(target_h * 1.2)

        img = Image.open(image_path)
        if img.size[0] >= final_w and img.size[1] >= final_h:
            return image_path  # Already large enough

        img_resized = img.resize((final_w, final_h), Image.LANCZOS)
        img_resized.save(image_path, quality=95)
        print(f"[AIImage] Upscaled to {final_w}x{final_h} (Ken Burns headroom)")
        return image_path
    except Exception as e:
        print(f"[AIImage] Upscale warning: {e}")
        return image_path


# ── Generator 1: Local Stable Diffusion XL (FREE, unlimited) ─

def _load_sdxl_pipeline():
    """Lazy-load the SDXL pipeline onto GPU. Kept in memory for batch use."""
    global _sdxl_pipe

    if _sdxl_pipe is not None:
        return _sdxl_pipe

    import torch
    from diffusers import StableDiffusionXLPipeline, EulerDiscreteScheduler

    model_id = "stabilityai/stable-diffusion-xl-base-1.0"
    print(f"[AIImage] Loading SDXL pipeline ({model_id})...")

    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    )

    # Set scheduler
    pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)

    # Move to GPU
    pipe = pipe.to("cuda")

    # Memory optimizations for 11GB VRAM
    pipe.enable_attention_slicing()
    pipe.enable_vae_tiling()

    _sdxl_pipe = pipe
    print("[AIImage] SDXL pipeline loaded on GPU")
    return _sdxl_pipe


def unload_sdxl():
    """Free VRAM by unloading the SDXL pipeline. Call after batch generation."""
    global _sdxl_pipe

    if _sdxl_pipe is not None:
        import torch
        del _sdxl_pipe
        _sdxl_pipe = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[AIImage] SDXL pipeline unloaded, VRAM freed")


def _generate_sdxl_sync(prompt: str, negative_prompt: str, output_path: str,
                         width: int, height: int, steps: int, cfg: float) -> str | None:
    """Synchronous SDXL generation (runs in thread via asyncio.to_thread)."""
    import torch

    pipe = _load_sdxl_pipeline()

    with torch.inference_mode():
        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=cfg,
            num_images_per_prompt=1,
        ).images[0]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path), quality=95)

    size_kb = output_path.stat().st_size / 1024
    print(f"[AIImage] SDXL: {output_path.name} ({size_kb:.0f}KB, {width}x{height}, {steps} steps)")
    return str(output_path)


async def generate_image_sdxl(
    prompt: str,
    output_path: Path,
    niche: str = "",
    orientation: str = "landscape",
) -> str | None:
    """
    Generate an image using local Stable Diffusion XL (FREE, unlimited).

    Requires: diffusers, torch with CUDA, RTX 2080 Ti (11GB VRAM).
    Uses float16 with attention slicing + VAE tiling for memory efficiency.
    Returns path to saved image, or None on failure.
    """
    if not ENABLE_LOCAL_SD:
        return None

    try:
        import torch
        if not torch.cuda.is_available():
            print("[AIImage] SDXL skipped: CUDA not available")
            return None

        # Check available VRAM — SDXL needs ~6GB free
        if _sdxl_pipe is None:  # Only check if model not already loaded
            vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            vram_used = torch.cuda.memory_allocated(0) / (1024**3)
            vram_reserved = torch.cuda.memory_reserved(0) / (1024**3)
            vram_free = vram_total - max(vram_used, vram_reserved)
            if vram_free < 6.0:
                print(f"[AIImage] SDXL skipped: only {vram_free:.1f}GB VRAM free (need 6GB). GPU likely busy.")
                return None
    except ImportError:
        print("[AIImage] SDXL skipped: torch not installed")
        return None

    try:
        import diffusers  # noqa: F401
    except ImportError:
        print("[AIImage] SDXL skipped: diffusers not installed")
        return None

    try:
        # SDXL optimal resolutions (multiples of 64)
        if orientation == "landscape":
            width, height = 1216, 832
        else:
            width, height = 832, 1216

        enhanced = _get_sdxl_prompt(prompt, niche, orientation)
        output_path = Path(output_path).with_suffix(".png")

        result = await asyncio.to_thread(
            _generate_sdxl_sync,
            enhanced,
            SDXL_NEGATIVE_PROMPT,
            str(output_path),
            width,
            height,
            SD_STEPS,
            SD_CFG_SCALE,
        )

        return result

    except Exception as e:
        err_msg = str(e)
        if "out of memory" in err_msg.lower():
            print(f"[AIImage] SDXL OOM — try reducing SD_STEPS or resolution. Falling back to cloud.")
            # Try to recover VRAM
            unload_sdxl()
        else:
            print(f"[AIImage] SDXL failed: {err_msg[:120]}")
        return None


# ── Generator 2: Gemini Flash Image (FREE — 500/day) ─────────

# Models to try in order (most reliable first, updated March 2026)
GEMINI_IMAGE_MODELS = [
    "gemini-2.0-flash-preview-image-generation",  # Most reliable as of March 2026
    "gemini-2.5-flash-image",                      # Nano Banana (fast, efficient)
    "gemini-3.1-flash-image-preview",              # Nano Banana 2 (4K, newest)
]


async def generate_image_gemini(
    prompt: str,
    output_path: Path,
    niche: str = "",
    orientation: str = "landscape",
) -> str | None:
    """
    Generate an image using Gemini Flash Image generation (FREE).

    Tries multiple models for rate limit resilience.
    Returns path to saved image, or None on failure.
    """
    if not GEMINI_API_KEY:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        enhanced = _enhance_prompt(prompt, niche, orientation)

        for model_name in GEMINI_IMAGE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=enhanced,
                    config=genai.types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )

                # Extract image from response
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                        output_path = Path(output_path)
                        output_path.parent.mkdir(parents=True, exist_ok=True)

                        # Determine extension from mime type
                        mime = part.inline_data.mime_type or "image/png"
                        if "jpeg" in mime or "jpg" in mime:
                            if output_path.suffix not in (".jpg", ".jpeg"):
                                output_path = output_path.with_suffix(".jpg")
                        else:
                            if output_path.suffix != ".png":
                                output_path = output_path.with_suffix(".png")

                        with open(output_path, "wb") as f:
                            f.write(part.inline_data.data)

                        size_kb = len(part.inline_data.data) / 1024
                        print(f"[AIImage] Gemini ({model_name.split('/')[-1]}): {output_path.name} ({size_kb:.0f}KB)")
                        return str(output_path)

            except Exception as model_err:
                err_str = str(model_err)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"[AIImage] Gemini {model_name}: rate limited, trying next model...")
                    await asyncio.sleep(3)
                    continue
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    # Model deprecated/removed — skip silently
                    continue
                elif "400" in err_str:
                    continue  # Model doesn't support this, try next
                else:
                    print(f"[AIImage] Gemini {model_name} error: {err_str[:80]}")
                    continue

    except Exception as e:
        print(f"[AIImage] Gemini failed: {e}")

    return None


# ── Generator 3: Cloudflare Workers AI FLUX (FREE — 100K/day) ─

async def generate_image_cloudflare(
    prompt: str,
    output_path: Path,
    niche: str = "",
    orientation: str = "landscape",
) -> str | None:
    """
    Generate an image using Cloudflare Workers AI (FREE — 100K images/day).

    Uses FLUX.1 schnell model. Requires CF_ACCOUNT_ID and CF_API_TOKEN.
    Retries up to 3 times with exponential backoff for reliability.
    Returns path to saved image, or None on failure.
    """
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None

    enhanced = _enhance_prompt(prompt, niche, orientation)
    api_url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {CF_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": enhanced,
                    "width": 1024 if orientation == "landscape" else 768,
                    "height": 768 if orientation == "landscape" else 1024,
                    "num_steps": 8,  # More steps = higher quality, more detail
                },
                timeout=120,  # Increased from 60s for reliability
            )

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                if "image" in content_type:
                    output_path = output_path.with_suffix(".png")
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                elif "json" in content_type:
                    data = response.json()
                    if "result" in data and "image" in data["result"]:
                        img_bytes = base64.b64decode(data["result"]["image"])
                        output_path = output_path.with_suffix(".png")
                        with open(output_path, "wb") as f:
                            f.write(img_bytes)
                    else:
                        print(f"[AIImage] Cloudflare: unexpected response format")
                        continue
                else:
                    print(f"[AIImage] Cloudflare: unexpected content-type: {content_type}")
                    continue

                size_kb = output_path.stat().st_size / 1024
                print(f"[AIImage] Cloudflare FLUX: {output_path.name} ({size_kb:.0f}KB)")
                return str(output_path)

            elif response.status_code == 429:
                # Rate limited — wait and retry
                wait = 2 ** (attempt + 1)
                print(f"[AIImage] Cloudflare rate limited, retrying in {wait}s...")
                await asyncio.sleep(wait)
                continue
            else:
                error_detail = response.text[:200] if response.text else str(response.status_code)
                print(f"[AIImage] Cloudflare API error (attempt {attempt + 1}): {error_detail}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 2 ** (attempt + 1)
            print(f"[AIImage] Cloudflare timeout/connection error (attempt {attempt + 1}/{max_retries}), retrying in {wait}s...")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait)
                continue
            print(f"[AIImage] Cloudflare failed after {max_retries} attempts: {e}")
            return None
        except Exception as e:
            print(f"[AIImage] Cloudflare failed: {e}")
            return None

    return None


# ── Generator 4: DALL-E 3 (PAID fallback — $0.04/image) ──────

async def generate_image_dalle(
    prompt: str,
    output_path: Path,
    size: str = "1792x1024",
    quality: str = "standard",
    niche: str = "",
) -> str | None:
    """
    Generate an image using DALL-E 3 (paid fallback).
    Cost: ~$0.04 (standard) or ~$0.08 (hd) per image.
    """
    if not OPENAI_API_KEY:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        enhanced = _enhance_prompt(prompt, niche)

        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced,
            size=size,
            quality=quality,
            n=1,
        )

        image_url = response.data[0].url
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(img_resp.content)

        print(f"[AIImage] DALL-E 3: {output_path.name}")
        return str(output_path)

    except Exception as e:
        print(f"[AIImage] DALL-E failed: {e}")
        return None


# ── Smart Image Generator (fallback chain) ────────────────────

async def generate_image(
    prompt: str,
    output_path: Path,
    niche: str = "",
    orientation: str = "landscape",
) -> str | None:
    """
    Generate an image using the best available generator.

    PREFER_LOCAL_IMAGES (default): local SDXL first (free/unlimited on the now-idle
    GPU, since video runs on WaveSpeed cloud) -> Cloudflare FLUX -> Gemini -> DALL-E.
    Set PREFER_LOCAL_IMAGES=false to go cloud-first (Cloudflare FLUX).
    """
    try:
        from config import PREFER_LOCAL_IMAGES
    except Exception:
        PREFER_LOCAL_IMAGES = True

    # 1. LOCAL SDXL first when preferred (free, unlimited, GPU is idle now)
    if PREFER_LOCAL_IMAGES:
        result = await generate_image_sdxl(prompt, output_path, niche, orientation)
        if result:
            return result

    # 2. Cloudflare FLUX (truly FREE — 100K/day, instant, cloud fallback)
    result = await generate_image_cloudflare(prompt, output_path, niche, orientation)
    if result:
        return result

    # 3. Gemini (free tier, good quality)
    result = await generate_image_gemini(prompt, output_path, niche, orientation)
    if result:
        return result

    # 4. Local SDXL as fallback if cloud-first mode
    if not PREFER_LOCAL_IMAGES:
        result = await generate_image_sdxl(prompt, output_path, niche, orientation)
        if result:
            return result

    # 5. Fall back to DALL-E (paid — last resort)
    size = "1792x1024" if orientation == "landscape" else "1024x1792"
    result = await generate_image_dalle(prompt, output_path, size=size, niche=niche)
    if result:
        return result

    return None


# ── Scene Image Generator (replaces stock footage) ───────────

async def generate_scene_images(
    scenes: list[dict],
    output_dir: Path,
    max_images: int = 50,
    orientation: str = "landscape",
    niche: str = "",
) -> list[dict]:
    """
    Generate AI images for ALL video scenes.

    If SDXL is available, loads the model once, generates all scenes, then
    unloads to free VRAM for downstream tasks (e.g., Wav2Lip).

    Args:
        scenes: Scene list with visual_description
        output_dir: Where to save images
        max_images: Max images to generate
        orientation: "landscape" or "portrait"
        niche: Niche key for style matching

    Returns:
        List of {scene_number, local_path, type}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    generated = 0
    failed = 0
    total = min(len(scenes), max_images)
    using_sdxl = False

    # Determine target resolution for upscaling
    if orientation == "landscape":
        target_w, target_h = 1920, 1080
    else:
        target_w, target_h = 1080, 1920

    # Check if SDXL is available for batch optimization
    if ENABLE_LOCAL_SD:
        try:
            import torch
            import diffusers  # noqa: F401
            if torch.cuda.is_available():
                using_sdxl = True
                print(f"[AIImage] SDXL available — will generate {total} scenes locally")
        except ImportError:
            pass

    for i, scene in enumerate(scenes):
        if generated >= max_images:
            break

        scene_num = scene.get("scene_number", i + 1)
        visual_desc = scene.get("visual", scene.get("visual_description", ""))

        if not visual_desc:
            continue

        print(f"[AIImage] Generating scene {i + 1}/{total} via {'SDXL' if using_sdxl else 'cloud'}...")

        path = output_dir / f"ai_scene_{scene_num:02d}.png"
        result = await generate_image(visual_desc, path, niche=niche, orientation=orientation)

        if result:
            # Upscale for Ken Burns headroom
            result = _upscale_image(result, target_w, target_h)
            results.append({
                "scene_number": scene_num,
                "local_path": result,
                "type": "ai_image",
            })
            generated += 1
        else:
            failed += 1

        # Small delay between cloud API calls (not needed for local SDXL)
        if not using_sdxl and generated % 5 == 0 and generated > 0:
            await asyncio.sleep(1)

    # Free VRAM after batch generation so Wav2Lip can use GPU
    if using_sdxl:
        unload_sdxl()

    provider = "SDXL" if using_sdxl else ("cloud AI" if (GEMINI_API_KEY or (CF_ACCOUNT_ID and CF_API_TOKEN)) else "DALL-E")
    print(f"[AIImage] Generated {generated}/{total} images via {provider} ({failed} failed)")
    return results


# CLI test
if __name__ == "__main__":

    async def test():
        from config import OUTPUT_DIR
        test_dir = OUTPUT_DIR / "test_ai_images"

        # Test the smart generator (will try SDXL first)
        result = await generate_image(
            prompt="A professional trader analyzing multiple screens with stock charts in a modern office",
            output_path=test_dir / "test_trading.png",
            niche="ai_trading",
            orientation="landscape",
        )
        if result:
            print(f"Success: {result}")
        else:
            print("All generators failed")

        # Cleanup VRAM after test
        unload_sdxl()

    asyncio.run(test())
