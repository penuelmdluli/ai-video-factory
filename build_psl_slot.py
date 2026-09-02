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
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
STATE = ROOT / "data" / "slot_state.json"
ALERTS = ROOT / "data" / "fail_alerts.json"
CLUB = "chiefs"                     # the page's lead club
XI_WINDOW_H = 14                    # predicted XI inside this many hours —
                                    # tuned so it lands on MATCHDAY MORNING for a
                                    # 19:30 kickoff, which is when team news is read.
                                    # Two slots fall inside it (08:00 and 13:30), so a
                                    # single failed build still has a second chance.
DEBATE_WINDOW_H = 96                # selection debate inside this many hours
DEBATE_GROUPS = ["forwards", "midfield", "defence"]

# No format twice in one day. A week simulation on 2026-08-26 showed the
# router firing forwards, midfield AND defence debates across the three slots
# of a single Thursday — the same format three times before lunch — because
# the only thing stopping a debate was whether that GROUP had been used for
# the fixture, not whether we had already debated something today.
# The between-games rotation. news stays last on merit, not by rule - it
# measured 22 against 452 for a staged lineup over 30 days.
# WHAT ACTUALLY WORKS, and nothing else.
#
# Owner call 2026-08-28: "we already know what works - the lineups work, and
# asking the fans. Stop the signings, focus on what works best."
#
# The measured top four on this page, by likes + 3x comments + 5x shares:
#
#     2596   roll-call: crest + HOW MANY CHIEFS FANS ARE HERE
#     1583   position debate: six names, one shirt
#     1210   predicted XI on the pitch
#      935   predicted XI on the pitch
#
# Not one dream format appears. dreamsign, dreamxi and titlerace were built
# on a hunch and the hunch was wrong; they are out of the rotation. The three
# that remain all do the same thing - they hand the fan a job he wants: count
# himself in, correct our XI, or pick between men he has opinions about.
# "love" joined on 2026-09-02 (owner: "fans love to send love for the love of
# the club"). It earns its slot like everything else - format_intel gives an
# unproven format exactly 1.0, so it competes without being handed the week.
FREE_FORMATS = ("rollcall", "xi", "debate", "fancall", "love", "role",
                "sim", "news")

ONCE_PER_DAY = ("debate", "fancall", "rollcall", "xi", "love", "role", "sim")

# The last hours before kickoff belong to the confirmed XI reel, which
# matchday.py posts off the real team sheet ~75 minutes out. The same
# simulation had the router posting a selection debate at 18:00 for a 19:30
# kickoff — 15 minutes before the actual team news, arguing about who should
# start when the answer was about to be published.
QUIET_BEFORE_KO_H = 3.5

# MATCHDAY (owner call 2026-08-26): on the day Chiefs play, 100% of the page is
# the game. Not "Chiefs-weighted", not a news reel that happens to mention the
# fixture — the crest, the team sheet, the argument about who starts. The order
# is deliberate: the roll-call goes out first because it is the cheapest thing
# a fan can answer and it warms the post that follows; the XI lands mid-morning
# when team news is read; the argument runs into kickoff.
MATCHDAY_ORDER = ["hype", "xi", "debate"]


def _alert(problems: list, fmt: str = "") -> None:
    """Raise a hand where something is actually watching.

    On 2026-08-30 the router died on a missing debate group and took three
    consecutive slots with it - roughly eight hours in which the only thing
    reaching the page was the blog crosspost. Every one of those failures was
    logged correctly and none of them was SEEN: the exit code went to
    psl_news.log and psl_news.log is read after somebody notices the page has
    gone quiet, which is the expensive way round.

    This writes to the same data/fail_alerts.json the facts checker uses, in
    the same shape, because self_heal.py already sweeps that file for anything
    logged in the last 24 hours and escalates it. Reusing the channel means a
    dead slot reaches the healer without a second notification path to
    maintain - and self_heal folds several alerts into ONE finding, so a
    format failing every slot all afternoon still costs a single agent run.
    """
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        data = json.loads(ALERTS.read_text(encoding="utf-8")) if ALERTS.exists() else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    data.append({"at": stamp, "check": "psl_slot",
                 "format": fmt or "?", "problems": problems})
    try:
        ALERTS.parent.mkdir(exist_ok=True)
        ALERTS.write_text(json.dumps(data[-60:], indent=2), encoding="utf-8")
    except Exception as e:
        # An alert that cannot be written must not be the thing that kills the
        # run - the builder failure is the news here, not the bookkeeping.
        _log(f"could not write alert ({str(e)[:60]})")


