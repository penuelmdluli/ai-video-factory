"""
Matchday orchestrator — lineup and result posts for the Genesis News page.

The matchday sequence every SA football page lives on:
  1. ~kickoff-1h : PREDICTED XI  (image post; XI drawn from the LIVE current squad)
  2. kickoff     : STARTING XI   (image post; official names pasted by the operator)
  3. full-time   : RESULT CARD   (image post; score + scorers)

Every post seeds an engagement comment — first comments from the page set the
tone and lift reach.

Usage:
    # predicted XI, auto-picked from the club's CURRENT Wikipedia squad:
    python matchday.py predict --club chiefs --opponent sundowns \
        --formation 4-3-3 --kickoff "SAT 15:00" --venue "FNB Stadium" --post

    # official lineup (paste the names once the team sheet drops):
    python matchday.py lineup --club chiefs --opponent sundowns \
        --formation 4-3-3 --kickoff "TODAY 15:00" \
        --players "32 Petersen; 2 Frosler; ...11 names..." --post

    # full-time result:
    python matchday.py result --home chiefs --away sundowns --score 2-1 \
        --scorers-home "Du Preez 34', Shabalala 78'" --scorers-away "Rayners 60'" \
        --venue "FNB Stadium" --post
"""
import os
import time
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import OUTPUT_DIR
from modules.club_brand import CLUB_BRAND

NICHE = "sa_pulse"


def _out(prefix: str) -> Path:
    d = Path(OUTPUT_DIR) / "matchday"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"


def _name(club: str) -> str:
    return CLUB_BRAND.get(club, {}).get("name", club.title())


async def _post_photo(path: str, caption: str, comment: str):
    from modules.uploader_facebook import upload_photo, post_comment
    r = await upload_photo(path, caption, NICHE)
    if r.get("status") == "uploaded" and comment:
        target = r.get("photo_id") or r.get("post_id")
        await post_comment(target, comment, NICHE)
    return r


async def cmd_lineup(a, predicted: bool):
    if a.players:
        players = [p.strip() for p in a.players.split(";") if p.strip()]
    elif predicted:
        from modules.psl_squads import predict_xi2
        # matchday content must never run on a stale roster — always re-pull.
        # formation "auto" (the default) uses the club's latest REAL formation.
        want = None if a.formation in ("", "auto") else a.formation
        players, a.formation = await predict_xi2(a.club, want, force_refresh=True)
        if not players:
            raise SystemExit(f"no live squad for '{a.club}' — pass --players manually")
    else:
        raise SystemExit("official lineup needs --players (paste the team sheet)")
    if len(players) < 11:
        raise SystemExit(f"only {len(players)} players — need 11")

    # Real faces where a licensed portrait exists (cached); jersey dots otherwise.
    # OFF by default: Commons coverage for PSL players is ~1 in 20, and one lone
    # photo circle among ten dots reads as a mistake, not a design. Flip
    # PLAYER_HEADS=true in .env when the head cache has real coverage.
    heads = {}
    import os as _os
    if _os.getenv("PLAYER_HEADS", "").lower() in ("true", "1", "yes"):
        try:
            from modules.psl_squads import get_squad
            from modules.player_heads import get_head
            by_sur = {p["name"].split()[-1].lower(): p["name"]
                      for p in await get_squad(a.club)}
            for p in players:
                full = by_sur.get(p.split()[-1].lower())
                if full:
                    h = await get_head(full)
                    if h:
                        heads[p] = h
            if heads:
                print(f"[Matchday] player heads found: {len(heads)}/11")
        except Exception as e:
            print(f"[Matchday] heads skipped: {e}")

    from modules.lineup_card import make_lineup_card
    out = make_lineup_card(
        _out("predicted" if predicted else "lineup"),
        club=a.club, opponent=a.opponent, players=players,
        formation=a.formation, kickoff=a.kickoff, competition=a.competition,
        predicted=predicted, heads=heads,
    )
    if not out:
        raise SystemExit("card render failed")
    print(f"card: {out}")

    # THE LINEUP IS A VIDEO NOW (owner call 2026-08-21). The static card still
    # goes out as the image post, but the reel is the animated reveal — crests,
    # fixture line, names loading in one by one, subs, and the prediction
    # disclaimer — which is the format the page is judged on.
    try:
        import subprocess
        cmd = [sys.executable, "-X", "utf8", "build_lineup_video.py",
               "--club", a.club, "--formation", a.formation]
        if a.opponent:
            cmd += ["--opponent", a.opponent]
        if a.kickoff:
            cmd += ["--kickoff", a.kickoff]
        if a.post:
            cmd += ["--post"]
        print(f"[Matchday] building the lineup reel: {' '.join(cmd[3:])}")
        r = subprocess.run(cmd, cwd=str(Path(__file__).parent),
                           capture_output=True, text=True, timeout=1800)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-3:]
        for line in tail:
            print(f"[Lineup] {line}")
    except Exception as e:
        print(f"[Matchday] lineup reel skipped: {str(e)[:120]}")

    if a.post:
        label = "Our PREDICTED XI" if predicted else "CONFIRMED: your starting XI"
        caption = (f"{label} — {_name(a.club)} vs {_name(a.opponent)}"
                   f"{' · ' + a.kickoff if a.kickoff else ''} ⚽\n\n"
                   f"#PSL #BetwayPremiership #{_name(a.club).replace(' ', '')} "
                   f"#{_name(a.opponent).replace(' ', '')}")
        comment = ("Rate this XI out of 10 — and tell us who YOU would start instead 👇"
                   if predicted else
                   "There's the team sheet — score prediction in the comments 👇")
        await _post_photo(out, caption, comment)
    return out


