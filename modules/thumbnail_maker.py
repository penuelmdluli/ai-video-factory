"""
Thumbnail Maker — Auto-generates click-worthy YouTube thumbnails.

Creates bold, high-contrast thumbnails with:
- Large dollar amounts or numbers
- Bold title text with 3D glow effect
- Dark gradient backgrounds
- Niche-specific accent colors
- Optional avatar face on right side
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import (
    THUMBNAIL_WIDTH,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_BG_COLOR,
    THUMBNAIL_TEXT_COLOR,
    THUMBNAIL_ACCENT_COLOR,
    THUMBNAIL_FONT_SIZE,
    ASSETS_DIR,
    SHOPMO_LOGO_PATH,
)


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load a font, falling back to default if custom fonts unavailable."""
    font_paths = [
        ASSETS_DIR / "fonts" / "Impact.ttf",
        ASSETS_DIR / "fonts" / "Arial-Bold.ttf",
        ASSETS_DIR / "fonts" / "Roboto-Bold.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(str(fp), size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_gradient_bg(draw: ImageDraw.Draw, width: int, height: int):
    """Draw a dark gradient background."""
    for y in range(height):
        ratio = y / height
        r = int(THUMBNAIL_BG_COLOR[0] * (1 - ratio * 0.5))
        g = int(THUMBNAIL_BG_COLOR[1] * (1 - ratio * 0.5))
        b = min(255, int(THUMBNAIL_BG_COLOR[2] + (40 * ratio)))
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_text_with_outline(
    draw: ImageDraw.Draw,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    outline_color: tuple = (0, 0, 0),
    outline_width: int = 4,
):
    """Draw text with a thick outline for readability."""
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx * dx + dy * dy <= outline_width * outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill)


def _draw_glow_text(
    img: Image.Image,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    glow_color: tuple,
    glow_radius: int = 8,
):
    """Draw text with a colored glow effect behind it."""
    # Create glow layer
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.text(position, text, font=font, fill=(*glow_color, 200))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))

    # Composite glow onto image
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, glow_layer)

    # Draw sharp text on top
    draw = ImageDraw.Draw(img_rgba)
    _draw_text_with_outline(draw, position, text, font, fill, outline_width=5)

    return img_rgba.convert("RGB")


import random as _random

# All 6 niches with color schemes
NICHE_COLORS = {
    "ai_trading": {"accent": (0, 255, 136), "secondary": (255, 200, 0)},
    "ai_money": {"accent": (0, 200, 255), "secondary": (255, 165, 0)},
    "tech_news": {"accent": (130, 100, 255), "secondary": (0, 200, 255)},
    "motivation": {"accent": (255, 200, 0), "secondary": (255, 100, 50)},
    "health_wellness": {"accent": (100, 220, 100), "secondary": (0, 200, 100)},
    "blissful_moments": {"accent": (255, 180, 100), "secondary": (255, 130, 200)},
    "daily_breakdown": {"accent": (220, 40, 40), "secondary": (255, 255, 255)},  # News red + white
    "shopmo_products": {"accent": (255, 100, 0), "secondary": (0, 200, 255)},  # Orange + blue (e-commerce)
    "limitless_you": {"accent": (0, 180, 255), "secondary": (255, 200, 0)},  # Blue + gold (self-improvement)
}


