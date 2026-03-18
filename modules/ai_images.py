"""
AI Image Generator — Creates custom images using FREE AI APIs.

Priority chain (all free):
1. Gemini Flash Image (500/day free — already have API key)
2. Cloudflare Workers AI FLUX (100K/day free — needs free CF account)
3. DALL-E 3 (paid fallback — $0.04/image)

This replaces generic stock footage with exact custom visuals for each scene.
"""
import asyncio
import base64
import requests
from pathlib import Path

from config import OPENAI_API_KEY, GEMINI_API_KEY


# ── Cloudflare Workers AI Config ──────────────────────────────
import os
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")


# ── Niche-Specific Image Style Prompts ────────────────────────
NICHE_IMAGE_STYLES = {
    "ai_trading": "shot on Canon EOS R5, dimly lit trading desk, real monitor screens, shallow depth of field, natural office lighting",
    "ai_money": "shot on Sony A7IV, natural indoor lighting, real laptop on wooden desk, warm ambient light, lifestyle photography",
    "tech_news": "shot on Nikon Z9, clean modern office, real tech devices, soft studio lighting, editorial photography style",
    "motivation": "shot on Canon 5D Mark IV, golden hour natural light, real outdoor location, dramatic sky, documentary style",
    "health_wellness": "shot on Fujifilm X-T5, natural daylight, real fresh ingredients, soft bokeh background, food/lifestyle photography",
    "blissful_moments": "shot on Sony A7III, golden hour, real outdoor location, warm natural tones, soft focus background, lifestyle photography",
    "daily_breakdown": "photojournalism style, Reuters/AP quality, real-world scene, dramatic natural lighting, documentary photography, raw and authentic",
}


def _enhance_prompt(prompt: str, niche: str = "", orientation: str = "landscape") -> str:
    """Enhance a scene description into a photorealistic image prompt.

    Key: We tell the model to generate a PHOTOGRAPH, not an illustration.
    Avoid AI-giveaway words like 'futuristic', 'holographic', 'neon'.
    """
    style = NICHE_IMAGE_STYLES.get(niche, "shot on Canon EOS R5, natural lighting, shallow depth of field")
    aspect = "wide 16:9 horizontal frame" if orientation == "landscape" else "vertical 9:16 portrait frame"

    return (
        f"Professional photograph, {aspect}. "
        f"{style}. "
        f"Scene: {prompt}. "
        f"Photorealistic, real-world setting, natural colors, no AI artifacts. "
        f"No text, no watermarks, no logos, no illustrations, no CGI."
    )


# ── Generator 1: Gemini Flash Image (FREE — 500/day) ─────────

# Models to try in order (newest first)
GEMINI_IMAGE_MODELS = [
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
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
                    await asyncio.sleep(2)
                    continue
                elif "400" in err_str:
                    continue  # Model doesn't support this, try next
                else:
                    print(f"[AIImage] Gemini {model_name} error: {err_str[:80]}")
                    continue

    except Exception as e:
        print(f"[AIImage] Gemini failed: {e}")

    return None


# ── Generator 2: Cloudflare Workers AI FLUX (FREE — 100K/day) ─

async def generate_image_cloudflare(
    prompt: str,
    output_path: Path,
    niche: str = "",
    orientation: str = "landscape",
) -> str | None:
    """
    Generate an image using Cloudflare Workers AI (FREE — 100K images/day).

    Uses FLUX.1 schnell model. Requires CF_ACCOUNT_ID and CF_API_TOKEN.
    Returns path to saved image, or None on failure.
    """
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None

    try:
        enhanced = _enhance_prompt(prompt, niche, orientation)

        # FLUX.1 schnell — fast, high quality (lowercase model name required)
        api_url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"

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
                "num_steps": 4,  # FLUX schnell optimized for 4 steps
            },
            timeout=60,
        )

        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if "image" in content_type:
                # Direct image response
                output_path = output_path.with_suffix(".png")
                with open(output_path, "wb") as f:
                    f.write(response.content)
            elif "json" in content_type:
                # JSON response with base64 image
                data = response.json()
                if "result" in data and "image" in data["result"]:
                    img_bytes = base64.b64decode(data["result"]["image"])
                    output_path = output_path.with_suffix(".png")
                    with open(output_path, "wb") as f:
                        f.write(img_bytes)
                else:
                    print(f"[AIImage] Cloudflare: unexpected response format")
                    return None
            else:
                print(f"[AIImage] Cloudflare: unexpected content-type: {content_type}")
                return None

            size_kb = output_path.stat().st_size / 1024
            print(f"[AIImage] Cloudflare FLUX: {output_path.name} ({size_kb:.0f}KB)")
            return str(output_path)

        else:
            error_detail = response.text[:200] if response.text else str(response.status_code)
            print(f"[AIImage] Cloudflare API error: {error_detail}")
            return None

    except Exception as e:
        print(f"[AIImage] Cloudflare failed: {e}")
        return None


