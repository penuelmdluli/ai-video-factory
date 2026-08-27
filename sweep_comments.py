"""
Sweep our OWN comments across every page for claims that have gone bad.

A page's replies age differently to its posts. A post is written once and sits
there; a reply says "tonight", "closes Friday", "still open" - and those go
stale on their own, without anyone touching them. The Siwelele reply was wrong
the moment it was written, but a reply saying "applications close Friday" was
RIGHT when we wrote it and is wrong now. Both mislead a supporter reading it
today, so both belong in the same sweep.

This checks our own comments only. Fans' comments are never touched: they are
allowed to be wrong, we are not.

Detectors are per page, because the failure modes differ:
  football  - a match called finished, or called "tonight", when the real
              fixture list says otherwise
  careers   - deadline language old enough that the job has likely closed
  all pages - links that no longer resolve

Report only by default. --delete removes what it finds, backing every comment
up to data/deleted_comments.json first.

    python sweep_comments.py                    # all pages, report only
    python sweep_comments.py --niche motivation
    python sweep_comments.py --delete
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
SAST = timezone(timedelta(hours=2))
GRAPH = "https://graph.facebook.com/v21.0"
BACKUP = Path("data/deleted_comments.json")

PAGES = ["sa_pulse", "motivation", "tech_news", "ai_money",
         "health_wellness", "blissful_moments", "limitless_you"]
NAMES = {"sa_pulse": "Genesis News", "motivation": "Mzansi Careers",
         "tech_news": "Tech Pulse Africa", "ai_money": "Smart Money AI",
         "health_wellness": "Herbal Organic Life",
         "blissful_moments": "Blissful Moments",
         "limitless_you": "Limitless You"}

FINISHED_CLAIM = re.compile(
    r"already (happened|played)|was played|couple days back|"
    r"past the teamsheet|final score|we (beat|lost to|drew)", re.I)
TONIGHT = re.compile(r"\btonight\b|\bthis evening\b", re.I)
DEADLINE = re.compile(r"clos(e|es|ing)|deadline|still open|apply before", re.I)
URL = re.compile(r"https?://[^\s)\]<>\"']+")


def _creds(niche):
    return (os.getenv("FB_PAGE_ID_" + niche, ""),
            os.getenv("FB_PAGE_TOKEN_" + niche)
            or os.getenv("FB_ACCESS_TOKEN_" + niche) or "")


def _age_days(created):
    try:
        when = datetime.fromisoformat(
            created.replace("Z", "+00:00")).astimezone(SAST)
        return (datetime.now(SAST) - when).days
    except Exception:
        return None


async def _own_comments(cl, pid, tok, posts=30):
    """Every comment WE posted on our recent posts."""
    out = []
    r = await cl.get(GRAPH + "/" + pid + "/posts",
                     params={"fields": "id,created_time", "limit": posts,
                             "access_token": tok})
    for p in r.json().get("data", []):
        try:
            rc = await cl.get(
                GRAPH + "/" + p["id"] + "/comments",
                params={"fields": "id,message,from,created_time",
                        "limit": 100, "filter": "stream", "access_token": tok})
            for c in rc.json().get("data", []):
                if (c.get("from") or {}).get("id") == pid and c.get("message"):
                    out.append({"id": c["id"], "message": c["message"],
                                "created": c.get("created_time", ""),
                                "post": p["id"]})
        except Exception:
            continue
    return out


async def _dead_links(cl, text):
    bad = []
    for u in URL.findall(text)[:3]:
        u = u.rstrip(".,);")
        try:
            r = await cl.get(u, follow_redirects=True, timeout=20)
            if r.status_code >= 400:
                bad.append(u + " -> HTTP " + str(r.status_code))
        except Exception as e:
            bad.append(u + " -> " + type(e).__name__)
    return bad


async def _football_flags(comments):
    """Comments whose match claims disagree with the real fixture list."""
    try:
        from modules.psl_fixtures import next_fixture
    except Exception as e:
        print("[Sweep] fixture lookup unavailable: " + str(e))
        return {}
    upcoming = {}
    for ck in ("chiefs", "pirates", "sundowns"):
        try:
            f = await next_fixture(ck)
        except Exception:
            continue
        if not f:
            continue
        opp = f["away"] if f.get("home_key") == ck else f["home"]
        upcoming[opp.split()[0].lower()] = f

    flags = {}
    for c in comments:
        m = c["message"].lower()
        age = _age_days(c["created"])
        for word, f in upcoming.items():
            if word not in m:
                continue
            label = f["home"] + " v " + f["away"]
            if FINISHED_CLAIM.search(m):
                flags.setdefault(c["id"], []).append(
                    "says the " + label + " match is finished, but it is "
                    "not played until " + (f.get("kickoff_iso") or "?")[:10])
            if TONIGHT.search(m) and age is not None and age >= 1:
                try:
                    ko = datetime.fromisoformat(f["kickoff_iso"])
                    if ko.date() != datetime.now(SAST).date():
                        flags.setdefault(c["id"], []).append(
                            "says 'tonight' but " + label + " is "
                            + ko.strftime("%a %d %b"))
                except Exception:
                    pass
    return flags


def _stale_deadline(c):
    """'closes Friday' written three weeks ago is now misleading."""
    age = _age_days(c["created"])
    if age is not None and age >= 10 and DEADLINE.search(c["message"]):
        return ("deadline language in a comment " + str(age)
                + " days old - verify the job has not closed")
    return None


async def sweep(niche, do_delete=False, posts=30):
    pid, tok = _creds(niche)
    if not (pid and tok):
        return {"niche": niche, "error": "no credentials"}

    findings = []
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as cl:
        mine = await _own_comments(cl, pid, tok, posts)
        fb = await _football_flags(mine) if niche == "sa_pulse" else {}
        for c in mine:
            probs = list(fb.get(c["id"], []))
            if niche == "motivation":
                s = _stale_deadline(c)
                if s:
                    probs.append(s)
            for d in await _dead_links(cl, c["message"]):
                probs.append("dead link: " + d)
            if probs:
                findings.append(dict(c, problems=probs))

        if do_delete and findings:
            log = (json.loads(BACKUP.read_text(encoding="utf-8"))
                   if BACKUP.exists() else [])
            for f in findings:
                log.append({"deleted_at": datetime.now(SAST).isoformat(),
                            "niche": niche,
                            "reason": "; ".join(f["problems"]),
                            "comment": f})
                try:
                    r = await cl.delete(GRAPH + "/" + f["id"],
                                        params={"access_token": tok})
                    f["deleted"] = r.status_code == 200
                except Exception as e:
                    f["deleted"] = False
                    f["error"] = str(e)
            BACKUP.parent.mkdir(exist_ok=True)
            BACKUP.write_text(json.dumps(log, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    return {"niche": niche, "checked": len(mine), "findings": findings}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche", default="")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--posts", type=int, default=30)
    a = ap.parse_args()

    total, checked = 0, 0
    for n in ([a.niche] if a.niche else PAGES):
        res = await sweep(n, a.delete, a.posts)
        name = NAMES.get(n, n)
        if res.get("error"):
            print("\n" + name.ljust(22) + " -- " + res["error"])
            continue
        fs = res["findings"]
        total += len(fs)
        checked += res["checked"]
        print("\n" + name.ljust(22) + str(res["checked"]).rjust(4)
              + " of our comments checked -> " + str(len(fs)) + " suspect")
        for f in fs:
            mark = ("DELETED" if f.get("deleted")
                    else "FAILED DELETE" if a.delete else "FOUND")
            print("   [" + mark + "] " + f["created"][:10] + "  " + f["id"])
            print("      " + f["message"][:150].replace("\n", " "))
            for p in f["problems"]:
                print("      ! " + p)

    print("\nCHECKED " + str(checked) + " of our own comments across all "
          "pages; " + str(total) + " suspect"
          + ("" if a.delete else "   (report only - rerun with --delete)"))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
