"""YOU PICK — one job, one name, chosen by South Africans.

Owner asked for "imagine them in power together for a better South Africa".
The first build of that (modules/dream_cabinet.py) had the PAGE name the
cabinet, and on 2 Sep its roster came back as Ramaphosa (Phala Phala evidence
in court), Zuma (a Gupta meeting story), Malema (owes a judge an apology),
Mbeki (lost a recusal bid) and a golfer. "Most covered" and "best performing"
are opposites on a day the news is all courtrooms, and a 10K page proposing
that side reads as sarcasm at best.

Turning the question around fixes it completely, and makes it a better post.
The page asserts nothing about anybody: it states one real, sourced fact, names
one job, and asks who should do it. The audience supplies every name, so there
is nothing for the page to get wrong and nothing to defend - and people argue
harder for their OWN answer than they ever will with ours.

Two posts, one argument, same loop as the Genesis formats:

    python build_your_cabinet.py --ask         # the question, off a live headline
    python build_your_cabinet.py --wall        # who South Africa picked
    python build_your_cabinet.py --ask --post

The hook is never invented. It comes from modules/sa_news.py - a story carried
by several newsrooms today - so the question arrives attached to something the
reader has already seen this week, which is the difference between a debate
prompt and a chain letter.
"""
import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "tech_news"
STATE = ROOT / "data" / "cabinet_asks.json"

# One job per post. A whole cabinet asks for eleven decisions and gets none;
# one chair asks for a single name and gets thousands. Each carries the words
# that decide which of today's headlines can introduce it.
SEATS = [
    {"key": "electricity", "title": "MINISTER OF ELECTRICITY",
     "job": "keep the lights on",
     "terms": ("eskom", "load shedding", "loadshedding", "electricity",
               "power cut", "grid", "nersa", "tariff")},
    {"key": "police", "title": "MINISTER OF POLICE",
     "job": "make people feel safe walking home",
     "terms": ("crime", "police", "saps", "murder", "hijack", "gang",
               "shooting", "safety", "kidnap")},
    {"key": "finance", "title": "MINISTER OF FINANCE",
     "job": "decide what your money is worth by Friday",
     "terms": ("rand", "budget", "tax", "sars", "treasury", "inflation",
               "reserve bank", "repo", "vat", "petrol price")},
    {"key": "jobs", "title": "MINISTER OF JOBS",
     "job": "find work for two in three young people",
     "terms": ("unemployment", "jobs", "hiring", "retrench", "labour",
               "vacanc", "work", "youth")},
    {"key": "water", "title": "MINISTER OF WATER",
     "job": "answer for every dry tap in the country",
     "terms": ("water", "drought", "dam", "tap", "sewage", "reservoir")},
    {"key": "transport", "title": "MINISTER OF TRANSPORT",
     "job": "own the trains, the taxis and the potholes",
     "terms": ("transport", "taxi", "prasa", "train", "pothole", "road",
               "n1", "traffic", "licence")},
    {"key": "health", "title": "MINISTER OF HEALTH",
     "job": "run the clinic your family actually uses",
     "terms": ("health", "hospital", "clinic", "nhi", "doctor", "nurse",
               "medicine", "patient")},
    {"key": "grants", "title": "MINISTER OF SOCIAL DEVELOPMENT",
     "job": "answer for every grant that pays a household",
     "terms": ("sassa", "grant", "srd", "postbank", "social development")},
]

# Below this the result is one person's opinion, not a country's.
MIN_VOTERS = 5

# Never printed on a card, whoever nominated it. The page is asking a sincere
# question about real public figures; publishing an insult as "South Africa's
# pick" hands the page's voice to whoever typed the worst thing.
ABUSE = re.compile(
    r"\b(idiot|stupid|fool|clown|dog|pig|monkey|thief|thug|criminal|"
    r"murderer|rapist|devil|satan|witch|bitch|fuck|shit|voetsek|kak|"
    r"moron|useless|corrupt|liar|scum|trash|rubbish|k[a4]ff|nigg)",
    re.IGNORECASE,
)


