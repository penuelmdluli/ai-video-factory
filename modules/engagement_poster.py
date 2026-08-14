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
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Mzansi Baby Stars",
    "limitless_you": "Africa 2050",
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
    Generate a PREMIUM engagement image card (1080x1080 square).

    v2 — Redesigned for maximum visual impact:
    - Clean, modern layout with breathing room
    - Properly wrapped text (no overflow)
    - Brighter backgrounds with niche-matched photos
    - Bold accent bar on left side (modern style)
    - No broken emoji rendering
    - Polls show A/B as separate styled blocks
    """
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    colors = NICHE_COLORS.get(niche, NICHE_COLORS["motivation"])
    accent = colors["accent"]
    accent2 = colors.get("accent2", accent)
    glow = colors.get("glow", accent)

    # ── Background: Pexels photo or clean gradient ──
    bg_photo = _fetch_pexels_bg(niche, W)
    if bg_photo:
        img = bg_photo.convert("RGB")
        # Darken enough for readability but keep photo visible
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.40)  # 40% brightness (was 30%)
        # Niche color tint
        tint = Image.new("RGB", (W, H), accent)
        img = Image.blend(img, tint, 0.15)
        # Soft blur for depth
        img = img.filter(ImageFilter.GaussianBlur(radius=3))
        draw = ImageDraw.Draw(img)
    else:
        _draw_diagonal_gradient(draw, W, H, colors["bg_dark"], colors["bg_mid"],
                               tuple(max(0, c - 5) for c in colors["bg_dark"]))

    # ── Subtle center glow (no harsh circle) ──
    img = _draw_radial_gradient(img, (W // 2, H // 2), 600, glow, 0.10)
    draw = ImageDraw.Draw(img)

    # ── Geometric accents (subtle) ──
    _draw_geometric_accents(draw, W, H, accent, random.randint(0, 3))

    # ── BOLD LEFT ACCENT BAR (modern design element) ──
    draw.rectangle([(0, 0), (12, H)], fill=accent)

    # ── Top accent line ──
    draw.rectangle([(0, 0), (W, 5)], fill=accent)

    # ── Header: Page name ──
    page_name = NICHE_PAGE_NAMES.get(niche, "AI Video Factory")
    name_font = _get_body_font(30, bold=True)
    draw.text((50, 40), page_name.upper(), font=name_font, fill=accent)

    # ── Content type badge (pill shape, no emoji — avoids broken rendering) ──
    type_labels = {
        "quote": "DAILY WISDOM", "tip": "HELPFUL TIP",
        "fact": "DID YOU KNOW", "poll": "YOUR THOUGHTS",
        "advice": "PRACTICAL ADVICE",
    }
    badge_text = type_labels.get(content_type, "FOR YOU")
    badge_font = _get_body_font(20, bold=True)
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = badge_bbox[2] - badge_bbox[0] + 36
    badge_h = badge_bbox[3] - badge_bbox[1] + 14

    bx, by = 50, 85
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)],
                           radius=badge_h // 2, fill=accent)
    draw.text((bx + 18, by + 4), badge_text, font=badge_font, fill=(0, 0, 0))

    # ── Thin divider line ──
    divider_y = by + badge_h + 25
    draw.line([(50, divider_y), (W - 50, divider_y)], fill=accent, width=2)

    # ── CONTENT AREA ──
    margin = 80  # Side margins for text (prevents overflow)
    max_text_w = W - margin * 2
    top_of_content = divider_y + 30
    footer_y = H - 90
    bottom_of_content = footer_y - 20

    if content_type == "quote":
        # ── QUOTE LAYOUT: Large italic-style text with attribution ──
        main_font = _get_font(44)
        text_display = f'"{text}"'
        lines = _wrap_text(text_display, main_font, max_text_w, draw)
        line_height = 58

        # Limit lines to fit
        max_lines = (bottom_of_content - top_of_content - 80) // line_height
        lines = lines[:max_lines]

        total_h = len(lines) * line_height + (50 if secondary_text else 0)
        y_start = top_of_content + (bottom_of_content - top_of_content - total_h) // 2
        y_start = max(y_start, top_of_content)

        for i, line in enumerate(lines):
            y = y_start + i * line_height
            bbox = draw.textbbox((0, 0), line, font=main_font)
            x = (W - (bbox[2] - bbox[0])) // 2
            _draw_text_with_glow(draw, img, (x, y), line, main_font, (255, 255, 255))

        # Attribution (properly wrapped)
        if secondary_text:
            sec_font = _get_body_font(26)
            sec_y = y_start + len(lines) * line_height + 20
            sec_lines = _wrap_text(secondary_text, sec_font, max_text_w, draw)
            for sl in sec_lines[:2]:
                bbox = draw.textbbox((0, 0), sl, font=sec_font)
                sx = (W - (bbox[2] - bbox[0])) // 2
                draw.text((sx + 2, sec_y + 2), sl, font=sec_font, fill=(0, 0, 0))
                draw.text((sx, sec_y), sl, font=sec_font, fill=accent)
                sec_y += 34

    elif content_type == "poll":
        # ── POLL LAYOUT: Question + two styled option blocks ──
        q_font = _get_font(40)
        lines = _wrap_text(text, q_font, max_text_w, draw)
        line_height = 54

        max_lines = 4
        lines = lines[:max_lines]
        y_start = top_of_content + 20

        for i, line in enumerate(lines):
            y = y_start + i * line_height
            bbox = draw.textbbox((0, 0), line, font=q_font)
            x = (W - (bbox[2] - bbox[0])) // 2
            _draw_text_with_glow(draw, img, (x, y), line, q_font, (255, 255, 255))

        # Parse options from secondary_text ("A: xxx  |  B: yyy")
        opt_a = "Option A"
        opt_b = "Option B"
        if secondary_text and "|" in secondary_text:
            parts = secondary_text.split("|")
            opt_a = parts[0].strip().lstrip("A:").strip()
            opt_b = parts[1].strip().lstrip("B:").strip() if len(parts) > 1 else "Option B"

        # Draw option boxes
        opt_font = _get_body_font(32, bold=True)
        opt_y = y_start + len(lines) * line_height + 40
        box_h = 70
        box_margin = 60

        # Option A box
        draw.rounded_rectangle(
            [(box_margin, opt_y), (W - box_margin, opt_y + box_h)],
            radius=15, fill=accent,
        )
        a_text = f"A:  {opt_a}"
        a_lines = _wrap_text(a_text, opt_font, W - box_margin * 2 - 40, draw)
        draw.text((box_margin + 20, opt_y + 18), a_lines[0] if a_lines else a_text,
                  font=opt_font, fill=(0, 0, 0))

        # Option B box
        opt_y2 = opt_y + box_h + 20
        draw.rounded_rectangle(
            [(box_margin, opt_y2), (W - box_margin, opt_y2 + box_h)],
            radius=15, fill=accent2,
        )
        b_text = f"B:  {opt_b}"
        b_lines = _wrap_text(b_text, opt_font, W - box_margin * 2 - 40, draw)
        draw.text((box_margin + 20, opt_y2 + 18), b_lines[0] if b_lines else b_text,
                  font=opt_font, fill=(0, 0, 0))

    else:
        # ── TIP / FACT LAYOUT: Clean centered text + source ──
        main_font = _get_body_font(40, bold=True)
        lines = _wrap_text(text, main_font, max_text_w, draw)
        line_height = 54

        max_lines = (bottom_of_content - top_of_content - 80) // line_height
        lines = lines[:max_lines]

        total_h = len(lines) * line_height + (40 if secondary_text else 0)
        y_start = top_of_content + (bottom_of_content - top_of_content - total_h) // 2
        y_start = max(y_start, top_of_content)

        for i, line in enumerate(lines):
            y = y_start + i * line_height
            bbox = draw.textbbox((0, 0), line, font=main_font)
            x = (W - (bbox[2] - bbox[0])) // 2
            _draw_text_with_glow(draw, img, (x, y), line, main_font, (255, 255, 255))

        # Source text (WRAPPED to fit)
        if secondary_text:
            sec_font = _get_body_font(22)
            sec_y = y_start + len(lines) * line_height + 20
            sec_lines = _wrap_text(secondary_text, sec_font, max_text_w, draw)
            for sl in sec_lines[:2]:
                bbox = draw.textbbox((0, 0), sl, font=sec_font)
                sx = (W - (bbox[2] - bbox[0])) // 2
                draw.text((sx + 1, sec_y + 1), sl, font=sec_font, fill=(0, 0, 0))
                draw.text((sx, sec_y), sl, font=sec_font, fill=accent)
                sec_y += 30

    # ── FOOTER BAR ──
    # Gradient fade into footer
    for i in range(25):
        r = int(accent[0] * i / 25)
        g = int(accent[1] * i / 25)
        b = int(accent[2] * i / 25)
        draw.line([(0, footer_y - 25 + i), (W, footer_y - 25 + i)], fill=(r, g, b))
    draw.rectangle([(0, footer_y), (W, H)], fill=accent)

    # Page name on left (instead of website URL — more branded)
    footer_font = _get_body_font(24, bold=True)
    draw.text((40, footer_y + 25), page_name.upper(), font=footer_font, fill=(0, 0, 0))

    # CTA text on right
    cta_map = {
        "quote": "SAVE & SHARE", "tip": "SCREENSHOT THIS",
        "fact": "SHARE THIS", "poll": "VOTE BELOW",
    }
    cta = cta_map.get(content_type, "ENGAGE")
    cta_bbox = draw.textbbox((0, 0), cta, font=footer_font)
    cta_w = cta_bbox[2] - cta_bbox[0]
    draw.text((W - cta_w - 40, footer_y + 25), cta, font=footer_font, fill=(0, 0, 0))

    # ── ShopMO logo overlay ──
    if niche == "shopmo_products":
        img = _overlay_shopmo_logo(img)

    # ── Subtle vignette for depth ──
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for i in range(80):
        alpha = int(30 * (1 - i / 80))
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
    Generate VIRAL engagement content using Claude AI as the brain.

    Claude crafts everything: the image text, the full caption, hashtags,
    and engagement hooks — all optimized for maximum Facebook reach.

    Returns: {type, text, secondary_text, caption, hashtags}
    """
    niche_name = NICHES.get(niche, {}).get("name", niche)
    page_name = NICHE_PAGE_NAMES.get(niche, niche)
    hashtags = NICHES.get(niche, {}).get("hashtags", [])[:5]

    if content_type == "mixed":
        content_type = random.choice(["quote", "tip", "fact", "poll"])

    # ── NICHE VOICE PROFILES (genuinely helpful, not clickbait) ──
    voice_profiles = {
        "ai_money": "You are a practical AI tools advisor for Smart Money AI. Share real, tested advice about using AI to earn. Be honest about what works and what doesn't. Speak like a helpful friend.",
        "tech_news": "You are a world news analyst for Tech Pulse Africa. Break down global events — wars, politics, geopolitics — so people understand what's really happening. Be factual, balanced, and direct.",
        "motivation": "You are a supportive life coach for Elevate You. Share practical steps people can take today. Be warm, encouraging, and honest. Give real advice, not empty hype.",
        "health_wellness": "You are a trusted wellness advisor for Herbal Organic Life. Share evidence-based health tips. Be caring and responsible. Always recommend consulting a doctor for serious issues.",
        "blissful_moments": "You are a loving parenting guide for Mzansi Baby Stars. Share practical tips for South African parents. Be warm, relatable, and celebrate family moments.",
        "daily_breakdown": "You are a proud South African voice for Mzansi Daily. Share what makes SA great — culture, food, nature, people, innovation. Cover news honestly. Celebrate the country. Be warm, patriotic, real.",
        "limitless_you": "You are an inspiring voice for Africa 2050. Share stories of African progress, innovation, and opportunity. Be proud, forward-looking, and empowering.",
    }
    voice = voice_profiles.get(niche, "You speak with warmth and genuine helpfulness.")

    # ── HELPFUL CONTENT PROMPTS ──
    prompts = {
        "tip": f"""You are the voice behind the Facebook page "{page_name}".
{voice}

Create ONE genuinely helpful tip that will improve someone's day.

RULES:
- Under 25 words — clear and practical
- Must include a SPECIFIC action someone can do TODAY
- Be honest and realistic — no exaggerations
- The tip should genuinely help people solve a real problem
- Make it feel like advice from a trusted friend
- Be relevant and timely for July 2026

Also provide why this works.

Return JSON: {{"tip": "...", "source": "Why it works: ..."}}""",

        "advice": f"""You are the voice behind the Facebook page "{page_name}".
{voice}

Create ONE piece of practical life advice that people will genuinely appreciate and share.

RULES:
- Under 30 words — warm, clear, and useful
- Focus on a real problem people face and offer a simple solution
- Be specific: include a number, timeframe, or exact method
- NO generic motivation like "believe in yourself"
- Write like you're helping a friend — genuine, caring, practical
- The advice should make people feel supported, not lectured

Also create a short follow-up question to encourage comments.

Return JSON: {{"advice": "...", "question": "What do you think? ..."}}""",

        "quote": f"""You are the voice behind the Facebook page "{page_name}".
{voice}

Create ONE meaningful quote that genuinely inspires and helps people.

RULES:
- Under 20 words — memorable and warm
- Must feel authentic and earned, not like a greeting card
- Focus on practical wisdom, not empty motivation
- Should make someone feel understood and encouraged

Return JSON: {{"quote": "...", "attribution": "- {page_name}"}}""",

        "fact": f"""You are the voice behind the Facebook page "{page_name}".
{voice}

Share ONE interesting fact that teaches people something useful.

RULES:
- Under 25 words — clear and informative
- Must be TRUE and verifiable
- Choose something practical that helps people make better decisions
- Make it educational, not shocking for shock's sake

Return JSON: {{"fact": "...", "source": "Source: ..."}}""",

        "poll": f"""You are the voice behind the Facebook page "{page_name}".
{voice}

Create ONE thoughtful question that encourages genuine discussion.

RULES:
- Under 15 words
- Both options should be valid — no trick answers
- Should spark real conversation, not just reactions
- Make it relevant to your audience's daily life

Return JSON: {{"question": "...?", "option_a": "...", "option_b": "..."}}""",
    }

    prompt = prompts.get(content_type, prompts["tip"])

    # ── Try Claude FIRST (primary brain) then Gemini fallback ──
    result = await _generate_with_ai(prompt)

    if not result:
        result = _get_fallback_content(niche, content_type)

    # ── BUILD VIRAL CAPTION (Claude-crafted, not template) ──
    caption = await _build_viral_caption(content_type, result, niche, page_name, hashtags)

    # Build image text
    if content_type == "quote":
        text = result.get("quote", "Your future self is watching. Make them proud.")
        secondary = result.get("attribution", f"- {page_name}")
    elif content_type == "tip":
        text = result.get("tip", "The 2-minute rule: if it takes less than 2 minutes, do it NOW.")
        secondary = result.get("source", "")
    elif content_type == "fact":
        text = result.get("fact", "Your brain processes images 60,000x faster than text.")
        secondary = result.get("source", "")
    elif content_type == "poll":
        text = result.get("question", "Which matters more?")
        opt_a = result.get("option_a", "Option A")
        opt_b = result.get("option_b", "Option B")
        secondary = f"A: {opt_a}  |  B: {opt_b}"
    else:
        text = "Level up today."
        secondary = ""

    return {
        "type": content_type,
        "text": text,
        "secondary_text": secondary,
        "caption": caption,
        "hashtags": hashtags,
    }


