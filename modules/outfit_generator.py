"""
Outfit Generator — AI-generated outfit variations for the news anchor.

Pipeline:
1. Describe anchor's appearance from base photo (Gemini Vision, one-time, cached)
2. Pick a random outfit from OUTFIT_BANK
3. Generate new image via Gemini image generation
4. Fall back to base photo if generation fails

Cache: assets/news_anchor/outfits/outfit_{hash}.png
"""
import hashlib
import json
import random
from pathlib import Path

from config import GEMINI_API_KEY, ASSETS_DIR


# ── Base Photo Path ────────────────────────────────────────────
NEWS_ANCHOR_DIR = ASSETS_DIR / "news_anchor"
OUTFITS_DIR = NEWS_ANCHOR_DIR / "outfits"
BASE_PHOTO = NEWS_ANCHOR_DIR / "base_photo.jpg"
APPEARANCE_CACHE = NEWS_ANCHOR_DIR / "appearance.json"


# ── Outfit Bank ────────────────────────────────────────────────
OUTFIT_BANK = [
    "sharp navy blue suit with crisp white shirt and red tie, professional news anchor look",
    "sleek charcoal grey suit with light blue shirt, modern broadcast journalist style",
    "black turtleneck sweater, intellectual news commentator look, clean and sharp",
    "casual dark blazer over a white crew-neck t-shirt, relaxed news analysis style",
    "burgundy suit jacket with black shirt, bold and confident news presenter",
    "classic black suit with white shirt and silver tie, formal evening news anchor",
    "olive green military-style jacket, field reporter war correspondent look",
    "brown leather jacket over dark henley, investigative journalist style",
    "light grey suit with no tie, open collar, modern daytime news style",
    "dark denim jacket over black shirt, casual weekend news roundup look",
    "all-black ensemble — black shirt, black blazer, sleek and authoritative",
    "white shirt with rolled sleeves, hands-on breaking news analyst look",
    "pinstripe navy suit, classic Wall Street meets newsroom professional",
    "dark green sweater over collared shirt, smart casual commentary style",
    "royal blue blazer with white pocket square, polished broadcast personality",
]


async def describe_anchor_appearance(photo_path: Path | str | None = None) -> str:
    """
    Use Gemini Vision to describe the anchor's appearance from their photo.
    Result is cached to avoid repeated API calls.

    Returns a description string like:
    "young Black man with short dark hair, clean shaven, medium build"
    """
    if photo_path is None:
        photo_path = BASE_PHOTO
    photo_path = Path(photo_path)

    # Check cache
    if APPEARANCE_CACHE.exists():
        try:
            cached = json.loads(APPEARANCE_CACHE.read_text())
            if cached.get("description"):
                return cached["description"]
        except Exception:
            pass

    if not GEMINI_API_KEY:
        return "professional male news anchor"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        # Read the image
        image_bytes = photo_path.read_bytes()

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                """Describe this person's physical appearance for use in an AI image generation prompt.
Include: gender, ethnicity/skin tone, hair style and color, facial hair, approximate age, build.
Keep it factual and concise (one sentence).
Example: "young Black man with short cropped dark hair, clean shaven, athletic build, warm brown eyes"
Do NOT include clothing or background — just the person.""",
            ],
        )

        if response and response.text:
            description = response.text.strip().strip('"').strip("'")
            # Cache it
            APPEARANCE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            APPEARANCE_CACHE.write_text(json.dumps({
                "description": description,
                "photo": str(photo_path),
                "generated_at": str(Path(photo_path).stat().st_mtime),
            }, indent=2))
            print(f"[Outfit] Anchor appearance: {description}")
            return description

    except Exception as e:
        print(f"[Outfit] Gemini vision failed: {e}")

    return "professional male news anchor"


async def generate_anchor_with_outfit(
    outfit_desc: str,
    output_path: Path,
    appearance: str | None = None,
) -> str | None:
    """
    Generate an image of the anchor wearing a specific outfit.
    Uses Gemini image generation.

    Returns path to generated image, or None if failed.
    """
    if not GEMINI_API_KEY:
        return None

    if appearance is None:
        appearance = await describe_anchor_appearance()

    prompt = f"""Professional photograph of a {appearance}, sitting at a modern news broadcast desk.
Wearing: {outfit_desc}.
Studio lighting with subtle blue/red accent lights in background.
Multiple monitors showing news graphics visible behind.
Upper body portrait, facing camera, confident expression, slight smile.
Photorealistic, 4K quality, broadcast TV style.
Dark studio background with professional news set."""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        # Try multiple image models
        image_models = [
            "gemini-2.0-flash-exp-image-generation",
            "gemini-2.5-flash-image",
        ]
        response = None
        for img_model in image_models:
            try:
                response = client.models.generate_content(
                    model=img_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                )
                if response and response.candidates:
                    break
            except Exception as me:
                print(f"[Outfit] {img_model}: {me}")
                continue

        # Extract image from response
        if response and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_data = part.inline_data.data
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(image_data)
                    print(f"[Outfit] Generated: {output_path.name} ({len(image_data)//1024}KB)")
                    return str(output_path)

        print(f"[Outfit] Gemini returned no image for outfit: {outfit_desc[:40]}...")
        return None

    except Exception as e:
        print(f"[Outfit] Gemini image generation failed: {e}")
        return None


async def get_anchor_image(
    output_dir: Path | str,
    force_outfit: str | None = None,
) -> str:
    """
    Main entry point: get an anchor image with a random outfit.

    1. Try AI-generated outfit variation
    2. Fall back to base photo

    Returns path to the anchor image.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    OUTFITS_DIR.mkdir(parents=True, exist_ok=True)

    # Pick a random outfit
    outfit = force_outfit or random.choice(OUTFIT_BANK)

    # Check cache
    outfit_hash = hashlib.md5(outfit.encode()).hexdigest()[:10]
    cached_path = OUTFITS_DIR / f"outfit_{outfit_hash}.png"

    if cached_path.exists() and cached_path.stat().st_size > 10000:
        print(f"[Outfit] Using cached outfit: {cached_path.name}")
        return str(cached_path)

    # Try AI generation
    print(f"[Outfit] Generating: {outfit[:50]}...")
    appearance = await describe_anchor_appearance()
    result = await generate_anchor_with_outfit(outfit, cached_path, appearance)

    if result and Path(result).exists():
        return result

    # Fallback to base photo
    base = BASE_PHOTO
    if not base.exists():
        # Try PNG variant
        base = NEWS_ANCHOR_DIR / "base_photo.png"

    if base.exists():
        print(f"[Outfit] Falling back to base photo: {base.name}")
        return str(base)

    raise FileNotFoundError(
        f"No anchor image found. Place your photo at {BASE_PHOTO}"
    )
