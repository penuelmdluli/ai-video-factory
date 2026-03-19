"""
Engagement Poster — Generates and posts image/text content to Facebook pages.

Posts between video uploads to keep followers engaged:
- Motivational quotes with branded image cards
- Tips & facts as visual infographics
- Polls & questions to drive comments
- Mixed content rotating through all types

Uses PIL for image generation with eye-catching visual effects:
- Radial/diagonal gradients, glow effects, geometric accents
- Centered text with proper vertical distribution
- Niche-specific color schemes and branding
"""
import os
import json
import math
import random
import asyncio
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

import requests as _requests

from config import (
    NICHES,
    ASSETS_DIR,
    OUTPUT_DIR,
    GEMINI_API_KEY,
    ANTHROPIC_API_KEY,
    ENGAGEMENT_CONTENT_TYPES,
    SHOPMO_LOGO_PATH,
    PEXELS_API_KEY,
    get_website_url,
)

# ── Niche Color Schemes ────────────────────────────────────
NICHE_COLORS = {
    "ai_trading": {
        "accent": (0, 255, 136), "accent2": (0, 180, 255),
        "bg_dark": (8, 15, 12), "bg_mid": (12, 30, 22), "glow": (0, 255, 136),
    },
    "ai_money": {
        "accent": (0, 200, 255), "accent2": (100, 255, 200),
        "bg_dark": (8, 12, 22), "bg_mid": (12, 22, 40), "glow": (0, 200, 255),
    },
    "tech_news": {
        "accent": (130, 100, 255), "accent2": (200, 100, 255),
        "bg_dark": (12, 8, 22), "bg_mid": (22, 14, 40), "glow": (130, 100, 255),
    },
    "motivation": {
        "accent": (255, 200, 0), "accent2": (255, 120, 0),
        "bg_dark": (22, 18, 5), "bg_mid": (38, 28, 8), "glow": (255, 200, 0),
    },
    "health_wellness": {
        "accent": (100, 220, 100), "accent2": (50, 200, 180),
        "bg_dark": (8, 22, 10), "bg_mid": (14, 35, 16), "glow": (100, 220, 100),
    },
    "blissful_moments": {
        "accent": (255, 180, 100), "accent2": (255, 120, 160),
        "bg_dark": (22, 16, 10), "bg_mid": (38, 26, 15), "glow": (255, 180, 100),
    },
    "daily_breakdown": {
        "accent": (220, 50, 50), "accent2": (255, 120, 50),
        "bg_dark": (22, 8, 8), "bg_mid": (38, 14, 14), "glow": (220, 50, 50),
    },
    "shopmo_products": {
        "accent": (255, 100, 0), "accent2": (255, 180, 0),
        "bg_dark": (22, 12, 4), "bg_mid": (38, 20, 8), "glow": (255, 100, 0),
    },
    "limitless_you": {
        "accent": (0, 180, 255), "accent2": (100, 80, 255),
        "bg_dark": (8, 12, 25), "bg_mid": (14, 22, 45), "glow": (0, 180, 255),
    },
}

# ── Page Display Names ────────────────────────────────────────
NICHE_PAGE_NAMES = {
    "ai_trading": "Beast Mode Academy",
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Blissful Moments",
    "daily_breakdown": "The Daily Breakdown",
    "shopmo_products": "ShopMO",
    "limitless_you": "Limitless You",
}

# ── Niche Emojis for visual punch ─────────────────────────────
NICHE_EMOJIS = {
    "ai_trading": "📊", "ai_money": "💰", "tech_news": "🔬",
    "motivation": "🔥", "health_wellness": "🌿", "blissful_moments": "✨",
    "daily_breakdown": "📰", "shopmo_products": "🛒", "limitless_you": "🧠",
}

