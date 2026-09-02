"""'Imagine them in power together' - a debate format for Tech Pulse Africa.

Owner call 2026-09-02: take the people currently driving the national
conversation and imagine them in one team building a better South Africa.

It works because it is the one post nobody scrolls past without an opinion.
Straight news gets a nod; a proposed cabinet gets an argument, and an argument
is the only thing on this page that reliably produces comments.

Two design rules do the heavy lifting.

FIRST, the names are MEASURED, not chosen. "Best performing people" is read off
the live feed - whoever is actually being written about this week, ranked by how
many separate stories carry them. A hand-written list of famous South Africans
would be the same seven names every month and would drift out of date within
one news cycle; the feed cannot, because it IS the news cycle. Curation only
happens in reverse: a small block list, so an accused in a court story does not
get promoted to Finance Minister by an algorithm that cannot read tone.

SECOND, it is fiction and must always look like fiction. This names real living
people, so every output is stamped as imagination, carries no invented quote,
attributes no invented policy, and asserts nothing about what any of them would
actually do. It asks the audience a question; it does not answer it. That is
both the honest framing and the one that survives contact with Facebook's
policy on real-person content - a page that reads as fabricating politics about
named individuals gets restricted, and a restricted page posts nothing at all.
"""
import asyncio
import re
from datetime import datetime

# Roles are deliberately about VISIBLE, everyday outcomes rather than the real
# cabinet's org chart. "Minister of Trade and Industry" starts no arguments;
# "the one who has to end load shedding" starts several, and it is the same job.
PORTFOLIOS = [
    ("President", "sets the direction and carries the blame"),
    ("Minister of Electricity", "has one job: keep the lights on"),
    ("Minister of Police", "has to make people feel safe walking home"),
    ("Minister of Finance", "decides what your money is worth by Friday"),
    ("Minister of Jobs", "must find work for two in three young people"),
    ("Minister of Health", "runs the clinic your family actually uses"),
    ("Minister of Education", "owns every matric result from here on"),
    ("Minister of Home Affairs", "answers for the queue and the border"),
    ("Minister of Water", "answers for every dry tap in the country"),
    ("Minister of Transport", "owns the trains, the taxis and the potholes"),
]

