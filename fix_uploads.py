"""
Fix cover photo uploads (correct parameter format) and retry Beast Mode Academy profile pic.
"""
import sys
import json
import requests
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

PAGES = [
    {
        "key": "ai_trading",
        "name": "Beast Mode Academy",
        "page_id": "103551448238854",
        "token": "EAAIaAVdodLYBQwYBr3s9H7bEXhZAMb4XAy1TTbdZCjYdbMBj1Tb8d7tw1hvIkClqzU8s395dFYjhhG8tPdwMc9GnZApZAkS2nG6LaOiBcaFvo0IZCZAnAMZCSaTAMn2IPAoou4VwvRPZCX74fIRqtsfH1RJ4ZCH43JPO8sqiRo3H3Y6e4ONngDv77j4pKZA5BTsZBouGhcHp9VxqSyQcdh1j6UBD4OUXZAXvxGGGkgwWWtpDVJZCH2NjsEsl5RzOoEwZDZD",
        "profile_photo_id": "1556288179839279",
        "cover_photo_id": "1556288259839271",
        "retry_profile": True,
    },
    {
        "key": "ai_money",
        "name": "Smart Money AI",
        "page_id": "100919755007786",
        "token": "EAAIaAVdodLYBQZBDd10klIlrbmuT1fu4QqGbb5jKfyntpUXDUTGXwSIUdnK9lqyQkmV0ZCT2r3y4DEAlDGQezvE7C0X83txikISnHzAI6ZCsrf6DQb8QsZArSxiqpwA0H5gSSZBMDp6gsx1ZArqxNguUHEjrhPzZC9C41JJslgzniNHMAIWRLUbKACQLMrmz4hCZBZAJSNXZADPUFX1FkHM4Pg5nFtWvhBCeOLiZBQPCv9GCdGPiaAgWZCmTAYpOMwZDZD",
        "cover_photo_id": "1405065161633250",
        "retry_profile": False,
    },
    {
        "key": "tech_news",
        "name": "Tech Pulse Africa",
        "page_id": "107465491085378",
        "token": "EAAIaAVdodLYBQwv0WpNIYfKs01HB4PorZCP4dgM7bvZBF9KuNZAajozLZBbNKrUZCCuMOwGcmIxA7IOBlOZCEd7tfG1XjgbFHal6vXvfw1TeW004nSC2P4nNI1ZBU23f3w2GlzP23YnEkQSt7kHYZC6MHbps3tqmv7idn2dQ6IBI6aQr734ZAJdtEX272I2snu24f9AeAAhrmZCU2sEOAGXbsBynZAwF8WCuZAaxGZBtKSPqWBctH0bD0gxibHU5IDAZDZD",
        "cover_photo_id": "1238357218484307",
        "retry_profile": False,
    },
    {
        "key": "motivation",
        "name": "Elevate You",
        "page_id": "102206758210905",
        "token": "EAAIaAVdodLYBQ2rK1JxgBS9PZCVzinlLQzP3OO1qp0KX61rJxCa9m5ouWhv7hvT0WeZAefY6vOfGOT6wfa1UhvAbby4GyottwxdejGAFZBiS2ndjjGjHYvyj7p2GnNqbOOpk9ExpZCHeX9af31ppTDkB2vdbYmO1HIwWzMY7MrsmskMtC0qWMwXuIPQcLQt48fja0gZAX31gFfg2GsZC67jESmioIqxTaor6ZBeCe1FLzZBP4hA0pyI1B5OciAZDZD",
        "cover_photo_id": "1245369301124707",
        "retry_profile": False,
    },
    {
        "key": "health_wellness",
        "name": "Herbal Organic Life",
        "page_id": "106788301081578",
        "token": "EAAIaAVdodLYBQyVjnpoA5UwHvOjWK7x6Ks9b1NSA2L3Cy0mLOzQw2FZAVZAshfT6TYekkRPN6QWKgmCg5habWvUaQKoxNlPmmA7fqh8EsbKHUwZBGbcbG9KZAng6s4uFEKZBc0nmqZC9GoI7B4gY9pD3XZACBQXHi0XYoJH1DQfwWPxXpiExYZAWjz2W6sEMtGKoVNr70soeYfDS51wn2jxsZC7bqm3s5oZAXmsqoTj09fOyDpa8BxWE27TYzk4QZDZD",
        "cover_photo_id": "1359579136187112",
        "retry_profile": False,
    },
]

IMAGE_DIR = r"C:\Users\PenuelM\Documents\ai-video-factory\assets\page_images"


