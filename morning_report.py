"""
What the factory did while nobody was watching.

Owner call 2026-08-27: "let it run tonight and show me the report tomorrow."

Built to be read cold, over coffee, without opening a single log. It reports
from EVIDENCE rather than from anything the system says about itself: posts
are counted off the pages' own timelines, the heal is judged by whether the
integrity check passes now, and formats are scored on engagement we pulled
back. A run that claims success and a run that produced a post are different
things, and last night proved it - the healer reported a launch and had
actually failed in zero seconds.

Anything that went wrong is printed FIRST and in full. A report you have to
scroll to find the bad news in is a report that hides it.

    python morning_report.py              # since 18:00 yesterday
    python morning_report.py --hours 24
"""
import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
SAST = timezone(timedelta(hours=2))
PAGES = {"sa_pulse": "Genesis News", "motivation": "Mzansi Careers"}


def _since(hours):
    return datetime.now(SAST) - timedelta(hours=hours)


def _rule(title):
    print("\n" + title)
    print("-" * max(24, len(title)))


async def posts_made(since):
    """Counted off the page itself - the only proof a post exists."""
    import httpx
    out = {}
    async with httpx.AsyncClient(timeout=40) as cl:
        for niche, name in PAGES.items():
            pid = os.getenv("FB_PAGE_ID_" + niche, "")
            tok = (os.getenv("FB_PAGE_TOKEN_" + niche)
                   or os.getenv("FB_ACCESS_TOKEN_" + niche) or "")
            if not (pid and tok):
                continue
            try:
                r = await cl.get(
                    f"https://graph.facebook.com/v21.0/{pid}/posts",
                    params={"fields": "id,message,created_time,shares,"
                                      "comments.summary(true),"
                                      "likes.summary(true)",
                            "limit": 40, "access_token": tok})
                data = r.json().get("data", [])
            except Exception as e:
                out[name] = {"error": str(e)[:80]}
                continue
            fresh = []
            for p in data:
                try:
                    when = datetime.fromisoformat(
                        p["created_time"].replace("Z", "+00:00")).astimezone(SAST)
                except Exception:
                    continue
                if when < since:
                    continue
                fresh.append({
                    "at": when.strftime("%H:%M"),
                    "msg": (p.get("message") or "").split("\n")[0][:64],
                    "likes": ((p.get("likes") or {}).get("summary") or {})
                             .get("total_count", 0),
                    "comments": ((p.get("comments") or {}).get("summary") or {})
                                .get("total_count", 0),
                    "shares": (p.get("shares") or {}).get("count", 0)})
            out[name] = {"posts": sorted(fresh, key=lambda x: x["at"])}
    return out


def heal_runs(since):
    p = ROOT / "data" / "heal_log.json"
    if not p.exists():
        return []
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for e in rows if isinstance(rows, list) else []:
        try:
            when = datetime.strptime(e.get("at", ""), "%Y-%m-%d %H:%M").replace(
                tzinfo=SAST)
        except Exception:
            continue
        if when >= since:
            out.append(e)
    return out


def replies_sent(since):
    db = ROOT / "data" / "growth_analytics.db"
    if not db.exists():
        return {}
    try:
        c = sqlite3.connect(str(db), timeout=10)
        rows = c.execute(
            "SELECT niche, COUNT(*) FROM replied_comments "
            "WHERE replied_at >= ? GROUP BY niche",
            (since.isoformat(),)).fetchall()
        c.close()
        return dict(rows)
    except Exception:
        return {}


def brain_cycles(since):
    p = ROOT / "data" / "brain_history.jsonl"
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                when = datetime.fromisoformat(e["at"])
            except Exception:
                continue
            if when >= since:
                out.append(e)
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=0)
    a = ap.parse_args()

    now = datetime.now(SAST)
    if a.hours:
        since = now - timedelta(hours=a.hours)
    else:
        # default: since 18:00 yesterday, which is "overnight" in practice
        y = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0,
                                              microsecond=0)
        since = y
    print("=" * 62)
    print(f"  OVERNIGHT REPORT — {since:%a %d %b %H:%M} to {now:%a %d %b %H:%M}")
    print("=" * 62)

    # ---- PROBLEMS FIRST, always -------------------------------------
    problems = []
    try:
        from check_facts_integrity import run as facts_run
        fp = await facts_run()
        problems += [("facts pack", x) for x in fp]
    except Exception as e:
        problems.append(("facts check", f"would not run: {e}"))

    heals = heal_runs(since)
    for h in heals:
        if not h.get("ok"):
            problems.append(("self-heal",
                             f"{h.get('problem')} FAILED — "
                             f"{(h.get('summary') or '')[:120]}"))

    _rule("PROBLEMS")
    if problems:
        for src, msg in problems:
            print(f"  ! [{src}] {msg}")
    else:
        print("  none — every check passes right now")

    # ---- what actually went out -------------------------------------
    _rule("POSTS (counted on the pages themselves)")
    made = await posts_made(since)
    total = 0
    for name, info in made.items():
        if info.get("error"):
            print(f"  {name}: could not read — {info['error']}")
            continue
        ps = info["posts"]
        total += len(ps)
        print(f"  {name}: {len(ps)} post(s)")
        for p in ps:
            print(f"     {p['at']}  {p['likes']:>3}L {p['comments']:>3}C "
                  f"{p['shares']:>2}S  {p['msg']}")
    if not total:
        print("  NOTHING WAS POSTED — check the slot logs")

    # ---- the healer --------------------------------------------------
    _rule("SELF-HEAL")
    if not heals:
        print("  did not need to run — nothing was broken")
    for h in heals:
        mark = "fixed" if h.get("ok") else "FAILED"
        print(f"  {h.get('at')}  {h.get('problem')}  [{mark}] "
              f"{h.get('minutes')}m  branch {h.get('branch') or '-'}")
        for line in (h.get("summary") or "").splitlines()[:6]:
            if line.strip():
                print(f"     {line.strip()[:96]}")
        if h.get("branch"):
            print(f"     REVIEW BEFORE MERGING:  git show {h['branch']}")

    # ---- community ---------------------------------------------------
    _rule("COMMUNITY")
    reps = replies_sent(since)
    if reps:
        for n, c in reps.items():
            print(f"  {PAGES.get(n, n)}: {c} repl(y/ies) sent")
    else:
        print("  no replies sent")

    # ---- what the numbers say ----------------------------------------
    _rule("WHAT IS WORKING (30-day scores)")
    cycles = brain_cycles(since)
    scored = None
    for c in reversed(cycles):
        if (c.get("scores") or {}).get("sa_pulse"):
            scored = c["scores"]["sa_pulse"]
            break
    if not scored:
        try:
            from modules.format_intel import scores as _sc
            scored = _sc("sa_pulse")
        except Exception:
            scored = None
    if scored:
        for fmt, s in sorted(scored.items(),
                             key=lambda kv: -kv[1]["avg_score"])[:8]:
            trust = "" if s["posts"] >= 3 else "  (too few to trust)"
            print(f"  {fmt:11} {s['avg_score']:8.1f}  over {s['posts']:3} "
                  f"posts{trust}")
    else:
        print("  no scores yet")

    print("\n" + "=" * 62)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
