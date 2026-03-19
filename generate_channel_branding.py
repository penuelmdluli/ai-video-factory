"""
Generate professional YouTube channel profile pictures and banners for all 6 niches.
Uses PIL/Pillow to create clean, modern branding assets.

Profile pics: 800x800 circular icon-style logos
Banners: 2560x1440 (YouTube recommended) with channel info

Usage: python generate_channel_branding.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

OUTPUT_DIR = Path(__file__).parent / "assets" / "youtube_branding"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Niche branding config
NICHES = {
    "ai_trading": {
        "name": "Beast Mode Academy",
        "tagline": "AI-Powered Trading Strategies",
        "icon_letter": "B",
        "icon_emoji": None,
        "primary_color": (0, 200, 83),       # Green
        "secondary_color": (0, 150, 60),
        "accent_color": (255, 215, 0),         # Gold
        "bg_dark": (10, 15, 25),
        "gradient_end": (0, 40, 20),
    },
    "ai_money": {
        "name": "Smart Money AI",
        "tagline": "Turn AI Tools Into Income",
        "icon_letter": "S",
        "icon_emoji": None,
        "primary_color": (0, 150, 255),       # Blue
        "secondary_color": (0, 100, 200),
        "accent_color": (0, 255, 150),         # Cyan-green
        "bg_dark": (10, 12, 30),
        "gradient_end": (0, 20, 50),
    },
    "tech_news": {
        "name": "Tech Pulse Africa",
        "tagline": "Africa's Tech & AI News",
        "icon_letter": "T",
        "icon_emoji": None,
        "primary_color": (130, 80, 255),      # Purple
        "secondary_color": (100, 50, 200),
        "accent_color": (0, 200, 255),         # Cyan
        "bg_dark": (15, 10, 30),
        "gradient_end": (30, 10, 50),
    },
    "motivation": {
        "name": "Elevate You",
        "tagline": "Elevate Your Mindset",
        "icon_letter": "E",
        "icon_emoji": None,
        "primary_color": (255, 100, 0),       # Orange
        "secondary_color": (200, 70, 0),
        "accent_color": (255, 200, 50),        # Yellow
        "bg_dark": (25, 12, 5),
        "gradient_end": (40, 15, 0),
    },
    "health_wellness": {
        "name": "Herbal Organic Life",
        "tagline": "Natural Health & Wellness",
        "icon_letter": "H",
        "icon_emoji": None,
        "primary_color": (50, 180, 80),       # Green
        "secondary_color": (30, 140, 60),
        "accent_color": (150, 220, 100),       # Light green
        "bg_dark": (8, 20, 10),
        "gradient_end": (10, 35, 15),
    },
    "blissful_moments": {
        "name": "Blissful Moments",
        "tagline": "Find Your Peace",
        "icon_letter": "B",
        "icon_emoji": None,
        "primary_color": (100, 150, 255),     # Soft blue
        "secondary_color": (70, 120, 220),
        "accent_color": (200, 170, 255),       # Lavender
        "bg_dark": (10, 12, 25),
        "gradient_end": (15, 15, 40),
    },
}


def get_font(size, bold=False):
    """Try to get a nice font, fall back to default."""
    font_paths = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]
    bold_fonts = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/impact.ttf",
    ]

    search = bold_fonts if bold else font_paths
    for fp in search:
        try:
            return ImageFont.truetype(fp, size)
        except (OSError, IOError):
            continue

    # Try any bold
    if bold:
        for fp in font_paths:
            try:
                return ImageFont.truetype(fp, size)
            except (OSError, IOError):
                continue

    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=0):
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def create_gradient(size, color_start, color_end, direction="horizontal"):
    """Create a gradient image."""
    img = Image.new("RGB", size)
    pixels = img.load()
    w, h = size

    for y in range(h):
        for x in range(w):
            if direction == "horizontal":
                ratio = x / w
            elif direction == "vertical":
                ratio = y / h
            elif direction == "diagonal":
                ratio = (x / w + y / h) / 2
            else:
                ratio = x / w

            r = int(color_start[0] + (color_end[0] - color_start[0]) * ratio)
            g = int(color_start[1] + (color_end[1] - color_start[1]) * ratio)
            b = int(color_start[2] + (color_end[2] - color_start[2]) * ratio)
            pixels[x, y] = (r, g, b)

    return img


def generate_profile_pic(niche: str, config: dict):
    """Generate an 800x800 profile picture."""
    size = 800
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle with gradient effect
    primary = config["primary_color"]
    secondary = config["secondary_color"]

    # Draw outer glow
    for i in range(20, 0, -1):
        alpha = int(255 * (1 - i / 20) * 0.3)
        glow_color = (*primary, alpha)
        margin = i * 3
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=glow_color
        )

    # Draw main circle
    margin = 60
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=config["bg_dark"]
    )

    # Draw accent ring
    ring_width = 8
    ring_margin = margin + 5
    draw.ellipse(
        [ring_margin, ring_margin, size - ring_margin, size - ring_margin],
        outline=primary,
        width=ring_width
    )

    # Draw inner accent line
    inner_margin = margin + 20
    draw.ellipse(
        [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
        outline=(*primary[:3],),
        width=2
    )

    # Draw the letter
    letter = config["icon_letter"]
    font_size = 340
    font = get_font(font_size, bold=True)

    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), letter, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2 - bbox[0]
    y = (size - text_height) // 2 - bbox[1] - 10

    # Draw letter shadow
    draw.text((x + 4, y + 4), letter, fill=(0, 0, 0, 150), font=font)

    # Draw letter with primary color
    draw.text((x, y), letter, fill=primary, font=font)

    # Draw small accent line under the letter
    line_y = y + text_height + 20
    line_w = 120
    line_x = (size - line_w) // 2
    draw.rounded_rectangle(
        [line_x, line_y, line_x + line_w, line_y + 6],
        radius=3,
        fill=config["accent_color"]
    )

    # Save
    path = OUTPUT_DIR / f"profile_{niche}.png"
    img.save(str(path), "PNG")
    print(f"  [OK] Profile pic: {path}")
    return path


def generate_banner(niche: str, config: dict):
    """Generate a 2560x1440 banner image."""
    w, h = 2560, 1440
    primary = config["primary_color"]
    accent = config["accent_color"]
    bg_dark = config["bg_dark"]
    gradient_end = config["gradient_end"]

    # Create base gradient
    img = create_gradient((w, h), bg_dark, gradient_end, "diagonal")
    draw = ImageDraw.Draw(img)

    # Add subtle grid pattern
    grid_color = tuple(min(c + 15, 255) for c in bg_dark)
    for x in range(0, w, 80):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
    for y in range(0, h, 80):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)

    # Add decorative accent lines
    # Top accent bar
    draw.rectangle([0, 0, w, 6], fill=primary)

    # Bottom accent bar
    draw.rectangle([0, h - 6, w, h], fill=primary)

    # Diagonal accent stripe (top right)
    for i in range(5):
        offset = i * 15
        alpha_color = tuple(min(c + 30, 255) for c in primary)
        draw.line(
            [(w - 400 + offset, 0), (w + offset, 400)],
            fill=alpha_color, width=3
        )

    # Diagonal accent stripe (bottom left)
    for i in range(5):
        offset = i * 15
        alpha_color = tuple(min(c + 30, 255) for c in primary)
        draw.line(
            [(0 - offset, h - 400), (400 - offset, h)],
            fill=alpha_color, width=3
        )

    # Channel name (centered in safe area: 1546x423 centered)
    # Safe area for TV: center 1546x423
    safe_x = (w - 1546) // 2
    safe_y = (h - 423) // 2

    # Channel name
    name_font = get_font(120, bold=True)
    name = config["name"]
    name_bbox = draw.textbbox((0, 0), name, font=name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_x = (w - name_w) // 2
    name_y = safe_y + 60

    # Name shadow
    draw.text((name_x + 3, name_y + 3), name, fill=(0, 0, 0), font=name_font)
    draw.text((name_x, name_y), name, fill=(255, 255, 255), font=name_font)

    # Accent line under name
    line_w = min(name_w + 40, 800)
    line_x = (w - line_w) // 2
    line_y = name_y + 140
    draw.rounded_rectangle(
        [line_x, line_y, line_x + line_w, line_y + 6],
        radius=3,
        fill=primary
    )

    # Tagline
    tag_font = get_font(56, bold=False)
    tagline = config["tagline"]
    tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_x = (w - tag_w) // 2
    tag_y = line_y + 30

    draw.text((tag_x, tag_y), tagline, fill=primary, font=tag_font)

    # Small "Subscribe" CTA text
    cta_font = get_font(36, bold=False)
    cta = "SUBSCRIBE FOR MORE"
    cta_bbox = draw.textbbox((0, 0), cta, font=cta_font)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_x = (w - cta_w) // 2
    cta_y = tag_y + 80

    # CTA pill background
    pill_pad_x = 30
    pill_pad_y = 12
    draw.rounded_rectangle(
        [cta_x - pill_pad_x, cta_y - pill_pad_y,
         cta_x + cta_w + pill_pad_x, cta_y + 36 + pill_pad_y],
        radius=25,
        fill=primary,
    )
    draw.text((cta_x, cta_y), cta, fill=(255, 255, 255), font=cta_font)

    # Decorative dots in corners
    dot_color = (*primary, )
    for i in range(8):
        for j in range(4):
            x_pos = 100 + i * 25
            y_pos = 100 + j * 25
            draw.ellipse([x_pos - 3, y_pos - 3, x_pos + 3, y_pos + 3], fill=dot_color)

    for i in range(8):
        for j in range(4):
            x_pos = w - 300 + i * 25
            y_pos = h - 200 + j * 25
            draw.ellipse([x_pos - 3, y_pos - 3, x_pos + 3, y_pos + 3], fill=dot_color)

    # Save
    path = OUTPUT_DIR / f"banner_{niche}.png"
    img.save(str(path), "PNG")
    print(f"  [OK] Banner: {path}")
    return path


def main():
    print("\n" + "=" * 60)
    print("  YouTube Channel Branding Generator")
    print("=" * 60)

    for niche, config in NICHES.items():
        print(f"\n--- {config['name']} ({niche}) ---")
        generate_profile_pic(niche, config)
        generate_banner(niche, config)

    print(f"\n{'=' * 60}")
    print(f"  All branding assets saved to: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
