#!/usr/bin/env python
"""Refresh Facebook PAGE tokens and make them PERMANENT (never expire).

Usage:
    python refresh_fb_token.py <USER_ACCESS_TOKEN>

Get <USER_ACCESS_TOKEN> from Graph API Explorer (https://developers.facebook.com/tools/explorer):
  select your app -> "User Token" -> add permissions pages_show_list,
  pages_read_engagement, pages_manage_posts -> Generate Access Token -> copy it.

This exchanges that short token for a LONG-LIVED user token, then reads the
never-expiring PAGE tokens from /me/accounts and writes them into .env. Your token
is used locally only and is NOT stored — only the resulting page tokens are saved.
"""
import sys, json, re, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
G = "https://graph.facebook.com/v19.0"

# Facebook page id -> our .env niche key
PAGE_KEY = {
    "104612394635916": "health_wellness",   # Herbal Organic (the expired one)
    "112465853843545": "blissful_moments",   # Mzansi Baby Stars
    "100919755007786": "tech_news",          # Tech Pulse Africa
    "104120995511039": "limitless_you",      # Africa 2050
    "102206758210905": "motivation",         # Elevate You
    "107465491085378": "ai_money",           # Smart Money AI
}


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
    if not secret:
        print("ERROR: FB_APP_SECRET missing from .env"); sys.exit(1)

    # 1) short-lived user token -> long-lived user token
    try:
        ll = get(f"{G}/oauth/access_token?" + urllib.parse.urlencode({
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": secret, "fb_exchange_token": user_tok}))
        ll_tok = ll.get("access_token", user_tok)
        print("[1/3] Long-lived user token obtained.")
    except Exception as e:
        print(f"ERROR exchanging token (check the token + app id/secret): {e}"); sys.exit(1)

    # 2) pages — a page token derived from a long-lived user token NEVER expires
    pages = get(f"{G}/me/accounts?" + urllib.parse.urlencode({
        "fields": "name,id,access_token", "access_token": ll_tok, "limit": "100"})).get("data", [])
    print(f"[2/3] {len(pages)} pages returned from /me/accounts.")

    # 3) write the permanent page tokens into .env
    env_text = ENV.read_text(encoding="utf-8", errors="replace")
    updated = []
    for pg in pages:
        key = PAGE_KEY.get(pg["id"])
        if not key:
            continue
        for k, v in [(f"FB_PAGE_TOKEN_{key}", pg["access_token"]), (f"FB_PAGE_ID_{key}", pg["id"])]:
            if re.search(rf"(?m)^{re.escape(k)}=.*$", env_text):
                env_text = re.sub(rf"(?m)^{re.escape(k)}=.*$", f"{k}={v}", env_text)
            else:
                env_text += ("" if env_text.endswith("\n") else "\n") + f"{k}={v}\n"
        updated.append(f"{key} ({pg['name']})")
    ENV.write_text(env_text, encoding="utf-8")
    print(f"[3/3] .env updated: {', '.join(updated) or '(no matching pages found)'}")

    # verify permanence
    app_tok = f"{app_id}|{secret}"
    print("\nVerification:")
    for pg in pages:
        key = PAGE_KEY.get(pg["id"])
        if not key:
            continue
        try:
            d = get(f"{G}/debug_token?" + urllib.parse.urlencode({
                "input_token": pg["access_token"], "access_token": app_tok})).get("data", {})
            exp = d.get("expires_at")
            print(f"   {key:18} valid={d.get('is_valid')} expires={'NEVER (permanent)' if exp == 0 else exp}")
        except Exception:
            pass
    print("\nDone. Restart is not needed — the pipeline reads .env fresh each run.")


if __name__ == "__main__":
    main()
