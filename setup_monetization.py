#!/usr/bin/env python3
"""
AI Video Factory - Monetization Setup Wizard
Run this after signing up for affiliate programs to plug in your IDs.
"""
import os
import re
import sys
import webbrowser

# Color codes for terminal
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RED = '\033[91m'
BOLD = '\033[1m'
RESET = '\033[0m'

def banner():
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗
║     AI Video Factory - Monetization Setup            ║
║     Plug in your affiliate IDs & API keys            ║
╚══════════════════════════════════════════════════════╝{RESET}
""")

SERVICES = [
    {
        "name": "Binance Affiliate",
        "signup_url": "https://www.binance.com/en/activity/affiliate",
        "instructions": "After signup, go to Affiliate Dashboard -> Your Referral Link.\nCopy the referral ID (the part after ?ref=)",
        "id_name": "Referral ID",
        "placeholder": "CPA_00DZ0RGQX0",
        "file": "modules/affiliate_manager.py",
        "search": "ref=CPA_00DZ0RGQX0",
        "replace_template": "ref={id}",
        "priority": "HIGH - 50% lifetime commission, your biggest audience (29K followers)"
    },
    {
        "name": "Amazon Associates",
        "signup_url": "https://affiliate-program.amazon.com/",
        "instructions": "After signup, your Associate Tag will be shown (format: yourname-20).\nCopy your Associate Tag.",
        "id_name": "Associate Tag",
        "placeholder": "traderadar-20",
        "file": "modules/affiliate_manager.py",
        "search": "tag=traderadar-20",
        "replace_template": "tag={id}",
        "priority": "HIGH - Universal product links, works for all niches"
    },
    {
        "name": "NordVPN Affiliate",
        "signup_url": "https://partnernetwork.nordvpn.com/",
        "instructions": "After signup, go to Dashboard -> Campaigns -> get your aff_id number.",
        "id_name": "Affiliate ID (number)",
        "placeholder": "XXXXX",
        "file": "modules/affiliate_manager.py",
        "search": "aff_id=XXXXX",
        "replace_template": "aff_id={id}",
        "priority": "MEDIUM - $40-100 per sale, great for tech_news audience"
    },
    {
        "name": "Fiverr Affiliates",
        "signup_url": "https://affiliates.fiverr.com/",
        "instructions": "After signup, go to Marketing Tools -> Your BTA ID.",
        "id_name": "BTA ID",
        "placeholder": "bta=XXXXX",
        "file": "modules/affiliate_manager.py",
        "search": "bta=XXXXX",
        "replace_template": "bta={id}",
        "priority": "MEDIUM - Good for ai_money niche"
    },
    {
        "name": "Stripe (Payments)",
        "signup_url": "https://dashboard.stripe.com/register",
        "instructions": "After signup:\n1. Go to Dashboard -> Developers -> API Keys\n2. Copy your Secret Key (starts with sk_live_)\n3. Create Payment Links for each product in Products -> Payment Links",
        "id_name": "Secret Key (sk_live_...)",
        "placeholder": None,
        "env_key": "STRIPE_SECRET_KEY",
        "priority": "HIGH - Required to accept payments on landing pages"
    },
    {
        "name": "Gumroad (Digital Products)",
        "signup_url": "https://gumroad.com/signup",
        "instructions": "After signup:\n1. Create products for each niche PDF\n2. Go to Settings -> Advanced -> Application ID\n3. Copy your Application ID for API access",
        "id_name": "Application ID",
        "placeholder": None,
        "env_key": "GUMROAD_APP_ID",
        "priority": "HIGH - Digital product delivery & payments"
    },
    {
        "name": "Email SMTP (Gmail or SendGrid)",
        "signup_url": "https://myaccount.google.com/apppasswords",
        "instructions": "For Gmail:\n1. Enable 2FA on your Google account\n2. Go to App Passwords (link above)\n3. Generate a new app password for 'Mail'\n4. Copy the 16-character password\n\nOR for SendGrid: https://signup.sendgrid.com/\nGet an API key from Settings -> API Keys",
        "id_name": "SMTP Password/API Key",
        "placeholder": None,
        "env_keys": {
            "EMAIL_SMTP_HOST": {"default": "smtp.gmail.com", "prompt": "SMTP Host"},
            "EMAIL_SMTP_PORT": {"default": "587", "prompt": "SMTP Port"},
            "EMAIL_SMTP_USER": {"default": "", "prompt": "Email address"},
            "EMAIL_SMTP_PASS": {"default": "", "prompt": "App Password/API Key"},
            "EMAIL_FROM_NAME": {"default": "GetTradeRadar", "prompt": "From Name"},
            "EMAIL_FROM_ADDRESS": {"default": "", "prompt": "From Email Address"},
        },
        "priority": "MEDIUM - Needed for email funnel to work"
    },
]

def update_file(filepath, search, replace):
    """Replace text in a file."""
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if search in content:
        content = content.replace(search, replace)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def update_env(key, value):
    """Add or update a key in .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith(f'{key}='):
            new_lines.append(f'{key}={value}\n')
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f'{key}={value}\n')

    with open(env_path, 'w') as f:
        f.writelines(new_lines)