def _log(m):
    print(f"[Slot] {m}", flush=True)


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _posted_today(st: dict) -> list:
    return (st.get("daily") or {}).get(_today(), [])


def _posted_on(st: dict, days_ago: int) -> list:
    from datetime import timedelta
    d = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
    return (st.get("daily") or {}).get(d, [])


def _fatigued(st: dict, fmt: str) -> bool:
    """True if this format ran on BOTH of the last two days.

    The router only ever checked today, so a format could legitimately run
    Monday, Tuesday and Wednesday and the page would look like it owns one
    idea. Two days in a row is a run; a third is a rut. Deliberately not a
    ban on the format itself - it steps aside for one day and comes back.
    """
    return fmt in _posted_on(st, 1) and fmt in _posted_on(st, 2)


def _rank_free(st: dict, options: list, day: str = "") -> list:
    """Order eligible formats by measured pull, with tired ones sent to the back.

    Learned weight decides between fresh options; fatigue only reorders, it
    never empties the list, because a slot must always have something to run.

    Ties are broken by a DATE-SEEDED shuffle, and that is what makes the page
    unpredictable. A week's simulation on 2026-08-27 ran the six formats in
    exactly the same order on all seven days: every new format sits at weight
    1.0 until it has three mature posts, so the sort was stable and simply
    returned them in list order. A regular could have set their watch by us.
    Seeding on the date keeps a day's run order fixed while it executes -
    six slots must not reshuffle between themselves - and different tomorrow.
    """
    import random as _r
    day = day or _today()
    shuffled = list(options)
    _r.Random(f"genesis-{day}").shuffle(shuffled)

    def key(f):
        try:
            from modules.format_intel import weight_for
            w = weight_for("sa_pulse", f)
        except Exception:
            w = 1.0
        # round the weight so near-equal formats tie and the shuffle decides,
        # rather than a 0.01 difference pinning the order for weeks
        return (1 if _fatigued(st, f) else 0, -round(w, 1))
    return sorted(shuffled, key=key)


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

    # CADENCE FOLLOWS THE FIXTURE, NOT THE CLOCK.
    #
    # Six slots used to run every day regardless of whether Chiefs played in
    # two days or twelve. The audit of 703 posts on 2026-08-27 says that is
    # the wrong shape:
    #
    #     26 Aug   20 posts (matchday)      3,945 engagement
    #     24 Aug   10 posts (2 days out)    3,159
    #     25 Aug   43 posts (no fixture)      298
    #
    # Volume is not the variable - proximity is. A heavy day next to a match
    # earns; the same volume in a quiet gap earns nothing and trains the
    # audience to scroll past us. So the quota tightens as the fixture
    # recedes, and the slots that would have run simply stand down.
    today_count = len(_posted_today(st))
    if hours <= 48:
        quota, why = 6, "matchday window"
    elif hours <= 96:
        quota, why = 4, "fixture is close"
    else:
        # Owner call 2026-08-28: 3 was too quiet for a nine-day gap. The
        # 25 Aug evidence is against 43 posts in a fixture-free day, not
        # against 5 — the collapse there was volume far past anything the
        # audience would absorb, and standing two slots down every quiet day
        # leaves the page silent from lunchtime onward.
        quota, why = 3, "quiet week"
    if today_count >= quota:
        _log(f"{today_count} posted today, quota {quota} ({why}) — "
             f"standing this slot down")
        return "none", {}

    # The matchday XI is tracked separately from any earlier one. A predicted
    # side posted three days out is a talking point; the same side posted the
    # day before kickoff is the post people actually come back for, and one
    # must not consume the other.
    # On matchday nothing else gets a slot. Each format is posted once, then
    # the next one takes over; if all three are spent the slot still stays on
    # the game rather than falling through to general news.
    try:
        is_matchday = ko.date() == datetime.now(ko.tzinfo).date() and hours >= -2
    except Exception:
        is_matchday = False
    if is_matchday and 0 <= hours <= QUIET_BEFORE_KO_H:
        _log(f"{hours:.1f}h to kickoff — holding the slot for the confirmed "
             f"XI reel off the real team sheet")
        return "none", {}

    if is_matchday:
        for fmt in MATCHDAY_ORDER:
            if done.get(f"md_{fmt}"):
                continue
            if fmt == "debate":
                used = done.get("debate_groups", [])
                grp = next((g for g in DEBATE_GROUPS if g not in used),
                           DEBATE_GROUPS[0])
                return "debate", {"fid": fid, "fx": fx, "group": grp,
                                  "md": "md_debate"}
            return fmt, {"fid": fid, "fx": fx, "slot": "xi_matchday",
                         "md": f"md_{fmt}"}
        # Once the crest, the team sheet and the argument are all out, a
        # fourth slot must NOT repeat the XI — the page would carry the same
        # eleven three times in a day, which is the automated look every other
        # fix today has been removing. Ask the fans about tonight instead.
        if "fancall" not in _posted_today(st):
            _log("matchday formats all posted — asking the fans rather than "
                 "posting the same eleven again")
            return "fancall", {"fid": fid, "day": _today()}
        _log("matchday formats and the fan call all posted — news reel")
        return "news", {"fid": fid}

    if 0 <= hours <= XI_WINDOW_H and not done.get("xi_matchday"):
        return "xi", {"fid": fid, "fx": fx, "slot": "xi_matchday"}
    if XI_WINDOW_H < hours <= DEBATE_WINDOW_H and not done.get("xi_early"):
        # only once the debate groups are spent, so the week leads with argument
        used_all = all(g in done.get("debate_groups", []) for g in DEBATE_GROUPS)
        if used_all:
            return "xi", {"fid": fid, "fx": fx, "slot": "xi_early"}
    today_done = _posted_today(st)
    if 0 <= hours <= DEBATE_WINDOW_H and "debate" not in today_done:
        used = done.get("debate_groups", [])
        nxt = next((g for g in DEBATE_GROUPS if g not in used), "")
        if nxt:
            return "debate", {"fid": fid, "fx": fx, "group": nxt}

    # FAN CALL. Owner call 2026-08-26: ask the supporters consistently — who
    # fills the empty shirts, who replaces him, who should start. It sits in
    # the between-games slots rather than on matchday, because matchday is
    # already full (crest, team sheet, argument) and these are the days the
    # page most needs a reason for someone to comment. The mode rotates by
    # day inside the builder, so the same question is never asked twice
    # running.
    # Where the choice is genuinely free, let the numbers pick.
    #
    # Everything above this line is fixture logic and stays fixed: on matchday
    # the team sheet outranks anything a scoreboard could tell us. But here,
    # between games, fancall and news are both eligible and the rotation used
    # to alternate them blind. Measured over 30 days on 2026-08-27, news came
    # last of every format we run, so alternating gave our weakest format an
    # equal share of the week forever. weight_for() is fed by real engagement
    # and clamped to [0.4, 2.0], so a strong format tilts the slot without
    # ever silencing the others - and an unproven format sits at exactly 1.0
    # so it can still earn its place.
    # Six formats compete for the between-games slots now, not two.
    #
    # Owner call 2026-08-27: "we need to be fully dynamic and unpredictable,
    # change our style". With two options the page had a visible rhythm a
    # regular could predict; with six, ranked by measured pull and with
    # anything that ran two days straight pushed to the back, the run order
    # stops being guessable while still favouring what works.
    free = [f for f in FREE_FORMATS if f not in today_done]
    if free:
        ranked = _rank_free(st, free)
        if len(free) > 1:
            _log("learned pick: " + ", ".join(
                f"{f}{'(tired)' if _fatigued(st, f) else ''}" for f in ranked))
        pick = ranked[0]
        if pick == "news":
            return "news", {"fid": fid}
        ctx = {"fid": fid, "day": _today()}
        if pick == "debate":
            # debate joined the free rotation on 2026-08-27, but the group it
            # argues about was only ever attached by the two fixture-window
            # branches above. Picked from the free list - which is every slot
            # once the fixture is more than DEBATE_WINDOW_H away - it reached
            # the builder with no group at all and the run died on the lookup,
            # taking the whole slot with it. Same rule as the windows: the
            # next group this fixture has not argued about; once all three are
            # spent, the one it has used least, so a long gap keeps rotating
            # instead of stalling on an empty string.
            used = done.get("debate_groups", [])
            ctx["group"] = next((g for g in DEBATE_GROUPS if g not in used),
                                min(DEBATE_GROUPS, key=used.count))
        return pick, ctx

    return "news", {"fid": fid}