# ── Pexels background search queries per niche ────────────────
NICHE_BG_QUERIES = {
    "ai_trading": ["stock market chart dark", "trading desk technology", "financial data dark"],
    "ai_money": ["money technology futuristic", "digital finance", "success business dark"],
    "tech_news": ["futuristic technology", "circuit board dark", "artificial intelligence"],
    "motivation": ["sunrise mountain", "lion powerful", "runner dark silhouette"],
    "health_wellness": ["healthy food green", "yoga nature", "meditation peaceful"],
    "blissful_moments": ["sunset beautiful", "happy people nature", "golden hour landscape"],
    "daily_breakdown": ["newspaper desk", "world globe dark", "news studio"],
    "shopmo_products": ["shopping lifestyle", "product unboxing", "online shopping"],
    "limitless_you": ["brain neural network", "galaxy stars", "person mountain top"],
}

# Cache for downloaded backgrounds
_bg_cache: dict[str, list[str]] = {}


def _fetch_pexels_bg(niche: str, size: int = 1080) -> Image.Image | None:
    """Fetch a random stock photo from Pexels to use as engagement background."""
    if not PEXELS_API_KEY:
        return None

    queries = NICHE_BG_QUERIES.get(niche, ["abstract dark background"])
    query = random.choice(queries)

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "per_page": 15, "orientation": "square", "size": "medium"}
        resp = _requests.get("https://api.pexels.com/v1/search", headers=headers,
                             params=params, timeout=10)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])

        if not photos:
            return None

        photo = random.choice(photos)
        # Get a reasonably sized image
        img_url = photo.get("src", {}).get("large", photo.get("src", {}).get("medium", ""))
        if not img_url:
            return None

        img_resp = _requests.get(img_url, timeout=15)
        img_resp.raise_for_status()

        from io import BytesIO
        img = Image.open(BytesIO(img_resp.content))

        # Crop to square from center
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        img = img.resize((size, size), Image.LANCZOS)

        return img

    except Exception as e:
        print(f"[Engagement] Pexels bg fetch failed: {e}")
        return None


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load Impact or Arial Black font."""
    font_paths = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
        ASSETS_DIR / "fonts" / "Impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(str(fp), size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _get_body_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a clean body font."""
    if bold:
        paths = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]
    else:
        paths = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    for fp in paths:
        try:
            return ImageFont.truetype(str(fp), size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_radial_gradient(img: Image.Image, center: tuple, radius: float,
                          color: tuple, intensity: float = 0.3):
    """Draw a soft radial glow effect."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(int(radius), 0, -3):
        alpha = int(intensity * 255 * (r / radius))
        alpha = min(alpha, 100)
        draw.ellipse(
            [center[0] - r, center[1] - r, center[0] + r, center[1] + r],
            fill=(*color, alpha)
        )
    img_rgba = img.convert("RGBA")
    return Image.alpha_composite(img_rgba, overlay).convert("RGB")


def _draw_diagonal_gradient(draw: ImageDraw.Draw, W: int, H: int,
                            c1: tuple, c2: tuple, c3: tuple):
    """Draw a rich diagonal gradient with three color stops."""
    for y in range(H):
        for x in range(0, W, 4):  # Step by 4 for performance
            # Diagonal factor (top-left to bottom-right)
            factor = (x / W * 0.5 + y / H * 0.5)
            if factor < 0.5:
                t = factor * 2
                r = int(c1[0] + (c2[0] - c1[0]) * t)
                g = int(c1[1] + (c2[1] - c1[1]) * t)
                b = int(c1[2] + (c2[2] - c1[2]) * t)
            else:
                t = (factor - 0.5) * 2
                r = int(c2[0] + (c3[0] - c2[0]) * t)
                g = int(c2[1] + (c3[1] - c2[1]) * t)
                b = int(c2[2] + (c3[2] - c2[2]) * t)
            draw.rectangle([(x, y), (x + 3, y)], fill=(r, g, b))


def _draw_geometric_accents(draw: ImageDraw.Draw, W: int, H: int,
                            accent: tuple, style: int = 0):
    """Draw geometric accent shapes for visual interest."""
    alpha_accent = (*accent, 30)

    if style == 0:
        # Corner lines
        for i in range(5):
            offset = i * 25
            draw.line([(0, offset), (offset, 0)], fill=(*accent, 60), width=2)
            draw.line([(W, H - offset), (W - offset, H)], fill=(*accent, 60), width=2)
    elif style == 1:
        # Dotted grid
        for x in range(0, W, 60):
            for y in range(0, H, 60):
                draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(*accent, 20))
    elif style == 2:
        # Diagonal stripes
        for i in range(-H, W + H, 80):
            draw.line([(i, 0), (i + H, H)], fill=(*accent, 15), width=1)
    elif style == 3:
        # Corner accent blocks
        block_size = 120
        draw.rectangle([(0, 0), (block_size, 6)], fill=accent)
        draw.rectangle([(0, 0), (6, block_size)], fill=accent)
        draw.rectangle([(W - block_size, H - 6), (W, H)], fill=accent)
        draw.rectangle([(W - 6, H - block_size), (W, H)], fill=accent)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int,
               draw: ImageDraw.Draw) -> list[str]:
    """Word-wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_text_with_glow(draw: ImageDraw.Draw, img: Image.Image,
                         xy: tuple, text: str, font: ImageFont.FreeTypeFont,
                         fill: tuple, glow_color: tuple = None,
                         anchor: str = None):
    """Draw text with a subtle glow/shadow effect."""
    x, y = xy
    # Shadow layers
    for offset in [3, 2]:
        draw.text((x + offset, y + offset), text, font=font,
                  fill=(0, 0, 0), anchor=anchor)
    # Main text
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _overlay_shopmo_logo(img: Image.Image) -> Image.Image:
    """Overlay ShopMO logo if it exists."""
    logo_path = SHOPMO_LOGO_PATH
    if not logo_path.exists():
        return img
    try:
        logo = Image.open(logo_path).convert("RGBA")
        ratio = 150 / logo.width
        logo = logo.resize((150, int(logo.height * ratio)), Image.LANCZOS)
        x = img.width - logo.width - 30
        y = img.height - logo.height - 100
        img_rgba = img.convert("RGBA")
        img_rgba.paste(logo, (x, y), logo)
        return img_rgba.convert("RGB")
    except Exception:
        return img


def generate_engagement_image(
    content_type: str,
    text: str,
    niche: str,
    output_path: str | Path,
    secondary_text: str = "",
) -> str:
    """
    Generate a premium engagement image card (1080x1080 square).

    Features:
    - Diagonal gradient backgrounds with radial glow
    - Centered, vertically distributed text
    - Geometric accent patterns
    - Accent divider lines
    - Branded header and footer bars
    """
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    colors = NICHE_COLORS.get(niche, NICHE_COLORS["motivation"])
    accent = colors["accent"]
    accent2 = colors.get("accent2", accent)
    glow = colors.get("glow", accent)

    # ── Background: try Pexels stock photo first, fallback to gradient ──
    bg_photo = _fetch_pexels_bg(niche, W)
    if bg_photo:
        img = bg_photo.convert("RGB")
        # Darken the photo significantly so text is readable
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.3)  # 30% brightness
        # Add color tint matching niche
        tint = Image.new("RGB", (W, H), accent)
        img = Image.blend(img, tint, 0.1)  # 10% tint
        # Slight blur for depth
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        draw = ImageDraw.Draw(img)
    else:
        # Fallback: diagonal gradient
        _draw_diagonal_gradient(draw, W, H, colors["bg_dark"], colors["bg_mid"],
                               tuple(max(0, c - 5) for c in colors["bg_dark"]))

    # ── Radial glow from center ──
    img = _draw_radial_gradient(img, (W // 2, H // 2 - 60), 500, glow, 0.18)
    # Secondary glow at top-right
    img = _draw_radial_gradient(img, (W - 100, 100), 350, accent2, 0.10)
    draw = ImageDraw.Draw(img)

    # ── Geometric accents ──
    style = random.randint(0, 3)
    _draw_geometric_accents(draw, W, H, accent, style)

    # ── Top accent bar (thick gradient feel) ──
    for i in range(8):
        alpha_ratio = 1.0 - (i / 8)
        r = int(accent[0] * alpha_ratio)
        g = int(accent[1] * alpha_ratio)
        b = int(accent[2] * alpha_ratio)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    # ── Header: Page name + emoji ──
    page_name = NICHE_PAGE_NAMES.get(niche, "AI Video Factory")
    emoji = NICHE_EMOJIS.get(niche, "💡")
    name_font = _get_font(32)
    header_text = f"{page_name.upper()}"
    draw.text((50, 35), header_text, font=name_font, fill=accent)

    # ── Content type badge (pill shape) ──
    type_labels = {
        "quote": "💬 DAILY QUOTE", "tip": "💡 PRO TIP",
        "fact": "🔍 DID YOU KNOW?", "poll": "🗳️ YOUR OPINION",
    }
    badge_text = type_labels.get(content_type, "✨ INSIGHT")
    badge_font = _get_font(22)
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = badge_bbox[2] - badge_bbox[0] + 40
    badge_h = badge_bbox[3] - badge_bbox[1] + 16

    # Pill-shaped badge
    bx, by = 50, 85
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)],
                           radius=badge_h // 2, fill=accent)
    draw.text((bx + 20, by + 5), badge_text, font=badge_font, fill=(0, 0, 0))

    # ── Accent divider line ──
    divider_y = by + badge_h + 30
    draw.line([(50, divider_y), (W - 50, divider_y)], fill=(*accent, 80), width=2)

    # ── Main text (CENTERED, vertically distributed) ──
    if content_type == "quote":
        main_font = _get_font(48)
        text_display = f'"{text}"'
    else:
        main_font = _get_body_font(42, bold=True)
        text_display = text

    lines = _wrap_text(text_display, main_font, W - 120, draw)
    line_height = 62 if content_type == "quote" else 56

    # Calculate vertical centering
    total_text_height = len(lines) * line_height
    sec_height = 50 if secondary_text else 0
    content_block_height = total_text_height + sec_height

    # Available space: between divider and bottom bar
    top_of_content = divider_y + 20
    bottom_of_content = H - 110  # Leave room for footer
    available_height = bottom_of_content - top_of_content

    # Center the content block vertically
    y_start = top_of_content + (available_height - content_block_height) // 2
    y_start = max(y_start, top_of_content + 10)

    for i, line in enumerate(lines):
        y = y_start + i * line_height
        if y > bottom_of_content - 60:
            break
        # Center horizontally
        bbox = draw.textbbox((0, 0), line, font=main_font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2

        _draw_text_with_glow(draw, img, (x, y), line, main_font, (255, 255, 255))

    # ── Secondary text (attribution/source) ──
    if secondary_text:
        sec_font = _get_body_font(28)
        sec_y = y_start + len(lines) * line_height + 25
        sec_y = min(sec_y, bottom_of_content - 40)
        bbox = draw.textbbox((0, 0), secondary_text, font=sec_font)
        sec_w = bbox[2] - bbox[0]
        sec_x = (W - sec_w) // 2
        draw.text((sec_x + 2, sec_y + 2), secondary_text, font=sec_font, fill=(0, 0, 0))
        draw.text((sec_x, sec_y), secondary_text, font=sec_font, fill=accent)

    # ── Bottom accent bar + gradient ──
    footer_y = H - 85
    # Gradient fade into bottom bar
    for i in range(20):
        alpha = int(255 * (i / 20))
        r = int(accent[0] * i / 20)
        g = int(accent[1] * i / 20)
        b = int(accent[2] * i / 20)
        draw.line([(0, footer_y - 20 + i), (W, footer_y - 20 + i)],
                  fill=(r, g, b))
    draw.rectangle([(0, footer_y), (W, H)], fill=accent)

    # Website URL (left)
    url_font = _get_font(26)
    website = get_website_url(niche)
    draw.text((40, footer_y + 22), website, font=url_font, fill=(0, 0, 0))

    # CTA text (right)
    cta_map = {
        "quote": "SAVE & SHARE", "tip": "SAVE THIS!",
        "fact": "SHARE THIS!", "poll": "COMMENT BELOW!",
    }
    cta = cta_map.get(content_type, "ENGAGE!")
    cta_bbox = draw.textbbox((0, 0), cta, font=url_font)
    cta_w = cta_bbox[2] - cta_bbox[0]
    draw.text((W - cta_w - 40, footer_y + 22), cta, font=url_font, fill=(0, 0, 0))

    # ── Emoji accent in bottom-right area (above footer) ──
    emoji_font = _get_body_font(72)
    try:
        draw.text((W - 120, footer_y - 90), emoji, font=emoji_font, fill=(255, 255, 255))
    except Exception:
        pass  # Emoji rendering may fail on some systems

    # ── ShopMO logo overlay ──
    if niche == "shopmo_products":
        img = _overlay_shopmo_logo(img)

    # ── Slight vignette for depth ──
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for i in range(100):
        alpha = int(40 * (1 - i / 100))
        v_draw.rectangle([(i, i), (W - i, H - i)], outline=(0, 0, 0, alpha))
    img_rgba = img.convert("RGBA")
    img = Image.alpha_composite(img_rgba, vignette).convert("RGB")

    # Save
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), quality=95)
    print(f"[Engagement] Image generated: {output_path.name} ({content_type})")
    return str(output_path)