def main():
    banner()

    print(f"{YELLOW}This wizard helps you set up all monetization services.{RESET}")
    print(f"{YELLOW}For each service, I'll open the signup page and wait for your ID.{RESET}")
    print(f"{YELLOW}Press Enter to skip any service you want to set up later.{RESET}\n")

    configured = []
    skipped = []

    for i, svc in enumerate(SERVICES, 1):
        print(f"\n{BOLD}{CYAN}--- [{i}/{len(SERVICES)}] {svc['name']} ---{RESET}")
        print(f"  Priority: {svc['priority']}")
        print(f"  {svc['instructions']}")

        open_browser = input(f"\n  {GREEN}Open signup page in browser? (y/n): {RESET}").strip().lower()
        if open_browser == 'y':
            webbrowser.open(svc['signup_url'])
            print(f"  {CYAN}Browser opened. Complete signup and come back here.{RESET}")

        # Handle services with multiple env keys (like SMTP)
        if 'env_keys' in svc:
            print(f"\n  {YELLOW}Configure email settings:{RESET}")
            all_set = False
            for key, info in svc['env_keys'].items():
                default = info['default']
                prompt_text = f"  {info['prompt']}"
                if default:
                    prompt_text += f" [{default}]"
                prompt_text += ": "
                val = input(f"  {GREEN}{prompt_text}{RESET}").strip()
                if not val and default:
                    val = default
                if val:
                    update_env(key, val)
                    all_set = True
            if all_set:
                configured.append(svc['name'])
                print(f"  {GREEN}Email settings saved to .env{RESET}")
            else:
                skipped.append(svc['name'])
            continue

        # Handle single env key services
        if 'env_key' in svc:
            val = input(f"\n  {GREEN}Paste your {svc['id_name']} (or Enter to skip): {RESET}").strip()
            if val:
                update_env(svc['env_key'], val)
                configured.append(svc['name'])
                print(f"  {GREEN}Saved to .env as {svc['env_key']}{RESET}")
            else:
                skipped.append(svc['name'])
                print(f"  {YELLOW}Skipped -- run this wizard again later{RESET}")
            continue

        # Handle affiliate ID replacement in files
        val = input(f"\n  {GREEN}Paste your {svc['id_name']} (or Enter to skip): {RESET}").strip()
        if val:
            search = svc['search']
            replace = svc['replace_template'].format(id=val)
            if update_file(svc['file'], search, replace):
                configured.append(svc['name'])
                print(f"  {GREEN}Updated in {svc['file']}{RESET}")
            else:
                print(f"  {RED}Pattern not found in {svc['file']} -- may already be configured{RESET}")
                configured.append(svc['name'] + " (may already be set)")
        else:
            skipped.append(svc['name'])
            print(f"  {YELLOW}Skipped -- run this wizard again later{RESET}")

    # Summary
    print(f"\n\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗")
    print(f"║                    SETUP COMPLETE                     ║")
    print(f"╚══════════════════════════════════════════════════════╝{RESET}\n")

    if configured:
        print(f"  {GREEN}Configured ({len(configured)}):{RESET}")
        for c in configured:
            print(f"     - {c}")

    if skipped:
        print(f"\n  {YELLOW}Skipped ({len(skipped)}):{RESET}")
        for s in skipped:
            print(f"     - {s}")
        print(f"\n  {YELLOW}Run 'python setup_monetization.py' again to configure skipped services.{RESET}")

    print(f"\n  {BOLD}Next steps:{RESET}")
    print(f"  1. Create products on Gumroad and update payment links in landing pages")
    print(f"  2. Point gettraderadar.com DNS to GitHub Pages")
    print(f"  3. Your scheduler is already pushing monetized content 24/7!")
    print(f"  4. Check your monetization dashboard at /dashboard/monetization.html")
    print(f"\n  {BOLD}{GREEN}Every video now earns you money. Let's go!{RESET}\n")

if __name__ == '__main__':
    main()