# ── Generator 3: DALL-E 3 (PAID fallback — $0.04/image) ──────

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
    Generate an image using the best available free API.

    Priority: Gemini (free) → Cloudflare FLUX (free) → DALL-E (paid)
    """
    # 1. Try Gemini (free, 500/day)
    result = await generate_image_gemini(prompt, output_path, niche, orientation)
    if result:
        return result

    # 2. Try Cloudflare FLUX (free, 100K/day)
    result = await generate_image_cloudflare(prompt, output_path, niche, orientation)
    if result:
        return result

    # 3. Fall back to DALL-E (paid)
    size = "1792x1024" if orientation == "landscape" else "1024x1792"
    result = await generate_image_dalle(prompt, output_path, size=size, niche=niche)
    if result:
        return result

    return None


# ── Scene Image Generator (replaces stock footage) ───────────

async def generate_scene_images(
    scenes: list[dict],
    output_dir: Path,
    max_images: int = 10,
    orientation: str = "landscape",
    niche: str = "",
) -> list[dict]:
    """
    Generate AI images for video scenes using free APIs.

    With free APIs (Gemini + Cloudflare), we can generate images for EVERY scene
    instead of just a few key moments. This replaces generic stock footage with
    exact custom visuals matching the script.

    Args:
        scenes: Scene list with visual_description
        output_dir: Where to save images
        max_images: Max images to generate (high limit OK with free APIs)
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

    # With free APIs, generate for ALL scenes (not just hook + every 4th)
    for scene in scenes:
        if generated >= max_images:
            break

        scene_num = scene.get("scene_number", 0)
        visual_desc = scene.get("visual", scene.get("visual_description", ""))

        if not visual_desc:
            continue

        path = output_dir / f"ai_scene_{scene_num:02d}.png"
        result = await generate_image(visual_desc, path, niche=niche, orientation=orientation)

        if result:
            results.append({
                "scene_number": scene_num,
                "local_path": result,
                "type": "ai_image",
            })
            generated += 1
        else:
            failed += 1

        # Small delay to respect rate limits
        if generated % 5 == 0:
            await asyncio.sleep(1)

    provider = "free AI" if (GEMINI_API_KEY or (CF_ACCOUNT_ID and CF_API_TOKEN)) else "DALL-E"
    print(f"[AIImage] Generated {generated} images via {provider} ({failed} failed)")
    return results


# CLI test
if __name__ == "__main__":

    async def test():
        from config import OUTPUT_DIR
        test_dir = OUTPUT_DIR / "test_ai_images"

        # Test the smart generator
        result = await generate_image(
            prompt="A futuristic AI trading dashboard with holographic charts and green data streams",
            output_path=test_dir / "test_trading.png",
            niche="ai_trading",
            orientation="landscape",
        )
        if result:
            print(f"Success: {result}")
        else:
            print("All generators failed (likely rate limited, try again later)")

    asyncio.run(test())