async def cmd_result(a):
    from modules.result_card import make_result_card
    sh = [s.strip() for s in (a.scorers_home or "").split(",") if s.strip()]
    sa = [s.strip() for s in (a.scorers_away or "").split(",") if s.strip()]
    out = make_result_card(
        _out("result"), home=a.home, away=a.away, score=a.score,
        scorers_home=sh, scorers_away=sa,
        competition=a.competition, venue=a.venue, status=a.status,
    )
    if not out:
        raise SystemExit("card render failed")
    print(f"card: {out}")

    # THE LINEUP IS A VIDEO NOW (owner call 2026-08-21). The static card still
    # goes out as the image post, but the reel is the animated reveal — crests,
    # fixture line, names loading in one by one, subs, and the prediction
    # disclaimer — which is the format the page is judged on.
    try:
        import subprocess
        cmd = [sys.executable, "-X", "utf8", "build_lineup_video.py",
               "--club", a.club, "--formation", a.formation]
        if a.opponent:
            cmd += ["--opponent", a.opponent]
        if a.kickoff:
            cmd += ["--kickoff", a.kickoff]
        if a.post:
            cmd += ["--post"]
        print(f"[Matchday] building the lineup reel: {' '.join(cmd[3:])}")
        r = subprocess.run(cmd, cwd=str(Path(__file__).parent),
                           capture_output=True, text=True, timeout=1800)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-3:]
        for line in tail:
            print(f"[Lineup] {line}")
    except Exception as e:
        print(f"[Matchday] lineup reel skipped: {str(e)[:120]}")

    if a.post:
        caption = (f"{a.status}: {_name(a.home)} {a.score} {_name(a.away)}"
                   f"{' · ' + a.venue if a.venue else ''} ⚽\n\n"
                   f"#PSL #BetwayPremiership #{_name(a.home).replace(' ', '')} "
                   f"#{_name(a.away).replace(' ', '')}")
        comment = "Player of the match? Drop your pick below 👇"
        await _post_photo(out, caption, comment)
    return out


