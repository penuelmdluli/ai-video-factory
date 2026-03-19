"""
Fix cover photo uploads - try multiple Facebook Graph API approaches.
The 'cover' parameter format seems to be the issue.
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
    },
    {
        "key": "ai_money",
        "name": "Smart Money AI",
        "page_id": "100919755007786",
        "token": "EAAIaAVdodLYBQZBDd10klIlrbmuT1fu4QqGbb5jKfyntpUXDUTGXwSIUdnK9lqyQkmV0ZCT2r3y4DEAlDGQezvE7C0X83txikISnHzAI6ZCsrf6DQb8QsZArSxiqpwA0H5gSSZBMDp6gsx1ZArqxNguUHEjrhPzZC9C41JJslgzniNHMAIWRLUbKACQLMrmz4hCZBZAJSNXZADPUFX1FkHM4Pg5nFtWvhBCeOLiZBQPCv9GCdGPiaAgWZCmTAYpOMwZDZD",
    },
    {
        "key": "tech_news",
        "name": "Tech Pulse Africa",
        "page_id": "107465491085378",
        "token": "EAAIaAVdodLYBQwv0WpNIYfKs01HB4PorZCP4dgM7bvZBF9KuNZAajozLZBbNKrUZCCuMOwGcmIxA7IOBlOZCEd7tfG1XjgbFHal6vXvfw1TeW004nSC2P4nNI1ZBU23f3w2GlzP23YnEkQSt7kHYZC6MHbps3tqmv7idn2dQ6IBI6aQr734ZAJdtEX272I2snu24f9AeAAhrmZCU2sEOAGXbsBynZAwF8WCuZAaxGZBtKSPqWBctH0bD0gxibHU5IDAZDZD",
    },
    {
        "key": "motivation",
        "name": "Elevate You",
        "page_id": "102206758210905",
        "token": "EAAIaAVdodLYBQ2rK1JxgBS9PZCVzinlLQzP3OO1qp0KX61rJxCa9m5ouWhv7hvT0WeZAefY6vOfGOT6wfa1UhvAbby4GyottwxdejGAFZBiS2ndjjGjHYvyj7p2GnNqbOOpk9ExpZCHeX9af31ppTDkB2vdbYmO1HIwWzMY7MrsmskMtC0qWMwXuIPQcLQt48fja0gZAX31gFfg2GsZC67jESmioIqxTaor6ZBeCe1FLzZBP4hA0pyI1B5OciAZDZD",
    },
    {
        "key": "health_wellness",
        "name": "Herbal Organic Life",
        "page_id": "106788301081578",
        "token": "EAAIaAVdodLYBQyVjnpoA5UwHvOjWK7x6Ks9b1NSA2L3Cy0mLOzQw2FZAVZAshfT6TYekkRPN6QWKgmCg5habWvUaQKoxNlPmmA7fqh8EsbKHUwZBGbcbG9KZAng6s4uFEKZBc0nmqZC9GoI7B4gY9pD3XZACBQXHi0XYoJH1DQfwWPxXpiExYZAWjz2W6sEMtGKoVNr70soeYfDS51wn2jxsZC7bqm3s5oZAXmsqoTj09fOyDpa8BxWE27TYzk4QZDZD",
    },
]

IMAGE_DIR = r"C:\Users\PenuelM\Documents\ai-video-factory\assets\page_images"


def set_cover(page):
    """Try multiple methods to set cover photo."""
    page_id = page["page_id"]
    token = page["token"]
    image_path = f"{IMAGE_DIR}\\{page['key']}_cover.png"

    print(f"\n{'='*60}")
    print(f"Setting cover for: {page['name']}")
    print(f"{'='*60}")

    # First upload photo
    print(f"  Uploading photo...")
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v24.0/{page_id}/photos",
            data={"access_token": token, "published": "false", "no_story": "true"},
            files={"source": (f"{page['key']}_cover.png", f, "image/png")},
            timeout=60,
        )
    print(f"  Upload: {resp.status_code} - {resp.text[:200]}")

    if resp.status_code != 200:
        print(f"  FAILED to upload photo")
        return False

    photo_id = resp.json().get("id")
    print(f"  Photo ID: {photo_id}")

    # Method A: POST with cover as JSON string (photo_id only, no offset)
    print(f"\n  Method A: cover as JSON string with just photo_id")
    try:
        resp_a = requests.post(
            f"https://graph.facebook.com/v24.0/{page_id}",
            params={"access_token": token},
            json={"cover": {"photo_id": photo_id}},
            timeout=30,
        )
        print(f"    Response ({resp_a.status_code}): {resp_a.text[:400]}")
        if resp_a.status_code == 200:
            print(f"    SUCCESS!")
            return True
    except Exception as e:
        print(f"    Error: {e}")

    # Method B: POST with cover as form field, just photo_id number
    print(f"\n  Method B: cover = photo_id string only")
    try:
        resp_b = requests.post(
            f"https://graph.facebook.com/v24.0/{page_id}",
            data={"access_token": token, "cover": photo_id},
            timeout=30,
        )
        print(f"    Response ({resp_b.status_code}): {resp_b.text[:400]}")
        if resp_b.status_code == 200:
            print(f"    SUCCESS!")
            return True
    except Exception as e:
        print(f"    Error: {e}")

    # Method C: URL-encoded form with cover as a proper nested param
    print(f"\n  Method C: URL-encoded nested params")
    try:
        payload = f"access_token={token}&cover=%7B%22photo_id%22%3A%22{photo_id}%22%7D"
        resp_c = requests.post(
            f"https://graph.facebook.com/v24.0/{page_id}",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        print(f"    Response ({resp_c.status_code}): {resp_c.text[:400]}")
        if resp_c.status_code == 200:
            print(f"    SUCCESS!")
            return True
    except Exception as e:
        print(f"    Error: {e}")

    # Method D: Use the photos endpoint with special param
    print(f"\n  Method D: Upload directly as published cover photo")
    try:
        with open(image_path, "rb") as f:
            resp_d = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/photos",
                data={
                    "access_token": token,
                    "published": "true",
                    "no_story": "true",
                    "is_cover_photo": "true",
                },
                files={"source": (f"{page['key']}_cover.png", f, "image/png")},
                timeout=60,
            )
        print(f"    Response ({resp_d.status_code}): {resp_d.text[:400]}")
        if resp_d.status_code == 200:
            print(f"    Uploaded as cover photo!")
            # Now try setting it
            new_id = resp_d.json().get("id")
            if new_id:
                resp_d2 = requests.post(
                    f"https://graph.facebook.com/v24.0/{page_id}",
                    params={"access_token": token},
                    json={"cover": photo_id},
                    timeout=30,
                )
                print(f"    Set cover ({resp_d2.status_code}): {resp_d2.text[:300]}")
    except Exception as e:
        print(f"    Error: {e}")

    # Method E: Get the photo URL and use cover[source]
    print(f"\n  Method E: Using cover source URL")
    try:
        # Get photo info
        photo_info = requests.get(
            f"https://graph.facebook.com/v24.0/{photo_id}",
            params={"access_token": token, "fields": "images,link"},
            timeout=30,
        )
        if photo_info.status_code == 200:
            pdata = photo_info.json()
            images = pdata.get("images", [])
            if images:
                source_url = images[0]["source"]
                resp_e = requests.post(
                    f"https://graph.facebook.com/v24.0/{page_id}",
                    data={
                        "access_token": token,
                        "cover[source]": source_url,
                    },
                    timeout=30,
                )
                print(f"    Response ({resp_e.status_code}): {resp_e.text[:400]}")
                if resp_e.status_code == 200:
                    print(f"    SUCCESS!")
                    return True
    except Exception as e:
        print(f"    Error: {e}")

    # Method F: Try using the /picture endpoint for cover
    print(f"\n  Method F: Direct file upload to page endpoint")
    try:
        with open(image_path, "rb") as f:
            resp_f = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}",
                data={
                    "access_token": token,
                },
                files={
                    "cover_photo.source": (f"{page['key']}_cover.png", f, "image/png"),
                },
                timeout=60,
            )
        print(f"    Response ({resp_f.status_code}): {resp_f.text[:400]}")
        if resp_f.status_code == 200:
            print(f"    SUCCESS!")
            return True
    except Exception as e:
        print(f"    Error: {e}")

    print(f"\n  ALL METHODS FAILED for {page['name']}")
    return False


def main():
    # First check what permissions/fields are available
    page = PAGES[0]
    print("Checking available page fields...")
    resp = requests.get(
        f"https://graph.facebook.com/v24.0/{page['page_id']}",
        params={
            "access_token": page["token"],
            "fields": "id,name,cover,permissions",
        },
        timeout=30,
    )
    print(f"Page info: {resp.text[:500]}")

    results = {}
    for page in PAGES:
        ok = set_cover(page)
        results[page["key"]] = ok
        time.sleep(1)

    print(f"\n\n{'='*60}")
    print("COVER PHOTO RESULTS")
    print(f"{'='*60}")
    for key, ok in results.items():
        print(f"  {key}: {'SUCCESS' if ok else 'FAILED'}")


if __name__ == "__main__":
    main()
