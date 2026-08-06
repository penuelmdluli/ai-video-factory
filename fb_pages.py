#!/usr/bin/env python
"""List your Facebook pages, and optionally connect one to a channel niche in .env
(with a PERMANENT page token).

Usage:
  python fb_pages.py <USER_TOKEN>                     # list all pages (pick one)
  python fb_pages.py <USER_TOKEN> <PAGE_ID> sa_pulse  # connect that page -> niche

Get <USER_TOKEN> from Graph API Explorer (User token; permissions pages_show_list,
pages_read_engagement, pages_manage_posts, pages_manage_metadata). Your token is
used locally only and is not stored.
"""
import sys, json, re, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
G = "https://graph.facebook.com/v19.0"


def env_val(key, default=""):
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    user_tok = sys.argv[1].strip()
    app_id = env_val("FB_APP_ID", "591543017174198")
    secret = env_val("FB_APP_SECRET")

    # long-lived exchange so the page tokens we read never expire
    try:
        ll = get(f"{G}/oauth/access_token?" + urllib.parse.urlencode({
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": secret, "fb_exchange_token": user_tok}))
        tok = ll.get("access_token", user_tok)
    except Exception:
        tok = user_tok

    pages = get(f"{G}/me/accounts?" + urllib.parse.urlencode({
        "fields": "name,id,category,fan_count,followers_count,access_token",
        "access_token": tok, "limit": "100"})).get("data", [])

    if len(sys.argv) >= 4:
        # connect mode: python fb_pages.py <tok> <page_id> <niche>
        page_id, niche = sys.argv[2].strip(), sys.argv[3].strip()
        pg = next((p for p in pages if p["id"] == page_id or p["name"].lower() == page_id.lower()), None)
        if not pg:
            print(f"Page '{page_id}' not found among your pages."); sys.exit(1)
        env_text = ENV.read_text(encoding="utf-8", errors="replace")
        for k, v in [(f"FB_PAGE_ID_{niche}", pg["id"]), (f"FB_PAGE_TOKEN_{niche}", pg["access_token"])]:
            if re.search(rf"(?m)^{re.escape(k)}=.*$", env_text):
                env_text = re.sub(rf"(?m)^{re.escape(k)}=.*$", f"{k}={v}", env_text)
            else:
                env_text += ("" if env_text.endswith("\n") else "\n") + f"{k}={v}\n"
        ENV.write_text(env_text, encoding="utf-8")
        print(f"CONNECTED: '{pg['name']}' ({pg['id']}) -> niche '{niche}' with a permanent token.")
        return

    # list mode
    print(f"\nYou manage {len(pages)} Facebook pages:\n")
    print(f"{'#':>2}  {'PAGE ID':<18} {'FOLLOWERS':>9}  {'CATEGORY':<22} NAME")
    print("-" * 90)
    for i, p in enumerate(sorted(pages, key=lambda x: -(x.get("followers_count") or x.get("fan_count") or 0)), 1):
        fans = p.get("followers_count") or p.get("fan_count") or 0
        print(f"{i:>2}  {p['id']:<18} {fans:>9}  {(p.get('category') or '')[:22]:<22} {p['name']}")
    print("\nPick one for Mzansi Pulse, then run:")
    print("  python fb_pages.py <USER_TOKEN> <PAGE_ID> sa_pulse")


if __name__ == "__main__":
    main()