def _layout_classic(img, draw, title_text, accent_text, colors, has_avatar, max_text_w, x_margin):
    """Layout 1: Classic left-aligned text + optional avatar right."""
    title_font = _get_font(THUMBNAIL_FONT_SIZE)
    words = title_text.split()
    if len(words) > 4:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        y_start = THUMBNAIL_HEIGHT // 2 - 120
    else:
        line1 = title_text
        line2 = None
        y_start = THUMBNAIL_HEIGHT // 2 - 60

    while title_font.size > 36:
        test_line = line1 if not line2 else max(line1, line2, key=len)
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] - bbox[0] <= max_text_w:
            break
        title_font = _get_font(title_font.size - 4)

    img = _draw_glow_text(img, (x_margin, y_start), line1, title_font,
                          fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"])
    if line2:
        img = _draw_glow_text(img, (x_margin, y_start + 110), line2, title_font,
                              fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"])

    draw = ImageDraw.Draw(img)
    if accent_text:
        accent_font = _get_font(60)
        ya = y_start + (230 if line2 else 120)
        _draw_text_with_outline(draw, (x_margin, ya), accent_text, accent_font, colors["accent"])

    # Bottom accent bar
    draw.rectangle([(0, THUMBNAIL_HEIGHT - 10), (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)], fill=colors["accent"])

    # AI badge
    badge_font = _get_font(32)
    draw.rounded_rectangle([(20, 20), (110, 65)], radius=12, fill=colors["accent"])
    draw.text((38, 26), "AI", font=badge_font, fill=(0, 0, 0))
    return img


def _layout_centered(img, draw, title_text, accent_text, colors, has_avatar, max_text_w, x_margin):
    """Layout 2: Big centered text with accent border frame."""
    title_font = _get_font(THUMBNAIL_FONT_SIZE + 12)
    words = title_text.split()
    if len(words) > 3:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
    else:
        line1 = title_text
        line2 = None

    while title_font.size > 40:
        test_line = line1 if not line2 else max(line1, line2, key=len)
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] - bbox[0] <= THUMBNAIL_WIDTH - 100:
            break
        title_font = _get_font(title_font.size - 4)

    # Center vertically
    y_start = THUMBNAIL_HEIGHT // 2 - (120 if line2 else 50)
    bbox1 = draw.textbbox((0, 0), line1, font=title_font)
    x1 = (THUMBNAIL_WIDTH - (bbox1[2] - bbox1[0])) // 2
    img = _draw_glow_text(img, (x1, y_start), line1, title_font,
                          fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"], glow_radius=12)
    if line2:
        bbox2 = draw.textbbox((0, 0), line2, font=title_font)
        x2 = (THUMBNAIL_WIDTH - (bbox2[2] - bbox2[0])) // 2
        img = _draw_glow_text(img, (x2, y_start + 120), line2, title_font,
                              fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"], glow_radius=12)

    draw = ImageDraw.Draw(img)
    # Accent border frame
    bw = 6
    draw.rectangle([(bw, bw), (THUMBNAIL_WIDTH - bw, THUMBNAIL_HEIGHT - bw)], outline=colors["accent"], width=bw)

    if accent_text:
        accent_font = _get_font(52)
        bbox_a = draw.textbbox((0, 0), accent_text, font=accent_font)
        xa = (THUMBNAIL_WIDTH - (bbox_a[2] - bbox_a[0])) // 2
        ya = y_start + (240 if line2 else 130)
        _draw_text_with_outline(draw, (xa, ya), accent_text, accent_font, colors["secondary"])
    return img


def _layout_diagonal(img, draw, title_text, accent_text, colors, has_avatar, max_text_w, x_margin):
    """Layout 3: Diagonal accent stripe with text on dark side."""
    # Draw diagonal accent stripe
    stripe_w = 200
    for y in range(THUMBNAIL_HEIGHT):
        x_offset = int(y * 0.6)
        draw.rectangle([(THUMBNAIL_WIDTH - stripe_w - x_offset, y),
                        (THUMBNAIL_WIDTH - x_offset, y)], fill=colors["accent"])

    # Text on left side
    title_font = _get_font(THUMBNAIL_FONT_SIZE)
    text_max = int(THUMBNAIL_WIDTH * 0.55)
    words = title_text.split()
    if len(words) > 4:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        y_start = THUMBNAIL_HEIGHT // 2 - 100
    else:
        line1 = title_text
        line2 = None
        y_start = THUMBNAIL_HEIGHT // 2 - 50

    while title_font.size > 36:
        test_line = line1 if not line2 else max(line1, line2, key=len)
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] - bbox[0] <= text_max:
            break
        title_font = _get_font(title_font.size - 4)

    img = _draw_glow_text(img, (50, y_start), line1, title_font,
                          fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"])
    if line2:
        img = _draw_glow_text(img, (50, y_start + 100), line2, title_font,
                              fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"])

    draw = ImageDraw.Draw(img)
    if accent_text:
        accent_font = _get_font(56)
        ya = y_start + (210 if line2 else 110)
        _draw_text_with_outline(draw, (50, ya), accent_text, accent_font, colors["secondary"])

    badge_font = _get_font(32)
    draw.rounded_rectangle([(20, 20), (110, 65)], radius=12, fill=colors["accent"])
    draw.text((38, 26), "AI", font=badge_font, fill=(0, 0, 0))
    return img


def _layout_split(img, draw, title_text, accent_text, colors, has_avatar, max_text_w, x_margin):
    """Layout 4: Vertical split — accent color left panel, dark right."""
    panel_w = int(THUMBNAIL_WIDTH * 0.35)
    draw.rectangle([(0, 0), (panel_w, THUMBNAIL_HEIGHT)], fill=colors["accent"])

    # Accent text in left panel (vertical)
    if accent_text:
        accent_font = _get_font(48)
        # Rotate text not supported easily, so place horizontally
        _draw_text_with_outline(draw, (20, THUMBNAIL_HEIGHT // 2 - 30),
                                accent_text, accent_font, (0, 0, 0), outline_color=(255, 255, 255))

    # Main text in right panel
    title_font = _get_font(THUMBNAIL_FONT_SIZE - 4)
    text_max = THUMBNAIL_WIDTH - panel_w - 60
    words = title_text.split()
    if len(words) > 3:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        y_start = THUMBNAIL_HEIGHT // 2 - 100
    else:
        line1 = title_text
        line2 = None
        y_start = THUMBNAIL_HEIGHT // 2 - 50

    while title_font.size > 36:
        test_line = line1 if not line2 else max(line1, line2, key=len)
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] - bbox[0] <= text_max:
            break
        title_font = _get_font(title_font.size - 4)

    tx = panel_w + 30
    img = _draw_glow_text(img, (tx, y_start), line1, title_font,
                          fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"])
    if line2:
        img = _draw_glow_text(img, (tx, y_start + 100), line2, title_font,
                              fill=THUMBNAIL_TEXT_COLOR, glow_color=colors["accent"])
    return img


def _layout_bottom_bar(img, draw, title_text, accent_text, colors, has_avatar, max_text_w, x_margin):
    """Layout 5: Full background image with thick bottom bar and text overlay."""
    # Thick accent bottom bar
    bar_h = int(THUMBNAIL_HEIGHT * 0.35)
    bar_y = THUMBNAIL_HEIGHT - bar_h
    # Semi-transparent dark overlay on bottom portion
    overlay = Image.new("RGBA", (THUMBNAIL_WIDTH, bar_h), (*colors["accent"], 220))
    img_rgba = img.convert("RGBA")
    img_rgba.paste(overlay, (0, bar_y), overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Text on the bar
    title_font = _get_font(THUMBNAIL_FONT_SIZE)
    words = title_text.split()
    if len(words) > 4:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
    else:
        line1 = title_text
        line2 = None

    while title_font.size > 36:
        test_line = line1 if not line2 else max(line1, line2, key=len)
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] - bbox[0] <= THUMBNAIL_WIDTH - 80:
            break
        title_font = _get_font(title_font.size - 4)

    y_start = bar_y + 20
    _draw_text_with_outline(draw, (40, y_start), line1, title_font, (0, 0, 0), outline_color=(255, 255, 255))
    if line2:
        _draw_text_with_outline(draw, (40, y_start + 90), line2, title_font, (0, 0, 0), outline_color=(255, 255, 255))

    if accent_text:
        accent_font = _get_font(44)
        ya = y_start + (190 if line2 else 100)
        _draw_text_with_outline(draw, (40, ya), accent_text, accent_font, (255, 255, 255))
    return img


THUMBNAIL_LAYOUTS = [
    _layout_classic,
    _layout_centered,
    _layout_diagonal,
    _layout_split,
    _layout_bottom_bar,
]


def generate_thumbnail(
    title_text: str,
    output_path: str | Path,
    accent_text: str | None = None,
    background_image: str | None = None,
    niche: str = "ai_trading",
    avatar_image: str | None = None,
    layout: int | None = None,
) -> str:
    """
    Generate a premium YouTube thumbnail with varied layouts.

    Args:
        title_text: Main bold text (3-5 words, e.g. "AI MADE $847")
        output_path: Where to save the thumbnail
        accent_text: Secondary text in accent color (e.g. "IN ONE DAY")
        background_image: Optional background image path
        niche: Niche for color scheme selection
        avatar_image: Optional avatar face image for right side
        layout: Layout index (0-4), or None for random

    Returns:
        Path to generated thumbnail
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    colors = NICHE_COLORS.get(niche, NICHE_COLORS["ai_trading"])

    # Choose layout: random if not specified
    if layout is None:
        layout = _random.randint(0, len(THUMBNAIL_LAYOUTS) - 1)
    layout_fn = THUMBNAIL_LAYOUTS[layout % len(THUMBNAIL_LAYOUTS)]

    # Determine text area
    has_avatar = avatar_image and Path(avatar_image).exists()
    text_area_w = int(THUMBNAIL_WIDTH * 0.58) if has_avatar else THUMBNAIL_WIDTH
    x_margin = 40
    max_text_w = text_area_w - x_margin * 2

    # Create base image
    if background_image and Path(background_image).exists():
        img = Image.open(background_image).resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 180))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay).convert("RGB")
    else:
        img = Image.new("RGB", (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
        draw_bg = ImageDraw.Draw(img)
        _draw_gradient_bg(draw_bg, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)

    # Paste avatar on right side if available
    if has_avatar:
        try:
            avatar = Image.open(avatar_image).convert("RGBA")
            avatar_w = int(THUMBNAIL_WIDTH * 0.42)
            avatar_h = THUMBNAIL_HEIGHT
            avatar = avatar.resize((avatar_w, avatar_h), Image.LANCZOS)
            img.paste(avatar.convert("RGB"), (THUMBNAIL_WIDTH - avatar_w, 0))
        except Exception:
            has_avatar = False

    # Apply layout
    title_upper = title_text.upper()
    accent_upper = accent_text.upper() if accent_text else None
    draw = ImageDraw.Draw(img)
    img = layout_fn(img, draw, title_upper, accent_upper, colors, has_avatar, max_text_w, x_margin)

    # ShopMO logo overlay for shopmo_products niche
    if niche == "shopmo_products" and SHOPMO_LOGO_PATH.exists():
        try:
            logo = Image.open(str(SHOPMO_LOGO_PATH)).convert("RGBA")
            logo_w = 200
            ratio = logo_w / logo.width
            logo = logo.resize((logo_w, int(logo.height * ratio)), Image.LANCZOS)
            x = THUMBNAIL_WIDTH - logo_w - 20
            y = 20
            img_rgba = img.convert("RGBA")
            img_rgba.paste(logo, (x, y), logo)
            img = img_rgba.convert("RGB")
        except Exception:
            pass

    # Save
    img.save(str(output_path), quality=95)
    layout_name = layout_fn.__doc__.split(":")[0].strip() if layout_fn.__doc__ else f"Layout {layout}"
    print(f"[Thumbnail] Generated: {output_path.name} ({layout_name})")

    return str(output_path)


def generate_thumbnail_from_script(
    script: dict,
    output_path: str | Path,
    chart_image: str | None = None,
    layout: str | int | None = None,
) -> str:
    """Generate a thumbnail using script metadata.

    Args:
        script: Script dict with title, thumbnail_text, niche
        output_path: Where to save the thumbnail
        chart_image: Optional chart image for background
        layout: Layout name (classic/centered/diagonal/split/bottom_bar)
               or index (0-4), or None for random
    """
    thumbnail_text = script.get("thumbnail_text", script.get("title", "AI VIDEO")[:30])

    # Try to extract a number/dollar amount for the accent
    import re
    money_match = re.search(r'\$[\d,]+[KkMmBb]?', script.get("title", ""))
    accent = money_match.group().upper() if money_match else None

    # Check for niche-specific avatar image
    niche = script.get("niche", "ai_trading")
    avatar_path = None
    _NICHE_AVATAR_FILES = {
        "ai_trading": "avatar_trading.png",
        "ai_money": "avatar_money.png",
        "tech_news": "avatar_tech.png",
    }
    avatar_file = _NICHE_AVATAR_FILES.get(niche, "")
    if avatar_file:
        candidate = ASSETS_DIR / "avatars" / avatar_file
        if candidate.exists():
            avatar_path = str(candidate)

    # Convert layout name to index if needed
    layout_idx = None
    if layout is not None:
        LAYOUT_NAME_MAP = {
            "classic": 0,
            "centered": 1,
            "diagonal": 2,
            "split": 3,
            "bottom_bar": 4,
        }
        if isinstance(layout, str):
            layout_idx = LAYOUT_NAME_MAP.get(layout.lower())
        elif isinstance(layout, int):
            layout_idx = layout

    return generate_thumbnail(
        title_text=thumbnail_text,
        output_path=output_path,
        accent_text=accent,
        background_image=chart_image,
        niche=niche,
        avatar_image=avatar_path,
        layout=layout_idx,
    )


# CLI test
if __name__ == "__main__":
    from config import OUTPUT_DIR

    thumb = generate_thumbnail(
        title_text="AI MADE $847",
        output_path=OUTPUT_DIR / "test_thumbnail.jpg",
        accent_text="IN ONE DAY",
        niche="ai_trading",
    )
    print(f"Thumbnail: {thumb}")