async def generate_engagement_content(niche: str, content_type: str) -> dict:
    """
    Generate engagement content using AI (Gemini/Claude).

    Returns: {type, text, secondary_text, caption, hashtags}
    """
    niche_name = NICHES.get(niche, {}).get("name", niche)
    hashtags = NICHES.get(niche, {}).get("hashtags", [])[:5]

    # Self-improvement niches get AI-coach framing for authority
    is_self_improvement = niche in ("limitless_you", "motivation")
    ai_frame = " Frame it as an insight from AI analysis of research/data — e.g. 'AI analyzed 10,000+ success stories and found...' or 'Data shows that...'. Make it feel like wisdom backed by AI intelligence, not generic motivation." if is_self_improvement else ""

    prompts = {
        "quote": f"""Generate ONE powerful, original motivational quote relevant to the {niche_name} niche.
The quote should be inspiring, shareable, and under 25 words.{ai_frame}
Also provide a short attribution (real or "- {NICHE_PAGE_NAMES.get(niche, 'Unknown')}").

Return JSON: {{"quote": "...", "attribution": "- ..."}}""",

        "tip": f"""Generate ONE practical, actionable tip for the {niche_name} audience.
The tip should be specific, useful, and under 30 words. Something people would save.{ai_frame}
Include a concrete number, timeframe, or method — not vague advice.

Return JSON: {{"tip": "...", "source": "Based on latest research"}}""",

        "fact": f"""Generate ONE surprising, true fact relevant to {niche_name}.
Include a specific number or statistic. Under 30 words. Must be factual.{ai_frame}

Return JSON: {{"fact": "...", "source": "Source: ..."}}""",

        "poll": f"""Generate ONE engaging poll question for the {niche_name} audience.
Include exactly 2 options (A and B). Should spark debate in comments.{ai_frame}

Return JSON: {{"question": "...?", "option_a": "...", "option_b": "..."}}""",
    }

    if content_type == "mixed":
        content_type = random.choice(["quote", "tip", "fact", "poll"])

    prompt = prompts.get(content_type, prompts["tip"])

    # Try Gemini first, then Claude
    result = await _generate_with_ai(prompt)

    if not result:
        # Fallback to hardcoded content
        result = _get_fallback_content(niche, content_type)

    # Build output
    if content_type == "quote":
        text = result.get("quote", "Stay focused. Stay hungry. Stay humble.")
        secondary = result.get("attribution", f"- {NICHE_PAGE_NAMES.get(niche, 'Unknown')}")
        caption = f'"{text}" {secondary}\n\n' + " ".join(hashtags)
    elif content_type == "tip":
        text = result.get("tip", "Start small. Stay consistent. Results follow.")
        secondary = result.get("source", "")
        caption = f"💡 PRO TIP: {text}\n\nSave this for later!\n\n" + " ".join(hashtags)
    elif content_type == "fact":
        text = result.get("fact", "The average person spends 2 hours daily on social media.")
        secondary = result.get("source", "")
        caption = f"🔍 DID YOU KNOW?\n\n{text}\n\n" + " ".join(hashtags)
    elif content_type == "poll":
        question = result.get("question", "Which do you prefer?")
        opt_a = result.get("option_a", "Option A")
        opt_b = result.get("option_b", "Option B")
        text = question
        secondary = f"A: {opt_a}  |  B: {opt_b}"
        caption = f"🗳️ YOUR OPINION MATTERS!\n\n{question}\n\nA: {opt_a}\nB: {opt_b}\n\nComment A or B below! 👇\n\n" + " ".join(hashtags)
    else:
        text = "Stay focused on your goals."
        secondary = ""
        caption = text + "\n\n" + " ".join(hashtags)

    # Add monetization CTAs to caption
    from modules.affiliate_manager import get_engagement_cta, get_lead_magnet_cta
    engagement_cta = get_engagement_cta(niche)
    if engagement_cta:
        caption += f"\n\n{engagement_cta}"

    # Add lead magnet CTA every ~3rd post (33% chance)
    if random.random() < 0.33:
        lead_cta = get_lead_magnet_cta(niche)
        if lead_cta:
            caption += f"\n\n{lead_cta}"

    # Add website URL to caption
    website = get_website_url(niche)
    if website not in caption:
        caption += f"\n\n🔗 {website}"

    return {
        "type": content_type,
        "text": text,
        "secondary_text": secondary,
        "caption": caption,
        "hashtags": hashtags,
    }


