"""
Generate profile pictures and cover photos for 5 Facebook pages.
Downloads stock images from Pexels, applies PIL overlays, then uploads to Facebook.
"""
import sys
import os
import io
import requests
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Reconfigure stdout for UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ── Configuration ──────────────────────────────────────────────────────────────
PEXELS_API_KEY = "5w8O4KmcVrju3hbJ2EkgLzaNxY3zHFIn9fmb6fgF8wvHQsOWDib4wUd9"
OUTPUT_DIR = Path(r"C:\Users\PenuelM\Documents\ai-video-factory\assets\page_images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADING_FONT = "C:/Windows/Fonts/impact.ttf"
SUBTITLE_FONT = "C:/Windows/Fonts/arialbd.ttf"

PAGES = [
    {
        "key": "ai_trading",
        "name": "Beast Mode Academy",
        "initials": "BMA",
        "page_id": "103551448238854",
        "token": "EAAIaAVdodLYBQwYBr3s9H7bEXhZAMb4XAy1TTbdZCjYdbMBj1Tb8d7tw1hvIkClqzU8s395dFYjhhG8tPdwMc9GnZApZAkS2nG6LaOiBcaFvo0IZCZAnAMZCSaTAMn2IPAoou4VwvRPZCX74fIRqtsfH1RJ4ZCH43JPO8sqiRo3H3Y6e4ONngDv77j4pKZA5BTsZBouGhcHp9VxqSyQcdh1j6UBD4OUXZAXvxGGGkgwWWtpDVJZCH2NjsEsl5RzOoEwZDZD",
        "tagline": "Master AI Trading",
        "pexels_profile": "stock market trading",
        "pexels_cover": "financial charts stock market",
        "colors": {"primary": (10, 30, 60), "secondary": (0, 180, 120), "accent": (0, 230, 160), "text": (255, 255, 255)},
    },
    {
        "key": "ai_money",
        "name": "Smart Money AI",
        "initials": "SMA",
        "page_id": "100919755007786",
        "token": "EAAIaAVdodLYBQZBDd10klIlrbmuT1fu4QqGbb5jKfyntpUXDUTGXwSIUdnK9lqyQkmV0ZCT2r3y4DEAlDGQezvE7C0X83txikISnHzAI6ZCsrf6DQb8QsZArSxiqpwA0H5gSSZBMDp6gsx1ZArqxNguUHEjrhPzZC9C41JJslgzniNHMAIWRLUbKACQLMrmz4hCZBZAJSNXZADPUFX1FkHM4Pg5nFtWvhBCeOLiZBQPCv9GCdGPiaAgWZCmTAYpOMwZDZD",
        "tagline": "Build Wealth with AI",
        "pexels_profile": "gold coins wealth",
        "pexels_cover": "luxury wealth money gold",
        "colors": {"primary": (20, 15, 5), "secondary": (218, 165, 32), "accent": (255, 215, 0), "text": (255, 255, 255)},
    },
    {
        "key": "tech_news",
        "name": "Tech Pulse Africa",
        "initials": "TPA",
        "page_id": "107465491085378",
        "token": "EAAIaAVdodLYBQwv0WpNIYfKs01HB4PorZCP4dgM7bvZBF9KuNZAajozLZBbNKrUZCCuMOwGcmIxA7IOBlOZCEd7tfG1XjgbFHal6vXvfw1TeW004nSC2P4nNI1ZBU23f3w2GlzP23YnEkQSt7kHYZC6MHbps3tqmv7idn2dQ6IBI6aQr734ZAJdtEX272I2snu24f9AeAAhrmZCU2sEOAGXbsBynZAwF8WCuZAaxGZBtKSPqWBctH0bD0gxibHU5IDAZDZD",
        "tagline": "AI News & Innovation",
        "pexels_profile": "technology artificial intelligence",
        "pexels_cover": "futuristic technology innovation",
        "colors": {"primary": (15, 10, 50), "secondary": (100, 60, 220), "accent": (140, 100, 255), "text": (255, 255, 255)},
    },
    {
        "key": "motivation",
        "name": "Elevate You",
        "initials": "EY",
        "page_id": "102206758210905",
        "token": "EAAIaAVdodLYBQ2rK1JxgBS9PZCVzinlLQzP3OO1qp0KX61rJxCa9m5ouWhv7hvT0WeZAefY6vOfGOT6wfa1UhvAbby4GyottwxdejGAFZBiS2ndjjGjHYvyj7p2GnNqbOOpk9ExpZCHeX9af31ppTDkB2vdbYmO1HIwWzMY7MrsmskMtC0qWMwXuIPQcLQt48fja0gZAX31gFfg2GsZC67jESmioIqxTaor6ZBeCe1FLzZBP4hA0pyI1B5OciAZDZD",
        "tagline": "Rise. Grind. Succeed.",
        "pexels_profile": "fire flames motivation",
        "pexels_cover": "sunrise mountain peak success",
        "colors": {"primary": (40, 15, 5), "secondary": (230, 120, 20), "accent": (255, 160, 50), "text": (255, 255, 255)},
    },
    {
        "key": "health_wellness",
        "name": "Herbal Organic Life",
        "initials": "HOL",
        "page_id": "106788301081578",
        "token": "EAAIaAVdodLYBQyVjnpoA5UwHvOjWK7x6Ks9b1NSA2L3Cy0mLOzQw2FZAVZAshfT6TYekkRPN6QWKgmCg5habWvUaQKoxNlPmmA7fqh8EsbKHUwZBGbcbG9KZAng6s4uFEKZBc0nmqZC9GoI7B4gY9pD3XZACBQXHi0XYoJH1DQfwWPxXpiExYZAWjz2W6sEMtGKoVNr70soeYfDS51wn2jxsZC7bqm3s5oZAXmsqoTj09fOyDpa8BxWE27TYzk4QZDZD",
        "tagline": "Natural Health & Wellness",
        "pexels_profile": "herbal tea natural remedies",
        "pexels_cover": "green nature organic herbs",
        "colors": {"primary": (10, 40, 15), "secondary": (40, 160, 60), "accent": (80, 200, 100), "text": (255, 255, 255)},
    },
]


# ── Pexels Download ────────────────────────────────────────────────────────────
def download_pexels_image(query: str, width: int, height: int, orientation: str = "landscape") -> Image.Image:
    """Search Pexels and download a relevant image."""
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": orientation}
    resp = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("photos"):
        raise ValueError(f"No Pexels results for query: {query}")

    # Pick the first photo
    photo = data["photos"][0]
    img_url = photo["src"]["large2x"]  # High-res version
    print(f"  Downloading from Pexels: {photo['photographer']} - {img_url[:80]}...")

    img_resp = requests.get(img_url, timeout=60)
    img_resp.raise_for_status()
    img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")

    # Resize/crop to desired dimensions
    img = crop_center(img, width, height)
    return img


def crop_center(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop image from center to target aspect ratio, then resize."""
    w, h = img.size
    target_ratio = target_w / target_h
    current_ratio = w / h

    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


# ── Profile Picture Generator ─────────────────────────────────────────────────
def generate_profile_pic(page: dict) -> Path:
    """Generate a 500x500 circular profile picture with initials overlay."""
    size = 500
    colors = page["colors"]

    # Download stock image
    print(f"  Fetching profile background for {page['name']}...")
    try:
        bg = download_pexels_image(page["pexels_profile"], size, size, orientation="square")
    except Exception as e:
        print(f"  Warning: Pexels download failed ({e}), creating gradient background")
        bg = Image.new("RGBA", (size, size), colors["primary"])

    # Darken the background
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.45)
    bg = bg.convert("RGBA")

    # Create gradient overlay
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # Radial-ish dark vignette
    for i in range(size // 2):
        alpha = int(180 * (i / (size // 2)) ** 2)
        r = size // 2 - i
        bbox = (size // 2 - r, size // 2 - r, size // 2 + r, size // 2 + r)
        draw_ov.ellipse(bbox, fill=(*colors["primary"][:3], alpha))

    bg = Image.alpha_composite(bg, overlay)

    # Add colored ring border
    draw = ImageDraw.Draw(bg)
    ring_width = 12
    # Outer ring
    draw.ellipse(
        [ring_width, ring_width, size - ring_width, size - ring_width],
        outline=colors["accent"], width=ring_width
    )
    # Inner glow ring
    draw.ellipse(
        [ring_width + 6, ring_width + 6, size - ring_width - 6, size - ring_width - 6],
        outline=(*colors["secondary"][:3], 120), width=3
    )

    # Add initials text
    try:
        font_initials = ImageFont.truetype(HEADING_FONT, 140)
    except:
        font_initials = ImageFont.load_default()

    initials = page["initials"]
    bbox_text = draw.textbbox((0, 0), initials, font=font_initials)
    tw = bbox_text[2] - bbox_text[0]
    th = bbox_text[3] - bbox_text[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - 15

    # Text shadow
    for offset in [(3, 3), (-1, -1), (2, 2)]:
        draw.text((tx + offset[0], ty + offset[1]), initials, fill=(0, 0, 0, 180), font=font_initials)
    # Main text
    draw.text((tx, ty), initials, fill=colors["text"], font=font_initials)

    # Add small tagline under initials
    try:
        font_small = ImageFont.truetype(SUBTITLE_FONT, 22)
    except:
        font_small = ImageFont.load_default()

    tag_short = page["name"]
    bbox_tag = draw.textbbox((0, 0), tag_short, font=font_small)
    tag_w = bbox_tag[2] - bbox_tag[0]
    tag_x = (size - tag_w) // 2
    tag_y = ty + th + 20

    # Tagline background pill
    pill_pad = 10
    draw.rounded_rectangle(
        [tag_x - pill_pad, tag_y - 4, tag_x + tag_w + pill_pad, tag_y + (bbox_tag[3] - bbox_tag[1]) + 4],
        radius=12,
        fill=(*colors["secondary"][:3], 160)
    )
    draw.text((tag_x, tag_y), tag_short, fill=colors["text"], font=font_small)

    # Create circular mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, size, size], fill=255)

    # Apply circular crop
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(bg, (0, 0), mask)

    # Save
    out_path = OUTPUT_DIR / f"{page['key']}_profile.png"
    result.save(str(out_path), "PNG", quality=95)
    print(f"  Saved profile pic: {out_path}")
    return out_path


# ── Cover Photo Generator ─────────────────────────────────────────────────────
def generate_cover_photo(page: dict) -> Path:
    """Generate an 820x462 cover photo with overlays."""
    width, height = 820, 462
    colors = page["colors"]

    # Download stock image
    print(f"  Fetching cover background for {page['name']}...")
    try:
        bg = download_pexels_image(page["pexels_cover"], width, height, orientation="landscape")
    except Exception as e:
        print(f"  Warning: Pexels download failed ({e}), creating gradient background")
        bg = Image.new("RGBA", (width, height), colors["primary"])

    # Darken background
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.4)
    bg = bg.convert("RGBA")

    # Create gradient overlay (left-to-right dark gradient)
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(gradient)

    # Bottom gradient bar
    for y in range(height):
        # Bottom third gets darker
        if y > height * 0.5:
            progress = (y - height * 0.5) / (height * 0.5)
            alpha = int(200 * progress)
            grad_draw.line([(0, y), (width, y)], fill=(*colors["primary"][:3], alpha))

    # Left side gradient for text readability
    for x in range(width // 2):
        progress = 1 - (x / (width // 2))
        alpha = int(160 * progress ** 1.5)
        grad_draw.line([(x, 0), (x, height)], fill=(*colors["primary"][:3], alpha))

    bg = Image.alpha_composite(bg, gradient)

    # Add accent stripe
    stripe = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    stripe_draw = ImageDraw.Draw(stripe)

    # Diagonal accent stripe at bottom
    stripe_y = height - 80
    points = [(0, stripe_y), (width, stripe_y - 30), (width, stripe_y - 22), (0, stripe_y + 8)]
    stripe_draw.polygon(points, fill=(*colors["accent"][:3], 200))

    # Secondary thin stripe
    stripe_y2 = stripe_y + 15
    points2 = [(0, stripe_y2), (width, stripe_y2 - 30), (width, stripe_y2 - 26), (0, stripe_y2 + 4)]
    stripe_draw.polygon(points2, fill=(*colors["secondary"][:3], 140))

    bg = Image.alpha_composite(bg, stripe)

    draw = ImageDraw.Draw(bg)

    # Page name (large heading)
    try:
        font_heading = ImageFont.truetype(HEADING_FONT, 56)
    except:
        font_heading = ImageFont.load_default()

    name = page["name"].upper()
    name_bbox = draw.textbbox((0, 0), name, font=font_heading)
    name_x = 50
    name_y = height // 2 - 60

    # Text shadow
    for ox, oy in [(3, 3), (2, 2), (1, 1)]:
        draw.text((name_x + ox, name_y + oy), name, fill=(0, 0, 0, 200), font=font_heading)
    draw.text((name_x, name_y), name, fill=colors["text"], font=font_heading)

    # Tagline
    try:
        font_tagline = ImageFont.truetype(SUBTITLE_FONT, 26)
    except:
        font_tagline = ImageFont.load_default()

    tagline = page["tagline"]
    tag_y = name_y + (name_bbox[3] - name_bbox[1]) + 15
    tag_bbox = draw.textbbox((0, 0), tagline, font=font_tagline)

    # Tagline background
    pad = 8
    draw.rounded_rectangle(
        [name_x - pad, tag_y - pad, name_x + (tag_bbox[2] - tag_bbox[0]) + pad * 2, tag_y + (tag_bbox[3] - tag_bbox[1]) + pad],
        radius=6,
        fill=(*colors["secondary"][:3], 180)
    )
    draw.text((name_x + pad, tag_y), tagline, fill=colors["text"], font=font_tagline)

    # Small decorative dot grid in top-right
    dot_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dot_draw = ImageDraw.Draw(dot_overlay)
    for dx in range(0, 120, 20):
        for dy in range(0, 120, 20):
            dot_draw.ellipse(
                [width - 160 + dx, 30 + dy, width - 156 + dx, 34 + dy],
                fill=(*colors["accent"][:3], 80)
            )
    bg = Image.alpha_composite(bg, dot_overlay)

    # Save
    out_path = OUTPUT_DIR / f"{page['key']}_cover.png"
    final = bg.convert("RGB")
    final.save(str(out_path), "PNG", quality=95)
    print(f"  Saved cover photo: {out_path}")
    return out_path


# ── Facebook Upload Functions ──────────────────────────────────────────────────
def upload_profile_picture(page: dict, image_path: Path) -> dict:
    """Upload profile picture to Facebook page."""
    page_id = page["page_id"]
    token = page["token"]
    results = {}

    print(f"  Uploading profile picture for {page['name']} (Page ID: {page_id})...")

    # Method: POST to /{page_id}/picture with the image file
    try:
        with open(str(image_path), "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/picture",
                data={"access_token": token},
                files={"source": (image_path.name, f, "image/png")},
                timeout=60,
            )
        print(f"    /picture response ({resp.status_code}): {resp.text[:300]}")
        results["picture_direct"] = {"status": resp.status_code, "response": resp.json() if resp.headers.get('content-type','').startswith('application/json') else resp.text[:300]}

        if resp.status_code == 200:
            print(f"    Profile picture set successfully!")
            return results
    except Exception as e:
        print(f"    /picture method error: {e}")
        results["picture_direct_error"] = str(e)

    # Fallback: Upload as photo, then try to set as profile
    print(f"    Trying fallback: upload as photo first...")
    try:
        with open(str(image_path), "rb") as f:
            resp2 = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/photos",
                data={"access_token": token, "published": "false"},
                files={"source": (image_path.name, f, "image/png")},
                timeout=60,
            )
        print(f"    /photos response ({resp2.status_code}): {resp2.text[:300]}")
        results["photos_upload"] = {"status": resp2.status_code, "response": resp2.json() if resp2.headers.get('content-type','').startswith('application/json') else resp2.text[:300]}

        if resp2.status_code == 200:
            photo_data = resp2.json()
            photo_id = photo_data.get("id")
            if photo_id:
                print(f"    Photo uploaded (ID: {photo_id}), now setting as profile pic...")
                resp3 = requests.post(
                    f"https://graph.facebook.com/v24.0/{page_id}",
                    data={
                        "access_token": token,
                        "profile_photo_url": f"https://graph.facebook.com/{photo_id}/picture"
                    },
                    timeout=30,
                )
                print(f"    Set profile response ({resp3.status_code}): {resp3.text[:300]}")
                results["set_profile"] = {"status": resp3.status_code, "response": resp3.text[:300]}
    except Exception as e:
        print(f"    Fallback method error: {e}")
        results["fallback_error"] = str(e)

    return results


def upload_cover_photo(page: dict, image_path: Path) -> dict:
    """Upload cover photo to Facebook page."""
    page_id = page["page_id"]
    token = page["token"]
    results = {}

    print(f"  Uploading cover photo for {page['name']} (Page ID: {page_id})...")

    # Step 1: Upload the photo (unpublished)
    try:
        with open(str(image_path), "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/photos",
                data={"access_token": token, "published": "false"},
                files={"source": (image_path.name, f, "image/png")},
                timeout=60,
            )
        print(f"    Photo upload response ({resp.status_code}): {resp.text[:300]}")
        results["photo_upload"] = {"status": resp.status_code, "response": resp.json() if resp.headers.get('content-type','').startswith('application/json') else resp.text[:300]}

        if resp.status_code == 200:
            photo_data = resp.json()
            photo_id = photo_data.get("id")

            if photo_id:
                # Step 2: Set as cover photo
                print(f"    Photo uploaded (ID: {photo_id}), setting as cover...")
                resp2 = requests.post(
                    f"https://graph.facebook.com/v24.0/{page_id}",
                    data={
                        "access_token": token,
                        "cover": json.dumps({"photo_id": photo_id, "offset_y": 0})
                    },
                    timeout=30,
                )
                print(f"    Set cover response ({resp2.status_code}): {resp2.text[:300]}")
                results["set_cover"] = {"status": resp2.status_code, "response": resp2.text[:300]}
            else:
                print(f"    No photo_id returned!")
                results["error"] = "No photo_id in upload response"
        else:
            print(f"    Photo upload failed!")
    except Exception as e:
        print(f"    Cover upload error: {e}")
        results["error"] = str(e)

    # Fallback: Try direct cover upload via source file
    if results.get("set_cover", {}).get("status") != 200 and "error" not in results.get("set_cover", {}).get("response", ""):
        print(f"    Trying direct cover source upload...")
        try:
            with open(str(image_path), "rb") as f:
                resp3 = requests.post(
                    f"https://graph.facebook.com/v24.0/{page_id}",
                    data={"access_token": token, "cover_source": "true"},
                    files={"source": (image_path.name, f, "image/png")},
                    timeout=60,
                )
            print(f"    Direct cover response ({resp3.status_code}): {resp3.text[:300]}")
            results["direct_cover"] = {"status": resp3.status_code, "response": resp3.text[:300]}
        except Exception as e:
            print(f"    Direct cover error: {e}")

    return results


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    all_results = {}

    for page in PAGES:
        print(f"\n{'='*70}")
        print(f"Processing: {page['name']} ({page['key']})")
        print(f"{'='*70}")

        # Step 1: Generate images
        print(f"\n[1/4] Generating profile picture...")
        profile_path = generate_profile_pic(page)

        print(f"\n[2/4] Generating cover photo...")
        cover_path = generate_cover_photo(page)

        # Step 3: Upload profile picture
        print(f"\n[3/4] Uploading profile picture...")
        profile_result = upload_profile_picture(page, profile_path)

        # Step 4: Upload cover photo
        print(f"\n[4/4] Uploading cover photo...")
        cover_result = upload_cover_photo(page, cover_path)

        all_results[page["key"]] = {
            "name": page["name"],
            "profile_path": str(profile_path),
            "cover_path": str(cover_path),
            "profile_upload": profile_result,
            "cover_upload": cover_result,
        }

    # Summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for key, result in all_results.items():
        print(f"\n{result['name']}:")
        print(f"  Profile: {result['profile_path']}")
        print(f"  Cover:   {result['cover_path']}")
        print(f"  Profile upload: {json.dumps(result['profile_upload'], indent=2, default=str)[:200]}")
        print(f"  Cover upload:   {json.dumps(result['cover_upload'], indent=2, default=str)[:200]}")

    # Save full results
    results_path = OUTPUT_DIR / "upload_results.json"
    with open(str(results_path), "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nFull results saved to: {results_path}")


if __name__ == "__main__":
    main()
