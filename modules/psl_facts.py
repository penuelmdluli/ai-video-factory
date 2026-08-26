"""
PSL facts pack — one compact, always-current block of league truth that gets
injected into every AI-written comment and reply, so the page talks in real
numbers ("Pirates top on 10 points", "Chiefs host Gallants Wednesday 19:30")
instead of vibes.

Cached 1h in data/psl_facts.json. Never raises — returns "" on total failure.

Usage:
    from modules.psl_facts import facts_pack
    facts = await facts_pack()
"""
import json
import time
from pathlib import Path

CACHE = Path(__file__).parent.parent / "data" / "psl_facts.json"
TTL = 3600


async def facts_pack() -> str:
    try:
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        if time.time() - c.get("at", 0) < TTL:
            return c.get("text", "")
    except Exception:
        pass

    lines = [
        # A comment claimed Nabi was the Chiefs coach. He is not — the model
        # filled the gap from memory because nothing here named a coach, and
        # our feed does not publish one. Never let it guess again.
        "NAME RULE: do NOT name any coach, manager or club official unless "
        "that exact name appears in the headlines you were given. If no name "
        "is supplied, say 'the coach' or 'Chiefs' instead. Getting a coach "
        "wrong is the fastest way to lose a football audience.",
    ]
    try:
        from modules.psl_standings import get_log
        rows = await get_log(6)
        if rows:
            lines.append("LOG: " + "; ".join(
                f"{r['rank']}. {r['name']} {r['points']}pts" for r in rows[:6]))
    except Exception:
        pass
    try:
        from datetime import datetime, timedelta
        from modules.psl_fixtures import fixtures_for, SAST
        played, coming = [], []
        for d in range(-3, 6):
            day = datetime.now(SAST) + timedelta(days=d)
            try:
                for f in await fixtures_for(day):
                    if f.get("completed"):
                        played.append(f"{f['home']} {f['home_score']}-"
                                      f"{f['away_score']} {f['away']}")
                    elif f.get("status") == "pre" and d >= 0:
                        coming.append(f"{f['home']} v {f['away']} "
                                      f"({f['kickoff_sast']})")
            except Exception:
                continue
        if played:
            lines.append("RECENT RESULTS: " + "; ".join(played[-6:]))
        if coming:
            lines.append("UPCOMING: " + "; ".join(coming[:4]))
    except Exception:
        pass

    text = "\n".join(lines)
    try:
        CACHE.write_text(json.dumps({"at": time.time(), "text": text},
                                    indent=2), encoding="utf-8")
    except Exception:
        pass
    return text