async def _generate_with_ai(prompt: str) -> dict | None:
    """Generate content using Gemini or Claude."""
    # Try Gemini first
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"[Engagement] Gemini failed: {e}")

    # Try Claude
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt + "\n\nRespond with ONLY the JSON, no markdown."}],
            )
            text = response.content[0].text.strip()
            # Strip markdown code block if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            print(f"[Engagement] Claude failed: {e}")

    return None


def _get_fallback_content(niche: str, content_type: str) -> dict:
    """Hardcoded fallback content when AI is unavailable."""
    fallbacks = {
        "quote": {
            "ai_trading": {"quote": "The market rewards patience and punishes greed.", "attribution": "- Beast Mode Academy"},
            "ai_money": {"quote": "Your income is a direct reflection of your value to the marketplace.", "attribution": "- Jim Rohn"},
            "tech_news": {"quote": "Technology is best when it brings people together.", "attribution": "- Matt Mullenweg"},
            "motivation": {"quote": "Discipline is the bridge between goals and accomplishment.", "attribution": "- Jim Rohn"},
            "health_wellness": {"quote": "Take care of your body. It's the only place you have to live.", "attribution": "- Jim Rohn"},
            "blissful_moments": {"quote": "Happiness is not something you find. It's something you create.", "attribution": "- Blissful Moments"},
            "daily_breakdown": {"quote": "An informed citizen is democracy's greatest asset.", "attribution": "- The Daily Breakdown"},
            "shopmo_products": {"quote": "Smart shopping is an art. ShopMO makes it easy.", "attribution": "- ShopMO"},
            "limitless_you": {"quote": "AI analyzed 10,000 high performers. The #1 trait wasn't talent — it was showing up on the days they didn't feel like it.", "attribution": "- Limitless You AI"},
        },
        "tip": {
            "ai_trading": {"tip": "Always set stop-losses before entering a trade. Protect your capital first, profits second.", "source": "Based on risk management research"},
            "ai_money": {"tip": "Automate 20% of your income into investments before spending. Pay yourself first.", "source": "Based on wealth-building data"},
            "tech_news": {"tip": "Use AI tools to automate repetitive tasks. The average worker saves 2.5 hours daily.", "source": "Based on productivity research"},
            "motivation": {"tip": "Write down 3 goals every morning. People who do this are 42% more likely to achieve them.", "source": "Based on Dominican University study"},
            "health_wellness": {"tip": "Drink water within 30 minutes of waking. It boosts metabolism by 24% for 90 minutes.", "source": "Based on clinical research"},
            "blissful_moments": {"tip": "Practice gratitude for 5 minutes daily. It increases happiness levels by 25% within 3 weeks.", "source": "Based on positive psychology"},
            "limitless_you": {"tip": "AI analyzed 50,000+ productivity patterns: a 90-minute focus block beats 3 hours of distracted work.", "source": "Based on AI performance analysis"},
        },
        "fact": {
            "ai_trading": {"fact": "AI-powered trading algorithms now handle over 70% of US stock market volume daily.", "source": "Source: Bloomberg Financial"},
            "ai_money": {"fact": "People with multiple income streams earn 2.7x more than those with one source.", "source": "Source: Bureau of Labor Statistics"},
            "tech_news": {"fact": "By 2030, AI will contribute $15.7 trillion to the global economy annually.", "source": "Source: PwC Global AI Study"},
            "motivation": {"fact": "People who write down goals are 42% more likely to achieve them.", "source": "Source: Dominican University"},
            "health_wellness": {"fact": "Walking just 7,000 steps daily reduces mortality risk by 50-70% in adults over 40.", "source": "Source: JAMA Network Open"},
            "blissful_moments": {"fact": "Acts of kindness trigger serotonin in both the giver AND receiver.", "source": "Source: Journal of Social Psychology"},
            "limitless_you": {"fact": "AI analysis of 1M+ daily routines shows: the top 1% spend 47 minutes on learning before 8 AM.", "source": "Source: AI Behavioral Analysis"},
        },
        "poll": {
            "ai_trading": {"question": "Which investment strategy do you prefer?", "option_a": "Long-term investing", "option_b": "Day trading"},
            "ai_money": {"question": "Best way to build wealth in 2026?", "option_a": "Start a side business", "option_b": "Invest in AI stocks"},
            "tech_news": {"question": "Which AI tool has changed your life most?", "option_a": "ChatGPT", "option_b": "AI coding assistants"},
            "motivation": {"question": "What drives you more?", "option_a": "Fear of failure", "option_b": "Vision of success"},
            "health_wellness": {"question": "Which matters more for health?", "option_a": "Diet (what you eat)", "option_b": "Exercise (how you move)"},
            "blissful_moments": {"question": "What brings you more joy?", "option_a": "Quiet alone time", "option_b": "Time with loved ones"},
            "limitless_you": {"question": "AI says these are equally powerful. Which do you prioritize?", "option_a": "Morning routine", "option_b": "Evening reflection"},
        },
    }
    type_fallbacks = fallbacks.get(content_type, {})
    return type_fallbacks.get(niche, type_fallbacks.get("motivation", {"quote": "Keep pushing forward.", "attribution": "- Unknown"}))