async def _goal_reel_post(f, ev, scorer_club: str, hs: int, as_: int):
    """Broadcast-grade animated Goal Reel posted minutes after a real goal
    (big-three fixtures). Teammate names come from REAL recent starters."""
    try:
        from modules.motion_kit import goal_reel
        from modules.psl_squads import recent_starts, get_squad
        from modules.uploader_facebook import upload_to_facebook, post_comment

        sur = (ev["who"] or "").strip()
        assist = (ev.get("assist") or "").strip()
        how = ev.get("how", "solo")
        starts, _ = await recent_starts(scorer_club)
        squad = await get_squad(scorer_club)
        num = next((p["no"] for p in squad
                    if p["name"].split()[-1].lower() == sur.lower()), "")
        mates = [p["name"].split()[-1].upper() for p in
                 sorted(squad, key=lambda p: -starts.get(
                     p["name"].split()[-1].lower(), 0))
                 if p["name"].split()[-1].lower() not in
                 (sur.lower(), assist.lower())][:3]
        players = {"sc": {"no": num or "", "name": sur.upper()}}
        for i, (m, anchor) in enumerate(zip(mates, [(.3, .5), (.5, .62),
                                                    (.2, .3)])):
            players[f"m{i}"] = {"no": "", "name": m}

        # replay TEMPLATE matched to how the goal actually happened
        mate_pos = {"m0": (.3, .5), "m1": (.5, .62), "m2": (.2, .3)}
        if how == "penalty":
            start = {"sc": (.5, .175), **mate_pos}
            replay = {"players": players, "start": start,
                      "moves": [("sc", (.5, .14))],
                      "ball": [(1.6, (.5, .12)), (2.3, (.46, .045))],
                      "arrow": None}
            how_label = "PENALTY"
        elif how in ("corner", "cross", "header"):
            players["as"] = {"no": "", "name": assist.upper() or "DELIVERY"}
            corner = how == "corner"
            start = {"sc": (.55, .30), "as": (.95, .05) if corner
                     else (.90, .30), **mate_pos}
            replay = {"players": players, "start": start,
                      "moves": [("sc", (.52, .10))],
                      "ball": [(1.2, start["as"]), (2.6, (.6, .12)),
                               (3.4, (.5, .04))],
                      "arrow": (start["as"], (.58, .13),
                                f"{(assist or 'the delivery').upper()}")}
            how_label = how.upper()
        elif how == "free kick":
            start = {"sc": (.5, .34), **mate_pos}
            replay = {"players": players, "start": start, "moves": [],
                      "ball": [(1.4, (.5, .32)), (2.4, (.56, .045))],
                      "arrow": None}
            how_label = "FREE KICK"
        else:
            if assist:
                players["as"] = {"no": "", "name": assist.upper()}
                start = {"sc": (.72, .40), "as": (.45, .48), **mate_pos}
                replay = {"players": players, "start": start,
                          "moves": [("sc", (.55, .12))],
                          "ball": [(1.0, (.45, .48)), (2.4, (.66, .28)),
                                   (3.3, (.56, .13)), (3.9, (.5, .04))],
                          "arrow": ((.72, .40), (.57, .14),
                                    f"{sur.upper()}'S RUN")}
            else:
                start = {"sc": (.75, .45), **mate_pos}
                replay = {"players": players, "start": start,
                          "moves": [("sc", (.55, .12))],
                          "ball": [(1.0, (.5, .6)), (2.6, (.7, .3)),
                                   (3.4, (.56, .13)), (3.9, (.5, .04))],
                          "arrow": ((.75, .45), (.57, .14),
                                    f"{sur.upper()}'S RUN")}
            how_label = "THE RUN"
        if replay.get("arrow") is None:
            replay.pop("arrow", None)

        # commentary voice line — real scorer, real assist, real score
        opp = f["away_key"] if ev["side"] == "home" else f["home_key"]
        minute_said = ev["clock"].replace("'", "")
        calls = {
            "penalty": f"Goal! {sur} makes no mistake from the penalty spot "
                       f"in minute {minute_said}.",
            "corner": f"Goal! From the corner, "
                      f"{assist + ' delivers and ' if assist else ''}"
                      f"{sur} finishes in minute {minute_said}.",
            "cross": f"Goal! {assist + ' with the cross, ' if assist else ''}"
                     f"{sur} turns it in, minute {minute_said}.",
            "header": f"Goal! {sur} rises highest and heads it home in "
                      f"minute {minute_said}.",
            "free kick": f"Goal! {sur} bends in the free kick, "
                         f"minute {minute_said}.",
        }
        call = calls.get(how,
                         f"Goal! {assist + ' slips in ' + sur if assist else sur + ' finishes it himself'}"
                         f" in minute {minute_said}.")
        call += (f" {_name(f['home_key'])} {hs}, {_name(f['away_key'])} "
                 f"{as_}. Follow Genesis News for every goal.")
        audio = None
        try:
            from modules.voice_generator import generate_voice
            vwork = Path(OUTPUT_DIR) / "matchday" / "goalvoice"
            vwork.mkdir(parents=True, exist_ok=True)
            v = await generate_voice(call, vwork, "goalcall", "short", NICHE)
            audio = (v or {}).get("audio_path")
        except Exception as e:
            print(f"[Auto] goal voice skipped: {str(e)[:80]}")

        out = _out("goalreel").with_suffix(".mp4")
        goal_reel(out, club=scorer_club, scorer=sur.upper(),
                  minute=ev["clock"], score=f"{hs}-{as_}",
                  vs=_name(opp), replay=replay,
                  narration_audio=audio, stamp_dur=3.5)
        cap = (f"🚨 THE GOAL REEL — {sur.upper()} {ev['clock']}!\n"
               f"LIVE: {_name(f['home_key'])} {hs}-{as_} "
               f"{_name(f['away_key'])}\n\n#PSL #BetwayPremiership")
        fb = await upload_to_facebook(video_path=str(out), title="Goal Reel",
                                      description=cap, niche=NICHE,
                                      is_reel=True)
        tid = fb.get("video_id") or fb.get("post_id")
        if tid and fb.get("status") == "uploaded":
            await post_comment(tid, "Rate that finish out of 10 👇", NICHE)
        print("[Auto] GOAL REEL posted")
    except Exception as e:
        print(f"[Auto] goal reel skipped: {str(e)[:110]}")


async def _red_card_post(f, ev, club: str):
    """Animated red-card piece for big-three matches."""
    try:
        from modules.motion_kit import card_alert
        from modules.uploader_facebook import upload_to_facebook, post_comment
        out = _out("redcard").with_suffix(".mp4")
        card_alert(out, player=(ev["who"] or "").upper(),
                   minute=ev["clock"], red=True, club=club)
        from modules.motion_kit import attach_voice
        out = await attach_voice(
            out, f"Red card! {ev['who']} is off in minute "
                 f"{ev['clock'].replace(chr(39), '')}, and "
                 f"{_name(club)} are down to ten men.")
        cap = (f"🟥 RED CARD — {ev['who']} {ev['clock']}\n"
               f"{_name(f['home_key'])} v {_name(f['away_key'])}, down to "
               f"ten.\n\n#PSL #BetwayPremiership")
        fb = await upload_to_facebook(video_path=str(out), title="Red Card",
                                      description=cap, niche=NICHE,
                                      is_reel=True)
        tid = fb.get("video_id") or fb.get("post_id")
        if tid and fb.get("status") == "uploaded":
            await post_comment(tid, "Fair red or soft? 👇", NICHE)
        print("[Auto] RED CARD reel posted")
    except Exception as e:
        print(f"[Auto] red card reel skipped: {str(e)[:110]}")


