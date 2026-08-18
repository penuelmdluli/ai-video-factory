"""
Story-type routing for Genesis News reels.

Every news reel used to open the same way — two static photo cards — whether
the story was a transfer, an injury, a quote or a league table move. Same
look, every time, which is what made the page feel repetitive even when the
stories were different.

This reads the headline and picks the motion template that actually fits, so
a transfer opens with the crest-to-crest move, a quote opens with kinetic
type, an injury opens with the card alert. The brand stays identical — same
colours, type and motion feel — only the template changes.

    kind, params = classify(title, extra_text)
    clip = render_intro(kind, params, out_path, duration)  # None if no fit
"""
import re
from pathlib import Path

from modules.club_brand import resolve_club, resolve_clubs

# Ordered — first match wins, so the most specific patterns sit at the top.
PATTERNS = [
    ("transfer", re.compile(
        r"\b(sign(s|ed|ing)?|transfer|move to|joins?|exit|departure|leaves?|"
        r"loan|deal|unveil|snap up|swoop|contract terminated|sold)\b", re.I)),
    ("quote", re.compile(r"[\"“']([^\"”']{12,})[\"”']|\bsays?\b|\bwarns?\b|"
                         r"\btells?\b|\binsists?\b|\bslams?\b", re.I)),
    ("injury", re.compile(
        r"\b(injur\w+|out for|sidelined|ruled out|fitness|recovery|"
        r"return(s|ing)? from|doubtful|strain|knock)\b", re.I)),
    ("discipline", re.compile(r"\b(red card|sent off|yellow card|suspend\w+|"
                              r"ban(ned)?|dismissal)\b", re.I)),
    ("table", re.compile(r"\b(log|table|standings?|top of|climb\w*|drop\w* to|"
                         r"points? (gap|clear)|title race)\b", re.I)),
    ("preview", re.compile(r"\b(preview|face|host|travel to|clash|kick[- ]?off|"
                           r"ahead of|next (match|game)|derby|fixture)\b", re.I)),
    ("player", re.compile(r"\b(form|star|hero|breakout|debut|rated|"
                          r"performance|impress\w+)\b", re.I)),
]

# Which templates we are willing to open a NEWS reel with. Result/goal reels
# are built by the matchday pipeline from real event data, never guessed here.
SUPPORTED = {"transfer", "quote", "injury", "discipline", "table", "preview",
             "player"}


def classify(title: str, extra: str = "") -> tuple[str, dict]:
    """Return (kind, params) for a headline. kind is '' when nothing fits."""
    text = f"{title} {extra}".strip()
    clubs = resolve_clubs(text) or []
    params = {"clubs": clubs, "title": title,
              "club": clubs[0] if clubs else "chiefs"}
    for kind, rx in PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        if kind == "quote":
            q = re.search(r"[\"“']([^\"”']{12,120})[\"”']", text)
            if q:
                params["quote"] = q.group(1).strip()
            else:
                # 'Da Cruz says X' — take what follows the verb as the line
                after = re.split(r"\bsays?\b|\bwarns?\b|\btells?\b|"
                                 r"\binsists?\b", text, maxsplit=1, flags=re.I)
                if len(after) < 2 or len(after[1].strip()) < 12:
                    continue
                params["quote"] = after[1].strip(" :—-")[:110]
            params["author"] = _speaker(text)
        if kind == "transfer":
            params["player"] = _person(title)
            params["from_club"] = clubs[0] if clubs else "chiefs"
            params["to_club"] = clubs[1] if len(clubs) > 1 else ""
        if kind in ("injury", "discipline", "player"):
            params["player"] = _person(title)
        return kind, params
    return "", params


_STOP_NAME = {
    "Kaizer", "Chiefs", "Orlando", "Pirates", "Mamelodi", "Sundowns",
    "Amakhosi", "Buccaneers", "Masandawana", "Betway", "Premiership",
    "PSL", "The", "What", "Why", "How", "After", "Before", "This", "New",
}