async def post_engagement_to_facebook(niche: str, content: dict, image_path: str | None = None) -> dict:
    """
    Post an engagement image or text to a Facebook page.

    Uses Graph API:
    - Image: POST /{page_id}/photos with source + message
    - Text-only: POST /{page_id}/feed with message
    """
    import requests

    page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")

    if not page_id or not page_token:
        print(f"[Engagement] No FB page config for {niche}, skipping")
        return {"success": False, "error": "no_config"}

    api_base = "https://graph.facebook.com/v24.0"

    try:
        if image_path and Path(image_path).exists():
            # Image post
            with open(image_path, "rb") as f:
                response = requests.post(
                    f"{api_base}/{page_id}/photos",
                    data={
                        "message": content["caption"],
                        "access_token": page_token,
                    },
                    files={"source": f},
                    timeout=60,
                )
        else:
            # Text-only post
            response = requests.post(
                f"{api_base}/{page_id}/feed",
                data={
                    "message": content["caption"],
                    "access_token": page_token,
                },
                timeout=30,
            )

        result = response.json()
        if "id" in result:
            post_type = "image" if image_path else "text"
            print(f"[Engagement] FB {post_type} posted to {niche}: {result['id']}")
            return {"success": True, "post_id": result["id"], "type": post_type}
        else:
            error = result.get("error", {}).get("message", str(result))
            print(f"[Engagement] FB post failed for {niche}: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        print(f"[Engagement] FB post error for {niche}: {e}")
        return {"success": False, "error": str(e)}


async def run_engagement_round(
    niches: list[str] | None = None,
    content_type: str | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """
    Run one round of engagement posts for all (or specified) niches.

    Generates content + image, then posts to each Facebook page.
    Returns list of results per niche.
    """
    if niches is None:
        niches = [n for n in NICHES.keys() if os.getenv(f"FB_PAGE_ID_{n}", "")]

    if content_type is None:
        # Rotate based on current hour
        hour = datetime.now().hour
        idx = hour % len(ENGAGEMENT_CONTENT_TYPES)
        content_type = ENGAGEMENT_CONTENT_TYPES[idx]

    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for niche in niches:
        try:
            print(f"\n[Engagement] {niche} | {content_type}")

            # Generate content
            content = await generate_engagement_content(niche, content_type)

            # Generate image
            output_dir = OUTPUT_DIR / "engagement" / niche
            image_path = str(output_dir / f"{content_type}_{timestamp}.jpg")
            generate_engagement_image(
                content_type=content["type"],
                text=content["text"],
                niche=niche,
                output_path=image_path,
                secondary_text=content.get("secondary_text", ""),
            )

            if dry_run:
                print(f"[Engagement] DRY RUN — would post to {niche}: {content['type']}")
                results.append({"niche": niche, "type": content["type"], "success": True, "dry_run": True})
                continue

            # Post to Facebook
            result = await post_engagement_to_facebook(niche, content, image_path)
            result["niche"] = niche
            result["content_type"] = content["type"]
            results.append(result)

            # Small delay between pages to avoid rate limiting
            await asyncio.sleep(3)

        except Exception as e:
            print(f"[Engagement] Error for {niche}: {e}")
            results.append({"niche": niche, "success": False, "error": str(e)})

    # Summary
    success = sum(1 for r in results if r.get("success"))
    print(f"\n[Engagement] Round complete: {success}/{len(results)} posted")
    return results


# CLI test
if __name__ == "__main__":
    async def test():
        # Test image generation for all types
        for ct in ["quote", "tip", "fact", "poll"]:
            content = await generate_engagement_content("motivation", ct)
            generate_engagement_image(
                content_type=content["type"],
                text=content["text"],
                niche="motivation",
                output_path=OUTPUT_DIR / "engagement" / "test" / f"test_{ct}.jpg",
                secondary_text=content.get("secondary_text", ""),
            )
            print(f"  [{ct}] {content['text'][:60]}...")

    asyncio.run(test())
