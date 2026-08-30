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

# A result claim belongs to the clause that carries it, not to the whole
# comment. The original Siwelele bug was the ENGINE saying a fixture had been
# played when it had not; the pack was given a FIXTURE IDENTITY RULE on
# 2026-08-27 and the engine now gets it right. This detector was never taught
# the same rule, so it still reads a comment the way the broken engine wrote
# one - "does the text mention the next opponent anywhere, and does it contain
# result language anywhere" - with nothing tying the two together.
#
# That misfired on 2026-08-29: "Richards Bay already wrapped on Wednesday - we
# drew 2-2, so now we're looking ahead to Siwelele next Sunday" is entirely
# correct, and the pack agrees (Richards Bay 2-2 Chiefs FINISHED Wed 26 Aug;
# Chiefs v Siwelele NOT PLAYED YET Sun 06 Sep). "we drew" is about Richards
# Bay, 87 characters and two clauses away from the word Siwelele. The sweep
# flagged it anyway, and --delete would have removed a correct reply; it also
# cost a full unattended heal run, which is the cost this file's own header
# warns about. A detector that cannot tell a corrected comment from the bug it
# was written to catch will keep deleting the fix.
#
# So claims are matched per clause. Splitting is deliberately conservative -
# sentence ends, dashes and a comma FOLLOWED BY a conjunction, never a bare
# comma - because "the Siwelele game, which was on Sunday, already happened"
# is one claim and must stay one clause.
CLAUSE_SPLIT = re.compile(
    r"[.!?;\n]+|\s+[—–]\s*|\s+-\s+|"
    r",\s+(?:so|but|and|then|now|while|whereas)\b")

# Language that marks a fixture as still to come. Present in the same clause
# as the opponent, it settles the tense on its own.
FORWARD_LOOK = re.compile(
    r"look(ing)? ahead|coming up|next up|still to come|upcoming|ahead of|"
    r"preview|kicks? off|will (play|face|meet)|due to (play|face)|"
    r"next (match|game|fixture|week|sunday|monday|tuesday|wednesday|"
    r"thursday|friday|saturday)", re.I)


def _clauses(text):
    """Split a comment into the units a single claim can live in."""
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c and c.strip()]


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
        probs = _claims_against(c, upcoming)
        if probs:
            flags[c["id"]] = probs
    return flags


def _claims_against(c, upcoming) -> list:
    """Problems in one comment, given the fixtures still to be played.

    Pure and offline so --selftest can prove both halves of the fix: that the
    2026-08-29 false positive stays quiet, and that the claims this detector
    exists to catch still fire. Neutering the detector would fix the symptom
    and lose the reason the file was written.
    """
    age = _age_days(c["created"])
    probs = []
    for clause in _clauses(c["message"].lower()):
        for word, f in upcoming.items():
            # The opponent must be named in the SAME clause as the claim.
            if word not in clause:
                continue
            label = f["home"] + " v " + f["away"]
            if FINISHED_CLAIM.search(clause) and not FORWARD_LOOK.search(clause):
                p = ("says the " + label + " match is finished, but it is "
                     "not played until " + (f.get("kickoff_iso") or "?")[:10])
                if p not in probs:
                    probs.append(p)
            if TONIGHT.search(clause) and age is not None and age >= 1:
                try:
                    ko = datetime.fromisoformat(f["kickoff_iso"])
                    if ko.date() != datetime.now(SAST).date():
                        p = ("says 'tonight' but " + label + " is "
                             + ko.strftime("%a %d %b"))
                        if p not in probs:
                            probs.append(p)
                except Exception:
                    pass
    return probs


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


def selftest() -> int:
    """Prove the football detector on known comments. Exit 0 = correct.

    Cases 1 and 2 are the 2026-08-29 incident: a correct comment the sweep
    flagged, and the wording of the original engine bug it was written to
    catch. Both must keep their verdicts - a change that silences case 1 by
    also silencing case 2 has deleted the detector, not fixed it.
    """
    now = datetime.now(SAST)
    ko = now + timedelta(days=7)
    upcoming = {"siwelele": {"home": "Kaizer Chiefs", "away": "Siwelele",
                             "home_key": "chiefs",
                             "kickoff_iso": ko.isoformat()}}
    old = (now - timedelta(days=2)).isoformat()

    cases = [
        # (should_flag, created, message)
        (False, old, "Hey Phili! That match against Richards Bay already "
                     "wrapped on Wednesday — we drew 2-2, so now we're "
                     "looking ahead to Siwelele next Sunday. Who'd you have "
                     "in that lineup if you were calling it?"),
        (True, old, "The Siwelele game already happened, we drew 2-2."),
        (True, old, "We beat Siwelele 3-0 at the weekend, brilliant stuff."),
        (True, old, "The Siwelele game, which was on Sunday, already played."),
        (True, old, "Big one against Siwelele tonight, Khosi nation!"),
        (False, old, "Looking ahead to Siwelele next Sunday."),
        (False, old, "We drew with Richards Bay on Wednesday, tough point."),
        (False, old, "Siwelele up next — who starts?"),
    ]

    bad = 0
    for want, created, msg in cases:
        got = _claims_against({"id": "t", "message": msg, "created": created},
                              upcoming)
        ok = bool(got) == want
        bad += 0 if ok else 1
        print(("  ok  " if ok else "  FAIL") + "  expected "
              + ("FLAG " if want else "clean") + " -> "
              + ("FLAG" if got else "clean") + "   " + msg[:64])
        if got and not want:
            for p in got:
                print("          spurious: " + p)
        if want and not got:
            print("          missed a claim this detector exists to catch")
    print(("\nSELFTEST PASS" if not bad else "\nSELFTEST FAIL - "
           + str(bad) + " case(s)") + " (" + str(len(cases)) + " checked)")
    return 1 if bad else 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche", default="")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--posts", type=int, default=30)
    ap.add_argument("--selftest", action="store_true",
                    help="check the football detector offline, post nothing")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

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
