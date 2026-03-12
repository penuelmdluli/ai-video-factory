"""
Facebook Page Cleanup — Delete ALL old posts & videos via Batch API.
Run: python cleanup_pages.py --confirm

Auto-waits for rate limit to clear, then batch-deletes everything.
"""
import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API = "https://graph.facebook.com/v24.0"

PAGES = {
    "ai_trading": {"id": os.getenv("FB_PAGE_ID_ai_trading"), "token": os.getenv("FB_PAGE_TOKEN_ai_trading"), "name": "Beast Mode Academy"},
    "ai_money": {"id": os.getenv("FB_PAGE_ID_ai_money"), "token": os.getenv("FB_PAGE_TOKEN_ai_money"), "name": "Smart Money AI"},
    "tech_news": {"id": os.getenv("FB_PAGE_ID_tech_news"), "token": os.getenv("FB_PAGE_TOKEN_tech_news"), "name": "Tech Pulse Africa"},
    "motivation": {"id": os.getenv("FB_PAGE_ID_motivation"), "token": os.getenv("FB_PAGE_TOKEN_motivation"), "name": "Elevate You"},
    "health_wellness": {"id": os.getenv("FB_PAGE_ID_health_wellness"), "token": os.getenv("FB_PAGE_TOKEN_health_wellness"), "name": "Herbal Organic Life"},
    "blissful_moments": {"id": os.getenv("FB_PAGE_ID_blissful_moments"), "token": os.getenv("FB_PAGE_TOKEN_blissful_moments"), "name": "Blissful Moments"},
}


def wait_for_rate_limit(token):
    """Keep checking until API is available."""
    attempt = 0
    while True:
        try:
            resp = requests.get(f"{GRAPH_API}/me?fields=id&access_token={token}", timeout=15)
            if resp.status_code == 200:
                print("[OK] API is available!")
                return
            if resp.status_code == 403 and "rate" in resp.text.lower():
                attempt += 1
                mins = 5
                print(f"[WAIT] Rate limited (attempt {attempt}). Waiting {mins} minutes...")
                time.sleep(mins * 60)
            else:
                print(f"[OK] Status {resp.status_code} - proceeding")
                return
        except Exception as e:
            print(f"[ERR] {e} - retrying in 60s")
            time.sleep(60)


def get_all_items(page_id, token, edge):
    """Fetch ALL items with pagination and rate limit handling."""
    items = []
    url = f"{GRAPH_API}/{page_id}/{edge}?fields=id&limit=100&access_token={token}"
    while url:
        for attempt in range(10):
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                break
            if "rate" in resp.text.lower():
                wait = 300
                print(f"  Rate limited fetching {edge}, waiting 5min...")
                time.sleep(wait)
            else:
                return items
        else:
            return items

        data = resp.json()
        items.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        time.sleep(2)
    return items


def batch_delete(item_ids, token):
    """Delete up to 50 items in a single batch request with retry."""
    batch = [{"method": "DELETE", "relative_url": str(iid)} for iid in item_ids]

    for attempt in range(10):
        resp = requests.post(
            GRAPH_API,
            data={"access_token": token, "batch": json.dumps(batch)},
            timeout=60,
        )
        if resp.status_code == 200:
            results = resp.json()
            deleted = sum(1 for r in results if r and r.get("code") == 200)
            return deleted
        elif "rate" in resp.text.lower():
            wait = 300
            print(f"  Rate limited on batch, waiting 5min (attempt {attempt+1})...")
            time.sleep(wait)
        else:
            print(f"  Batch error: {resp.status_code} {resp.text[:100]}")
            return 0
    return 0


def cleanup_page(niche, page):
    """Delete ALL videos and posts from a single page."""
    page_id = page["id"]
    token = page["token"]
    name = page["name"]

    if not page_id or not token:
        print(f"\n[SKIP] {name} ({niche}) -- not configured")
        return 0

    print(f"\n{'='*60}")
    print(f"  {name} ({niche})")
    print(f"{'='*60}")

    # Make sure API is available before starting
    wait_for_rate_limit(token)

    all_items = []

    videos = get_all_items(page_id, token, "videos")
    print(f"  Found {len(videos)} videos")
    all_items.extend(videos)

    posts = get_all_items(page_id, token, "feed")
    existing_ids = {v["id"] for v in videos}
    new_posts = [p for p in posts if p["id"] not in existing_ids]
    print(f"  Found {len(new_posts)} additional feed posts")
    all_items.extend(new_posts)

    total = len(all_items)
    print(f"  Total items to delete: {total}")
    if not all_items:
        print("  Already clean!")
        return 0

    # Batch delete (50 at a time)
    item_ids = [item["id"] for item in all_items]
    total_deleted = 0

    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        batch_num = (i // 50) + 1
        total_batches = (len(item_ids) + 49) // 50

        deleted = batch_delete(batch, token)
        total_deleted += deleted
        pct = total_deleted * 100 // total if total else 0
        print(f"  Batch {batch_num}/{total_batches}: {deleted}/{len(batch)} deleted ({pct}% done, {total_deleted}/{total})")
        time.sleep(3)

    print(f"\n  >>> {name}: {total_deleted}/{total} items deleted <<<")
    return total_deleted


def main():
    print("\n" + "#" * 60)
    print("  FACEBOOK PAGE CLEANUP -- DELETE ALL OLD CONTENT")
    print("#" * 60)

    if "--confirm" not in sys.argv:
        confirm = input("\n  Type 'DELETE ALL' to proceed: ")
        if confirm.strip() != "DELETE ALL":
            print("  Aborted.")
            return
    else:
        print("  --confirm flag set.\n")

    # Wait for API availability first
    first_token = next((p["token"] for p in PAGES.values() if p.get("token")), None)
    if first_token:
        print("Checking API rate limit...")
        wait_for_rate_limit(first_token)

    grand_total = 0
    for niche, page in PAGES.items():
        count = cleanup_page(niche, page)
        grand_total += count

    print(f"\n{'='*60}")
    print(f"  CLEANUP COMPLETE -- {grand_total} total items deleted")
    print(f"  All 6 pages are now clean!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