def _run(cmd: list[str]) -> int:
    _log("running: " + " ".join(cmd[1:]))
    return subprocess.run([sys.executable, "-X", "utf8"] + cmd[1:], cwd=str(ROOT)).returncode


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    try:
        return await _slot(a)
    except Exception:
        # decide() promises never to raise and the dispatch below was assumed
        # safe, so nothing caught a crash between them - the run simply ended
        # with a traceback and the slot stood empty. --dry is exempt: it is
        # how this router gets probed by hand, and a probe must not wake the
        # healer.
        if not a.dry:
            _alert(["SLOT CRASHED - no post went out",
                    traceback.format_exc().strip().splitlines()[-1]],
                   fmt="router")
            _log("slot crashed - alert written for the self-heal sweep")
        raise


async def _slot(a):
    fmt, ctx = await decide()
    _log(f"format: {fmt.upper()}" + (f" ({ctx.get('group')})" if ctx.get("group") else ""))
    if a.dry:
        return 0

    if fmt == "none":
        return 0

    post = ["--post"] if a.post else []
    if fmt == "hype":
        rc = _run(["py", "build_matchday_hype.py", "--club", CLUB] + post)
    elif fmt == "xi":
        # A NEW SHAPE AND A NEW CALL EVERY TIME.
        #
        # The XI is built from the last real team sheet, so left alone it
        # produces nearly the same side on every card - and the format only
        # works because supporters want to correct it. There is nothing to
        # correct in an eleven they argued about on Tuesday. lineup_variety
        # hands out a formation and a bench player who did not start, and
        # never repeats a pairing until it has used them all.
        shape, calls = "4-3-3", []
        try:
            from modules.lineup_variety import pick as _variety
            shape, calls = asyncio.run(_variety(CLUB))
            _log(f"variety: {shape}" + (f" + {calls[0]} starts" if calls
                                        else " (shape only)"))
        except Exception as e:
            _log(f"variety unavailable ({str(e)[:60]}) — default shape")
        args = ["py", "build_lineup_video.py", "--club", CLUB,
                "--formation", shape]
        if calls:
            args += ["--start", ",".join(calls)]
        rc = _run(args + post)
    elif fmt == "fancall":
        # ANSWER THE LAST ONE FIRST.
        #
        # Every gaps caption promises "we will read the most-backed eleven back
        # to you before kickoff" and nothing ever did - a promise made on every
        # one of these posts and kept none of them. The verdict runs BEFORE the
        # next question so the page never asks a second time while the first is
        # still unanswered, which is the version supporters would notice.
        #
        # It refuses on its own when there is no open ask or too few voters, so
        # a non-zero exit here is normal and must not block the new question.
        try:
            vrc = _run(["py", "build_gaps_verdict.py", "--club", CLUB] + post)
            _log("gaps verdict posted" if vrc == 0 else
                 "no gaps verdict due (no open ask, or too few voters)")
        except Exception as e:
            _log(f"gaps verdict skipped: {str(e)[:80]}")
        rc = _run(["py", "build_fill_the_gaps.py", "--club", CLUB, "--video"]
                  + post)
    elif fmt == "sim":
        # THE SIMULATION: Chiefs play the upcoming fixture before it happens -
        # three goals, a scoreline, crowd and crests from the first frame. It
        # needs a fixture to simulate and exits non-zero without one, which is
        # correct and not a failure; the slot falls through to another format
        # on the next run rather than posting a match against nobody.
        rc = _run(["py", "build_match_sim.py", "--club", CLUB,
                   "--goals", "3"] + post)
        if rc != 0:
            _log("simulation skipped (no upcoming fixture?) - trying the role reel")
            rc = _run(["py", "build_role_analysis.py", "--club", CLUB,
                       "--players", "2"] + post)
    elif fmt == "role":
        # THE ROLE: teach a position, then name the Chiefs man who plays it.
        # Two players per edition by default - different roles, so the viewer
        # sees how the jobs connect rather than the same lesson twice - and the
        # shape comes from lineup_variety, so the board is not the same
        # formation every week. build_role_analysis rotates the subjects itself
        # on a least-analysed-first ledger.
        rc = _run(["py", "build_role_analysis.py", "--club", CLUB,
                   "--players", "2"] + post)
    elif fmt == "love":
        # WALL FIRST, then the next question - the same order as fancall, and
        # for the same reason: the card promises "the best go on a card with
        # your name on it", so the page must never ask a second time while the
        # first answer is still owed. The wall exits non-zero when there is no
        # open ask or too few supporters, which is normal and must not stop the
        # new question going out.
        try:
            wrc = _run(["py", "build_love_post.py", "--club", CLUB, "--wall"]
                       + post)
            _log("love wall posted" if wrc == 0 else
                 "no love wall due (no open ask, or too few supporters)")
        except Exception as e:
            _log(f"love wall skipped: {str(e)[:80]}")
        rc = _run(["py", "build_love_post.py", "--club", CLUB, "--ask"] + post)
    elif fmt == "debate":
        # The reveal treatment replaced the flat card sequence: same six names,
        # staged one at a time behind a loader, which is what the lineup format
        # was already doing when it outscored everything else 20 to 1.
        rc = _run(["py", "build_reveal_reel.py", "--club", CLUB,
                   "--group", ctx["group"]] + post)
        if rc != 0:
            _log("reveal build failed - falling back to the card debate")
            rc = _run(["py", "build_debate_video.py", "--club", CLUB,
                       "--group", ctx["group"]] + post)
    elif fmt == "rollcall":
        # The single best-performing post this page has ever made.
        rc = _run(["py", "build_matchday_hype.py", "--club", CLUB,
                   "--force"] + post)
    else:
        rc = _run(["py", "build_psl_news.py"] + post)

    # Only record success. A failed XI build must be retried at the next slot,
    # not silently marked done and skipped for the rest of the fixture week.
    if rc == 0 and a.post and fmt in ONCE_PER_DAY:
        st = _state()
        st.setdefault("daily", {}).setdefault(_today(), [])
        if fmt not in st["daily"][_today()]:
            st["daily"][_today()].append(fmt)
        # keep the ledger small — nothing older than a fortnight matters
        for k in sorted(st["daily"])[:-14]:
            st["daily"].pop(k, None)
        _save(st)
        _log(f"recorded {fmt} for {_today()}")

    if rc == 0 and a.post and ctx.get("fid") and fmt in ("hype", "xi", "debate"):
        st = _state()
        rec = st.setdefault(ctx["fid"], {})
        if ctx.get("md"):
            rec[ctx["md"]] = datetime.now().isoformat()
        if fmt == "hype":
            pass
        elif fmt == "xi":
            rec[ctx.get("slot", "xi_matchday")] = datetime.now().isoformat()
        else:
            rec.setdefault("debate_groups", []).append(ctx["group"])
        _save(st)
        _log(f"recorded {fmt} for fixture {ctx['fid']}")
    elif rc != 0:
        _log(f"builder exited {rc} — nothing recorded, next slot will retry")
        # Only on a posting run. A build started by hand that fails is a
        # person watching a terminal; a posting slot that fails is a hole in
        # the page nobody is looking at.
        if a.post:
            _alert([f"{fmt} builder exited {rc} - the slot posted nothing; "
                    f"see logs/psl_news.log for the builder output"], fmt=fmt)
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
