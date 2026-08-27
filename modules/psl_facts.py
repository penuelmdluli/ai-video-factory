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
TTL = 600      # match state goes stale fast on a matchday


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
        now = datetime.now(SAST)

        # THE CLOCK. Without this the model had no idea what "today" was, so
        # it wrote about finished matches as if they were about to kick off.
        lines.insert(0, "RIGHT NOW: " + now.strftime("%A %d %B %Y, %H:%M")
                     + " South African time.")

        played, coming, live = [], [], []
        for d in range(-6, 22):
            day = now + timedelta(days=d)
            try:
                fixtures = await fixtures_for(day)
            except Exception:
                continue
            for f in fixtures:
                when = day.strftime("%a %d %b")
                score = f"{f.get('home_score')}-{f.get('away_score')}"
                status = str(f.get("status", "")).lower()
                if f.get("completed"):
                    rel = "TODAY" if d == 0 else ("YESTERDAY" if d == -1
                                                  else when)
                    played.append(f"{f['home']} {score} {f['away']} "
                                  f"(FINISHED, {rel})")
                elif status in ("in", "live", "inprogress"):
                    live.append(f"{f['home']} {score} {f['away']} "
                                "(BEING PLAYED RIGHT NOW)")
                elif d >= 0:
                    ko = f.get("kickoff_iso") or ""
                    rel = "TODAY" if d == 0 else ("TOMORROW" if d == 1
                                                  else when)
                    try:
                        kt = datetime.fromisoformat(ko)
                        if kt <= now:
                            continue
                        coming.append(f"{f['home']} v {f['away']} "
                                      f"(NOT PLAYED YET, {rel} "
                                      f"{kt.strftime('%H:%M')})")
                    except ValueError:
                        coming.append(f"{f['home']} v {f['away']} "
                                      f"(NOT PLAYED YET, {rel})")
        if live:
            lines.append("IN PLAY: " + "; ".join(live))
        if played:
            lines.append("ALREADY PLAYED: " + "; ".join(played[-6:]))
        if coming:
            lines.append("STILL TO COME: " + "; ".join(coming[:6]))

        # THE CLUBS WE ACTUALLY POST ABOUT, always, whatever the window.
        #
        # 2026-08-27: a comment said the Siwelele game had already been
        # played. It had not - Chiefs v Siwelele is 5 September. But the
        # fixture was 9 days out, the scan stopped at 8, and the upcoming
        # list was cut to 4, so that match appeared NOWHERE in this pack.
        # The only line naming Siwelele was "Siwelele 1-1 Chippa United
        # (FINISHED)" - a different match, against a different opponent.
        # The model was not guessing; it answered from the only evidence we
        # gave it. A pack that omits the fixture we are posting about is not
        # merely incomplete, it is actively misleading, so these lines are
        # pinned in and never truncated.
        nxt = []
        try:
            from modules.psl_fixtures import next_fixture
            for ck, cname in (("chiefs", "Kaizer Chiefs"),
                              ("pirates", "Orlando Pirates"),
                              ("sundowns", "Mamelodi Sundowns")):
                try:
                    f = await next_fixture(ck)
                except Exception:
                    continue
                if not f:
                    continue
                try:
                    kt = datetime.fromisoformat(f.get("kickoff_iso") or "")
                    days = (kt.date() - now.date()).days
                    when = ("TODAY" if days == 0 else
                            "TOMORROW" if days == 1 else
                            f"{kt.strftime('%a %d %b')}, {days} days from now")
                    stamp = f"{when} at {kt.strftime('%H:%M')}"
                except ValueError:
                    stamp = "date not published"
                nxt.append(f"{cname}: NEXT MATCH is {f['home']} v {f['away']}"
                           f" - NOT PLAYED YET, {stamp}")
            if nxt:
                lines.append("NEXT MATCH FOR THE CLUBS WE COVER (this "
                             "overrides anything above): " + "; ".join(nxt))
        except Exception as e:
            print(f"[Facts] next-match block skipped: {e}")

        # Silence here is the actual danger, and it is what let the Siwelele
        # bug out a second time: the block above was dead, the pack was built
        # and cached anyway, and the only Siwelele line left in it was the
        # FINISHED game against Chippa. The pack read as complete, so the
        # engine answered from it. When we cannot state a club's next match,
        # the pack must SAY it cannot rather than quietly leaving the fixture
        # out - missing evidence the model knows about is safe, missing
        # evidence it does not is how a supporter gets told a match that has
        # not kicked off was already played.
        if not nxt:
            lines.append(
                "FIXTURE DATA UNAVAILABLE: the next-match lookup failed, so "
                "this pack does NOT contain the upcoming fixture for any club "
                "we cover. Say nothing about when any club plays next or "
                "whether any fixture has been played - a club appearing in a "
                "FINISHED line above tells you nothing about its next match.")

        # A club name on its own is not a match. "Siwelele" appears in a
        # finished game against Chippa AND in an unplayed game against
        # Chiefs; treating those as the same fixture is what caused the bug.
        lines.append(
            "FIXTURE IDENTITY RULE: a match is identified by BOTH clubs, "
            "never by one club name. Seeing a club in a FINISHED line does "
            "not mean its next match has been played - the same club appears "
            "in several fixtures against different opponents. Before you say "
            "any match has been played, find the line naming BOTH clubs and "
            "read its status. If no line names both clubs, say nothing about "
            "that fixture's result.")
        lines.append(
            "TENSE RULE: a match marked FINISHED has already been played - "
            "write about it in the past tense and never preview it. Only a "
            "match marked NOT PLAYED YET may be previewed, and only say "
            "'tonight' if it is marked TODAY. Never invent a fixture that is "
            "not listed here.")
    except Exception:
        pass


    text = "\n".join(lines)
    try:
        CACHE.write_text(json.dumps({"at": time.time(), "text": text},
                                    indent=2), encoding="utf-8")
    except Exception:
        pass
    return text