def _match_day(f: dict) -> str:
    """A fixture's SAST match date as YYYYMMDD, for pinning ESPN's scoreboard."""
    iso = f.get("kickoff_iso") or ""
    return iso[:10].replace("-", "") if len(iso) >= 10 else ""


async def _live_details(fixture_id: str, day: str = "") -> dict:
    """Everything live from the scoreboard: scorers, red cards, per-event keys.

    `day` is the fixture's match date (YYYYMMDD). ESPN's undated scoreboard
    advances to the NEXT matchday, so relying on it can starve a match that is
    still in play of its goals, and lose the result card at full time. Asking
    for the match date pins the feed; the undated call remains a fallback for
    when the dated one does not carry the fixture.
    """
    import httpx
    SB = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/scoreboard"
    out = {"sh": [], "sa": [], "events": [], "ych": [], "yca": []}

    def _has(evs):
        return any(str(e.get("id")) == str(fixture_id) for e in evs)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            events = []
            if day:
                events = (await client.get(SB, params={"dates": day})).json().get("events", [])
            if not _has(events):
                events = (await client.get(SB)).json().get("events", [])
    except Exception:
        return out
    for e in events:
        if str(e.get("id")) != str(fixture_id):
            continue
        comp = (e.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): str(c.get("team", {}).get("id", ""))
                 for c in comp.get("competitors", [])}
        home_id = sides.get("home", "")
        seq: dict[tuple[str, str, str], int] = {}
        for det in comp.get("details", []):
            kind = det.get("type", {}).get("text", "") or ""
            is_goal = kind.lower().startswith("goal") or det.get("scoringPlay")
            is_red = "red card" in kind.lower()
            is_yellow = "yellow card" in kind.lower()
            if not (is_goal or is_red or is_yellow):
                continue
            names = [a.get("displayName", "") for a in det.get("athletesInvolved", [])]
            who = names[0].split()[-1] if names and names[0] else kind
            clock = det.get("clock", {}).get("displayValue", "")
            side = "home" if str(det.get("team", {}).get("id", "")) == home_id else "away"
            entry = f"{who} {clock}"
            # the second involved athlete on a goal is the ASSIST; the play
            # text tells us HOW (penalty/corner/cross/header/free kick)
            assist = names[1].split()[-1] if len(names) > 1 and names[1] else ""
            how_txt = (det.get("text") or kind).lower()
            how = ("penalty" if "penalt" in how_txt else
                   "own goal" if "own goal" in how_txt else
                   "corner" if "corner" in how_txt else
                   "free kick" if "free kick" in how_txt else
                   "header" if "header" in how_txt else
                   "cross" if "cross" in how_txt else
                   "solo")
            if is_goal:
                (out["sh"] if side == "home" else out["sa"]).append(entry)
            if is_yellow:
                (out["ych"] if side == "home" else out["yca"]).append(entry)
                continue          # yellows ride on cards, never their own post
            # Nth event of this kind by this player on this side. ESPN
            # revises the clock on a goal minutes after the fact; the ordinal
            # does not move, so a correction can no longer masquerade as a
            # second goal. A genuine brace still increments and still posts.
            ev_kind = "GOAL" if is_goal else "RED"
            seq_id = (ev_kind, side, who)
            seq[seq_id] = seq.get(seq_id, 0) + 1
            out["events"].append({
                "key": f"{ev_kind}|{side}|{who}|{seq[seq_id]}",
                "kind": "GOAL" if is_goal else "RED CARD",
                "side": side, "who": who, "clock": clock,
                "assist": assist, "how": how,
            })
        break
    return out


async def _scorers(fixture_id: str, day: str = "") -> tuple[list[str], list[str], str, str]:
    d = await _live_details(fixture_id, day)
    return d["sh"], d["sa"], "", ""