def _log(m):
    print(f"[Cabinet] {m}", flush=True)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"asks": [], "used": []}


def _save(d: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                     encoding="utf-8")


async def choose_seat_and_hook():
    """A seat, and a real headline that introduces it.

    Seats rotate least-used-first, but a seat whose subject is actually IN
    today's news jumps the queue: "Eskom made R30.3bn profit - who should run
    electricity?" is a question with a reason to exist today, where the same
    question cold is just a survey.
    """
    from modules.sa_news import get_sa_briefing

    d = _state()
    counts = {s["key"]: 0 for s in SEATS}
    for k in d.get("used", []):
        if k in counts:
            counts[k] += 1
    order = sorted(SEATS, key=lambda s: (counts[s["key"]],
                                         [x["key"] for x in SEATS].index(s["key"])))

    stories = []
    try:
        stories = (await get_sa_briefing()).get("stories") or []
    except Exception as e:
        _log(f"headline feed unavailable ({str(e)[:60]}) — asking without a hook")

    # Best corroborated story first, so the hook is one several newsrooms ran.
    for seat in order:
        for s in stories:
            text = (s.get("headline", "") + " " + " ".join(s.get("also") or [])).lower()
            if any(t in text for t in seat["terms"]):
                return seat, s
    return order[0], None


# Public figures South Africans actually nominate for these jobs. Matched
# CASE-INSENSITIVELY, because a comment is not a headline: the first test of
# this counted "Julius Malema" and missed "malema", "RAMAPHOSA!!!" and
# "ramaphosa again", which is most of how people really type. The extractor in
# dream_cabinet is right for headlines and wrong here for exactly that reason.
KNOWN_FIGURES = [
    # Multi-word surnames FIRST and matched longest-first. Building this list
    # with .split() on spaces turned "Andre de Ruyter" - the one name certain
    # to come up on an Eskom question - into two candidates, "De" and "Ruyter",
    # each with its own vote.
    "de ruyter", "de lille", "van damme", "du plessis",
    "ramaphosa", "malema", "zuma", "mbeki", "mashatile", "steenhuisen",
    "mkhwanazi", "motsoaledi", "godongwana", "lesufi", "ntshavheni",
    "mchunu", "mckenzie", "zille", "maimane", "holomisa", "shivambu",
    "ndlozi", "gordhan", "ramokgopa", "marokane", "oberholzer", "molefe",
    "koko", "mantashe", "creecy", "motsepe", "rupert", "oppenheimer",
    "sexwale", "mabuza", "magashule", "sisulu", "dlamini", "pandor",
    "nzimande", "kodwa", "didiza", "schreiber", "macpherson", "whitfield",
    "tshabalala", "nkabane", "simelane", "mahlobo", "hlophe", "madonsela",
    "makwetu", "maluleke", "gigaba", "patel",
]
# Longest first so "de ruyter" is claimed before "ruyter" can be.
KNOWN_FIGURES.sort(key=len, reverse=True)

# "Julius Malema" and "malema" are one candidate, not two. Without collapsing
# to the surname the vote splits across spellings and nobody wins - the first
# test produced five candidates on five votes, every one of them tied at 1.
_NAME_TOKENS = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def _names_in(text: str) -> set:
    """Public figures a comment nominates, keyed on SURNAME.

    Two passes, because case cannot be trusted in a comment thread. Known
    figures match however they are typed; anyone else is caught only when the
    commenter capitalises a full name, which is the honest limit - a bare
    lowercase word we do not recognise is far more likely to be a noun than a
    nomination, and inventing a candidate would corrupt the count.
    """
    raw = str(text or "")
    if ABUSE.search(raw):
        return set()

    found = set()
    low = raw.lower()
    claimed = low
    for fig in KNOWN_FIGURES:
        if re.search(rf"(?<![a-z]){re.escape(fig)}(?![a-z])", claimed):
            found.add(fig.title())
            # Blank the match so a compound surname cannot be counted again by
            # its own last word.
            claimed = re.sub(rf"(?<![a-z]){re.escape(fig)}(?![a-z])",
                             " " * len(fig), claimed)

    # Anyone not on the list, when they are written like a name.
    from modules.dream_cabinet import _candidates
    for cand in _candidates(raw):
        surname = cand.split()[-1]
        if surname.lower() in KNOWN_FIGURES or surname.title() in found:
            continue
        # A word already consumed by a compound match is not a new candidate.
        if surname.lower() not in claimed:
            continue
        found.add(surname.title())
    return found


