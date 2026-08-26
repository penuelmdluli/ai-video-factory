"""
CONFIRMED XI — the real team sheet, with our morning call marked against it.

Owner call 2026-08-26: "we need to use this format for the future real line up
from team, we can then check and analyse and offer even a prediction based on
the line".

The team sheet drops on the ESPN summary feed 60-75 minutes before kickoff and
every page in the country has the same graphic within seconds. Reposting it is
worth nothing. What no rival can copy is the MARKING — this page called a side
eight hours earlier, so the confirmed post opens by scoring that call, then
reveals the real eleven, then reads what the selection actually tells you and
calls the game off the back of it.

Three acts, same engine as the predicted reel:
  1  WE CALLED IT   — our XI, ticked and crossed, ending on a score
  2  CONFIRMED XI   — the real eleven revealed, live loaders on the rest
  3  SHAPE + CALL   — the real formation moving, then our prediction

    python build_official_xi.py --club chiefs
    python build_official_xi.py --club chiefs --post
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "sa_pulse"


def _log(m):
    print(f"[Official] {m}", flush=True)


def match_call(club_name: str, xi: list[str], formation: str,
               opp_name: str, home: bool) -> list[str]:
    """The prediction the owner asked for — read off the side that was picked.

    Deliberately reasoned from the team sheet rather than pulled out of the
    air: how many are committed forward, and whether the shape defends with a
    back three or a back four. A called score with no reasoning under it is
    the kind of thing a fan calls out, and rightly.
    """
    parts = [int(x) for x in str(formation).split("-") if x.strip().isdigit()]
    fwd = parts[-1] if parts else 2
    back = parts[0] if parts else 4
    lines = [f"So what does that tell us?"]
    if fwd >= 3:
        lines.append(f"Three forwards. {club_name} are going for this one.")
    elif fwd <= 1:
        lines.append("One up top. This is a side set up to stay in the game "
                     "first.")
    else:
        lines.append("Two up top, with the shape to get bodies around them.")
    if back >= 5:
        lines.append("A back five means the wing-backs decide how far up the "
                     "pitch this is played.")
    elif back <= 3:
        lines.append("A back three is a bet on winning the ball high.")
    goals = "2-1" if fwd >= 3 else ("1-0" if fwd <= 1 else "2-0")
    where = "at home" if home else "away"
    lines.append(f"Our call, {where} to {opp_name}: {club_name} "
                 f"{goals}.")
    lines.append("Tell us your score in the comments.")
    return lines


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--fixture", default="", help="ESPN event id (else today's)")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_official_xi.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    from modules.psl_fixtures import next_fixture, official_lineups
    from modules.club_brand import CLUB_BRAND, official_badge

    fx = await next_fixture(a.club)
    if not fx:
        _log("no upcoming fixture")
        return 1
    fid = a.fixture or str(fx.get("id", ""))

    sheets = await official_lineups(fid)
    sheet = sheets.get(a.club)
    if not sheet or len(sheet.get("players") or []) < 11:
        _log("team sheet not published yet — nothing to confirm. "
             "This is expected until ~75 minutes before kickoff.")
        return 2

    confirmed = sheet["players"][:11]
    real_formation = sheet.get("formation") or "4-3-3"
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
    home = fx["home_key"] == a.club
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_name = CLUB_BRAND.get(opp_key, {}).get("name",
                                               opp_key.replace("_", " ").title())
    _log(f"confirmed XI ({real_formation}): {', '.join(confirmed)}")

    # our morning call, if there was one for THIS fixture
    store = {}
    try:
        pp = ROOT / "data" / "xi_predictions.json"
        store = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
    except Exception:
        store = {}
    pred = store.get(fid) or {}
    predicted = pred.get("xi") or []

    from modules.xi_verdict import compare, verdict_lines
    v = compare(predicted, confirmed) if predicted else None
    if v:
        _log(f"our call scored {v['score']} — missed {v['missed']}, "
             f"surprises {v['surprises']}")
    else:
        _log("no stored prediction for this fixture — opening on the XI itself")

    from PIL import Image
    crest = None
    bp = official_badge(a.club)
    if bp:
        crest = Image.open(bp).convert("RGBA")

    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"officialxi_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    kickoff = " · ".join(x for x in (fx.get("kickoff_sast", ""),
                                     fx.get("venue", "")) if x)

    # Reuse the whole reel engine — only act one differs.
    from build_lineup_video import build_frames, render_video, _reveal_ticks
    from modules.lineup_card import make_lineup_card as _mk
    from modules.club_brand import CLUB_BRAND as _CB
    accent = tuple(_CB.get(a.club, {}).get("colors", {})
                   .get("primary", (255, 193, 7)))

    cards = build_frames(work, a.club, opp_key, real_formation, confirmed,
                         kickoff, bench=[], predicted=False)
    if not cards:
        _log("no cards rendered — aborting")
        return 1

    lines = [f"The team sheet is in."]
    if v:
        lines += verdict_lines(club_name, v, pred.get("formation", ""),
                               real_formation)
    lines += [f"Here is the confirmed {club_name} eleven.",
              f"The shape is {real_formation.replace('-', ' ')}."]
    lines += match_call(club_name, confirmed, real_formation, opp_name, home)
    narration = " ".join(lines)
    total = max(16.0, len(narration) / 15.0 + 5.0)
    _log(f"narration: {len(narration)} chars — {total:.1f}s")

    intro_fn = None
    if v:
        from modules.verdict_card import build_ctx as vctx, frame as vfr
        from PIL import Image as _I
        _size = _I.open(cards[0]).size
        _c = vctx(predicted, v, _size, accent, crest=crest)
        intro_fn = lambda t, dur, _x=_c: vfr(t, dur, _x)

    bg = work / "pitch_bg.png"
    _mk(bg, club=a.club, players=[""] * len(confirmed), opponent=opp_key,
        formation=real_formation, kickoff=kickoff,
        competition="Betway Premiership", predicted=False, pending=False)

    silent = work / "official_silent.mp4"
    render_video(cards, silent, total=total, formation=real_formation,
                 players=confirmed, bg=bg, bench=False, accent=accent,
                 crest=crest, intro_fn=intro_fn, predicted=False)

    from modules.motion_kit import attach_voice
    voiced = await attach_voice(silent, narration, work / "voiced.mp4")

    reveal_t = total * 0.62
    times = [reveal_t * (i + 1) / max(1, len(cards)) for i in range(len(cards))]
    tw = _reveal_ticks(work / "ticks.wav", times, total)
    final = Path(voiced)
    if tw and Path(tw).exists():
        try:
            from moviepy import (VideoFileClip, AudioFileClip,
                                 CompositeAudioClip)
            vv = VideoFileClip(str(voiced))
            tt = AudioFileClip(str(tw))
            if tt.duration > vv.duration:
                tt = tt.subclipped(0, vv.duration)
            mixed = work / "ticked.mp4"
            vv.with_audio(CompositeAudioClip([vv.audio, tt])).write_videofile(
                str(mixed), codec="libx264", audio_codec="aac", logger=None)
            vv.close(); tt.close()
            final = mixed
        except Exception as e:
            _log(f"tick mix skipped: {str(e)[:100]}")

    from modules.music_bed import add_bed
    final = add_bed(final, work / "final.mp4", NICHE, total, log=_log)

    cover = work / "cover.jpg"
    Image.open(cards[-1]).convert("RGB").save(cover, quality=94)

    title = f"CONFIRMED XI — {club_name} {'vs' if home else 'away to'} {opp_name}"
    vline = (f"We called {v['score']} of it this morning.{chr(10)}" if v else "")
    caption = (f"✅ CONFIRMED — the official {club_name} starting eleven "
               f"{'vs' if home else 'away to'} {opp_name}. "
               f"{real_formation}.{chr(10)}{chr(10)}{vline}"
               f"Happy with this side? Tell us below 👇{chr(10)}{chr(10)}"
               f"#KaizerChiefs #Amakhosi #PSL #BetwayPremiership #TeamNews")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover),
         "title": title, "description": caption, "xi": confirmed,
         "formation": real_formation,
         "verdict": v, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title, caption, cover, niche=NICHE,
                          tags=["KaizerChiefs", "Amakhosi", "PSL", "TeamNews",
                                "BetwayPremiership"])
        _log(f"published: { {k: (val or {}).get('status') for k, val in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
