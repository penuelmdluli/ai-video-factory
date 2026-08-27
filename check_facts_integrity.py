"""
Standing self-check on what the comment engine is told.

Three bugs in a row came from the same place, and none of them were the
model's fault:

  * it thought a finished match was still to come (no clock in the pack)
  * it named a coach nobody had given it (no rule against filling gaps)
  * it said the Siwelele game had been played (the fixture was outside the
    scan window, so the only line naming Siwelele was a DIFFERENT match)

Each time the pack was wrong or incomplete and the model answered honestly
from bad evidence. Fixing the model is not the lever - checking the evidence
is. So this asserts the properties the pack must always have, and it runs on
a schedule so the next one is caught by us instead of by a supporter in the
comments.

Exit 0 = clean, 1 = something is wrong. Run: python check_facts_integrity.py
"""
import asyncio
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
SAST = timezone(timedelta(hours=2))
CLUBS = (("chiefs", "Kaizer Chiefs"), ("pirates", "Orlando Pirates"),
         ("sundowns", "Mamelodi Sundowns"))
ALERTS = Path("data/fail_alerts.json")


async def run() -> list[str]:
    from modules.psl_facts import facts_pack
    from modules.psl_fixtures import next_fixture

    pack = await facts_pack()
    bad = []

    # 1. The clock must be today. A cached pack from yesterday is how a
    #    finished match reads as tonight's game.
    now = datetime.now(SAST)
    want = now.strftime("%A %d %B %Y")
    if want not in pack:
        found = re.search(r"RIGHT NOW: ([^,]+,[^,]+)", pack)
        bad.append(f"CLOCK STALE: pack says '{found.group(1) if found else '?'}'"
                   f", today is {want}")

    # 2. Every club we post about must have its next fixture named IN FULL.
    #    This is the Siwelele bug: the match existed, we just never said it.
    for key, name in CLUBS:
        try:
            f = await next_fixture(key)
        except Exception as e:
            bad.append(f"FIXTURE LOOKUP FAILED for {name}: {e}")
            continue
        if not f:
            continue
        opp = f["away"] if f.get("home_key") == key else f["home"]
        if opp.split()[0] not in pack:
            bad.append(f"MISSING FIXTURE: {name} play {opp} "
                       f"({f.get('kickoff_iso','')[:10]}) and the opponent is "
                       f"never named in the pack")
        elif f"{f['home']} v {f['away']}" not in pack:
            bad.append(f"AMBIGUOUS FIXTURE: '{opp}' appears in the pack but "
                       f"never as '{f['home']} v {f['away']}' - the engine "
                       f"can only match it to some other match")

    # 3. No club may be described as both finished and unplayed against the
    #    same opponent.
    played = re.search(r"ALREADY PLAYED: (.+)", pack)
    coming = re.search(r"STILL TO COME: (.+)", pack)
    if played and coming:
        def pairs(txt, sep):
            out = set()
            for chunk in txt.split(";"):
                m = re.match(r"\s*(.+?)\s+" + sep + r"\s+(.+?)\s*\(", chunk)
                if m:
                    a = re.sub(r"\s+\d+-\d+$", "", m.group(1)).strip()
                    out.add((a, m.group(2).strip()))
            return out
        clash = pairs(played.group(1), r"\d+-\d+") & pairs(coming.group(1), "v")
        for a, b in clash:
            bad.append(f"CONTRADICTION: {a} v {b} is listed as both FINISHED "
                       f"and NOT PLAYED YET")

    # 4. The rules that stop the model inventing must still be present.
    for rule, why in (("NAME RULE", "stops invented coach names"),
                      ("TENSE RULE", "stops previewing finished matches"),
                      ("FIXTURE IDENTITY RULE", "stops club-name collisions")):
        if rule not in pack:
            bad.append(f"RULE MISSING: {rule} ({why})")
    return bad


def main():
    try:
        bad = asyncio.run(run())
    except Exception as e:
        bad = [f"CHECK ITSELF FAILED: {e}"]

    stamp = datetime.now(SAST).strftime("%Y-%m-%d %H:%M")
    if not bad:
        print(f"[FactsCheck] {stamp} - clean, pack is safe to comment from")
        return 0

    print(f"[FactsCheck] {stamp} - {len(bad)} PROBLEM(S):")
    for b in bad:
        print(f"  ! {b}")
    try:
        data = json.loads(ALERTS.read_text(encoding="utf-8")) if ALERTS.exists() else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    data.append({"at": stamp, "check": "psl_facts", "problems": bad})
    ALERTS.parent.mkdir(exist_ok=True)
    ALERTS.write_text(json.dumps(data[-60:], indent=2), encoding="utf-8")
    return 1


if __name__ == "__main__":
    sys.exit(main())
