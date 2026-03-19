"""
Facebook Page Token Generator — Gets permanent page access tokens via OAuth.

Usage:
  python auth_facebook_pages.py
  (Opens browser → log in → approve permissions → prints all page tokens)

  python auth_facebook_pages.py --page "Limitless You"
  (Only show token for a specific page)

Flow:
  1. Opens browser to Facebook OAuth dialog
  2. User logs in and approves permissions
  3. Gets short-lived user token from redirect
  4. Exchanges for long-lived user token (60-day)
  5. Fetches all pages with permanent page tokens
  6. Optionally adds new page tokens to .env
"""
import http.server
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

load_dotenv(override=True)

# Facebook App credentials (MOTIVATIONS app)
APP_ID = os.getenv("FB_APP_ID", "591543017174198")
APP_SECRET = os.getenv("FB_APP_SECRET", "")
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
GRAPH_API = "https://graph.facebook.com/v24.0"

ENV_PATH = Path(__file__).parent / ".env"

# Permissions needed for page management
PERMISSIONS = [
    "pages_manage_posts",
    "pages_read_engagement",
    "pages_show_list",
    "pages_read_user_content",
    "publish_video",
]


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    """Handle the OAuth redirect callback."""
    auth_code = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                OAuthHandler.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Success!</h1><p>You can close this tab.</p>")
            else:
                error = params.get("error_description", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error</h1><p>{error}</p>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress server logs


def get_user_token_via_oauth() -> str:
    """Open browser for Facebook OAuth and return a short-lived user token."""
    scope = ",".join(PERMISSIONS)
    auth_url = (
        f"https://www.facebook.com/v24.0/dialog/oauth"
        f"?client_id={APP_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={scope}"
        f"&response_type=code"
    )

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), OAuthHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print(f"\nOpening browser for Facebook login...")
    print(f"If it doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=120)
    server.server_close()

    if not OAuthHandler.auth_code:
        print("ERROR: No auth code received. Did you approve the permissions?")
        sys.exit(1)

    # Exchange code for short-lived token
    resp = requests.get(
        f"{GRAPH_API}/oauth/access_token",
        params={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": OAuthHandler.auth_code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def exchange_long_lived(short_token: str) -> str:
    """Exchange short-lived token for a long-lived user token (60 days)."""
    resp = requests.get(
        f"{GRAPH_API}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"Long-lived user token obtained (expires: {data.get('expires_in', 'never')}s)")
    return data["access_token"]


def get_all_pages(user_token: str) -> list[dict]:
    """Fetch all pages the user manages with their permanent page tokens."""
    pages = []
    url = f"{GRAPH_API}/me/accounts?fields=id,name,access_token&limit=100&access_token={user_token}"
    while url:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        pages.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
    return pages


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Get Facebook page tokens")
    parser.add_argument("--page", help="Filter for a specific page name")
    parser.add_argument("--save", action="store_true", help="Save new tokens to .env")
    parser.add_argument("--user-token", help="Use an existing user access token instead of OAuth")
    args = parser.parse_args()

    if not APP_SECRET:
        print("ERROR: FB_APP_SECRET not set in .env")
        print("Get it from: https://developers.facebook.com/apps/591543017174198/settings/basic/")
        print("Add to .env: FB_APP_SECRET=<your_app_secret>")
        sys.exit(1)

    if args.user_token:
        user_token = args.user_token
    else:
        short_token = get_user_token_via_oauth()
        user_token = exchange_long_lived(short_token)

    pages = get_all_pages(user_token)

    # Map of known niche keys to page names
    NICHE_MAP = {
        "Beast Mode Academy": "ai_trading",
        "Smart Money AI": "ai_money",
        "Tech Pulse Africa": "tech_news",
        "Elevate You": "motivation",
        "Herbal Organic Life": "health_wellness",
        "Blissful Moments": "blissful_moments",
        "Limitless You": "limitless_you",
        "The Daily Breakdown": "daily_breakdown",
        "ShopMO": "shopmo_products",
    }

    print(f"\n{'='*60}")
    print(f"Found {len(pages)} pages:\n")

    for p in pages:
        name = p["name"]
        page_id = p["id"]
        token = p.get("access_token", "")

        if args.page and args.page.lower() not in name.lower():
            continue

        niche = NICHE_MAP.get(name, "")
        niche_label = f" [{niche}]" if niche else ""

        print(f"  {name}{niche_label}")
        print(f"    ID:    {page_id}")
        print(f"    Token: {token[:40]}..." if token else "    Token: (none)")

        if args.save and niche and token:
            existing_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
            existing_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
            if not existing_id or not existing_token:
                set_key(str(ENV_PATH), f"FB_PAGE_ID_{niche}", page_id)
                set_key(str(ENV_PATH), f"FB_PAGE_TOKEN_{niche}", token)
                print(f"    -> Saved to .env as FB_PAGE_ID_{niche} / FB_PAGE_TOKEN_{niche}")
            else:
                print(f"    -> Already in .env")
        print()

    print(f"{'='*60}")

    if not args.save:
        print("\nTip: Run with --save to auto-add missing page tokens to .env")


if __name__ == "__main__":
    main()