def retry_profile_pic(page):
    """Retry setting profile picture for Beast Mode Academy."""
    page_id = page["page_id"]
    token = page["token"]
    image_path = f"{IMAGE_DIR}\\{page['key']}_profile.png"

    print(f"\n--- Retrying profile picture for {page['name']} ---")

    # Try the direct /picture endpoint again
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/picture",
                data={"access_token": token},
                files={"source": (f"{page['key']}_profile.png", f, "image/png")},
                timeout=60,
            )
        print(f"  /picture response ({resp.status_code}): {resp.text[:500]}")
        if resp.status_code == 200:
            print(f"  SUCCESS: Profile picture set!")
            return True
    except Exception as e:
        print(f"  Error: {e}")

    # Try uploading as a photo with profile_photo flag
    try:
        with open(image_path, "rb") as f:
            resp2 = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/photos",
                data={
                    "access_token": token,
                    "published": "true",
                    "is_profile_photo": "true",
                },
                files={"source": (f"{page['key']}_profile.png", f, "image/png")},
                timeout=60,
            )
        print(f"  /photos (is_profile_photo) response ({resp2.status_code}): {resp2.text[:500]}")
        if resp2.status_code == 200:
            print(f"  SUCCESS via is_profile_photo!")
            return True
    except Exception as e:
        print(f"  Error: {e}")

    return False


def set_cover_photo(page):
    """Set cover photo using the already-uploaded photo ID."""
    page_id = page["page_id"]
    token = page["token"]
    cover_photo_id = page["cover_photo_id"]
    image_path = f"{IMAGE_DIR}\\{page['key']}_cover.png"

    print(f"\n--- Setting cover photo for {page['name']} (photo_id: {cover_photo_id}) ---")

    # Method 1: Use cover as a dict-style parameter (not JSON string)
    print(f"  Method 1: cover[photo_id] = {cover_photo_id}")
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v24.0/{page_id}",
            data={
                "access_token": token,
                "cover[photo_id]": cover_photo_id,
                "cover[offset_y]": "0",
            },
            timeout=30,
        )
        print(f"    Response ({resp.status_code}): {resp.text[:500]}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") or data.get("id"):
                print(f"    SUCCESS: Cover photo set!")
                return True
    except Exception as e:
        print(f"    Error: {e}")

    # Method 2: Upload fresh photo with published=true, then set cover
    print(f"  Method 2: Fresh upload + set cover")
    try:
        with open(image_path, "rb") as f:
            resp2 = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/photos",
                data={
                    "access_token": token,
                    "published": "false",
                    "no_story": "true",
                },
                files={"source": (f"{page['key']}_cover.png", f, "image/png")},
                timeout=60,
            )
        print(f"    Fresh upload response ({resp2.status_code}): {resp2.text[:300]}")
        if resp2.status_code == 200:
            new_photo_id = resp2.json().get("id")
            if new_photo_id:
                print(f"    New photo ID: {new_photo_id}, setting as cover...")
                resp3 = requests.post(
                    f"https://graph.facebook.com/v24.0/{page_id}",
                    data={
                        "access_token": token,
                        "cover[photo_id]": new_photo_id,
                        "cover[offset_y]": "0",
                    },
                    timeout=30,
                )
                print(f"    Set cover response ({resp3.status_code}): {resp3.text[:500]}")
                if resp3.status_code == 200:
                    print(f"    SUCCESS: Cover photo set with new upload!")
                    return True
    except Exception as e:
        print(f"    Error: {e}")

    # Method 3: Use cover_url with the photo URL
    print(f"  Method 3: Using photo URL as cover source")
    try:
        # Get the photo URL
        resp_get = requests.get(
            f"https://graph.facebook.com/v24.0/{cover_photo_id}",
            params={"access_token": token, "fields": "images"},
            timeout=30,
        )
        print(f"    Photo info ({resp_get.status_code}): {resp_get.text[:300]}")
        if resp_get.status_code == 200:
            images = resp_get.json().get("images", [])
            if images:
                photo_url = images[0].get("source", "")
                if photo_url:
                    resp4 = requests.post(
                        f"https://graph.facebook.com/v24.0/{page_id}",
                        data={
                            "access_token": token,
                            "cover": photo_url,
                        },
                        timeout=30,
                    )
                    print(f"    cover=URL response ({resp4.status_code}): {resp4.text[:500]}")
                    if resp4.status_code == 200:
                        print(f"    SUCCESS: Cover set via URL!")
                        return True
    except Exception as e:
        print(f"    Error: {e}")

    print(f"  FAILED: Could not set cover photo for {page['name']}")
    return False


def main():
    results = {}

    for page in PAGES:
        print(f"\n{'='*60}")
        print(f"Page: {page['name']}")
        print(f"{'='*60}")

        # Retry profile pic for Beast Mode Academy
        if page.get("retry_profile"):
            profile_ok = retry_profile_pic(page)
            results[f"{page['key']}_profile"] = profile_ok

        # Fix cover photo for all
        cover_ok = set_cover_photo(page)
        results[f"{page['key']}_cover"] = cover_ok

        time.sleep(1)  # Rate limit buffer

    print(f"\n\n{'='*60}")
    print("FIX RESULTS")
    print(f"{'='*60}")
    for key, ok in results.items():
        status = "SUCCESS" if ok else "FAILED"
        print(f"  {key}: {status}")


if __name__ == "__main__":
    main()
