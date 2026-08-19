"""
Verified opportunity feed for Mzansi Careers.

The page posted once and then had nothing to say, because every post was
hand-built. To run 4-5 posts a day we need a supply of opportunities — but
never at the cost of the one rule that makes the page worth following.

So the details are not written by us or by a model: they are lifted verbatim
from the employer's own careers page. A claim that came off the official page
is verifiable by definition, and link_check re-tests it at post time. If a
page goes down or stops mentioning opportunities, that employer is skipped
rather than posted with stale text.

    op = next_opportunity()      # rotates, never repeats within the cycle
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from modules.link_check import UA, check_link, fetch_text

STATE = Path(__file__).parent.parent / "data" / "careers_feed_state.json"
COOLDOWN_DAYS = 6          # an employer may not repeat inside this window

# Official employer pages only — every one of these was link-checked live.
SOURCES = [
    ("TRANSNET", "https://www.transnet.net/YouthDevelopmentProgrammes",
     "Youth Development Programmes"),
    ("ESKOM", "https://www.eskom.co.za/careers/", "Careers at Eskom"),
    ("SARS", "https://www.sars.gov.za/careers/", "Careers at SARS"),
    ("SASOL", "https://www.sasol.com/careers", "Careers at Sasol"),
    ("NYDA", "https://www.nyda.gov.za/", "Youth development support"),
    ("SA YOUTH", "https://www.sayouth.mobi/", "Youth opportunities"),
    ("SHOPRITE", "https://www.shopriteholdings.co.za/careers.html",
     "Careers at Shoprite"),
    ("PICK N PAY", "https://www.pnp.co.za/careers", "Careers at Pick n Pay"),
    ("WOOLWORTHS", "https://www.woolworths.co.za/corporate/careers",
     "Careers at Woolworths"),
    ("STANDARD BANK",
     "https://www.standardbank.com/sbg/standard-bank-group/careers",
     "Careers at Standard Bank"),
    ("ABSA", "https://www.absa.africa/careers/", "Careers at Absa"),
    ("VODACOM", "https://www.vodacom.com/careers.php", "Careers at Vodacom"),
    ("DENEL", "https://www.denel.co.za/careers", "Careers at Denel"),
    ("PRASA", "https://www.prasa.com/careers.html", "Careers at PRASA"),
]

KEYWORDS = re.compile(
    r"\b(learnership|internship|graduate programme|graduate program|bursar|"
    r"apprentice|work integrated|vacanc|trainee|youth|school leaver|"
    r"in-service|experiential|development programme)\w*\b", re.I)


def _load():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def extract_lines(text, limit=4):
    """Short, self-contained lines from the page that mention opportunities."""
    out, seen = [], set()
    for raw in re.split(r"(?<=[.!?])\s+|•|\u2022|\n", text):
        s = " ".join(raw.split())
        if not (25 <= len(s) <= 150) or not KEYWORDS.search(s):
            continue
        # skip nav noise and cookie/legal boilerplate
        if re.search(r"cookie|privacy|terms|javascript|browser", s, re.I):
            continue
        key = s.lower()[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def opportunity_for(name, url, programme):
    """Build one opportunity, or None if the page has nothing usable."""
    link = check_link(url)
    if not link["ok"]:
        print(f"[CareersFeed] {name}: link dead ({link['note']}) — skipped")
        return None
    try:
        text = fetch_text(link["final"])
    except Exception as e:
        print(f"[CareersFeed] {name}: unreadable ({e}) — skipped")
        return None
    lines = extract_lines(text)
    if len(lines) < 2:
        print(f"[CareersFeed] {name}: nothing on the page right now — skipped")
        return None
    return {
        "key": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        "employer": name,
        "programme": programme,
        "card_details": lines,
        "reel_details": tuple(l[:38] for l in lines[:3]),
        "must_verify": lines,          # lifted from the page, so they verify
        "apply_url": link["final"],
        "closes": "", "closes_full": "", "closes_card": "", "days_left": None,
        "hook": f"{name.title()} opportunities",
        "kicker": programme,
        "source": f"Verified on {name.title()}'s official careers page",
        "apply_steps": [
            f"Open the official {name.title()} careers page (link in comments)",
            "Read the programme that matches your qualification",
            "Follow the employer's own application instructions",
            "Have your ID, CV and academic record ready as PDFs",
        ],
        "yt_title": f"{name.title()} — {programme}"[:90],
        "yt_tags": ["SA jobs", "learnership", "internship", name.lower()],
    }


def next_opportunity(skip_recent=True):
    """The next employer due, skipping any posted inside the cooldown."""
    state = _load()
    now = datetime.now()
    order = state.get("order") or []
    if sorted(order) != sorted(s[0] for s in SOURCES):
        order = [s[0] for s in SOURCES]
    idx = state.get("idx", 0)
    by_name = {s[0]: s for s in SOURCES}

    for step in range(len(order)):
        name = order[(idx + step) % len(order)]
        last = state.get("posted", {}).get(name)
        if skip_recent and last:
            try:
                if now - datetime.fromisoformat(last) < timedelta(
                        days=COOLDOWN_DAYS):
                    continue
            except Exception:
                pass
        src = by_name.get(name)
        if not src:
            continue
        op = opportunity_for(*src)
        if op:
            state["order"] = order
            state["idx"] = (idx + step + 1) % len(order)
            state.setdefault("posted", {})[name] = now.isoformat()
            _save(state)
            return op
    return None