async def _post_motm(f, sh: list[str], sa: list[str], post: bool) -> bool:
    """
    Full-time MAN OF THE MATCH post — a real face on a real award.
    Pick: top scorer on the winning side (first scorer on a draw). Image:
    licensed photo of the player, else a same-day fan-shot CC still of the club
    (real match texture), else skip — never a fake face.
    """
    try:
        hs, as_ = int(f["home_score"] or 0), int(f["away_score"] or 0)
    except ValueError:
        return False
    if hs > as_:
        pool, club = sh, f["home_key"]
    elif as_ > hs:
        pool, club = sa, f["away_key"]
    else:
        pool, club = (sh or sa), (f["home_key"] if sh else f["away_key"])
    if not pool or not club:
        return False
    from collections import Counter
    surname = Counter(s.split()[0] for s in pool if s.split()).most_common(1)[0][0]

    from modules.psl_squads import get_squad
    full = next((p["name"] for p in await get_squad(club)
                 if p["name"].split()[-1].lower() == surname.lower()), surname)

    img, credit = None, ""
    try:
        from modules.free_press_images import photos_for_player, download
        hits = await photos_for_player(full, 1)
        if hits:
            img = await download(hits[0], Path("output/matchday") / f"motm_{surname}.jpg")
            credit = hits[0]["credit"]
    except Exception:
        pass
    if not img:
        # OWNER vault media of this club beats any CC still (photo, else the
        # sharpest clean frame of their footage)
        try:
            from modules.owner_media import owner_images, pick_owner_video
            oi = owner_images([club], limit=1)
            if oi:
                img, credit = oi[0]["path"], oi[0]["credit"]
            else:
                ov = pick_owner_video([club])
                if ov:
                    from modules.clean_frames import sharpest_frames
                    picks = sharpest_frames(
                        ov["path"], Path("output/matchday/owner_frames"), 1, 8)
                    if picks:
                        img, credit = picks[0][0], ov["credit"]
        except Exception:
            pass
    if not img:
        try:
            from modules.cc_clips import fetch_cc_clip
            from build_psl_news import _frames_from_clip
            name = _name(club)
            clip = await fetch_cc_clip(f"{name} highlights", Path("output/matchday/cc"))
            if clip:
                frames = _frames_from_clip({**clip, "club": club},
                                           Path("output/matchday"), 1)
                if frames:
                    img, credit = frames[0]["path"], frames[0]["credit"]
        except Exception:
            pass
    if not img:
        print("[Auto] MOTM skipped — no licensed image available")
        return False

    from modules.news_card import make_news_card
    out = make_news_card(
        img, _out("motm"),
        headline=f"{full} — Our Man of the Match",
        kicker="MAN OF THE MATCH", credit=credit, club=club)
    if not out:
        return False
    if post:
        caption = (f"🏆 OUR MAN OF THE MATCH: {full} — "
                   f"{_name(f['home_key'])} {f['home_score']}-{f['away_score']} "
                   f"{_name(f['away_key'])} ⚽\n\n#PSL #BetwayPremiership")
        await _post_photo(out, caption, "Agree? Or who was YOUR man of the match? 👇")
    return True


# ── SINGLE POSTER ────────────────────────────────────────────────────────
# Every goal, card and full-time on 25 Aug was posted TWICE. The cause is in
# cmd_live's own docstring: the resident watcher runs 24/7 AND the five-minute
# scheduled task calls the same cmd_auto "as a backup". It is not a backup, it
# is a second poster. Both read data/matchday_state.json at the top of the
# run, both find the event unseen, both post, and the state file — written
# once at the very END of cmd_auto — records the loser's copy last.
#
# Hence a mutex rather than more state. Whoever holds it posts; anyone else
# returns immediately and tries again on its next tick. A lock whose owner has
# died is stolen after LOCK_STALE_S so a crash can never mute the page.
_LOCK = Path("data/matchday.lock")
LOCK_STALE_S = 600


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return True          # cannot tell -> assume alive, never double-post


def _acquire() -> bool:
    try:
        _LOCK.parent.mkdir(parents=True, exist_ok=True)
        if _LOCK.exists():
            age = time.time() - _LOCK.stat().st_mtime
            try:
                owner = int((_LOCK.read_text(encoding="utf-8") or "0").split(",")[0])
            except Exception:
                owner = 0
            if owner != os.getpid() and age < LOCK_STALE_S and _pid_alive(owner):
                print(f"[Auto] another poster holds the lock (pid {owner}, "
                      f"{age:.0f}s) - skipping this tick")
                return False
            if age >= LOCK_STALE_S or not _pid_alive(owner):
                print(f"[Auto] stealing stale lock from pid {owner}")
        _LOCK.write_text(f"{os.getpid()},{time.time()}", encoding="utf-8")
        return True
    except Exception as e:
        print(f"[Auto] lock unavailable ({e}) - proceeding")
        return True


def _release():
    try:
        if _LOCK.exists() and _LOCK.read_text(encoding="utf-8").startswith(
                str(os.getpid()) + ","):
            _LOCK.unlink()
    except Exception:
        pass