async def _page_token() -> str:
    import os
    return (os.getenv(f"FB_PAGE_TOKEN_{NICHE}")
            or os.getenv("FB_PAGE_TOKEN") or "")


async def tally(post_id: str) -> dict:
    """One person, one vote. Counting mentions would let one loud commenter
    elect a minister on his own."""
    from modules.community_manager import _all_comments_on

    token = await _page_token()
    if not token:
        return {"votes": {}, "voters": 0, "comments": 0, "error": "no page token"}
    comments = await _all_comments_on(str(post_id), token)

    by_person = defaultdict(set)
    skipped = 0
    for c in comments:
        msg = c.get("message") or ""
        if ABUSE.search(msg):
            skipped += 1
            continue
        who = ((c.get("from") or {}).get("id")
               or (c.get("from") or {}).get("name") or c.get("id"))
        named = _names_in(msg)
        if who and named:
            by_person[who] |= named

    votes = defaultdict(int)
    for _p, names in by_person.items():
        for n in names:
            votes[n] += 1
    return {"votes": dict(sorted(votes.items(), key=lambda kv: -kv[1])),
            "voters": len(by_person), "comments": len(comments),
            "skipped": skipped}


def _card(out_path: Path, kicker: str, headline: str, body: list,
          footer: str) -> Path:
    from PIL import Image, ImageDraw
    from modules.thumbnail_pro import _font

    # Tech Pulse Africa's own colours, not a club's: deep ink with a green
    # rule, so the card is recognisably this page and not a Genesis card.
    accent = (0, 168, 107)
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 14], fill=accent)
    d.rectangle([0, H - 14, W, H], fill=accent)

    y = 88
    d.text((70, y), kicker, font=_font(40, "news"), fill=accent)
    y += 74
    f_head = _font(70, "news")
    for line in _wrap(d, headline, f_head, W - 140):
        d.text((70, y), line, font=f_head, fill=(255, 255, 255))
        y += 82
    y += 26
    f_body = _font(38, "news")
    f_name = _font(34, "news")
    for item in body:
        if isinstance(item, dict):
            d.text((70, y), f"{item['n']}", font=f_name, fill=accent)
            d.text((150, y), item["name"], font=f_body, fill=(238, 238, 238))
            y += 62
        else:
            for line in _wrap(d, str(item), f_body, W - 140):
                d.text((70, y), line, font=f_body, fill=(225, 225, 225))
                y += 52
            y += 16
        if y > H - 190:
            break
    d.text((70, H - 104), footer, font=_font(32, "news"), fill=accent)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)
    return out_path


def _wrap(draw, text, font, max_w):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