# Words that look like surnames to a regex but are places, bodies or brands.
# Without this the feed nominates "Cape Town" for Finance Minister.
NOT_A_PERSON = {
    "south", "africa", "african", "cape", "town", "johannesburg", "durban",
    "pretoria", "gauteng", "kwazulu", "natal", "limpopo", "mpumalanga",
    "soweto", "eastern", "western", "northern", "free", "state", "north",
    "west", "eskom", "sassa", "transnet", "prasa", "sars", "saps", "npa",
    "anc", "eff", "mkp", "ifp", "parliament", "cabinet", "government",
    "national", "assembly", "high", "court", "supreme", "constitutional",
    "reserve", "bank", "stats", "home", "affairs", "public", "protector",
    "postbank", "shell", "wild", "coast", "september", "october", "november",
    "december", "january", "february", "march", "april", "june", "july",
    "august", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "judge", "minister", "president", "deputy",
    "police", "the", "this", "that", "what", "why", "how", "when", "who",
    "watch", "live", "listen", "opinion", "breaking", "update", "afriforum",
    "operation", "dudula", "union", "buildings", "luthuli", "house", "city",
    "council", "commission", "committee", "department", "university",
    "school", "hospital", "airport", "stadium", "province", "premier",
    "sunday", "times", "daily", "news", "mail", "guardian", "citizen",
    "sowetan", "moneyweb", "briefly", "groundup", "bloomberg", "reuters",
    # Scandals and places that read exactly like a surname pair. "Phala Phala"
    # is a farm, and on 2 Sep it out-ranked every actual human being.
    "phala", "nkandla", "bosasa", "gupta", "guptas", "zondo", "marikana",
    "esidimeni", "steinhoff", "tembisa", "lonmin", "seriti",
    # Headlines start with a capital, so the first word of any sentence looks
    # like a first name. "Did Ramaphosa act in bad faith?" nominated a
    # candidate called "Did Ramaphosa" alongside the real one.
    "did", "does", "will", "can", "should", "could", "would", "must", "has",
    "have", "had", "was", "were", "are", "his", "her", "its", "our", "their",
    "your", "more", "most", "after", "before", "amid", "over", "under",
    "with", "and", "but", "for", "not", "now", "here", "there", "these",
    "those", "still", "just", "only", "even", "back", "down", "out", "off",
    "into", "about", "against", "between", "during", "without", "within",
    "another", "every", "each", "some", "many", "few", "all", "both", "such",
    "same", "than", "then", "once", "again", "also", "well", "very", "much",
    "less", "least", "best", "worst", "one", "two", "three", "four", "five",
    "big", "new", "old", "top", "full", "real", "major", "huge", "why",
    "inside", "behind", "meet", "here's", "heres", "look", "read", "listen",
    # Headline verbs. A capitalised surname followed by a capitalised verb is
    # the commonest false name of all - "Ramaphosa Seeks", "Overturn Cash-In" -
    # because headline case capitalises the verb too.
    "seeks", "seek", "says", "said", "wants", "want", "calls", "call",
    "urges", "urge", "warns", "warn", "slams", "slam", "hits", "hit",
    "faces", "face", "denies", "deny", "backs", "back", "wins", "win",
    "loses", "lose", "quits", "quit", "resigns", "resign", "defends",
    "defend", "reveals", "reveal", "admits", "admit", "claims", "claim",
    "vows", "vow", "blasts", "blast", "opens", "open", "closes", "close",
    "launches", "launch", "announces", "announce", "confirms", "confirm",
    "rejects", "reject", "approves", "approve", "overturn", "overturns",
    "questions", "question", "explains", "explain", "asks", "ask",
    "returns", "return", "moves", "move", "takes", "gives", "give",
    "loom", "looms", "apologise", "apologize", "agrees", "agree",
    # Organisation and document tails. "Zuma Foundation" and "Sofa Report" are
    # not people, and both were nominated for cabinet.
    "foundation", "trust", "party", "group", "movement", "forum", "institute",
    "council", "report", "panel", "inquiry", "bill", "act", "plan", "deal",
    "fund", "bank", "board", "union", "league", "alliance", "coalition",
    "summit", "centre", "center", "association", "society", "federation",
    "holdings", "limited", "africa's", "sofa", "cash-in",
    # Named for a metro, a street and an airport, not a candidate.
    "mandela", "tambo", "sisulu", "biko", "luthuli",
}

# A person can be the MOST-covered name in the country for reasons that make
# putting them in a fantasy cabinet grotesque - they are on trial, they are a
# victim, they died this week. Coverage volume cannot tell those apart from
# competence, so any story carrying these words disqualifies the names in it
# from THAT story's count. It is a blunt instrument on purpose: a false
# exclusion costs one name, a false inclusion costs the page.
DISQUALIFYING_CONTEXT = re.compile(
    r"\b(murder|murdered|killed|dead|death|died|funeral|rape|raped|assault|"
    r"abuse|abused|kidnap|hijack|shot|shooting|stabbed|arrest|arrested|"
    r"convicted|sentenced|guilty|fraud|corruption|looting|bail|"
    r"court appearance|charged|charges|trial|accused|victim|missing|"
    r"crash|collision|tragedy|hospitalised|hospitalized|ill|cancer)\b",
    re.IGNORECASE,
)

# Two capitalised words in a row, allowing Mc/O'/hyphenated surnames. Cheap,
# and good enough on headline text, which is almost entirely names and nouns.
NAME_RE = re.compile(
    r"\b([A-Z][a-z]{2,}(?:['-][A-Z][a-z]+)?)\s+([A-Z][a-z]{2,}(?:['-][A-Z][a-z]+)?)\b"
)

# Single well-known surnames carry a story on their own in SA headlines
# ("Malema agrees to apologise"), and a bigram-only reader misses every one.
SOLO_SURNAME_RE = re.compile(
    r"\b(Ramaphosa|Malema|Zuma|Mbeki|Mashatile|Steenhuisen|Mkhwanazi|"
    r"Motsoaledi|Godongwana|Lesufi|Ntshavheni|Mchunu|McKenzie|Zille|"
    r"Ngobese-Zuma|Maimane|Holomisa|Shivambu|Ndlozi|Gordhan)\b"
)