async def cmd_auto(a):
    """
    Fixture-aware cadence — safe to run every hour of every day:
      · quiet day → does nothing (normal news cadence continues elsewhere)
      · pre-match (KO within 4h) → posts the PREDICTED XI once
      · full-time → posts the RESULT card once, scorers included when ESPN has them
    State in data/matchday_state.json prevents double-posting.
    """
    import json as _json
    from modules.psl_fixtures import todays_fixtures, priority, SAST, BIG_THREE
    from datetime import datetime as _dt, timedelta as _td

    if not _acquire():
        return

    state_p = Path("data/matchday_state.json")
    try:
        state = _json.loads(state_p.read_text(encoding="utf-8"))
    except Exception:
        state = {}

    # CHIEFS ONLY (owner call 2026-08-26). This used to cover every PSL
    # fixture on the reasoning that a football news page reports every score.
    # It is not a football news page, it is a Kaizer Chiefs page — and on
    # 25 Aug that reasoning filled the feed with Marumo Gallants, TS Galaxy,
    # Durban City, Chippa and Kruger United while Chiefs were not playing.
    fixtures = [f for f in await todays_fixtures()
                if "chiefs" in (f.get("home_key"), f.get("away_key"))]
    if not fixtures:
        print("[Auto] no Kaizer Chiefs fixture today - nothing to cover")
        _release()
        return
    if not fixtures:
        print("[Auto] no qualifying fixtures today — normal cadence")
        return
    now = _dt.now(SAST)

    for f in fixtures:
        st = state.setdefault(f["id"], {})
        club = f["home_key"] if f["home_key"] in BIG_THREE else \
            (f["away_key"] if f["away_key"] in BIG_THREE else f["home_key"])
        opp = f["away_key"] if club == f["home_key"] else f["home_key"]
        label = f"{f['home']} vs {f['away']}"

        pri_ok = priority(f) >= 1 or a.all
        # 1) predicted XI, once, inside the 4h pre-match window (big-three)
        ko = _dt.fromisoformat(f["kickoff_iso"]) if f["kickoff_iso"] else None
        if (pri_ok and ko and not st.get("predicted") and f["status"] == "pre"
                and _td(0) < ko - now <= _td(hours=4)):
            print(f"[Auto] pre-match window: {label} — posting predicted XI")
            ns = argparse.Namespace(
                club=club, opponent=opp, formation="auto",
                kickoff=" · ".join(x for x in (f["kickoff_sast"], f["venue"]) if x),
                competition="Betway Premiership", players="", post=a.post)
            try:
                await cmd_lineup(ns, predicted=True)
                st["predicted"] = now.isoformat()
            except SystemExit as e:
                print(f"[Auto] predicted XI skipped: {e}")

        # 1b) PRE-MATCH HYPE, once, ~75 min out (big-three): badge-tower cover
        #     + kickoff caption — the "we are LIVE today" drumbeat
        if (pri_ok and ko and not st.get("hype") and f["status"] == "pre"
                and _td(0) < ko - now <= _td(minutes=75)):
            try:
                from modules.matchup_cover import make_matchup_cover
                hype = make_matchup_cover(
                    _out("hype"), f["home_key"], f["away_key"],
                    line=" · ".join(x for x in (f["kickoff_sast"], f["venue"]) if x))
                if hype and a.post:
                    caption = (f"🚨 KICKOFF SOON: {_name(f['home_key'])} vs "
                               f"{_name(f['away_key'])} — {f['kickoff_sast']}"
                               f"{' · ' + f['venue'] if f['venue'] else ''} ⚽\n\n"
                               f"Live goals, cards and the result — right here.\n"
                               f"#PSL #BetwayPremiership")
                    await _post_photo(hype, caption,
                                      "Final score predictions — LAST CALL 👇")
                    # ANIMATED countdown reel rides with the hype post —
                    # live ticking clock to kickoff
                    try:
                        from modules.motion_kit import countdown
                        from modules.uploader_facebook import (
                            upload_to_facebook, post_comment)
                        secs = max(60, int((ko - now).total_seconds()))
                        cd = _out("countdown").with_suffix(".mp4")
                        countdown(cd,
                                  title=f"{_name(f['home_key'])} v "
                                        f"{_name(f['away_key'])}",
                                  when=f["kickoff_sast"],
                                  clubs=(f["home_key"], f["away_key"]),
                                  start_secs=secs, duration=8.0)
                        from modules.motion_kit import attach_voice
                        cd = await attach_voice(
                            cd, f"Kickoff is coming. {_name(f['home_key'])} "
                                f"against {_name(f['away_key'])}, "
                                f"{f['kickoff_sast']}. Live goals, cards and "
                                "the result, right here on Genesis News.")
                        fb = await upload_to_facebook(
                            video_path=str(cd), title="Countdown",
                            description=caption, niche=NICHE, is_reel=True)
                        tid = fb.get("video_id") or fb.get("post_id")
                        if tid and fb.get("status") == "uploaded":
                            await post_comment(
                                tid, "Where are you watching from? 👇", NICHE)
                        print("[Auto] countdown reel posted")
                    except Exception as e:
                        print(f"[Auto] countdown skipped: {str(e)[:100]}")
                st["hype"] = now.isoformat()
                print(f"[Auto] pre-match hype posted: {label}")
            except Exception as e:
                print(f"[Auto] hype failed: {e}")

        # 2) OFFICIAL starting XI, once, as soon as the team sheet is published
        #    (ESPN summary feed carries it ~60-75 min before kickoff)
        if (pri_ok and ko and not st.get("lineup") and not f["completed"]
                and _td(hours=-1) <= ko - now <= _td(hours=2)):
            from modules.psl_fixtures import official_lineups
            sheets = await official_lineups(f["id"])
            sheet = sheets.get(club)
            if sheet:
                print(f"[Auto] official XI published: {label} — posting starting XI")
                # The CONFIRMED XI reel, not a static card. Every page in the
                # country has the same team-sheet graphic within seconds of it
                # dropping; the one thing they cannot copy is our own morning
                # call being marked against it. build_official_xi opens on that
                # verdict, reveals the real eleven, then calls the game off the
                # side that was actually picked.
                #
                # Run as a subprocess so a failed render cannot take the live
                # watcher down with it. Blocking is safe here: the sheet lands
                # ~75 minutes before kickoff, so there is no live match to miss.
                import subprocess as _sp
                cmd = [sys.executable, "-X", "utf8",
                       str(Path(__file__).parent / "build_official_xi.py"),
                       "--club", club]
                if a.post:
                    cmd.append("--post")
                rc = _sp.run(cmd, cwd=str(Path(__file__).parent)).returncode
                if rc == 0:
                    st["lineup"] = now.isoformat()
                    print("[Auto] confirmed XI reel posted")
                elif rc == 2:
                    print("[Auto] team sheet not published yet — will retry")
                else:
                    print(f"[Auto] confirmed XI reel failed (rc={rc}) — "
                          f"not recorded, next tick retries")

        # 2a-ii) LONG-FORM PREVIEW. Owner call 2026-08-26: "we need to always
        # post the long". Hung off this watcher rather than a new scheduled
        # task — the watcher already runs every five minutes and already knows
        # when it is matchday, and a new task would need admin.
        #
        # It waits for the predicted XI to exist for this fixture, because the
        # long-form follows that side rather than picking its own; running it
        # first would put a different eleven on YouTube from the one on the
        # page.
        if (pri_ok and ko and not st.get("longform") and not f["completed"]
                and _td(hours=0) <= ko - now <= _td(hours=14)):
            try:
                _pp = Path(__file__).parent / "data" / "xi_predictions.json"
                _have = (_json.loads(_pp.read_text(encoding="utf-8"))
                         .get(str(f["id"]))) if _pp.exists() else None
            except Exception:
                _have = None
            if _have:
                import subprocess as _sp2
                cmd = [sys.executable, "-X", "utf8",
                       str(Path(__file__).parent / "build_longform_preview.py"),
                       "--club", club]
                if a.post:
                    cmd.append("--post")
                rc = _sp2.run(cmd, cwd=str(Path(__file__).parent)).returncode
                if rc == 0:
                    st["longform"] = now.isoformat()
                    print("[Auto] long-form preview posted")
                else:
                    print(f"[Auto] long-form rc={rc} — not recorded, will retry")
            else:
                print("[Auto] long-form waiting on the predicted XI")

        # 2b) LIVE updates — a card for every new goal / red card while in play
        if f["status"] == "in" and f["home_key"] and f["away_key"]:
            live = await _live_details(f["id"], _match_day(f))
            # score derived from the SAME payload as the events — the fixtures
            # snapshot lags a fresh goal ("GOAL by Xulu" on a 0-0 card)
            hs = max(int(f["home_score"] or 0), len(live["sh"]))
            as_ = max(int(f["away_score"] or 0), len(live["sa"]))
            seen = set(st.get("events", []))
            fresh = [ev for ev in live["events"] if ev["key"] not in seen]
            for ev in fresh[:3]:
                scorer_club = f["home_key"] if ev["side"] == "home" else f["away_key"]
                status = (f"GOAL {ev['clock']}" if ev["kind"] == "GOAL"
                          else f"RED CARD {ev['clock']}")
                from modules.result_card import make_result_card
                card = make_result_card(
                    _out("live"), home=f["home_key"], away=f["away_key"],
                    score=f"{hs}-{as_}",
                    scorers_home=live["sh"], scorers_away=live["sa"],
                    cards_home=live.get("ych"), cards_away=live.get("yca"),
                    competition="Betway Premiership", venue=f["venue"],
                    status=status)
                if card and a.post:
                    emoji = "⚽" if ev["kind"] == "GOAL" else "🟥"
                    caption = (f"{emoji} {ev['kind']}! {_name(scorer_club)} — "
                               f"{ev['who']} {ev['clock']}\n\n"
                               f"LIVE: {_name(f['home_key'])} {hs}-{as_} "
                               f"{_name(f['away_key'])}\n"
                               f"#PSL #BetwayPremiership")
                    await _post_photo(card, caption,
                                      "What a moment! Your reaction? 👇" if ev["kind"] == "GOAL"
                                      else "Does this change the game? 👇")
                    # ANIMATED follow-up for big-three drama: the Goal Reel /
                    # red-card motion piece, minutes after the real moment
                    # A goal earns the animated follow-up. A red card does
                    # not — owner call 2026-08-26: the card post says it in
                    # full, and a second piece of media for a sending-off is
                    # two posts about the same moment.
                    from modules.psl_fixtures import priority as _prio
                    if _prio(f) >= 1 and ev["kind"] == "GOAL":
                        await _goal_reel_post(f, ev, scorer_club, hs, as_)
                print(f"[Auto] live event posted: {ev['key']}")
                seen.add(ev["key"])
                # Persist immediately. The state file used to be written once,
                # at the very end of the run, so anything that interrupted a
                # tick mid-way re-posted every event it had already sent.
                st["events"] = sorted(seen)
                try:
                    state_p.parent.mkdir(parents=True, exist_ok=True)
                    state_p.write_text(_json.dumps(state, indent=2),
                                       encoding="utf-8")
                except Exception as e:
                    print(f"[Auto] state save failed: {str(e)[:80]}")
            st["events"] = sorted(seen)

        # 3) result card, once, after full-time
        if f["completed"] and not st.get("result") and f["home_key"] and f["away_key"]:
            print(f"[Auto] full-time: {label} {f['home_score']}-{f['away_score']}")
            sh, sa, *_ = await _scorers(f["id"], _match_day(f))
            ns = argparse.Namespace(
                home=f["home_key"], away=f["away_key"],
                score=f"{f['home_score']}-{f['away_score']}",
                scorers_home=", ".join(sh), scorers_away=", ".join(sa),
                competition="Betway Premiership", venue=f["venue"],
                status="FULL-TIME", post=a.post)
            await cmd_result(ns)
            st["result"] = now.isoformat()
            try:
                from modules.call_tracker import settle_calls
                settle_calls(f["home_key"], f["away_key"],
                             int(f["home_score"] or 0), int(f["away_score"] or 0),
                             sh + sa)
            except Exception as e:
                print(f"[Calls] settle failed: {e}")
            # follow the score card with the MOTM face — the post-match pair
            if pri_ok and not st.get("motm"):
                try:
                    if await _post_motm(f, sh, sa, a.post):
                        st["motm"] = now.isoformat()
                except Exception as e:
                    print(f"[Auto] MOTM failed: {e}")

    state_p.parent.mkdir(parents=True, exist_ok=True)
    state_p.write_text(_json.dumps(state, indent=2), encoding="utf-8")
    _release()
    print("[Auto] done")


