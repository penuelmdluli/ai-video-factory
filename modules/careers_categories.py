"""
Job categories for Mzansi Careers.

The page has to work for everyone: the person who left school and needs a
driver or cleaner post, AND the person who studied teaching, nursing, IT or
accounting and cannot find a first job. Posting only one end of that range
tells half our audience the page is not for them.

So every advert in the circular is classified, and the daily slots rotate
through the categories. Over a week, a teacher, a nurse, an electrician and
a general worker all see themselves on the page.

Requests from the comments (modules/careers_requests) push a category up the
queue, so what people ask for is what they get next.
"""
import re

# order matters: the first pattern that matches wins, so specific first
CATEGORIES = [
    ("education", "Teaching & Education", re.compile(
        r"teacher|educator|lecturer|principal|ecd|early childhood|"
        r"education specialist|school|curriculum|librarian|tutor", re.I)),
    ("health", "Health & Care", re.compile(
        r"nurse|nursing|medical|clinical|pharmac|radiograph|physio|"
        r"dental|paramedic|emergency care|health promot|dietician|"
        r"occupational therap|psycholog", re.I)),
    ("trades", "Trades & Artisans", re.compile(
        r"artisan|electrician|plumber|mechanic|welder|carpenter|boilermaker|"
        r"fitter|millwright|handyman|tradesman|technician|foreman", re.I)),
    ("general", "General Work", re.compile(
        r"cleaner|general worker|road worker|groundsman|gardener|porter|"
        r"food service|household aid|laundry|kitchen|housekeep|labour|"
        r"messenger|driver|operator", re.I)),
    ("safety", "Safety & Security", re.compile(
        r"security|traffic officer|correctional|peace officer|firefighter|"
        r"safety officer|inspector", re.I)),
    ("social", "Social & Community", re.compile(
        r"social work|community development|auxiliary worker|youth worker|"
        r"child care|probation", re.I)),
    ("admin", "Admin & Office", re.compile(
        r"clerk|administrat|receptionist|secretar|data captur|switchboard|"
        r"registry|typist|office", re.I)),
    ("finance", "Finance & Audit", re.compile(
        r"account|audit|financ|budget|payroll|supply chain|procurement|"
        r"revenue|treasury", re.I)),
    ("it", "IT & Technical", re.compile(
        r"information technology|\bit \b|systems|network|developer|"
        r"data scien|analyst|gis|software|cyber", re.I)),
    ("engineering", "Engineering & Science", re.compile(
        r"engineer|scientist|survey|environmental|forestry|agricultur|"
        r"geolog|chemist|laborator", re.I)),
]

LABELS = {key: label for key, label, _ in CATEGORIES}
ORDER = [key for key, _, _ in CATEGORIES]


def classify(post) -> str:
    """Category key for one circular advert."""
    # Title only. Including the department made every post in the
    # "Department of Employment and Labour" look like general work.
    text = post.get("title", "")
    for key, _label, rx in CATEGORIES:
        if rx.search(text):
            return key
    return "admin"


def label(key: str) -> str:
    return LABELS.get(key, "Opportunities")


def rotation(slot_no: int, requested: list[str] | None = None) -> list[str]:
    """Category preference order for this slot.

    Requested categories come first — if people ask for teaching posts, that
    is what goes out next — then the standing rotation so nobody is dropped.
    """
    req = [c for c in (requested or []) if c in ORDER]
    rest = [c for c in ORDER if c not in req]
    start = slot_no % max(1, len(rest))
    return req + rest[start:] + rest[:start]