def _person(text: str) -> str:
    """Best guess at the person a headline is about.

    Handles the three things that broke it: possessives ("Maseko's"), club
    names being read as people ("Chippa"), and only catching a first name
    when the headline gives both ("Feisal Salum").
    """
    # Headlines are title case, so "longest run of capitalised words" grabs
    # whole phrases ("Maseko Copenhagen Exit"). Take the first real name
    # instead, and carry a following word only when the first is a particle
    # so "Da Cruz" survives.
    particles = {"DA", "DE", "VAN", "DI", "LE", "MC", "MAC", "O", "DOS", "DU"}
    toks = [re.sub(r"[’']s$", "", t.strip(".,:;!?()\"“”'"))
            for t in (text or "").split()]
    for i, w in enumerate(toks):
        if not w or not w[0].isupper() or w in _STOP_NAME or resolve_club(w):
            continue
        if w.upper() in particles and i + 1 < len(toks):
            nxt = toks[i + 1]
            if nxt and nxt[0].isupper():
                return f"{w} {nxt}".upper()
        return w.upper()
    return ""


def _speaker(text: str) -> str:
    head = re.split(r"\bsays?\b|\bwarns?\b|\btells?\b|\binsists?\b", text,
                    maxsplit=1, flags=re.I)[0]
    return _person(head).title() or "Genesis News"


def _log_rows(top: int = 16) -> list:
    """Live league table. Empty list rather than stale or invented numbers."""
    import asyncio
    from modules.psl_standings import get_log
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(get_log(top=top)) or []
        return []          # already inside a loop — caller renders without it
    except Exception as e:
        print(f"[StoryRouter] log unavailable: {e}")
        return []


def _league_stats(club_a: str, club_b: str):
    """Head-to-head bars built from the REAL league table.

    The template ships with placeholder stats ("CLEAN SHEETS 5 v 4"). Those
    are invented numbers and must never reach a post, so this returns the
    actual table figures or nothing at all.
    """
    rows = _log_rows()
    if not rows:
        return None
    by_key = {r.get("team_key"): r for r in rows}
    a, b = by_key.get(club_a), by_key.get(club_b)
    if not (a and b):
        return None
    # Every bar must be higher-is-better: the template gives the longer bar
    # and the star to the bigger number. League position is lower-is-better,
    # so showing it as a bar would say 2nd beats 1st.
    def ppg(r):
        return round(r["points"] / r["played"], 1) if r.get("played") else 0
    return (
        ("POINTS", a["points"], b["points"]),
        ("POINTS PER GAME", ppg(a), ppg(b)),
        ("MATCHES PLAYED", a["played"], b["played"]),
    )


def render_intro(kind: str, params: dict, out_path, duration: float = 6.5):
    """Render the matching template. Returns a path, or None if none fits."""
    if kind not in SUPPORTED:
        return None
    out = Path(out_path)
    club = params.get("club") or "chiefs"
    try:
        from modules import motion_kit as mk
        if kind == "transfer":
            to_club = params.get("to_club") or ""
            if not (params.get("player") and to_club):
                return None
            return mk.transfer_move(out, player=params["player"],
                                    from_club=params.get("from_club", club),
                                    to_club=to_club, fee="REPORTED",
                                    duration=duration)
        if kind == "quote":
            if not params.get("quote"):
                return None
            return mk.quote_kinetic(out, quote=params["quote"].upper(),
                                    author=params.get("author", ""),
                                    club=club, duration=duration)
        if kind == "discipline":
            return mk.card_alert(out, player=params.get("player") or "PLAYER",
                                 minute="", red=True, club=club,
                                 duration=min(duration, 5.0))
        if kind in ("injury", "player"):
            # player_spotlight's default stats are placeholders ("CLEAN
            # SHEETS 9/12"). Rendering them would publish invented numbers,
            # so this template only runs on real stats — which we do not have
            # per player yet. Until then the reel opens normally.
            return None
        if kind == "preview":
            clubs = params.get("clubs") or []
            if len(clubs) < 2:
                return None
            stats = _league_stats(clubs[0], clubs[1])
            if not stats:
                return None      # never fall back to the placeholder numbers
            return mk.head_to_head(
                out, a=(clubs[0].upper(), clubs[0]),
                b=(clubs[1].upper(), clubs[1]), stats=stats,
                duration=duration)
        if kind == "table":
            from modules.log_race import render_log_race
            rows = _log_rows()
            if not rows:
                return None
            return render_log_race(rows, {}, str(out))
    except Exception as e:
        print(f"[StoryRouter] {kind} intro failed: {e}")
    return None