async def cmd_live(a):
    """
    Resident live watcher — the speed layer. Polls every 45s while any PSL
    game is IN PLAY (goals/cards/FT post within a minute of the feed), sleeps
    5 min otherwise. Run 24/7 under PM2; the 5-min scheduled task stays as a
    backup for when this process is down.
    """
    from modules.psl_fixtures import todays_fixtures

    # REAP OLDER SELVES. pm2 restart spawns a new watcher but does not always
    # kill the old one: on 26 Aug a process from 07:39 was still alive at
    # 19:18 alongside the 09:23 one, won the mutex, and posted the CONFIRMED
    # XI using code from before the verdict reel existed. The mutex did its
    # job — only one poster acted — but the one that acted was running stale
    # logic, which is a failure the mutex alone can never catch.
    try:
        import psutil
        me = os.getpid()
        for proc in psutil.process_iter(["pid", "cmdline", "create_time"]):
            try:
                cl = " ".join(proc.info.get("cmdline") or [])
                if (proc.info["pid"] != me and "matchday.py" in cl
                        and " live" in f" {cl}"):
                    print(f"[Live] killing older watcher pid {proc.info['pid']}")
                    proc.kill()
            except Exception:
                continue
    except Exception as e:
        print(f"[Live] could not reap older watchers: {str(e)[:90]}")

    print("[Live] resident watcher started")
    while True:
        try:
            live_now = any(f["status"] == "in" for f in await todays_fixtures())
            await cmd_auto(a)
        except Exception as e:
            print(f"[Live] tick failed: {e}")
            live_now = False
        await asyncio.sleep(45 if live_now else 300)