async def _build_viral_caption(content_type: str, content: dict, niche: str,
                                page_name: str, hashtags: list[str]) -> str:
    """
    Build a viral Facebook caption using Claude AI.

    Facebook algorithm rewards: comments, shares, saves, time spent reading.
    This caption is engineered for all four.
    """
    # Build the content summary for the caption prompt
    if content_type == "quote":
        core_text = content.get("quote", "")
        attribution = content.get("attribution", "")
        content_summary = f'Quote: "{core_text}" {attribution}'
    elif content_type == "tip":
        core_text = content.get("tip", "")
        content_summary = f"Tip: {core_text}"
    elif content_type == "fact":
        core_text = content.get("fact", "")
        source = content.get("source", "")
        content_summary = f"Fact: {core_text} ({source})"
    elif content_type == "poll":
        q = content.get("question", "")
        a = content.get("option_a", "")
        b = content.get("option_b", "")
        content_summary = f"Poll: {q} | A: {a} | B: {b}"
    else:
        content_summary = str(content)

    caption_prompt = f"""Write a VIRAL Facebook caption for this content from the page "{page_name}".

CONTENT: {content_summary}
TYPE: {content_type}

CAPTION RULES (Facebook algorithm optimization):
1. HOOK (first line): Pattern interrupt that stops the scroll. Use caps, a bold claim, or a question. This is the ONLY line people see before clicking "See more"
2. BODY: Present the content naturally. Add context or a mini-story (2-3 lines max)
3. ENGAGEMENT TRIGGER: End with something that DEMANDS a response — a question, challenge, or "tag someone"
4. Use line breaks for readability (Facebook loves whitespace)
5. Use 2-4 emojis strategically (not every line)
6. Keep total caption under 300 characters for maximum reach
7. DO NOT include hashtags (I'll add them separately)
8. DO NOT include any URLs

{"For polls: present both options clearly with A: and B: and say 'Comment your answer below!'" if content_type == "poll" else ""}

Return ONLY the caption text, no quotes:"""

    caption = None

    # Try Claude for the caption
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=250,
                messages=[{"role": "user", "content": caption_prompt}],
            )
            caption = response.content[0].text.strip().strip('"')
        except Exception as e:
            print(f"[Engagement] Claude caption gen failed: {e}")

    # Fallback to template captions
    if not caption:
        if content_type == "quote":
            quote = content.get("quote", "")
            attr = content.get("attribution", "")
            caption = f'THIS hit different 🔥\n\n"{quote}"\n{attr}\n\nType "YES" if this resonates 👇'
        elif content_type == "tip":
            tip = content.get("tip", "")
            caption = f"SAVE THIS before you forget 💡\n\n{tip}\n\nTag someone who needs to see this 👇"
        elif content_type == "fact":
            fact = content.get("fact", "")
            caption = f"Wait... WHAT? 🤯\n\n{fact}\n\nDid you know this? Comment below 👇"
        elif content_type == "poll":
            q = content.get("question", "")
            a = content.get("option_a", "")
            b = content.get("option_b", "")
            caption = f"This is DIVIDING our community 🔥\n\n{q}\n\nA: {a}\nB: {b}\n\nDrop your answer below! 👇"
        else:
            caption = f"Thoughts? 💭\n\n{content_summary}\n\nComment below 👇"

    # ── Add hashtags ──
    caption += "\n\n" + " ".join(hashtags)

    # ── Add monetization CTAs ──
    from modules.affiliate_manager import get_engagement_cta, get_lead_magnet_cta
    engagement_cta = get_engagement_cta(niche)
    if engagement_cta:
        caption += f"\n\n{engagement_cta}"

    # Lead magnet CTA (25% chance — not too spammy)
    if random.random() < 0.25:
        lead_cta = get_lead_magnet_cta(niche)
        if lead_cta:
            caption += f"\n\n{lead_cta}"

    # Website URL
    website = get_website_url(niche)
    if website not in caption:
        caption += f"\n\n🔗 {website}"

    return caption


async def _generate_with_ai(prompt: str) -> dict | None:
    """Generate content using Claude (primary) or Gemini (fallback).

    Claude is primary because Gemini free tier quota is easily exhausted
    by the video pipeline, leaving nothing for engagement posts.
    """
    # Try Claude first (reliable, no free-tier quota issues)
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
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

    # Fallback to Gemini
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
    from config import page_locked

    # Locked page (e.g. blissful_moments = SAGA OF THE NORTH) — never post here.
    if page_locked(niche):
        print(f"[Engagement] {niche} page is locked to its own poster — skipping")
        return {"success": False, "error": "page_locked"}

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
