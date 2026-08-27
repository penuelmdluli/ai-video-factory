"""
The loop that runs the factory's own improvement, end to end.

Owner call 2026-08-27: "we need to create a human machine that is able to
heal, improve, adjust, analyze, end to end learn".

The pieces already existed and none of them talked to each other. Metrics were
collected but never scored; the router rotated formats it had no opinion
about; integrity checks printed to a log nobody opened; a broken build waited
for someone to notice in the morning. This is the loop that joins them:

    OBSERVE   pull real engagement for every post on every page
    ANALYSE   score each format on what this page is FOR - comments and
              shares over likes - and read what supporters keep raising
    ADJUST    write weights the slot router consults on its next run
    CHECK     verify the facts the comment engine speaks from, and our own
              published comments
    HEAL      when something is broken, hand it to Claude with the evidence
    REMEMBER  append every cycle to data/brain_history.jsonl, forever

REMEMBER is the part that makes the rest worth doing. A single reading says
lineups beat news; a year of readings says whether that held, when it changed
and what we did about it. Disk is cheap and the archive is append-only, so
nothing is ever overwritten by a later opinion.

    python brain.py                 # full cycle, heal if needed
    python brain.py --no-heal       # observe, analyse, adjust, check only
    python brain.py --report        # print what we have learned so far
"""
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
SAST = timezone(timedelta(hours=2))
HISTORY = ROOT / "data" / "brain_history.jsonl"
PAGES = ["sa_pulse", "motivation", "tech_news", "ai_money",
         "health_wellness", "blissful_moments", "limitless_you"]


def _log(m):
    print("[Brain] " + m)


def _remember(entry: dict):
    """Append-only. A later cycle never edits an earlier one."""
    HISTORY.parent.mkdir(exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def history(limit: int = 400) -> list:
    if not HISTORY.exists():
        return []
    out = []
    with HISTORY.open(encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out[-limit:]


async def observe_and_analyse() -> dict:
    from modules.format_intel import collect, scores, save_weights, fan_topics
    result = {"collected": {}, "scores": {}, "weights": {}, "topics": {}}
    for niche in PAGES:
        try:
            n = await collect(niche, 100)
        except Exception as e:
            _log(niche + ": collect failed - " + str(e))
            continue
        if not n:
            continue
        result["collected"][niche] = n
        sc = scores(niche)
        if sc:
            result["scores"][niche] = sc
            result["weights"][niche] = save_weights(niche)
        t = fan_topics(niche)
        if t:
            result["topics"][niche] = t[:10]
    return result


async def check() -> list:
    """Everything currently wrong, using the detectors we already trust."""
    try:
        from self_heal import detect_async
        return await detect_async()
    except Exception as e:
        _log("detectors unavailable: " + str(e))
        return []


def _drift(niche: str, sc: dict) -> list:
    """What changed since last time - the part a single reading cannot show."""
    prev = None
    for h in reversed(history()):
        if h.get("scores", {}).get(niche):
            prev = h["scores"][niche]
            break
    if not prev:
        return []
    notes = []
    for fmt, now in sc.items():
        was = prev.get(fmt)
        if not was or was.get("posts", 0) < 3 or now.get("posts", 0) < 3:
            continue
        a, b = was.get("avg_score", 0), now.get("avg_score", 0)
        if a > 0 and abs(b - a) / a >= 0.35:
            notes.append(f"{fmt}: {a:.0f} -> {b:.0f} "
                         + ("UP" if b > a else "DOWN"))
    return notes


async def cycle(do_heal=True) -> dict:
    started = datetime.now(SAST)
    _log(started.strftime("%Y-%m-%d %H:%M") + " - cycle start")

    data = await observe_and_analyse()
    for niche, sc in data["scores"].items():
        best = sorted(sc.items(), key=lambda kv: -kv[1]["avg_score"])[:3]
        _log(niche + ": " + ", ".join(
            f"{f}={a['avg_score']:.0f}({a['posts']}p)" for f, a in best))
        for d in _drift(niche, sc):
            _log("  DRIFT " + d)

    problems = await check()
    if problems:
        _log(str(len(problems)) + " problem(s): "
             + ", ".join(p["name"] for p in problems))
    else:
        _log("nothing broken")

    healed = None
    if problems and do_heal:
        # self_heal owns the caps, the lock and the branch. Calling it as a
        # process rather than importing heal() keeps that policy in one place.
        try:
            r = subprocess.run([sys.executable, "-X", "utf8",
                                str(ROOT / "self_heal.py")],
                               cwd=str(ROOT), capture_output=True, text=True,
                               timeout=2000)
            healed = (r.stdout or "")[-1500:]
            _log("heal run finished (exit " + str(r.returncode) + ")")
        except Exception as e:
            healed = "heal failed: " + str(e)
            _log(healed)

    entry = {
        "at": started.isoformat(),
        "collected": data["collected"],
        "scores": data["scores"],
        "weights": data["weights"],
        "topics": data["topics"],
        "problems": [{"name": p["name"], "severity": p["severity"]}
                     for p in problems],
        "healed": healed,
        "minutes": round((datetime.now(SAST) - started).total_seconds() / 60, 1),
    }
    _remember(entry)
    _log("cycle done in " + str(entry["minutes"]) + "m, remembered")
    return entry


def report():
    h = history()
    if not h:
        print("No cycles recorded yet. Run: python brain.py")
        return
    print("CYCLES RECORDED: " + str(len(h))
          + "   first: " + h[0]["at"][:16] + "   last: " + h[-1]["at"][:16])
    last = h[-1]
    for niche, sc in (last.get("scores") or {}).items():
        print("\n" + niche)
        for fmt, a in sorted(sc.items(), key=lambda kv: -kv[1]["avg_score"]):
            trust = "" if a["posts"] >= 3 else "   (too few posts to trust)"
            print(f"   {fmt:12} avg {a['avg_score']:8.1f}  over {a['posts']:3} posts"
                  f"  [{a['comments']} comments, {a['shares']} shares]{trust}")
        w = (last.get("weights") or {}).get(niche) or {}
        if w:
            print("   weights -> " + ", ".join(
                f"{k}={v}" for k, v in sorted(w.items(), key=lambda kv: -kv[1])))
        t = (last.get("topics") or {}).get(niche) or []
        if t:
            print("   fans keep saying: " + ", ".join(x for x, _ in t[:8]))
    probs = [p for e in h for p in (e.get("problems") or [])]
    if probs:
        tally = {}
        for p in probs:
            tally[p["name"]] = tally.get(p["name"], 0) + 1
        print("\nPROBLEMS SEEN ACROSS ALL CYCLES: " + ", ".join(
            f"{k} x{v}" for k, v in sorted(tally.items(), key=lambda kv: -kv[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-heal", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
        return 0
    asyncio.run(cycle(do_heal=not a.no_heal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