def main():
    ap = argparse.ArgumentParser(description="Genesis News matchday posts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("predict", "lineup"):
        s = sub.add_parser(name)
        s.add_argument("--club", required=True, help="club key, e.g. chiefs")
        s.add_argument("--opponent", default="", help="opponent key")
        s.add_argument("--formation", default="auto",
                       help='"auto" = the club\'s latest real formation')
        s.add_argument("--kickoff", default="", help='e.g. "SAT 15:00"')
        s.add_argument("--competition", default="Betway Premiership")
        s.add_argument("--players", default="",
                       help='semicolon-separated, GK first: "32 Petersen; 2 Frosler; ..."')
        s.add_argument("--post", action="store_true")

    r = sub.add_parser("result")
    r.add_argument("--home", required=True)
    r.add_argument("--away", required=True)
    r.add_argument("--score", required=True, help='e.g. 2-1')
    r.add_argument("--scorers-home", default="", help='comma-separated: "Du Preez 34\', ..."')
    r.add_argument("--scorers-away", default="")
    r.add_argument("--competition", default="Betway Premiership")
    r.add_argument("--venue", default="")
    r.add_argument("--status", default="FULL-TIME")
    r.add_argument("--post", action="store_true")

    au = sub.add_parser("auto", help="fixture-aware: predicted XI pre-match, result at FT")
    au.add_argument("--post", action="store_true")
    au.add_argument("--all", action="store_true",
                    help="cover every PSL fixture, not just big-three games")

    lv = sub.add_parser("live", help="resident watcher: 45s polling while games are in play")
    lv.add_argument("--post", action="store_true")
    lv.add_argument("--all", action="store_true")

    a = ap.parse_args()
    if a.cmd == "predict":
        asyncio.run(cmd_lineup(a, predicted=True))
    elif a.cmd == "lineup":
        asyncio.run(cmd_lineup(a, predicted=False))
    elif a.cmd == "auto":
        asyncio.run(cmd_auto(a))
    elif a.cmd == "live":
        asyncio.run(cmd_live(a))
    else:
        asyncio.run(cmd_result(a))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure('matchday', f"MATCHDAY RUN FAILED: {type(e).__name__}: {str(e)[:140]}")
        except Exception:
            pass
        raise
