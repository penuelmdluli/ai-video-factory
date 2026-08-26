"""
Line-up video + analysis — the format the audience actually asks for.

Owner call 2026-08-24: "make a line up video and also lineup analysis, with top
class graphics". The graphics already existed — modules/lineup_card.py renders a
broadcast-grade XI on a pitch with real crests — but nothing in the pipeline
ever called it. This wires it into a posted video.

Why it is built from graphics and not faces: no Kaizer Chiefs player has a
freely-licensed photograph on Wikimedia Commons (checked 2026-08-24, 0 of 39).
PSL photography belongs to BackpagePix and Getty. A pitch graphic carrying real
names, real numbers and the real crest is both legal and, at feed size, clearer
than a face.

    python build_lineup_video.py --club chiefs --opponent sundowns
    python build_lineup_video.py --club chiefs --post
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
_CALLW = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}
NICHE = "sa_pulse"
W, H = 1080, 1920

FORMATIONS = {"4-3-3": [1, 4, 3, 3], "4-2-3-1": [1, 4, 2, 3, 1],
              "3-5-2": [1, 3, 5, 2], "4-4-2": [1, 4, 4, 2]}


def _log(m):
    print(f"[Lineup] {m}", flush=True)


async def pick_xi_real(club: str) -> tuple[list[str], str, str, list[str]]:
    """(XI, formation, provenance) from the club's most recent REAL team sheet.

    Squad-list order is not a team. Basing the side on who actually started
    last time is the only version a fan cannot call invented — and it is what
    put Phili, Monyane, Mmodi, Moloisane and Mthethwa back in the XI after the
    first cut dropped all five despite every one of them having started.
    """
    from modules.psl_fixtures import last_lineup
    sheet = await last_lineup(club)
    if sheet:
        # Provenance used to read "last XI v Mamelodi Sundowns (23 Aug)" and
        # went out in both the narration and the caption. On a Kaizer Chiefs
        # page there is no reason to put a rival's name in our own team-news
        # post — it hands them the mention and it tells the viewer where the
        # side came from before the reveal has earned it. The date carries the
        # same credibility without naming anybody.
        # sheet["date"] is ISO, which read as "our last match (2026-08-15)"
        # in the caption. Nobody says a date that way out loud.
        _d = str(sheet.get("date", ""))
        try:
            from datetime import date as _date
            _d = _date.fromisoformat(_d[:10]).strftime("%d %b").lstrip("0")
        except Exception:
            pass
        return (sheet["players"], sheet["formation"],
                f"our last match ({_d})" if _d else "our last match",
                sheet.get("bench", []))
    return [], "", "", []


def pick_xi(club: str, formation: str = "4-3-3") -> list[str]:
    """A plausible XI from the real cached squad — real names, real numbers.

    Chosen by listed position so the shape is honest: goalkeeper in goal,
    defenders in the back line. It is a prediction and the card says so.
    """
    cache = json.loads((ROOT / "data" / "psl_squads_cache.json").read_text(encoding="utf-8"))
    squad = (cache.get(club) or {}).get("squad") or []
    by_pos = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in squad:
        pos = (p.get("pos") or "").upper()
        bucket = ("GK" if pos.startswith("G") else
                  "DF" if pos.startswith("D") else
                  "MF" if pos.startswith("M") else
                  "FW" if pos else "")
        if bucket:
            by_pos[bucket].append(p)
    want = FORMATIONS.get(formation, FORMATIONS["4-3-3"])
    n_gk, n_df = want[0], want[1]
    n_fw = want[-1]
    n_mf = 11 - n_gk - n_df - n_fw
    plan = [("GK", n_gk), ("DF", n_df), ("MF", n_mf), ("FW", n_fw)]

    xi = []
    for bucket, n in plan:
        pool = by_pos.get(bucket, [])
        for p in pool[:n]:
            no = str(p.get("no", "") or "").strip()
            surname = (p.get("name", "") or "").split()[-1]
            xi.append(f"{no} {surname}".strip())
    return xi[:11]



def _reveal_ticks(out_wav: Path, times: list[float], total: float) -> Path | None:
    """A short percussive tick under each name as it lands.

    Synthesised rather than loaded from the SFX library so the reel has no
    asset dependency: a build must never lose its audio because a wav moved.
    """
    try:
        import wave
        import numpy as np
        sr = 44100
        buf = np.zeros(int(sr * (total + 0.5)), dtype=np.float32)
        for i, t in enumerate(times):
            k = int(t * sr)
            n = int(sr * 0.11)
            if k + n >= len(buf):
                break
            e = np.exp(-np.linspace(0, 9, n))            # fast decay
            # rises slightly through the XI so the last name lands highest
            f0 = 520 + 26 * i
            tone = np.sin(2 * np.pi * f0 * np.arange(n) / sr)
            click = np.sin(2 * np.pi * 1750 * np.arange(n) / sr) * np.exp(
                -np.linspace(0, 34, n))
            buf[k:k + n] += (tone * 0.55 + click * 0.45) * e * 0.30
        peak = float(np.max(np.abs(buf))) or 1.0
        buf = (buf / max(1.0, peak)) * 0.32
        with wave.open(str(out_wav), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((buf * 32767).astype("<i2").tobytes())
        return out_wav
    except Exception as e:
        print(f"[Lineup] reveal ticks skipped: {str(e)[:100]}")
        return None


def analysis_lines(club: str, opponent: str, formation: str, xi: list[str],
                   provenance: str = "", bench: list[str] | None = None) -> list[str]:
    """Narration. Built from what is actually on the card, so it can never
    describe a player who is not in the XI."""
    from modules.club_brand import CLUB_BRAND
    name = CLUB_BRAND.get(club, {}).get("name", club.title())
    opp = CLUB_BRAND.get(opponent, {}).get("name", opponent.title()) if opponent else ""
    parts = formation.split("-")
    keeper = xi[0].split(" ", 1)[-1] if xi else ""
    back = [p.split(" ", 1)[-1] for p in xi[1:1 + int(parts[0])]] if len(parts) > 1 else []
    front = [p.split(" ", 1)[-1] for p in xi[-int(parts[-1]):]] if len(parts) > 1 else []

    bench = bench or []
    # BREAKING-NEWS FRAMING. The old opening stated the whole premise in one
    # sentence and then read a list, which gives a viewer no reason to stay
    # past the third name. It now opens like team news breaking, says the
    # names are still coming, and holds the full eleven to the end.
    lines = [
        "Breaking team news.",
        f"This is the {name} eleven we expect"
        + (f" against {opp}." if opp else "."),
        "The names are coming in now. Stay with us for the full eleven.",
        f"The shape is {formation.replace('-', ' ')}.",
    ]
    if keeper:
        lines.append(f"{keeper} starts in goal.")
    if back:
        lines.append("The back line reads " + ", ".join(back) + ".")
    # Saying WHERE the side comes from is what makes it undeniable — but after
    # the reveal has done its work, not before it has started.
    if provenance:
        lines.append(f"This is built on the side that started {provenance}.")
    if front:
        lines.append("Up top, " + " and ".join(front) + " carry the goals.")
    lines += [
        (("On the bench: " + ", ".join(b.split(" ", 1)[-1] for b in bench[:5]) + ".")
         if bench else ""),
        "That is the Genesis News call, not the official team sheet.",
        "Tell us who you would drop in the comments.",
        "Subscribe to Genesis News — we post the team sheets the moment they land.",
    ]
    return [l for l in lines if l]


def build_frames(work: Path, club: str, opponent: str, formation: str,
                 xi: list[str], kickoff: str,
                 bench: list[str] | None = None,
                 highlight: list[int] | None = None) -> list[Path]:
    """One card per revealed player — the build-up animation."""
    from modules.lineup_card import make_lineup_card
    cards = []
    for n in range(1, len(xi) + 1):
        out = work / f"reveal_{n:02d}.png"
        # pad to a full XI so row widths — and therefore x positions — never
        # change between frames; blank entries render nothing
        revealed = xi[:n] + [""] * (len(xi) - n)
        p = make_lineup_card(out, club=club, players=revealed, opponent=opponent,
                             formation=formation, kickoff=kickoff,
                             competition="Betway Premiership", predicted=True,
                             # bench on EVERY frame: it shortens the pitch, so
                             # adding it only at the end would move all eleven
                             # markers on the last card and smear the crossfade
                             bench=bench, highlight=highlight)
        if p:
            cards.append(Path(p))
    return cards


def render_video(cards: list[Path], out: Path, total: float,
                 reveal_frac: float = 0.62, formation: str = "4-3-3",
                 players: list[str] | None = None, bg: Path | None = None,
                 bench: bool = False, accent=(255, 193, 7)) -> str:
    """Reveal the XI one man at a time, then hold the full card.

    Owner note 2026-08-24: the first cut fired all eleven in about four
    seconds and then sat on a static card for the remaining twenty-five —
    the reveal was over before the narration had named anyone. The build now
    spans most of the video so each man lands roughly as he is talked about,
    and consecutive cards cross-fade instead of hard-cutting.
    """
    from PIL import Image
    from modules.motion_kit import _render, DARK

    frames = [Image.open(c).convert("RGB") for c in cards]
    n = len(frames)
    canvas_y = (H - frames[0].height) // 2
    reveal_t = total * reveal_frac
    per = reveal_t / n                       # seconds per player
    fade = min(0.28, per * 0.35)             # tail of each slot spent blending

    # Phase two: once the side is named, animate the SHAPE. Owner call — the
    # reveal ends around 16s and the rest of the runtime should show the block
    # moving as one, forward into an attacking shape and back into a defensive
    # one, so it reads like a team rather than eleven dots.
    motion_t = max(0.0, total - reveal_t)
    bg_img = Image.open(bg).convert("RGB") if bg and Path(bg).exists() else None
    if motion_t > 4 and bg_img is not None and players:
        u = motion_t / 5.0
        plan = [("base", u * 0.7), ("attack", u * 1.4), ("base", u * 0.9),
                ("defend", u * 1.4), ("base", u * 0.6)]
    else:
        plan = None

    def frame_fn(t):
        base = Image.new("RGB", (W, H), DARK)
        if plan and t >= reveal_t:
            from modules.tactics_motion import frame as tframe
            img = tframe(bg_img, formation, players, t - reveal_t, plan,
                         accent=accent, bench=bench)
        else:
            pos = t / per
            idx = min(n - 1, int(pos))
            into = (pos - idx) * per         # seconds into this player's slot
            if idx < n - 1 and into > per - fade:
                # cross-fade into the next card so the reveal reads as motion
                u2 = (into - (per - fade)) / fade
                img = Image.blend(frames[idx], frames[idx + 1],
                                  min(1.0, max(0.0, u2)))
            else:
                img = frames[idx]
        base.paste(img, (0, canvas_y))
        return base

    return _render(frame_fn, out, duration=total, fps=24)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--opponent", default="",
                    help="override; normally resolved from the next fixture")
    ap.add_argument("--formation", default="4-3-3")
    ap.add_argument("--kickoff", default="")
    ap.add_argument("--start", default="",
                    help="comma-separated players the owner wants started; "
                         "each replaces a same-position pick and becomes one "
                         "of the big calls on the card")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_lineup_video.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    # ALWAYS the upcoming game. A predicted XI against a match already played
    # tells the reader we are not watching — on 24 Aug this shipped "Chiefs vs
    # Sundowns", a fixture from the 15th.
    competition = "Betway Premiership"
    if not a.opponent:
        from modules.psl_fixtures import next_fixture
        fx = await next_fixture(a.club)
        if not fx:
            _log(f"no upcoming fixture for {a.club} — refusing to build against "
                 f"a past game. Pass --opponent to override.")
            return 1
        a.opponent = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
        home = fx["home_key"] == a.club
        a.kickoff = a.kickoff or " · ".join(
            x for x in (fx.get("kickoff_sast", ""), fx.get("venue", "")) if x)
        _log(f"next fixture: {fx.get('home')} v {fx.get('away')} — "
             f"{fx.get('kickoff_sast')} ({'home' if home else 'away'})")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"lineup_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    # Prefer the real team sheet; fall back to the squad only if ESPN has none.
    xi, real_formation, provenance, bench = await pick_xi_real(a.club)
    if xi:
        a.formation = real_formation or a.formation
        _log(f"using REAL {provenance} — formation {a.formation}")
    else:
        _log("no published team sheet found — falling back to squad order")
        xi = pick_xi(a.club, a.formation)
    if len(xi) < 11:
        _log(f"only {len(xi)} players resolved — squad cache is thin, aborting")
        return 1

    # Never name a man who cannot play. Building from the last team sheet makes
    # this failure likely: someone who started the previous match and has been
    # injured since is still, to the sheet, a starter. A fan spotted exactly
    # that on 24 Aug — "fielding injured players like Frosler" — and it is the
    # comment that costs credibility, because it proves we are not watching.
    from modules.injuries import filter_xi
    xi, swaps = filter_xi(a.club, xi, bench)
    for dropped, came_in, why in swaps:
        if came_in:
            _log(f"INJURY: {dropped} out ({why}) — {came_in} in")
        else:
            _log(f"INJURY: {dropped} out ({why}) — no cover on the bench")
    bench = [b for b in bench if b not in xi]

    # TWO BIG CALLS. Owner call 2026-08-24 — every XI should carry a couple of
    # selections worth arguing about. They are real changes from the side that
    # started last time, same position for same position, marked in red on the
    # card and named out loud, so the argument is about our opinion and never
    # about whether we know the team.
    from modules.bold_calls import (pick as pick_calls, apply as apply_calls,
                                    _pos_map, _surname)

    # OWNER SELECTIONS. When the owner names the side, their picks ARE the big
    # calls — the algorithm does not get a second opinion on top, or the card
    # ends up carrying four changes and reads like a mistake rather than a
    # position. Each name replaces a same-position starter, because a forced
    # keeper swapped for a forward is how an XI stops being a shape.
    forced = [w.strip() for w in a.start.split(",") if w.strip()]
    calls = []
    if forced:
        # _pos_map is keyed by SURNAME, so resolving a full name against it
        # finds nothing. Read the squad straight from the cache instead.
        import json as _json
        _sq = _json.loads((ROOT / "data" / "psl_squads_cache.json")
                          .read_text(encoding="utf-8"))
        squad = {(pl.get("name") or ""): (pl.get("pos") or "").upper()[:2]
                 for pl in (_sq.get(a.club) or {}).get("squad") or []
                 if pl.get("name")}
        # The XI is written "<no> <Surname>" ("13 Mmodi"). A forced pick has to
        # match that or the card reads "13 Mmodi" beside "Renaldo Leaner".
        _no = {(pl.get("name") or ""): str(pl.get("no") or "").strip()
               for pl in (_sq.get(a.club) or {}).get("squad") or []
               if pl.get("name")}

        def _entry(full: str) -> str:
            sn, n = _surname(full), _no.get(full, "")
            return f"{n} {sn}".strip()

        def _norm(x: str) -> str:
            import unicodedata
            return "".join(c for c in unicodedata.normalize("NFKD", str(x))
                           if not unicodedata.combining(c)).lower().strip()

        def _resolve(q: str) -> str:
            qn = _norm(q)
            for n in squad:                       # exact, then surname, then token
                if _norm(n) == qn:
                    return n
            for n in squad:
                if _norm(_surname(n)) == qn:
                    return n
            hits = [n for n in squad if qn in _norm(n)]
            return hits[0] if len(hits) == 1 else ""

        def _grp(n: str) -> str:
            return squad.get(n) or squad.get(_resolve(_surname(n)), "")

        picked = [x for x in (_resolve(w) for w in forced) if x]
        for want, name in zip(forced, (_resolve(w) for w in forced)):
            if not name:
                _log(f"START: '{want}' matched no one in the squad — skipped")
                continue
            if any(_norm(_surname(n)) == _norm(_surname(name)) for n in xi):
                _log(f"START: {name} already in the XI")
                continue
            g = _grp(name)
            cand = [k for k, n in enumerate(xi)
                    if _grp(n) == g
                    and not any(_norm(_surname(n)) == _norm(_surname(f))
                                for f in picked)]
            if not cand:
                _log(f"START: no {g} free to make way for {name} — skipped")
                continue
            k = cand[-1]                          # the last pick in that unit
            calls.append({"index": k, "in": _entry(name), "out": xi[k],
                          "reason": "our call", "hook": ""})
            bench = [b for b in bench if _surname(b) != _surname(name)] + [xi[k]]
            xi = list(xi)
            xi[k] = _entry(name)                  # so the next resolve sees it
        # apply() re-writes these indexes, so hand it the ORIGINAL XI back
        for c in calls:
            xi[c["index"]] = c["out"]
    else:
        calls = pick_calls(a.club, xi, bench, n=2)
    marks = []
    if calls:
        xi, marks = apply_calls(xi, calls)
        for c in calls:
            _log(f"BIG CALL: {c['in']} in for {c['out']} ({c['reason']})")
        bench = [b for b in bench if b not in xi]
    _log(f"XI: {', '.join(xi)}")

    cards = build_frames(work, a.club, a.opponent, a.formation, xi, a.kickoff,
                         bench=bench, highlight=marks)
    _log(f"reveal frames: {len(cards)}")
    if not cards:
        _log("no cards rendered — aborting")
        return 1

    from modules.club_brand import CLUB_BRAND as _CBn
    club_label = _CBn.get(a.club, {}).get("name", a.club.title())
    lines = analysis_lines(a.club, a.opponent, a.formation, xi,
                           provenance=provenance, bench=bench)
    if calls:
        from modules.bold_calls import narration as call_narration
        # slot the calls in before the sign-off, not after it
        lines = lines[:-2] + call_narration(club_label, calls) + lines[-2:]
    narration = " ".join(lines)
    _log(f"narration: {len(narration)} chars")

    # Kokoro runs ~2.8 words/sec; the estimate matched the real 25.1s narration
    # to within a second on the first build, so pace the whole video off it.
    total = max(14.0, len(narration) / 15.0 + 5.0)
    # empty pitch for the motion phase to draw markers onto
    from modules.lineup_card import make_lineup_card as _mk
    bg = work / "pitch_bg.png"
    _mk(bg, club=a.club, players=[""] * len(xi), opponent=a.opponent,
        formation=a.formation, kickoff=a.kickoff,
        competition="Betway Premiership", predicted=True, bench=bench)
    from modules.club_brand import CLUB_BRAND as _CB
    accent = tuple(_CB.get(a.club, {}).get("colors", {}).get("primary", (255, 193, 7)))

    silent = work / "lineup_silent.mp4"
    render_video(cards, silent, total=total, formation=a.formation,
                 players=xi, bg=bg, bench=bool(bench), accent=accent)
    _log(f"video: {silent.name} — {total:.1f}s, "
         f"{(total * 0.62) / max(1, len(cards)):.1f}s per player")

    from modules.motion_kit import attach_voice
    voiced = await attach_voice(silent, narration, work / "voiced.mp4")

    # One tick per name, on the frame that name appears.
    final = Path(voiced)
    reveal_t = total * 0.62
    times = [reveal_t * (i + 1) / max(1, len(cards)) for i in range(len(cards))]
    tw = _reveal_ticks(work / "ticks.wav", times, total)
    if tw and Path(tw).exists():
        try:
            from moviepy import (VideoFileClip, AudioFileClip,
                                 CompositeAudioClip)
            v = VideoFileClip(str(voiced))
            t = AudioFileClip(str(tw))
            if t.duration > v.duration:
                t = t.subclipped(0, v.duration)
            mixed = work / "final.mp4"
            v.with_audio(CompositeAudioClip([v.audio, t])).write_videofile(
                str(mixed), codec="libx264", audio_codec="aac", logger=None)
            v.close(); t.close()
            final = mixed
            _log(f"reveal ticks mixed under {len(times)} names")
        except Exception as e:
            _log(f"tick mix skipped: {str(e)[:100]}")
    _log(f"voiced: {Path(final).name}")

    # Cover: the finished card, crest and all
    cover = work / "cover.jpg"
    from PIL import Image
    Image.open(cards[-1]).convert("RGB").save(cover, quality=94)

    # Proper club names, never the internal keys: a reel went out on 24 Aug
    # captioned "vs Richards_Bay" because .title() was applied to the key.
    from modules.club_brand import CLUB_BRAND
    club_name = CLUB_BRAND.get(a.club, {}).get(
        "name", a.club.replace("_", " ").title())
    opp_name = CLUB_BRAND.get(a.opponent, {}).get(
        "name", a.opponent.replace("_", " ").title()) if a.opponent else ""
    when = f" — {a.kickoff}" if a.kickoff else ""
    title = (f"{club_name} Predicted XI vs {opp_name}" if opp_name
             else f"{club_name} Predicted XI")
    calls_line = ""
    if calls:
        bits = " and ".join(
            f"{c['in'].split(None, 1)[-1]} in for {c['out'].split(None, 1)[-1]}"
            for c in calls)
        calls_line = ((chr(10) * 2) + _CALLW.get(len(calls), str(len(calls))).upper()
                      + " BIG CALLS: " + bits +
                      ". Disagree? Tell us who you'd start.")
    src_line = ((chr(10) * 2) + "Based on the XI that started "
                + provenance + ".") if provenance else ""
    caption = (f"GENESIS NEWS PREDICTION — the {club_name} eleven we expect"
               f"{' vs ' + opp_name if opp_name else ''}{when} "
               f"({a.formation}). Our call as a page, not the official team "
               f"sheet, and not us speaking for you. "
               f"Who would you drop? 👇" + calls_line + src_line +
               f"\n\n#PSL #BetwayPremiership #KaizerChiefs "
               f"#Amakhosi #PredictedXI")

    manifest = {"niche": NICHE, "format_type": "short", "is_short": True,
                "built_at": datetime.now().isoformat(),
                "video_path": str(final), "thumbnail": str(cover),
                "title": title, "description": caption, "xi": xi,
                "formation": a.formation}
    (work / "upload_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title, caption, cover, niche=NICHE,
                          tags=["PSL", "KaizerChiefs", "Amakhosi",
                                "PredictedXI", "BetwayPremiership"])
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
