"""
DPSA Public Service Vacancy Circular parser.

The circular is the highest-volume legitimate source of jobs in South Africa:
the government's own weekly PDF carrying hundreds of posts across every
national and provincial department. Corporate careers sites are mostly
JavaScript and yield nothing to a scraper; this is a plain document, published
by the employer, updated every week.

Every field we publish is lifted verbatim from that PDF — post title,
reference number, salary, centre, closing date — so a Mzansi Careers post
about a government job is quoting the official circular, not paraphrasing it.

    circ = latest_circular()          # {'number', 'year', 'pdf', 'page'}
    posts = parse_posts(circ['pdf'])  # list of dicts, one per vacancy
"""
import io
import re
from datetime import date
from pathlib import Path

import requests

from modules.link_check import UA

BASE = "https://www.dpsa.gov.za"
CACHE = Path(__file__).parent.parent / "data" / "dpsa_cache"

POST_RE = re.compile(
    r"POST\s+(\d+\s*/\s*\d+)\s*:\s*(.+?)(?:\s+REF\s*NO[:\.]?\s*([^\s]+))?\s*$",
    re.I | re.M)
FIELD_RE = {
    "salary": re.compile(r"^\s*SALARY\s*:?\s*(.+)$", re.I | re.M),
    "centre": re.compile(r"^\s*CENTRE\s*:?\s*(.+)$", re.I | re.M),
}
CLOSING_RE = re.compile(r"CLOSING\s+DATE\s*:?\s*([0-9]{1,2}\s+\w+\s+\d{4})",
                        re.I)
ANNEX_RE = re.compile(r"ANNEXURE\s+([A-Z]{1,2})\b", re.I)
DEPT_RE = re.compile(r"^\s*(DEPARTMENT OF [A-Z ,&/\-]+|PROVINCIAL "
                     r"ADMINISTRATION[A-Z :,&/\-]*|OFFICE OF THE [A-Z ]+)\s*$",
                     re.M)


def _iso_week_guess(today=None):
    """The circular number tracks the ISO week fairly closely."""
    d = today or date.today()
    return d.isocalendar()[1]


def find_circular_page(number: int, year: int) -> str | None:
    url = f"{BASE}/newsroom/psvc/circular-{number}-of-{year}/"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=45)
        return url if r.status_code == 200 and ".pdf" in r.text else None
    except Exception:
        return None


def pdf_link_on(page_url: str) -> str | None:
    """The full circular PDF (not the per-department annexures)."""
    r = requests.get(page_url, headers={"User-Agent": UA}, timeout=60)
    pdfs = re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.I)
    full = [p for p in pdfs if re.search(r"CIRCULAR", p, re.I)]
    return (full or pdfs or [None])[0]


def latest_circular(max_back: int = 12) -> dict | None:
    """Newest published circular, walking back from this week's number."""
    year = date.today().year
    start = _iso_week_guess() + 1
    for n in range(start, max(1, start - max_back), -1):
        page = find_circular_page(n, year)
        if not page:
            continue
        pdf = pdf_link_on(page)
        if pdf:
            return {"number": n, "year": year, "page": page, "pdf": pdf}
    return None


def fetch_pdf(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / (re.sub(r"[^A-Za-z0-9]+", "_", url)[-80:] + ".pdf")
    if key.exists() and key.stat().st_size > 10000:
        return key.read_bytes()
    r = requests.get(url, headers={"User-Agent": UA}, timeout=300)
    r.raise_for_status()
    key.write_bytes(r.content)
    return r.content


def _clean(s: str) -> str:
    """Normalise PDF artifacts: PSYCHO -SOCIAL -> PSYCHO-SOCIAL."""
    s = " ".join(s.replace(chr(8217), "'").split())
    s = re.sub(r"\s+-\s*(?=[A-Za-z])", "-", s)
    s = re.sub(r"^[A-Z]?\s*:\s*", "", s)
    return s.strip()


def parse_posts(pdf_url_or_bytes, limit: int = 400) -> list[dict]:
    """Every vacancy in the circular, with the fields we are willing to post."""
    import PyPDF2
    data = (pdf_url_or_bytes if isinstance(pdf_url_or_bytes, bytes)
            else fetch_pdf(pdf_url_or_bytes))
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    posts, dept, closing = [], "", ""
    for page in reader.pages:
        text = page.extract_text() or ""
        m = DEPT_RE.search(text)
        if m:
            dept = _clean(m.group(1)).title()
        c = CLOSING_RE.search(text)
        if c:
            closing = _clean(c.group(1))
        for pm in POST_RE.finditer(text):
            num, title, ref = pm.group(1), _clean(pm.group(2)), pm.group(3)
            tail = text[pm.end(): pm.end() + 1200]
            sal = FIELD_RE["salary"].search(tail)
            cen = FIELD_RE["centre"].search(tail)
            title = re.sub(r"\s*REF\s*NO.*$", "", title, flags=re.I).strip()
            if len(title) < 6:
                continue
            posts.append({
                "post_no": _clean(num),
                "title": title,
                "ref": _clean(ref or ""),
                "salary": _clean(sal.group(1)) if sal else "",
                "centre": _clean(cen.group(1)) if cen else "",
                "department": dept,
                "closing": closing,
            })
            if len(posts) >= limit:
                return posts
    return posts

# Entry-level work is what most unemployed South Africans can actually apply
# for: cleaners, drivers, general workers, road workers, porters. The circular
# is full of them — 70 in one issue — and they were being skipped while the
# page posted director posts nobody in that position can take.
ENTRY_TITLES = re.compile(
    r"cleaner|driver|general worker|road worker|food service|household aid|"
    r"groundsman|gardener|messenger|porter|handyman|tradesman aid|labour|"
    r"housekeep|security officer|kitchen|laundry|nursing assistant|"
    r"auxiliary|data captur|receptionist|switchboard", re.I)
ENTRY_MAX_SALARY = 260000          # rands per annum, ~level 1-5


def salary_value(text):
    """The annual rand figure in a salary line, or None."""
    m = re.search(r"R" + chr(92) + "s?([" + chr(92) + "d ]{5,})", text or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def positions_in(title):
    """How many posts this advert carries: 'ROAD WORKER (X99 POSTS)' -> 99."""
    m = re.search(r"[(]?" + chr(92) + "s*X" + chr(92) + "s*(" + chr(92) +
                  "d{1,3})" + chr(92) + "s*POSTS?", title or "", re.I)
    return int(m.group(1)) if m else 1


def is_entry_level(post):
    """Low-barrier work: prioritised in the rotation, not a public claim."""
    v = salary_value(post.get("salary", ""))
    if v is not None and v <= ENTRY_MAX_SALARY:
        return True
    return bool(ENTRY_TITLES.search(post.get("title", "")) and
                (v is None or v <= 330000))


# Saying "no degree needed" is a factual claim about the requirements, and a
# salary band does not prove it — an HR Officer on R237k normally needs a
# diploma. Only the manual roles, where it is true, may carry the badge.
NO_DEGREE_TITLES = re.compile(
    r"cleaner|general worker|road worker|groundsman|gardener|porter|"
    r"food service|household aid|laundry|kitchen|housekeep|labour|"
    r"messenger|driver|tradesman aid|handyman|security guard", re.I)


def no_degree_needed(post) -> bool:
    v = salary_value(post.get("salary", ""))
    return bool(NO_DEGREE_TITLES.search(post.get("title", ""))
                and (v is None or v <= 220000))
