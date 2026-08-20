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
        "reel_details": tuple(lines[:3]),
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


def next_opportunity(skip_recent=True, prefer_dpsa=True):
    """Next opportunity to post.

    The circular is tried first: it is the only source with enough verified
    volume to fill five slots a day. Employer pages are the fallback and the
    variety.
    """
    if prefer_dpsa:
        op = dpsa_opportunity()
        if op:
            return op
    return _next_employer_page(skip_recent)


def _next_employer_page(skip_recent=True):
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


# ── Government circular: the volume source ────────────────────────────────
# Corporate careers sites are JavaScript and yield nothing to a scraper. The
# DPSA circular is a plain weekly PDF with hundreds of real posts, published
# by the employer itself. Every field below is quoted from that document.

def dpsa_opportunity():
    """The next unposted vacancy from the current DPSA circular."""
    from modules.dpsa_circular import latest_circular, parse_posts, fetch_pdf
    import io
    try:
        circ = latest_circular()
        if not circ:
            print("[CareersFeed] DPSA: no circular found")
            return None
        posts = parse_posts(circ["pdf"], limit=400)
    except Exception as e:
        print(f"[CareersFeed] DPSA unavailable: {e}")
        return None
    if not posts:
        return None

    from modules.dpsa_circular import (is_entry_level, positions_in,
                                       no_degree_needed)

    state = _load()
    done = set(state.get("dpsa_done", []))
    key_of = lambda p: f"{circ['number']}:{p['post_no']}"          # noqa: E731
    usable = [p for p in posts
              if key_of(p) not in done and p["salary"] and p["centre"]
              and p["closing"]]

    # The page has to work for everyone — the school leaver looking for a
    # driver post AND the graduate teacher or nurse who cannot find a first
    # job. So slots rotate through every field, and whatever people ASK for
    # in the comments jumps the queue.
    from modules.careers_categories import classify, rotation, label
    try:
        from modules.careers_requests import requested
        wanted = requested()
    except Exception as e:
        print(f"[CareersFeed] requests unavailable: {e}")
        wanted = []

    n = int(state.get("slot_no", 0))
    state["slot_no"] = n + 1
    by_cat = {}
    for p in usable:
        by_cat.setdefault(classify(p), []).append(p)

    nxt, chosen_cat = None, ""
    # A requested field takes one slot in three — enough that people see
    # their request answered, not so much that it crowds everyone else out.
    honour = wanted if (n % 3 == 0) else []
    # Coverage must not cost the people who need us most their slots.
    # Two of three go to low-barrier work whatever the field rotation
    # says; the third rotates freely so every profession still appears.
    if n % 3 != 2:
        low = [q for q in usable if is_entry_level(q)]
        if low:
            low.sort(key=lambda q: (0 if no_degree_needed(q) else 1,
                                    -positions_in(q["title"])))
            nxt, chosen_cat = low[0], classify(low[0])
            print("[CareersFeed] low-barrier slot")
    for cat in ([] if nxt is not None else rotation(n, honour)):
        pool = by_cat.get(cat)
        if not pool:
            continue
        # inside a field, the advert that helps the most people goes first
        # inside a field: work people can actually get first, then the
        # advert that helps the most people
        pool.sort(key=lambda p: (0 if is_entry_level(p) else 1,
                                 -positions_in(p["title"])))
        nxt, chosen_cat = pool[0], cat
        break
    if nxt is None and usable:
        nxt, chosen_cat = usable[0], classify(usable[0])
    if nxt is not None:
        why = " (requested)" if chosen_cat in wanted else ""
        print(f"[CareersFeed] field: {label(chosen_cat)}{why}")
    if not nxt:
        print("[CareersFeed] DPSA: every post in this circular already used")
        return None

    # the official document's own words — the gate checks these against it
    tidy = lambda v: v.strip().rstrip(":").strip()          # noqa: E731
    details = []
    if positions_in(nxt["title"]) > 1:
        details.append(f"{positions_in(nxt['title'])} positions available")
    details += [
        f"Salary: {tidy(nxt['salary'])}",
        f"Centre: {tidy(nxt['centre'])}",
        f"Closing date: {tidy(nxt['closing'])}",
    ]
    if nxt["ref"]:
        details.insert(0, f"Reference: {nxt['ref']}")

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(fetch_pdf(circ["pdf"])))
        source_text = " ".join((pg.extract_text() or "")
                               for pg in reader.pages)
    except Exception:
        source_text = ""

    state.setdefault("dpsa_done", []).append(key_of(nxt))
    _save(state)

    # A real, credited photo instead of a flat green rectangle in the feed.
    try:
        from modules.careers_images import backdrop_for
        bg, bg_credit = backdrop_for(nxt["department"], nxt["title"])
    except Exception as e:
        print(f"[CareersFeed] backdrop unavailable: {e}")
        bg, bg_credit = None, ""

    seats = positions_in(nxt["title"])
    # "ROAD WORKER ( X99 POSTS)" reads badly as a job title when the count is
    # already its own line — strip it back to the role.
    role = re.sub(r"[(]?" + chr(92) + "s*X" + chr(92) + "s*" + chr(92) +
                  "d{1,3}" + chr(92) + "s*POSTS?" + chr(92) + "s*[)]?", "",
                  nxt["title"], flags=re.I).strip(" .-()")
    entry_level = is_entry_level(nxt)
    no_degree = no_degree_needed(nxt)
    dept = nxt["department"] or "Public Service"
    # "DEPARTMENT OF BASIC EDUCATION" truncated to 28 chars cut mid-word;
    # drop the boilerplate prefix and keep the name itself.
    # Keep the whole department name. Cutting at 26 characters produced
    # "FORESTRY, FISHERIES AND" — the card renderers shrink or wrap now, so
    # the data layer has no business truncating.
    short = re.sub(r"^Department Of\s+", "", dept, flags=re.I).strip()
    return {
        "key": "dpsa-" + str(circ["number"]) + "-" + re.sub(
            r"[^0-9]+", "-", nxt["post_no"]).strip("-"),
        "employer": short.upper(),
        "programme": role.title()[:60],
        "card_details": details,
        "reel_details": tuple(details[:3]),
        # verify only the short factual strings, which appear verbatim
        "must_verify": [nxt["salary"], nxt["centre"], nxt["closing"]],
        "source_text": source_text,
        "apply_url": circ["page"],
        "closes": nxt["closing"], "closes_full": nxt["closing"],
        "closes_card": f"CLOSES {nxt['closing'].upper()}", "days_left": None,
        "hook": role.title()[:44],
        "kicker": dept.title(),
        "source": f"Public Service Vacancy Circular {circ['number']} of "
                  f"{circ['year']}",
        # generic wording turned into "official Forestry, Fisheries And The
        # Environment source", which wraps badly and reads like filler
        "apply_line": "Apply FREE via the official DPSA circular",
        "positions": seats,
        "entry_level": entry_level,
        "no_degree": no_degree,
        "category": chosen_cat,
        "category_label": label(chosen_cat),
        "bg_photo": bg,
        "photo_credit": bg_credit,
        "apply_steps": [
            "Open the official DPSA circular (link in the comments)",
            f"Find post {nxt['post_no']} — reference {nxt['ref'] or 'in the circular'}",
            "Apply with a fully completed Z83 form and your CV",
            "Send it to the address given in the circular before the closing date",
        ],
        "yt_title": f"{role.title()[:60]} — {nxt['centre'][:24]}",
        "yt_tags": ["government jobs", "DPSA", "public service", "SA jobs"],
    }
