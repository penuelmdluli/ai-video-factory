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

    if a.post:
        caption = (f"{a.status}: {_name(a.home)} {a.score} {_name(a.away)}"
                   f"{' · ' + a.venue if a.venue else ''} ⚽\n\n"
                   f"#PSL #BetwayPremiership #{_name(a.home).replace(' ', '')} "
                   f"#{_name(a.away).replace(' ', '')}")
        comment = "Player of the match? Drop your pick below 👇"
        await _post_photo(out, caption, comment)
    return out


async def _live_details(fixture_id: str) -> dict:
    """Everything live from the scoreboard: scorers, red cards, per-event keys."""
    import httpx
    out = {"sh": [], "sa": [], "events": [], "ych": [], "yca": []}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/scoreboard")
            events = r.json().get("events", [])
    except Exception:
        return out
    for e in events:
        if str(e.get("id")) != str(fixture_id):
            continue
        comp = (e.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): str(c.get("team", {}).get("id", ""))
                 for c in comp.get("competitors", [])}
        home_id = sides.get("home", "")
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
            if is_goal:
                (out["sh"] if side == "home" else out["sa"]).append(entry)
            if is_yellow:
                (out["ych"] if side == "home" else out["yca"]).append(entry)
                continue          # yellows ride on cards, never their own post
            out["events"].append({
                "key": f"{'GOAL' if is_goal else 'RED'}|{side}|{who}|{clock}",
                "kind": "GOAL" if is_goal else "RED CARD",
                "side": side, "who": who, "clock": clock,
            })
        break
    return out


async def _scorers(fixture_id: str) -> tuple[list[str], list[str], str, str]:
    d = await _live_details(fixture_id)
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

    state_p = Path("data/matchday_state.json")
    try:
        state = _json.loads(state_p.read_text(encoding="utf-8"))
    except Exception:
        state = {}

    # ALL PSL fixtures get live goals + results (a football news page reports
    # every score); predicted XI / team sheets / MOTM stay big-three unless --all.
    fixtures = await todays_fixtures()
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

        # 2) OFFICIAL starting XI, once, as soon as the team sheet is published
        #    (ESPN summary feed carries it ~60-75 min before kickoff)
        if (pri_ok and ko and not st.get("lineup") and not f["completed"]
                and _td(hours=-1) <= ko - now <= _td(hours=2)):
            from modules.psl_fixtures import official_lineups
            sheets = await official_lineups(f["id"])
            sheet = sheets.get(club)
            if sheet:
                print(f"[Auto] official XI published: {label} — posting starting XI")
                ns = argparse.Namespace(
                    club=club, opponent=opp, formation=sheet["formation"],
                    kickoff=" · ".join(x for x in (f["kickoff_sast"], f["venue"]) if x),
                    competition="Betway Premiership",
                    players="; ".join(sheet["players"]), post=a.post)
                try:
                    await cmd_lineup(ns, predicted=False)
                    st["lineup"] = now.isoformat()
                except SystemExit as e:
                    print(f"[Auto] official XI skipped: {e}")

        # 2b) LIVE updates — a card for every new goal / red card while in play
        if f["status"] == "in" and f["home_key"] and f["away_key"]:
            live = await _live_details(f["id"])
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
                print(f"[Auto] live event posted: {ev['key']}")
                seen.add(ev["key"])
            st["events"] = sorted(seen)

        # 3) result card, once, after full-time
        if f["completed"] and not st.get("result") and f["home_key"] and f["away_key"]:
            print(f"[Auto] full-time: {label} {f['home_score']}-{f['away_score']}")
            sh, sa, *_ = await _scorers(f["id"])
            ns = argparse.Namespace(
                home=f["home_key"], away=f["away_key"],
                score=f"{f['home_score']}-{f['away_score']}",
                scorers_home=", ".join(sh), scorers_away=", ".join(sa),
                competition="Betway Premiership", venue=f["venue"],
                status="FULL-TIME", post=a.post)
            await cmd_result(ns)
            st["result"] = now.isoformat()
            # follow the score card with the MOTM face — the post-match pair
            if pri_ok and not st.get("motm"):
                try:
                    if await _post_motm(f, sh, sa, a.post):
                        st["motm"] = now.isoformat()
                except Exception as e:
                    print(f"[Auto] MOTM failed: {e}")

    state_p.parent.mkdir(parents=True, exist_ok=True)
    state_p.write_text(_json.dumps(state, indent=2), encoding="utf-8")
    print("[Auto] done")


async def cmd_live(a):
    """
    Resident live watcher — the speed layer. Polls every 45s while any PSL
    game is IN PLAY (goals/cards/FT post within a minute of the feed), sleeps
    5 min otherwise. Run 24/7 under PM2; the 5-min scheduled task stays as a
    backup for when this process is down.
    """
    from modules.psl_fixtures import todays_fixtures
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
    main()
