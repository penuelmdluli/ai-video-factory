"""
Instagram setup checker for the Genesis News page.

Instagram posting has been failing on every run for a simple reason: it was
never configured. INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID are both empty,
and the Instagram account is not linked to the Facebook page, so the Graph API
has nothing to publish to.

This checks every link in that chain, says exactly which one is broken, and
writes the account id into .env automatically once the link exists — so the
only manual step is the one that genuinely cannot be done through the API.

    python setup_instagram.py            # check and configure what it can
"""
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
GRAPH = "https://graph.facebook.com/v24.0"
ENV = Path(__file__).parent / ".env"
NEEDED_SCOPES = ["instagram_basic", "instagram_content_publish"]


def _set_env(key: str, value: str):
    """Write or replace a key in .env, leaving everything else untouched."""
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    line = f"{key}={value}"
    if re.search(rf"^{key}=.*$", text, re.M):
        text = re.sub(rf"^{key}=.*$", line, text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    ENV.write_text(text, encoding="utf-8")
    print(f"  .env updated: {key}")


def main(niche="sa_pulse"):
    token = os.getenv(f"FB_PAGE_TOKEN_{niche}")
    page_id = os.getenv(f"FB_PAGE_ID_{niche}")
    if not (token and page_id):
        print(f"FAIL: no Facebook page credentials for '{niche}'")
        return 1

    print(f"Instagram setup check — page {page_id} ({niche})\n")
    ok = True

    # 1. scopes on the page token
    d = requests.get(f"{GRAPH}/debug_token",
                     params={"input_token": token, "access_token": token},
                     timeout=45).json().get("data", {})
    scopes = d.get("scopes", [])
    for s in NEEDED_SCOPES:
        have = s in scopes
        print(f"[{'ok ' if have else 'MISSING'}] scope {s}")
        ok &= have

    # 2. is an Instagram account linked to the page?
    r = requests.get(f"{GRAPH}/{page_id}",
                     params={"fields": "instagram_business_account{id,username,"
                                       "followers_count}",
                             "access_token": token}, timeout=45).json()
    iga = r.get("instagram_business_account")
    if not iga:
        print("[MISSING] no Instagram account linked to this Facebook page")
        print("\n  Link it here (this cannot be done through the API):")
        print("    Meta Business Suite -> Settings -> Accounts ->")
        print("    Instagram accounts -> Connect account")
        print("  The Instagram account must be Professional "
              "(Business or Creator).")
        return 1

    print(f"[ok ] linked account: @{iga.get('username')} "
          f"({iga.get('followers_count', '?')} followers)")
    _set_env("INSTAGRAM_USER_ID", iga["id"])
    _set_env("INSTAGRAM_ACCESS_TOKEN", token)

    if not ok:
        print("\nAccount is linked, but the token is missing a scope above.")
        print("Re-authorise the app with that scope, then run this again.")
        return 1

    print("\nInstagram is configured. Next reel will post there too.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sa_pulse"))
