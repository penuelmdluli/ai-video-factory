"""
Slot router — decides WHICH format this posting slot should carry.

Owner call 2026-08-24: "the fans love the analysis, how do we slot this into
the schedule too?". The answer is not more scheduled tasks. Three PSL slots
already run every day, and the two posts missed on 23 and 24 August were both
caused by GPU contention — adding a fourth and fifth build would make that
worse, not better. So the existing slots stay, and the format rotates.

The rotation is driven by the fixture, not the clock, because a predicted XI is
worth most the day before a game and worthless the day after:

    kickoff within 14h   -> PREDICTED XI      (matchday morning)
    kickoff in 30h-96h   -> SELECTION DEBATE  (once per fixture, rotating group)
    otherwise            -> NEWS REEL         (the default, as before)

State in data/slot_state.json keyed by fixture id, so the same XI is never
posted three times in a day. Anything unexpected falls through to the news
reel: a slot must never go empty because the router could not make up its mind.

    python build_psl_slot.py --post
    python build_psl_slot.py --dry     # print the decision, build nothing
"""
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
STATE = ROOT / "data" / "slot_state.json"
CLUB = "chiefs"                     # the page's lead club
XI_WINDOW_H = 14                    # predicted XI inside this many hours —
                                    # tuned so it lands on MATCHDAY MORNING for a
                                    # 19:30 kickoff, which is when team news is read.
                                    # Two slots fall inside it (08:00 and 13:30), so a
                                    # single failed build still has a second chance.
DEBATE_WINDOW_H = 96                # selection debate inside this many hours
DEBATE_GROUPS = ["forwards", "midfield", "defence"]


def _log(m):
    print(f"[Slot] {m}", flush=True)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(s: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


async def decide() -> tuple[str, dict]:
    """(format, context). Never raises — falls back to the news reel."""
    try:
        from modules.psl_fixtures import next_fixture, SAST
        fx = await next_fixture(CLUB)
    except Exception as e:
        _log(f"fixture lookup failed ({str(e)[:60]}) — news reel")
        return "news", {}

    if not fx:
        _log("no upcoming fixture — news reel")
        return "news", {}

    try:
        ko = datetime.fromisoformat(fx["kickoff_iso"])
        hours = (ko - datetime.now(ko.tzinfo)).total_seconds() / 3600
    except Exception:
        _log("fixture has no usable kickoff — news reel")
        return "news", {}

    fid = str(fx.get("id", ""))
    st = _state()
    done = st.get(fid, {})
    _log(f"next fixture {fx.get('home')} v {fx.get('away')} in {hours:.1f}h")

    # The matchday XI is tracked separately from any earlier one. A predicted
    # side posted three days out is a talking point; the same side posted the
    # day before kickoff is the post people actually come back for, and one
    # must not consume the other.
    if 0 <= hours <= XI_WINDOW_H and not done.get("xi_matchday"):
        return "xi", {"fid": fid, "fx": fx, "slot": "xi_matchday"}
    if XI_WINDOW_H < hours <= DEBATE_WINDOW_H and not done.get("xi_early"):
        # only once the debate groups are spent, so the week leads with argument
        used_all = all(g in done.get("debate_groups", []) for g in DEBATE_GROUPS)
        if used_all:
            return "xi", {"fid": fid, "fx": fx, "slot": "xi_early"}
    if 0 <= hours <= DEBATE_WINDOW_H:
        used = done.get("debate_groups", [])
        nxt = next((g for g in DEBATE_GROUPS if g not in used), "")
        if nxt:
            return "debate", {"fid": fid, "fx": fx, "group": nxt}
    return "news", {"fid": fid}


def _run(cmd: list[str]) -> int:
    _log("running: " + " ".join(cmd[1:]))
    return subprocess.run([sys.executable, "-X", "utf8"] + cmd[1:], cwd=str(ROOT)).returncode


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    fmt, ctx = await decide()
    _log(f"format: {fmt.upper()}" + (f" ({ctx.get('group')})" if ctx.get("group") else ""))
    if a.dry:
        return 0

    post = ["--post"] if a.post else []
    if fmt == "xi":
        rc = _run(["py", "build_lineup_video.py", "--club", CLUB] + post)
    elif fmt == "debate":
        rc = _run(["py", "build_debate_video.py", "--club", CLUB,
                   "--group", ctx["group"]] + post)
    else:
        rc = _run(["py", "build_psl_news.py"] + post)

    # Only record success. A failed XI build must be retried at the next slot,
    # not silently marked done and skipped for the rest of the fixture week.
    if rc == 0 and a.post and ctx.get("fid") and fmt in ("xi", "debate"):
        st = _state()
        rec = st.setdefault(ctx["fid"], {})
        if fmt == "xi":
            rec[ctx.get("slot", "xi_matchday")] = datetime.now().isoformat()
        else:
            rec.setdefault("debate_groups", []).append(ctx["group"])
        _save(st)
        _log(f"recorded {fmt} for fixture {ctx['fid']}")
    elif rc != 0:
        _log(f"builder exited {rc} — nothing recorded, next slot will retry")
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
