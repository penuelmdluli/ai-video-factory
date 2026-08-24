"""
Injury guard — never name a man who cannot play.

2026-08-24, from the comments on our own predicted XI:

    "Yoh fielding injured players like Frosler. You are not Chiefs supporter."

That is the comment that does real damage. A bold selection starts an argument;
naming an injured player ends the argument, because it proves the page is not
watching. The XI is built from the last real team sheet, which makes exactly
this failure likely: a man who started the previous match and has been injured
since is still, as far as the team sheet knows, a starter.

Two sources, deliberately in this order:

1. data/injury_list.json — owner-maintained, authoritative. ESPN publishes NO
   injury feed for rsa.1 (checked 2026-08-24, the endpoint returns empty), so
   there is no automatic source that can be trusted on its own.
2. The PSL news cache — a supporting sweep. It catches a well-covered absence
   but it missed Frosler entirely, so it is never the only line of defence.

Flagging is by surname, which is how team sheets and headlines both refer to
players. A false positive costs one name in an XI; a false negative costs the
page's credibility, so the guard errs toward leaving a man out.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
LIST_PATH = ROOT / "data" / "injury_list.json"
NEWS_CACHE = ROOT / "data" / "psl_news_cache.json"

INJURY_WORDS = re.compile(
    r"injur|ruled out|sidelin|out for|doubtful|surgery|hamstring|achilles|"
    r"knee|ankle|groin|strain|absence|will miss|misses out|not fit",
    re.IGNORECASE)

# Words that flip the meaning — "returns from injury" is not an injury report.
CLEARED_WORDS = re.compile(
    r"return|back in|fit again|recovered|cleared|available again|steps up",
    re.IGNORECASE)


def _load_list() -> dict:
    try:
        return json.loads(LIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def manual_out(club: str) -> dict:
    """{surname: reason} from the owner list, dropping expired entries."""
    data = _load_list().get(club, {})
    out, today = {}, datetime.now().date()
    for name, rec in (data or {}).items():
        if isinstance(rec, str):
            out[name.lower()] = rec
            continue
        until = (rec or {}).get("until", "")
        try:
            if until and datetime.fromisoformat(until).date() < today:
                continue          # recovered — entry has lapsed
        except Exception:
            pass
        out[name.lower()] = (rec or {}).get("reason", "listed as out")
    return out


def news_out(club: str, squad_surnames: list[str]) -> dict:
    """{surname: headline} for squad men named in an injury headline."""
    try:
        cache = json.loads(NEWS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    heads = []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("title") or o.get("headline") or ""
            if t:
                heads.append(str(t))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(cache.get(club, cache))
    found = {}
    for h in heads:
        if not INJURY_WORDS.search(h) or CLEARED_WORDS.search(h):
            continue
        for s in squad_surnames:
            if len(s) > 3 and re.search(rf"\b{re.escape(s)}\b", h, re.IGNORECASE):
                found.setdefault(s.lower(), h[:110])
    return found


def unavailable(club: str, squad_surnames: list[str] | None = None) -> dict:
    """{surname: reason} — everyone who should not be named in an XI."""
    out = manual_out(club)
    if squad_surnames:
        for k, v in news_out(club, squad_surnames).items():
            out.setdefault(k, f"news: {v}")
    return out


def filter_xi(club: str, xi: list[str], bench: list[str] | None = None):
    """Drop unavailable men from the XI, promoting cover from the bench.

    Returns (xi, replacements) where replacements is [(dropped, brought_in,
    reason)] so the caller can say WHY the side changed rather than quietly
    fielding a different eleven.
    """
    def surname(entry):
        parts = str(entry).split(None, 1)
        return (parts[1] if len(parts) > 1 else str(entry)).strip().lower()

    pool = [str(b) for b in (bench or []) if str(b).strip()]
    names = [surname(p) for p in list(xi) + pool]
    out_map = unavailable(club, names)
    if not out_map:
        return list(xi), []

    new_xi, swaps, used = [], [], set()
    for entry in xi:
        s = surname(entry)
        if s not in out_map:
            new_xi.append(entry)
            continue
        cover = ""
        for b in pool:
            bs = surname(b)
            if bs in out_map or bs in used:
                continue
            cover, _ = b, used.add(bs)
            break
        swaps.append((entry, cover, out_map[s]))
        if cover:
            new_xi.append(cover)
    return new_xi, swaps


if __name__ == "__main__":
    import sys
    club = sys.argv[1] if len(sys.argv) > 1 else "chiefs"
    if not LIST_PATH.exists():
        LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        LIST_PATH.write_text(json.dumps({
            "_README": ("Owner-maintained injury/suspension list. ESPN has no "
                        "injury feed for the PSL, so this file is the reliable "
                        "source. Key by SURNAME. 'until' is optional; once the "
                        "date passes the entry stops applying."),
            "_EXAMPLE": {"chiefs": {"frosler": {"reason": "injured",
                                                "until": "2026-09-30"}}},
            "chiefs": {}, "pirates": {}, "sundowns": {},
        }, indent=2), encoding="utf-8")
        print(f"created {LIST_PATH}")
    print(f"{club}: unavailable ->", unavailable(club) or "nobody listed")