async def do_ask(a) -> int:
    seat, story = await choose_seat_and_hook()
    hook = ""
    if story:
        hook = story["headline"]
        _log(f"hook ({story['outlet_count']} outlets): {hook[:80]}")
    _log(f"seat: {seat['title']}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"cabinet_ask_{stamp}"
    body = ([hook] if hook else []) + [
        f"If you could put ONE person in charge tomorrow — someone who must "
        f"{seat['job']} — who would it be?"]
    card = _card(work / "ask.png", "YOU PICK", seat["title"], body,
                 "ONE NAME IN THE COMMENTS · TECH PULSE AFRICA")
    _log(f"card: {card}")

    nl = chr(10)
    src = f" ({story['lead_source']})" if story else ""
    caption = (
        f"YOU PICK THE {seat['title'].replace('MINISTER OF ', '')} MINISTER. 👇{nl}{nl}"
        + (f"{hook}{src}.{nl}{nl}" if hook else "")
        + f"Forget who holds the job. If YOU could put one person in charge "
          f"tomorrow — someone who must {seat['job']} — who?{nl}{nl}"
          f"One name. We will count them and post South Africa's pick.{nl}{nl}"
          f"#SouthAfrica #Mzansi #SANews #SouthAfricaNews #TechPulseAfrica")

    if not a.post:
        _log("dry run — pass --post to publish")
        print(nl + caption + nl)
        return 0

    from modules.uploader_facebook import upload_photo
    r = await upload_photo(str(card), caption, NICHE)
    _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
    if (r or {}).get("status") != "uploaded":
        return 1
    pid = r.get("photo_id") or r.get("post_id")
    d = _state()
    d["asks"].append({"post_id": str(pid), "seat": seat["key"],
                      "title": seat["title"], "hook": hook,
                      "asked_at": datetime.now().isoformat(timespec="seconds"),
                      "answered_at": ""})
    d["used"] = (d.get("used", []) + [seat["key"]])[-40:]
    d["asks"] = d["asks"][-60:]
    _save(d)
    return 0


async def do_wall(a) -> int:
    d = _state()
    open_asks = [x for x in d.get("asks", []) if not x.get("answered_at")]
    if not open_asks:
        _log("no unanswered cabinet post on record")
        return 1
    ask = open_asks[-1]
    _log(f"counting {ask['title']} (post {ask['post_id']})")

    res = await tally(ask["post_id"])
    if res.get("error"):
        _log(f"cannot read the thread: {res['error']}")
        return 1
    _log(f"{res['comments']} comments, {res['voters']} people named someone, "
         f"{res['skipped']} skipped as abuse")
    for n, v in list(res["votes"].items())[:8]:
        _log(f"   {v:>3} {n}")
    if res["voters"] < a.min_voters:
        _log(f"only {res['voters']} voters — below the {a.min_voters} floor")
        return 2
    top = list(res["votes"].items())[:5]
    if not top:
        _log("nobody named a person we could read — no wall")
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"cabinet_wall_{stamp}"
    body = [{"n": v, "name": n} for n, v in top]
    card = _card(work / "wall.png", "SOUTH AFRICA PICKED", ask["title"], body,
                 f"{res['voters']} PEOPLE VOTED · TECH PULSE AFRICA")
    _log(f"card: {card}")

    nl = chr(10)
    lead, lead_votes = top[0]
    caption = (
        f"SOUTH AFRICA PICKED. 👇{nl}{nl}"
        f"We asked who should be {ask['title'].title()}. "
        f"{res['voters']} of you answered, and {lead.upper()} came top with "
        f"{lead_votes}.{nl}{nl}"
        f"One vote per person, no matter how many times you commented. "
        f"This is your list, not ours.{nl}{nl}"
        f"Disagree? The next seat goes up soon.{nl}{nl}"
        f"#SouthAfrica #Mzansi #SANews #SouthAfricaNews #TechPulseAfrica")

    (work / "post_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "card": str(card), "caption": caption,
         "result": res, "ask": ask, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")

    if not a.post:
        _log("dry run — pass --post to publish")
        print(nl + caption + nl)
        return 0

    from modules.uploader_facebook import upload_photo, post_comment
    r = await upload_photo(str(card), caption, NICHE)
    _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
    if (r or {}).get("status") != "uploaded":
        _log("post failed — ask stays OPEN for a retry")
        return 1
    ask["answered_at"] = datetime.now().isoformat(timespec="seconds")
    _save(d)
    try:
        await post_comment(ask["post_id"],
                           f"Counted — {res['voters']} of you voted and "
                           f"{lead} came top. Full list is up on the page.",
                           NICHE)
    except Exception as e:
        _log(f"could not reply on the original post: {str(e)[:90]}")
    return 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", action="store_true")
    ap.add_argument("--wall", action="store_true")
    ap.add_argument("--min-voters", type=int, default=MIN_VOTERS)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    if not a.ask and not a.wall:
        a.ask = True
    return await (do_wall(a) if a.wall else do_ask(a))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