def _candidates(headline: str) -> set:
    """People plausibly named in one headline."""
    if DISQUALIFYING_CONTEXT.search(headline):
        return set()

    found = set()
    for first, second in NAME_RE.findall(headline):
        if first.lower() in NOT_A_PERSON or second.lower() in NOT_A_PERSON:
            continue
        # A repeated word is a place or a scandal, never a person: Phala Phala,
        # Baden Baden. Cheaper than listing every one of them.
        if first.lower() == second.lower():
            continue
        found.add(f"{first} {second}")
    for solo in SOLO_SURNAME_RE.findall(headline):
        # Drop the bare surname when the full name is already present, so
        # "Julius Malema" and "Malema" are not counted as two people.
        if not any(solo in f for f in found):
            found.add(solo)
    return found


def rank_people(stories: list[dict], min_stories: int = 1) -> list[dict]:
    """Who the country is actually talking about, by how widely it is carried.

    Weighted by OUTLET count rather than story count: five papers on one story
    is a bigger presence than one paper writing five times, and the second is
    what a single busy desk looks like.
    """
    tally: dict[str, dict] = {}
    for s in stories:
        text = " ".join([s.get("headline", "")] + list(s.get("also", []) or []))
        weight = max(1, s.get("outlet_count", 1))
        for name in _candidates(text):
            slot = tally.setdefault(name, {"name": name, "score": 0,
                                           "stories": 0, "headlines": []})
            slot["score"] += weight
            slot["stories"] += 1
            if s.get("headline"):
                slot["headlines"].append(s["headline"])

    people = [p for p in tally.values() if p["stories"] >= min_stories]
    people.sort(key=lambda p: (-p["score"], -p["stories"], p["name"]))
    return people


def build_prompt_block(people: list[dict], seats: int = 4) -> str:
    """The instruction block for a 'dream team' post, or '' if too few names."""
    if len(people) < seats:
        return ""

    roster = "\n".join(
        f"- {p['name']} (in {p['stories']} of today's stories, "
        f"weight {p['score']}) - seen in: \"{p['headlines'][0][:90]}\""
        for p in people[:seats + 3]
    )
    picks = ", ".join(f"{r} ({why})" for r, why in PORTFOLIOS[:seats])
    today = datetime.now().strftime("%d %B %Y")

    return f"""## FORMAT: IMAGINE THE TEAM ({today})

This post is an OPEN HYPOTHETICAL, not news, and must read as one from the
first second. It asks South Africans one question: if these people were put in
one team to fix the country, who takes which job?

PEOPLE IN THE NATIONAL CONVERSATION RIGHT NOW (measured from today's headlines,
not chosen by us):
{roster}

SEATS TO FILL: {picks}

HARD RULES:
1. Open by SAYING it is imagination - "Imagine for a second..." - and say so
   again on screen. The viewer must never be able to mistake this for a report.
2. Assign each seat to one person above and give ONE reason, drawn ONLY from
   what the headlines say they are already doing. No invented record.
3. NEVER invent a quote, a promise, a policy or a plan for any of them. Do not
   say what they "would" do as though it were known - say what you are asking
   the audience to consider.
4. Criticise or praise a public ROLE and a public ACTION, never a person's
   character, family, race or nationality.
5. End on the question, not the answer: ask the audience who they would swap
   out and why. The comments are the point of this format.
6. If a name above is unfamiliar, leave the seat open and ask the audience to
   fill it. An honest gap beats a confident invention."""


async def get_dream_team_block(seats: int = 4) -> str:
    """Fetch today's names and return the ready-to-inject prompt block."""
    from modules.sa_news import get_sa_briefing

    briefing = await get_sa_briefing()
    people = rank_people(briefing.get("stories") or [])
    return build_prompt_block(people, seats=seats)


if __name__ == "__main__":
    async def _main():
        from modules.sa_news import get_sa_briefing
        b = await get_sa_briefing(force_refresh=True)
        people = rank_people(b.get("stories") or [])
        print("PEOPLE IN THE CONVERSATION:")
        for p in people:
            print(f"  {p['score']:>3}  {p['name']:<28} ({p['stories']} stories)")
        print()
        print(build_prompt_block(people) or "(too few names for this format today)")

    asyncio.run(_main())
