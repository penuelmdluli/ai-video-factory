"""
Genesis News — PSL news reel builder. Static images only, no video generation.

The full pipeline is built to generate video, and every stall in this project has
come from that: RunPod hung, WaveSpeed hung, local SVD ran ~47s/step for an hour.
A news page does not need generated video. It needs one or two REAL, recent,
correctly-credited images, edited into news cards, with voice, subtitles and
music over the top.

Pipeline:
  1. live sourced headlines   (modules/psl_news)
  2. script + fact guards     (modules/script_writer — Claude subscription CLI)
  3. voice + SRT              (modules/voice_generator — Kokoro af_heart)
  4. 1-2 real photos          (modules/free_press_images — CC-licensed, credited)
                              falling back to Cloudflare FLUX matchday b-roll
  5. news cards               (modules/news_card — headline, kicker, credit, logo)
  6. assemble                 (Ken Burns + karaoke subtitles + music)
  7. upload_manifest.json     so the existing uploader can post it

Usage:
    python build_psl_news.py              # build only
    python build_psl_news.py --post       # build then post to the Genesis News page
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import NICHES, OUTPUT_DIR
from modules.club_brand import resolve_club, resolve_clubs, CLUB_BRAND

NICHE = "sa_pulse"
MAX_CARDS = 2          # "one or two real recent images and we are done"


def _log(msg):
    print(f"[PSL] {msg}", flush=True)


# Club names recur in every PSL title, so they must not count as "similar" —
# otherwise a Pirates story looks like a Chiefs story. What matters is whether
# the STORY is new.
_CLUB_WORDS = {
    "chiefs", "kaizer", "amakhosi", "pirates", "orlando", "buccaneers",
    "sundowns", "mamelodi", "masandawana", "psl", "betway", "premiership",
    "vs", "united", "fc",
}


def _stem(w: str) -> str:
    """Crude stem so 'injury' / 'injured' / 'injuries' count as one word."""
    for suf in ("ies", "ing", "ed", "es", "s", "y"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _is_fresh(topic: str, recent: list[str], min_new: int = 3,
              window: int = 8) -> bool:
    """True if the topic brings genuinely new subject matter.

    Word-overlap alone let 'Da Cruz's Five-Injury Problem' and 'Salum Reports
    After Da Cruz's Injury Crisis' both through — same story, different words.
    This instead demands the topic introduce at least `min_new` content words
    that appear NOWHERE in the last `window` topics.
    """
    stop = _CLUB_WORDS | {
        "the", "a", "an", "is", "are", "to", "for", "in", "of", "and", "or",
        "how", "why", "what", "this", "that", "with", "from", "it", "its",
        "not", "can", "do", "does", "will", "be", "on", "at", "after",
        "really", "actually", "means", "matter", "matters", "explained",
    }

    def words(s):
        ws = {w.lower().strip(".,!?:;'\"()—-") for w in s.split()}
        return {_stem(w) for w in ws - stop if len(w) > 3}

    mine = words(topic)

    # Guard 0 — framing repetition. On 2026-08-24 eleven of the last twelve
    # topics opened "Chiefs vs Sundowns:", and every one passed the word tests
    # below because club names are stopped out. The subject matter was new each
    # time; the packaging never was, so the page read like one story on loop.
    def frame(s):
        head = s.split(":")[0] if ":" in s else " ".join(s.split()[:4])
        return " ".join(sorted(
            w.lower().strip(".,!?:;'\"()—-") for w in head.split() if w.strip()))

    mine_frame = frame(topic)
    if mine_frame and sum(1 for t in recent[:6] if frame(t) == mine_frame) >= 1:
        return False

    # Guard 1 — no immediate re-tread. Sharing two content words with either
    # of the last two topics means it is the same story wearing new words
    # ('five defenders' -> 'lost five defenders and still held').
    for t in recent[:2]:
        if len(mine & words(t)) >= 2:
            return False
    # Guard 2 — over the recent window, the topic must bring real new subject
    # matter, not just recombine what we have already said.
    seen = set()
    for t in recent[:window]:
        seen |= words(t)
    return len(mine - seen) >= min_new


# Angle rotation — even the same club gets a different treatment each slot,
# so three posts about one team are three different pieces of content.
# Owner call 2026-08-19: stop re-telling the last Chiefs game. Half of these
# angles now point FORWARD — the next fixture, the transfer window, what is
# about to happen — so the page breaks news instead of reviewing it.
# ANGLES — rewritten 2026-08-19 from the page's own numbers. Every top
# performer on Facebook is a DISPUTE: a contract standoff (4,333 views), an
# injury crisis (3,950), a warning (2,485), a VAR row (2,182). The most
# produced pieces — the Full Tactical Picture (1,591) and Best XI (1,800) —
# sat BELOW plain news reels about an argument. So the angle now has to
# carry a disagreement, not just information.
ANGLES = [
    "a DISAGREEMENT between two named people — a coach, a player, a pundit "
    "or a club — and what each side is actually claiming",
    "a selection or transfer call fans are ARGUING about, with the case for "
    "and against laid out",
    "a decision that cost points — refereeing, a substitution, a tactical "
    "switch — and who is being blamed",
    "LOOK AHEAD to the next fixture through the one contested question that "
    "decides it",
    "a claim in the headlines that deserves pushback: who says it, and why "
    "the other side disagrees",
    "a record, stat or table position that fans refuse to accept at face "
    "value",
]


def slot_plan() -> tuple[str, str]:
    """(lead club, required angle) for this run — rotates through the week."""
    from datetime import datetime as _d
    n = _d.now()
    # CHIEFS ONLY (owner call 2026-08-26). This used to be a 5-of-7 cycle that
    # gave two slots a week to Pirates and Sundowns. It is a Kaizer Chiefs page
    # read by Kaizer Chiefs fans, and the numbers said the same thing long
    # before the instruction did: Chiefs posts ran a median 1,066 views against
    # 90 for everything else. A Sundowns story on this page is a slot spent on
    # an audience that is not here.
    #
    # Variety now comes from the ANGLE, not from the club. There are enough
    # angles and enough Chiefs sweeps that no two slots have to tell the same
    # story — which was the original reason the rotation existed.
    idx = n.timetuple().tm_yday * 3 + (0 if n.hour < 11 else
                                       1 if n.hour < 17 else 2)
    return "chiefs", ANGLES[idx % len(ANGLES)]


async def pick_topic() -> str:
    # VARIETY RULE (owner 2026-08-17, hardened 2026-08-18): the page ran ~20
    # straight reels off one Chiefs fixture. The old guard retried ONCE and
    # then used the repeat anyway. Now it keeps asking until the topic brings
    # genuinely new subject matter, and each slot is handed a required angle.
    from modules.topic_generator import (generate_trending_topic_ai,
                                         _get_recent_topic_titles,
                                         _record_topic)
    recent = _get_recent_topic_titles(NICHE, days=14)
    lead, angle = slot_plan()
    try:
        from modules.psl_news import set_lead_club
        set_lead_club(lead)   # topic generator + script writer both follow it
    except Exception as e:
        _log(f"lead club not set: {e}")
    _log(f"slot plan: lead={lead} angle={angle}")

    topic = ""
    for attempt in range(4):
        cand = await generate_trending_topic_ai(NICHE, recent_titles=recent,
                                                angle=angle)
        if not cand:
            continue
        if _is_fresh(cand, recent):
            topic = cand
            break
        _log(f"attempt {attempt + 1} repeats recent coverage: {cand[:60]}")
        recent = [cand] + recent
    if not topic:
        # The old fallback pasted the ANGLE — a prompt instruction — straight
        # into the headline, so a quiet news day shipped a reel titled
        # "Kaizer Chiefs vs Mamelodi Sundowns: a DISAGREEMENT between two named
        # people...". A slow feed is normal; a broken headline is not.
        # These are evergreen formats that stand on their own, weighted to what
        # the audience actually watches: line-ups and Chiefs analysis.
        import random as _r
        club = {"chiefs": "Kaizer Chiefs", "pirates": "Orlando Pirates",
                "sundowns": "Mamelodi Sundowns"}.get(lead, "Kaizer Chiefs")
        nick = {"chiefs": "Amakhosi", "pirates": "the Buccaneers",
                "sundowns": "Masandawana"}.get(lead, "Amakhosi")
        evergreen = [
            f"{club} Predicted XI: The Eleven That Should Start The Next Game",
            f"{club} Player Ratings: Every {nick} Man Out Of Ten",
            f"{club} Injury List: Who Is Fit, Who Is Doubtful, Who Is Out",
            f"Inside {club}: The Tactical Shift {nick} Fans Keep Arguing About",
            f"{club} Form Guide: What The Last Five Games Actually Show",
            f"{club} Squad Depth: The Position {nick} Still Have Not Fixed",
            f"{club} Transfer Watch: Every Name Linked And How Real It Is",
            f"{club} In The Log: What {nick} Need To Reach The Top Three",
        ]
        fresh = [e for e in evergreen if _is_fresh(e, recent)]
        topic = _r.choice(fresh or evergreen)
        _log(f"no fresh news topic after 4 tries — evergreen format: {topic}")
    _record_topic(NICHE, topic)
    _log(f"topic: {topic}")
    return topic


# Rotating closing asks. The prompt requires one, but a prompt is a request,
# not a guarantee — and the channel converts ~0.25% of views to subscribers,
# so the ask is too valuable to leave to chance.
SUBSCRIBE_LINES = [
    "Subscribe to Genesis News — we call every Chiefs game before kick-off.",
    "Subscribe. We break the team news before the whistle.",
    "Hit subscribe — the log race, every Friday, on Genesis News.",
    "Subscribe to Genesis News for the real Amakhosi picture, every day.",
    "Subscribe — we post the team sheets the moment they land.",
]


def _ensure_subscribe(script: dict) -> dict:
    """Guarantee the last scene actually says 'subscribe'."""
    scenes = script.get("scenes") or []
    if not scenes:
        return script
    last = scenes[-1]
    text = (last.get("narration") or "")
    if "subscrib" in text.lower():
        return script
    from datetime import datetime as _d
    line = SUBSCRIBE_LINES[_d.now().timetuple().tm_yday % len(SUBSCRIBE_LINES)]
    last["narration"] = f"{text.rstrip()} {line}".strip()
    last["duration_seconds"] = last.get("duration_seconds", 4) + 2
    _log("closing subscribe ask was missing — appended")
    return script


async def write_script(topic: str) -> dict:
    from modules.script_writer import generate_script
    script = await generate_script(topic, NICHE, "short")
    if not script:
        raise RuntimeError("script generation failed")
    script = _ensure_subscribe(script)
    _log(f"script: {script.get('title', '')[:70]} ({len(script.get('scenes', []))} scenes)")
    return script


async def make_voice(script: dict, work: Path) -> dict:
    from modules.voice_generator import generate_voice
    from modules.script_writer import get_full_narration
    narration = get_full_narration(script)
    result = await generate_voice(narration, work, "voiceover", "short",
                                  NICHE, script.get("scenes"))
    if not result:
        raise RuntimeError("voice generation failed")
    _log(f"voice: {result.get('engine')}/{result.get('voice')} "
         f"{result.get('duration_estimate', 0):.0f}s")
    return result


_NAME_STOP = {
    # club/league words + sentence-starters that look like "Firstname Surname"
    "kaizer", "chiefs", "orlando", "pirates", "mamelodi", "sundowns", "amakhosi",
    "amazulu", "chippa", "united", "durban", "city", "golden", "arrows", "magesi",
    "marumo", "gallants", "orbit", "college", "polokwane", "richards", "bay",
    "sekhukhune", "siwelele", "stellenbosch", "galaxy", "south", "africa",
    "african", "premier", "soccer", "league", "betway", "premiership", "soweto",
    "derby", "genesis", "news", "the", "what", "why", "how", "this", "that",
    "here", "watch", "live", "breaking", "latest", "caf", "champions", "cup",
    "fnb", "stadium", "loftus", "versfeld", "moses", "mabhida", "coach", "boss",
}


def _player_names(*texts: str) -> list[str]:
    """Capitalised first-last pairs that aren't club/league words — probable players."""
    seen, out = set(), []
    for t in texts:
        for m in re.finditer(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z']{2,})\b", t or ""):
            cand = f"{m.group(1)} {m.group(2)}"
            if any(w.lower() in _NAME_STOP for w in cand.split()):
                continue
            if cand.lower() not in seen:
                seen.add(cand.lower())
                out.append(cand)
    return out


def _frames_from_clip(clip: dict, work: Path, need: int) -> list[dict]:
    """
    Still frames from a recent CC-BY highlight video — REAL, days-old imagery
    of the actual club, which beats years-old Commons photos every time. The
    video's CC licence covers stills, and the same creator credit is burned in.
    """
    import subprocess
    out = []
    dur_probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", clip["path"]], capture_output=True, text=True)
    try:
        dur = float(dur_probe.stdout.strip())
    except Exception:
        dur = 10.0
    # sharpest frames win — a blurred still makes a cheap-looking card
    try:
        from modules.clean_frames import sharpest_frames
        picks = sharpest_frames(clip["path"], work / "photos" / "cands",
                                need=need, samples=10)
    except Exception:
        picks = []
    if not picks:      # fallback: old fixed offsets
        picks = [("", dur * f) for f in (0.35, 0.7)][:need]
    for i, (cand, t) in enumerate(picks):
        if len(out) >= need:
            break
        p = work / "photos" / f"ccframe_{i+1}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        if cand:
            import shutil as _sh
            _sh.copy2(cand, p)
        else:
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                 "-i", clip["path"], "-frames:v", "1", "-q:v", "2", str(p)],
                capture_output=True)
            if r.returncode != 0:
                continue
        if p.exists() and p.stat().st_size > 30_000:
            out.append({"path": str(p),
                        "credit": ("Genesis News footage" if clip.get("owner")
                                   else f"still: {clip['channel']} (CC BY, via YouTube)"),
                        "archive_year": "", "club": clip.get("club", ""),
                        "real": True})
    if out:
        _log(f"cc video stills: {len(out)} from '{clip['title'][:40]}'")
    return out


async def gather_images(script: dict, briefing: dict, work: Path) -> tuple[list[dict], dict | None]:
    """
    One or two REAL images, correctly credited, plus the CC clip for motion.
    Priority: recent photo of a NAMED player -> still frames from a recent
    CC-BY highlight video (real + days old) -> club-first Commons photo ->
    generated matchday b-roll. Never a scraped press photo.
    """
    from modules.free_press_images import photos_for_club, photos_for_player, download
    from modules.ai_images import generate_image_cloudflare

    title = script.get("title", "")
    narrations = " ".join(s.get("narration", "") for s in script.get("scenes", []))
    club = resolve_club(title) or resolve_club(narrations) or "generic"
    _log(f"club context: {club}")

    raw_dir = work / "photos"
    out = []

    # 0) OWNER MEDIA — the owner's own photos outrank every other source:
    #    fully licensed, real, current. Sent via the WhatsApp vault.
    #    Match on EVERY club in the story (a Chiefs–Sundowns recap names two),
    #    and only vault media filed under one of them may ride the story.
    try:
        from modules.club_brand import resolve_clubs as _rc
        owner_clubs = _rc(f"{title} {narrations}") or [club]
    except Exception:
        owner_clubs = [club]
    try:
        from modules.owner_media import owner_images
        for img in owner_images(owner_clubs, limit=MAX_CARDS):
            out.append(img)
            _log(f"owner photo: {Path(img['path']).name}")
    except Exception as e:
        _log(f"owner media skipped: {e}")

    # 1) The players the story is actually about — newest photo first.
    heads = " ".join(i.get("title", "") for k in briefing or {}
                     if isinstance(briefing.get(k), list)
                     for i in briefing[k][:3] if isinstance(i, dict))
    players = _player_names(title, narrations, heads)[:8]
    story_clubs = []

    # Validate against CURRENT squads — title-case headlines make the
    # capitalised-bigram heuristic hallucinate "players" like "Warning Means".
    # A candidate only survives if a real squad member matches it.
    try:
        from modules.psl_squads import get_squad
        from modules.club_brand import resolve_clubs
        story_clubs = resolve_clubs(f"{title} {narrations} {heads}") or [club]
        roster = {}
        for ck in story_clubs[:3]:
            for p in await get_squad(ck):
                roster[p["name"].split()[-1].lower()] = p["name"]
        verified = []
        for cand in players:
            canon = roster.get(cand.split()[-1].lower())
            if canon:
                verified.append(canon)      # use the squad's canonical spelling
        players = list(dict.fromkeys(verified))[:4]
    except Exception as e:
        _log(f"squad validation skipped: {e}")
        players = players[:4]
    if players:
        _log(f"player candidates (squad-verified): {players}")
    def _archive(hit) -> str:
        # Stamp ARCHIVE only when the photo is genuinely old — a shot from this
        # season or last is current coverage, not archive material.
        y = hit.get("year") or 0
        return str(y) if y and y < datetime.now().year - 1 else ""

    for name in players:
        if len(out) >= MAX_CARDS:
            break
        for hit in await photos_for_player(name, 1):
            path = await download(hit, raw_dir / f"photo_{len(out)+1}.jpg")
            if path:
                out.append({"path": path, "credit": hit["credit"],
                            "archive_year": _archive(hit),
                            "club": club, "real": True})
                _log(f"player photo: {name} ({hit.get('year') or 'undated'})")

    # 2) Still frames from a recent CC-BY highlight video of this club —
    #    real footage from THIS WEEK beats an old Commons photo. The local
    #    clip library (daily sweep) answers instantly; live fetch is fallback.
    cc_clip = None
    # OWNER FOOTAGE FIRST — their own clips beat every other video source.
    try:
        from modules.owner_media import pick_owner_video
        # headline clubs first — footage should match what the title says,
        # not a club only mentioned in passing
        title_clubs = resolve_clubs(title)
        ov = (pick_owner_video(title_clubs) if title_clubs else None) \
            or pick_owner_video(owner_clubs)
        if ov:
            cc_clip = {**ov, "club": club}
            _log(f"OWNER footage: {Path(ov['path']).name} '{ov['caption'][:30]}'")
    except Exception as e:
        _log(f"owner video skipped: {e}")
    # GAME-TIME RULE (owner): while a big-three fixture is live/today, every
    # video must show THE LIVE GAME — search for footage of this exact fixture
    # uploaded today before touching the library.
    try:
        if cc_clip:
            raise StopIteration          # owner footage already chosen
        from datetime import datetime as _dt
        from modules.psl_fixtures import todays_fixtures, SAST
        from modules.cc_clips import fetch_cc_clip as _fetch
        for f in await todays_fixtures():
            keys = {f["home_key"], f["away_key"]}
            if not keys & set(story_clubs or [club]):
                continue
            hn = CLUB_BRAND.get(f["home_key"], {}).get("name", "")
            an = CLUB_BRAND.get(f["away_key"], {}).get("name", "")
            live = await _fetch(f"{hn} vs {an}", work / "cc", days=1)
            if live:
                cc_clip = {**live, "club": f["home_key"]}
                _log(f"LIVE GAME footage: {live['title'][:45]}")
            break
    except Exception as e:
        _log(f"live-game clip check skipped: {e}")
    if not cc_clip:
        try:
            from modules.clip_library import pick_clip
            # any club in the story can supply the live window — Chiefs footage
            # is valid on a Chiefs-vs-Sundowns story even when Sundowns lead it.
            # pick_clip rotates: a FRESH clip every build, never the same one
            # twice in a row while alternatives exist.
            for ck in ([club] + [c for c in story_clubs if c != club]):
                chosen = pick_clip(ck)
                if chosen:
                    cc_clip = {**chosen, "club": ck}
                    _log(f"clip from library ({ck}, rotated): {chosen['title'][:45]}")
                    break
        except Exception as e:
            _log(f"clip library skipped: {e}")
    if not cc_clip:
        try:
            from modules.cc_clips import fetch_cc_clip
            club_name = CLUB_BRAND.get(club, {}).get("name", "PSL")
            cc_clip = await fetch_cc_clip(f"{club_name} highlights", work / "cc")
            if cc_clip:
                cc_clip["club"] = club
        except Exception as e:
            _log(f"cc clip lookup skipped: {e}")
    if cc_clip and len(out) < MAX_CARDS:
        out += _frames_from_clip(cc_clip, work, MAX_CARDS - len(out))

    # 3) Club/matchday photos to fill the remainder. A photo whose title lists
    #    ANOTHER team first ("Go Ahead Eagles - Mamelodi Sundowns ...") is shot
    #    from the opponent's side — it reads as the wrong club on a card, so
    #    the on-brand generated matchday visual below beats it.
    club_words = CLUB_BRAND.get(club, {}).get("name", club).lower().split()
    if len(out) < MAX_CARDS:
        for hit in await photos_for_club(club, (MAX_CARDS - len(out)) + 2):
            head = hit["title"].split("-")[0].lower()
            if not any(w in head for w in club_words):
                _log(f"photo skipped (opponent-first): {hit['title'][:50]}")
                continue
            path = await download(hit, raw_dir / f"photo_{len(out)+1}.jpg")
            if path:
                out.append({"path": path, "credit": hit["credit"],
                            "archive_year": _archive(hit),
                            "club": club, "real": True})
            if len(out) >= MAX_CARDS:
                break
    _log(f"licensed photos: {len(out)}")

    while len(out) < MAX_CARDS:
        n = len(out) + 1
        brand = CLUB_BRAND.get(club, {})
        colours = brand.get("prompt_colors", "team colours")
        prompt = (
            f"RAW press photograph, packed South African football stadium at night under "
            f"floodlights, ecstatic anonymous supporters in {colours}, vuvuzelas raised, "
            f"makarapa helmets, motion blur, long lens sports photography, no logos, "
            f"no badges, no text"
        )
        p = raw_dir / f"generated_{n}.png"
        got = await generate_image_cloudflare(prompt, p, niche=NICHE,
                                              orientation="portrait", enhance=False)
        if not got:
            break
        out.append({"path": got, "credit": "Genesis News illustration",
                    "archive_year": "", "club": club, "real": False})
    _log(f"images total: {len(out)}")
    return out, cc_clip


async def _make_prediction(title: str, log_rows: list) -> str:
    """
    "OUR CALL: CHIEFS 2-1 — BAARTMAN TO SCORE" for two-club stories.
    Favourite = higher log position; scorer = the favourite's most-started
    forward. Pure labelled opinion built from real data — never a stated fact.
    """
    clubs = resolve_clubs(title)
    if len(clubs) < 2:
        return ""
    # ONLY predict a matchup with an UPCOMING fixture (next 7 days, not yet
    # kicked off). Completed games drop out of ESPN's day feed within hours,
    # so "not finished" can't be tested — "has a future game" can. This is
    # what killed the fake "OUR CALL 2-1" on the already-played 1-1 derby.
    try:
        from datetime import timedelta as _td
        from modules.psl_fixtures import fixtures_for, SAST
        from datetime import datetime as _dt
        upcoming = False
        for dd in range(0, 7):
            for f in await fixtures_for(_dt.now(SAST) + _td(days=dd)):
                if {f["home_key"], f["away_key"]} == set(clubs[:2]) and \
                        f["status"] == "pre":
                    upcoming = True
                    break
            if upcoming:
                break
        if not upcoming:
            return ""
    except Exception:
        return ""
    from modules.psl_squads import recent_starts, get_squad
    rank = {r.get("team_key"): r.get("rank", 99) for r in log_rows or []}
    a, b = clubs[:2]
    fav = a if rank.get(a, 99) <= rank.get(b, 99) else b

    def sur(n: str) -> str:
        w = n.split()
        if len(w) >= 2 and w[-2].lower() in ("du", "de", "van", "von", "le", "da", "dos"):
            return " ".join(w[-2:])
        return w[-1] if w else n

    starts, _f = await recent_starts(fav)
    squad = await get_squad(fav)
    fws = sorted([p for p in squad if p["pos"] == "FW"],
                 key=lambda p: -starts.get(sur(p["name"]).lower(), 0))
    scorer = sur(fws[0]["name"]).upper() if fws else ""
    short = CLUB_BRAND.get(fav, {}).get("name", fav).upper() \
        .replace("KAIZER ", "").replace("MAMELODI ", "").replace("ORLANDO ", "")
    txt = f"OUR CALL: {short} 2-1"
    if scorer:
        txt += f" — {scorer} TO SCORE"
    try:
        from modules.call_tracker import record_call
        other = b if fav == a else a
        record_call(fav, other, "2-1", scorer, txt)
    except Exception:
        pass
    return txt


def build_cards(script: dict, images: list[dict], briefing: dict, work: Path,
                prediction: str = "", log_rows: list | None = None,
                has_video: bool = False, video_cards: int = 0) -> list[str]:
    """Turn each image into a branded news card carrying the headline + credit."""
    from modules.news_card import make_news_card

    club = images[0]["club"] if images else "generic"
    kicker = CLUB_BRAND.get(club, {}).get("name", "PSL")
    headline = script.get("title", "")

    # Second card leads on the strongest sourced headline, so the two cards say
    # different things instead of repeating the title.
    lead = ""
    for key in (club, "chiefs", "premiership"):
        items = briefing.get(key) or []
        if items:
            lead = items[0]["title"]
            break

    cards = []
    for i, img in enumerate(images):
        text = headline if i == 0 else (lead or headline)
        credit = img["credit"]
        if img["real"]:
            credit = f"photo: {credit}"
        out = work / f"card_{i+1}.png"
        vm = i < video_cards        # this card carries the live window

        made = make_news_card(img["path"], out, headline=text, kicker=kicker,
                              credit=credit, club=club,
                              archive_year=img.get("archive_year", ""),
                              prediction=prediction if i == 0 else "",
                              log_rows=log_rows if (i == 1 or len(images) == 1)
                              else None,
                              # big crest fills the photo zone wherever the
                              # live video window is NOT playing; on the video
                              # card the crest-VS-crest rides ON the footage
                              big_crest=not vm and ((i > 0) or not has_video),
                              show_crests=not vm and ((i > 0) or not has_video),
                              video_mode=vm)
        if made:
            cards.append(made)
    _log(f"news cards: {len(cards)}")
    return cards


CANVAS = (1080, 1920)
CAPTION_BOTTOM_MARGIN = 300     # keeps subs clear of the card's own headline block


def _caption_clips(segments, video_w, work: Path):
    """
    Tech Pulse Africa caption style — the SAME renderer the tech_news reels use
    (assemble_full.render_caption_png): PIL-drawn, wrapped to max 2 lines, font
    shrunk until every line fits inside 86% of the frame width (never cut off),
    key words highlighted in accent, heavy black outline. MoviePy TextClip was
    clipping words at the frame edge; this can't.
    """
    from moviepy import ImageClip
    from assemble_full import render_caption_png, CAP_H
    clips = []
    cap_dir = work / "captions"
    cap_dir.mkdir(exist_ok=True)
    for i, seg in enumerate(segments):
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start + 1))
        if end <= start:
            continue
        try:
            png = render_caption_png(txt, video_w, str(cap_dir / f"cap_{i}.png"))
            clips.append(
                ImageClip(png).with_start(start).with_duration(end - start)
                .with_position(("center",
                                CANVAS[1] - CAPTION_BOTTOM_MARGIN - CAP_H // 2)))
        except Exception as e:
            print(f"[PSL] caption clip skipped: {e}")
    return clips


def _vs_badge(clubs: list[str], work: Path) -> str | None:
    """Crest-VS-crest bug that rides on the live video window (broadcast style)."""
    from PIL import Image, ImageDraw, ImageFont
    from modules.club_brand import official_badge
    badges = [official_badge(c) for c in clubs[:2]]
    badges = [b for b in badges if b]
    if not badges:
        return None
    try:
        vf = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 44)
    except Exception:
        vf = ImageFont.load_default()
    box, pad = 128, 22
    img = Image.new("RGBA", (CANVAS[0], box + pad * 2 + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    vs_w = int(d.textlength("VS", font=vf)) + 26 if len(badges) == 2 else 0
    panels = []
    for b in badges:
        crest = Image.open(b).convert("RGBA")
        r = min(box / crest.width, box / crest.height)
        crest = crest.resize((int(crest.width * r), int(crest.height * r)),
                             Image.LANCZOS)
        panels.append(crest)
    total = sum(p.width + pad * 2 for p in panels) + (vs_w + 14 if vs_w else 0)
    # content-sized (not canvas-wide) so the caller can corner-align it
    img = Image.new("RGBA", (total + 8, box + pad * 2 + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 4
    for j, crest in enumerate(panels):
        pw, ph = crest.width + pad * 2, crest.height + pad * 2
        panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        ImageDraw.Draw(panel).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=22,
                                                fill=(255, 255, 255, 235))
        img.alpha_composite(panel, (x, 4))
        img.alpha_composite(crest, (x + pad, 4 + pad))
        x += pw
        if j == 0 and len(panels) == 2:
            vy = 4 + ph // 2 - 26
            d.text((x + 16, vy + 3), "VS", font=vf, fill=(0, 0, 0, 235))
            d.text((x + 13, vy), "VS", font=vf, fill=(255, 193, 7, 255))
            x += vs_w + 14
    p = work / "vs_badge.png"
    img.save(p)
    return str(p)


def _subscribe_strip(work: Path) -> str:
    """YouTube-red SUBSCRIBE pill shown in the reel's final seconds."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        fb = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 42)
        fs = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    except Exception:
        fb = fs = ImageFont.load_default()
    img = Image.new("RGBA", (CANVAS[0], 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    t1, t2 = "SUBSCRIBE", "youtube.com/@GenesisNewsPSL"
    w1, w2 = d.textlength(t1, font=fb), d.textlength(t2, font=fs)
    total = w1 + w2 + 110
    x0 = (CANVAS[0] - total) / 2
    d.rounded_rectangle([x0, 8, x0 + w1 + 56, 74], radius=16, fill=(230, 33, 23))
    d.text((x0 + 28, 18), t1, font=fb, fill=(255, 255, 255))
    d.rounded_rectangle([x0 + w1 + 70, 14, x0 + total, 68], radius=14,
                        fill=(10, 12, 16, 215))
    d.text((x0 + w1 + 90, 26), t2, font=fs, fill=(235, 238, 242))
    p = work / "subscribe.png"
    img.save(p)
    return str(p)


def _credit_strip(text: str, work: Path) -> str:
    """Small semi-transparent credit bar for real-footage segments."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    except Exception:
        f = ImageFont.load_default()
    img = Image.new("RGBA", (CANVAS[0], 56), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = d.textlength(text, font=f)
    d.rounded_rectangle([CANVAS[0] / 2 - w / 2 - 24, 0,
                         CANVAS[0] / 2 + w / 2 + 24, 52], radius=14,
                        fill=(0, 0, 0, 170))
    d.text((CANVAS[0] / 2 - w / 2, 10), text, font=f, fill=(235, 240, 245, 255))
    p = work / "cc_credit.png"
    img.save(p)
    return str(p)


def _story_intro(script: dict, work: Path, max_dur: float) -> str | None:
    """Render the motion template that matches this story type.

    Every reel used to open with the same two static cards whatever the story
    was. Now a transfer opens with the crest-to-crest move, a quote with
    kinetic type, an injury with the player spotlight — same brand, different
    template. Returns None when nothing fits, and the reel opens as before.
    """
    try:
        from modules.story_router import classify, render_intro
        title = script.get("title", "")
        kind, params = classify(title, script.get("caption", ""))
        if not kind:
            _log("story type: none matched — standard card open")
            return None
        dur = max(4.0, min(6.5, max_dur))
        clip = render_intro(kind, params, work / f"intro_{kind}.mp4", dur)
        if clip:
            _log(f"story type: {kind} — opening with its template ({dur:.1f}s)")
        else:
            _log(f"story type: {kind} — template lacked data, standard open")
        return clip
    except Exception as e:
        _log(f"story intro skipped: {e}")
        return None


async def assemble(script: dict, voice: dict, cards: list[str], work: Path,
                   cc_clip: dict | None = None,
                   log_rows: list | None = None) -> str:
    """
    Compose the reel directly — NO Ken Burns, NO zoom, NO cinematic effects.

    The cards are already finished 1080x1920 artwork with the logo, headline and
    credit positioned exactly. The main assembler applies a 1.5x Ken Burns zoom,
    which cropped straight through all of it: the wordmark vanished, the kicker
    and headline were cut off at both edges, and the attribution was clipped.
    A pre-composed card must be shown 1:1.
    """
    from moviepy import (AudioFileClip, ImageClip, CompositeVideoClip,
                         CompositeAudioClip, concatenate_videoclips)
    from modules.caption_generator import parse_subtitle_to_segments, group_words_into_phrases
    from modules.caption_align import align_captions
    from modules.script_writer import get_full_narration

    voice_audio = AudioFileClip(voice["audio_path"])
    duration = voice_audio.duration

    segments = parse_subtitle_to_segments(voice["subtitle_path"])
    # The SRT is a transcription and mangles SA names ("Kiser", "Maim Lodi").
    # Respell every word from the narration text — timing from the SRT,
    # spelling from the script.
    segments = align_captions(get_full_narration(script), segments)
    captions = group_words_into_phrases(segments, max_words=4)

    # Timeline: cards held static (a news frame wants to be read). Real
    # CC-licensed footage PLAYS INSIDE the card's photo window — the zone
    # between the top bar and the headline block — so the title, log and
    # credits stay on screen while live match video runs above them.
    per = duration / max(1, len(cards))
    stills = [ImageClip(str(c)).with_duration(per).resized(CANVAS) for c in cards]
    base = concatenate_videoclips(stills, method="compose").with_duration(duration)

    overlay_layers = []
    if cc_clip:
        try:
            from moviepy import VideoFileClip, concatenate_videoclips as _cat
            # Full-bleed window on a dark stage (card draws the stage +
            # horizontal log strip below) — no photo slivers, log visible.
            WIN_Y, WIN_H = 190, 620
            # everything starts at 0: the footage window used to fade in at 0.3s, which left a black
            # rectangle on frame zero — the frame TikTok takes as the cover
            vc = VideoFileClip(cc_clip["path"]).without_audio()
            # owner footage fills BOTH cards' windows; other sources card 1 only
            emb_dur = float(duration - 0.6) if cc_clip.get("owner")                 else float(per - 0.3)
            src = vc
            if src.duration < emb_dur:
                src = _cat([vc] * (int(emb_dur // vc.duration) + 1))
            s = max(CANVAS[0] / src.w, WIN_H / src.h)
            emb = src.subclipped(0, emb_dur).resized(s)
            x1 = max(0, int((emb.w - CANVAS[0]) / 2))
            y1 = max(0, int((emb.h - WIN_H) / 2))
            emb = (emb.cropped(x1=x1, y1=y1, width=CANVAS[0], height=WIN_H)
                   .with_start(0).with_position((0, WIN_Y)))
            overlay_layers.append(emb)
            overlay_layers.append(
                ImageClip(_credit_strip(cc_clip["credit"], work))
                .with_start(0).with_duration(emb_dur)
                .with_position((28, WIN_Y + WIN_H - 62)))
            # crest VS crest rides ON the footage — small, top-right corner,
            # never blocking the action
            vs = _vs_badge(resolve_clubs(script.get("title", "")), work)
            if vs:
                vsc = ImageClip(vs).resized(0.55)
                overlay_layers.append(
                    vsc.with_start(0).with_duration(emb_dur)
                    .with_position((CANVAS[0] - int(vsc.w) - 20, WIN_Y + 10)))
            _log(f"live window: {emb_dur:.1f}s full-bleed on dark stage")

            # Animated stats band over the card's static log strip. Live
            # table only — the strip used to be dead artwork under moving
            # video; now it staggers in, ticks the points up, pulses the club
            # the story is about and flips to a focus panel.
            try:
                from modules.stats_layer import stats_band, BAND_XY
                club = (resolve_clubs(script.get("title", "")) or [None])[0]
                band = stats_band(log_rows, emb_dur, club=club)
                if band:
                    overlay_layers.append(
                        band.with_start(0).with_position(BAND_XY))
                    _log(f"stats band: live log, {len(log_rows)} rows")
            except Exception as e:
                _log(f"stats band skipped: {e}")
        except Exception as e:
            _log(f"cc clip window skipped: {e}")

    # subscribe promo — final seconds, YouTube red, above the caption band
    try:
        sub = _subscribe_strip(work)
        overlay_layers.append(
            ImageClip(sub).with_start(max(0, duration - 4.0))
            .with_duration(min(4.0, duration))
            .with_position(("center", CANVAS[1] - 120)))
    except Exception as e:
        _log(f"subscribe strip skipped: {e}")

    # Story-matched opening. It plays full frame over the cards for its own
    # length, then the reel continues exactly as before — voice and caption
    # timing are untouched, so nothing can drift.
    intro_path = _story_intro(script, work, duration * 0.34)
    if intro_path:
        try:
            from moviepy import VideoFileClip
            iv = VideoFileClip(str(intro_path)).without_audio()
            iv = iv.subclipped(0, min(iv.duration, duration * 0.34))
            # appended, not inserted — it must cover the live-footage window
            # and the credit strip while it plays, or they punch through it
            # START AT 1.2s, NOT 0. TikTok picks the FIRST FRAME as the
            # cover and we never set one, so every reel since 18 Aug was
            # showing a dark crest card in the grid: those posts sit at
            # 3-28 views while the ones whose cover is the news card sit at
            # 900-1,600. Frame zero must be the card with the photo.
            overlay_layers.append(
                iv.resized(CANVAS).with_start(1.2).with_position((0, 0)))
        except Exception as e:
            _log(f"intro overlay skipped: {e}")

    layers = [base] + overlay_layers + _caption_clips(captions, CANVAS[0], work)
    video = CompositeVideoClip(layers, size=CANVAS).with_duration(duration)

    # Music bed under the voice, quiet enough to stay a news read.
    audio_tracks = [voice_audio]
    try:
        from modules.video_assembler import _get_music_track
        mp = _get_music_track(niche=NICHE)
        if mp and Path(mp).exists():
            bed = AudioFileClip(mp)
            if bed.duration < duration:
                from moviepy import concatenate_audioclips
                reps = int(duration // bed.duration) + 1
                bed = concatenate_audioclips([bed] * reps)
            audio_tracks.append(bed.subclipped(0, duration).with_volume_scaled(0.10))
            _log("music bed added")
    except Exception as e:
        _log(f"music skipped: {e}")

    video = video.with_audio(CompositeAudioClip(audio_tracks).with_duration(duration))

    out = work / "final.mp4"
    # Unique temp audio per build. MoviePy defaults to "<name>TEMP_MPY_wvf_snd"
    # beside the output, and with ten scheduled slots a day two builds can
    # overlap and fight over that file (WinError 32), killing one of them.
    _tmp_audio = str(work / f"_snd_{os.getpid()}.m4a")
    video.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac",
                          temp_audiofile=_tmp_audio,
                          preset="medium", threads=4, logger=None)
    for c in stills:
        c.close()
    voice_audio.close()
    _log(f"assembled (static, no zoom): {out}")
    return str(out)


def hook_from_title(title: str) -> str:
    """Squeeze a headline into a thumbnail hook.

    'Chiefs vs Sundowns: Da Cruz's Five-Injury Problem' -> "Da Cruz's
    Five-Injury Problem". Drops the fixture prefix and trailing punctuation
    but never cuts mid-phrase — the thumb engine shrinks to fit, so a clipped
    hook would just read as broken.
    """
    t = (title or "").strip()
    if ":" in t:
        t = t.split(":")[-1].strip() or t
    for sep in (" — ", " - "):
        if sep in t:
            t = t.split(sep)[0].strip() or t
    t = t.rstrip("?!.").strip()
    return t or "PSL"


def write_manifest(script: dict, video_path: str, work: Path, voice: dict, images: list | None = None, prediction: str = "", log_rows: list | None = None) -> Path:
    hashtags = NICHES[NICHE]["hashtags"]
    caption = script.get("caption") or script.get("title", "")

    # Reel cover. The old badge-first news_card read as dull at feed size —
    # busy, dark, headline too small to land (owner call 2026-08-18). Now the
    # thumb_engine look: photo edge-to-edge, ONE huge hook, fixed brand bug.
    # news_card stays as the fallback when there is no usable photo.
    thumb = str(work / "card_1.png")
    clubs = resolve_clubs(script.get("title", "") + " " + caption)
    bg, bg_credit = None, ""
    for img in images or []:
        if Path(img.get("path", "")).exists():
            bg, bg_credit = img["path"], img.get("credit", "")
            break
    kicker = CLUB_BRAND.get(clubs[0] if clubs else "", {}).get("name", "PSL")
    try:
        from modules.thumb_engine import make_reel_cover
        if bg:
            thumb = make_reel_cover(
                work / "cover.jpg",
                hook=hook_from_title(script.get("title", "")),
                kicker=kicker, photo=bg, brand="genesis", focus=0.5,
                # the crest is what a Chiefs fan sees first in a feed
                club=clubs[0] if clubs else "chiefs")
    except Exception as e:
        _log(f"thumb_engine cover skipped: {e}")
    if thumb == str(work / "card_1.png") and bg:
        try:
            from modules.news_card import make_news_card
            c = make_news_card(bg, work / "cover.png",
                               headline=script.get("title", ""), kicker=kicker,
                               credit=bg_credit, club=clubs[0] if clubs else "",
                               log_rows=log_rows or None, cover_mode=True,
                               big_crest=True)
            if c:
                thumb = c
        except Exception as e:
            _log(f"cover skipped: {e}")
    manifest = {
        "niche": NICHE,
        "format_type": "short",
        "is_short": True,
        "uploaded": False,
        "built_at": datetime.now().isoformat(),
        "video_path": str(video_path),
        "title": script.get("title", "PSL News"),
        "description": script.get("description") or caption,
        "caption": caption,
        "tags": [h.lstrip("#") for h in hashtags],
        "comment_hashtags": [],
        "srt_path": voice.get("subtitle_path", ""),
        "thumb_path": thumb,
        "prediction": prediction,
    }
    p = work / "upload_manifest.json"
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(f"manifest: {p}")
    return p


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="post to the Genesis News page after building")
    ap.add_argument("--topic", default="", help="force a specific story angle")
    args = ap.parse_args()

    from modules.psl_news import get_psl_briefing
    briefing = await get_psl_briefing()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(OUTPUT_DIR) / f"{NICHE}_short_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    if args.topic:
        topic = args.topic
        _log(f"topic forced by operator: {topic}")
        try:
            from modules.topic_generator import _record_topic
            _record_topic(NICHE, topic)
        except Exception:
            pass
    else:
        topic = await pick_topic()
    script = await write_script(topic)
    voice = await make_voice(script, work)
    images, cc_clip = await gather_images(script, briefing, work)
    if not images:
        raise RuntimeError("no usable images — refusing to build")
    # Live log + our score/scorer call — the extras that make a card shareable.
    log_rows, prediction = [], ""
    try:
        from modules.psl_standings import get_log
        log_rows = await get_log(6)
    except Exception as e:
        _log(f"standings skipped: {e}")
    try:
        prediction = await _make_prediction(script.get("title", ""), log_rows)
        if prediction:
            _log(f"prediction: {prediction}")
    except Exception as e:
        _log(f"prediction skipped: {e}")

    cards = build_cards(script, images, briefing, work, prediction, log_rows,
                        has_video=bool(cc_clip),
                        video_cards=(2 if (cc_clip and cc_clip.get("owner"))
                                     else (1 if cc_clip else 0)))
    video = await assemble(script, voice, cards, work, cc_clip=cc_clip,
                           log_rows=log_rows)
    write_manifest(script, video, work, voice, images, prediction, log_rows)

    _log("BUILD COMPLETE")
    if args.post:
        await post_to_page(work)
        _log("POST COMPLETE")


async def _story_comment(manifest: dict) -> str:
    """One seeded comment that debates THIS video's actual story.

    Gemini writes it from the title + narration; empty string on any failure
    so the caller falls back to the generic templates.
    """
    title = manifest.get("title", "")
    desc = (manifest.get("description") or "")[:400]
    if not title:
        return ""
    try:
        import os
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
        facts = ""
        try:
            from modules.psl_facts import facts_pack
            facts = await facts_pack()
        except Exception:
            pass
        prompt = (
            "You run Genesis News, a South African PSL football fan page. "
            "Write ONE first comment to pin under our own reel about this "
            "story:\n"
            f"TITLE: {title}\nSTORY: {desc}\n\n"
            + (f"LIVE LEAGUE FACTS (use ONE if it sharpens the question, "
               f"quote numbers exactly):\n{facts}\n\n" if facts else "")
            + "Rules: max 25 words, ask fans ONE specific question about THIS "
            "story (a player, a decision, a take) that starts an argument, "
            "sound like a fan not a brand, 1-2 emojis, end with 👇, no "
            "hashtags, no links. Reply with the comment text only."
        )
        r = client.models.generate_content(model="gemini-flash-lite-latest",
                                           contents=prompt)
        text = (r.text or "").strip().strip('"')
        if 10 < len(text) < 220:
            _log(f"story comment: {text[:60]}")
            return text
    except Exception as e:
        _log(f"story comment fallback: {str(e)[:80]}")
    return ""


def _seed_youtube_comments(video_id: str, story_comment: str):
    """Seed our opening comments on our OWN Short — same family-we-chat
    pattern as Facebook (owner 2026-08-17: 'I don't see the YouTube
    comment on reels and shorts')."""
    try:
        from modules.playlists import _yt
        yt = _yt()
        msgs = [m for m in (
            story_comment,
            "📲 Follow Genesis News on Facebook for lineups before kickoff "
            "and live matchday updates — search 'Genesis News PSL'. 🇿🇦⚽",
        ) if m]
        for m in msgs:
            yt.commentThreads().insert(part="snippet", body={
                "snippet": {"videoId": video_id, "topLevelComment": {
                    "snippet": {"textOriginal": m}}}}).execute()
        _log(f"YouTube comments seeded on {video_id} ({len(msgs)})")
    except Exception as e:
        _log(f"YouTube comment seed failed: {str(e)[:100]}")


async def post_to_page(work: Path) -> dict | None:
    """
    Post the built reel DIRECTLY to the Genesis News page (no YouTube/TikTok
    fan-out — this page is the product), then seed the comment section:
      1. an engagement comment (score prediction / opinion bait), and
      2. a follow CTA — first comments from the page lift reach and set the tone.
    """
    from modules.uploader_facebook import upload_to_facebook, post_comment
    from modules.club_brand import resolve_clubs, CLUB_BRAND

    mp = work / "upload_manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    if manifest.get("uploaded"):
        _log("already posted — skipping")
        return None

    fb = await upload_to_facebook(
        video_path=manifest["video_path"],
        title=manifest["title"],
        description=manifest["description"],
        niche=NICHE,
        hashtags=manifest.get("tags", []),
        is_reel=True,
        thumbnail_path=manifest.get("thumb_path"),
    )
    if fb.get("status") != "uploaded":
        _log(f"FB upload failed: {fb}")
        return fb

    post_id = fb.get("post_id")
    comment_target = fb.get("video_id") or post_id   # reels only accept comments on the video id
    try:
        from modules.playlists import add_facebook
        if fb.get("video_id"):
            add_facebook(fb["video_id"])
    except Exception as e:
        _log(f"fb playlist skipped: {e}")
    clubs = resolve_clubs(manifest.get("title", ""))
    names = [CLUB_BRAND.get(c, {}).get("name", c.title()) for c in clubs[:2]]
    pred = manifest.get("prediction", "")
    if pred:
        # our call, stated openly — the first comment IS the debate starter
        c1 = f"🔮 {pred}. Agree or are we dreaming? Drop YOUR scoreline 👇⚽"
    else:
        # STORY-SPECIFIC comment — written from the actual script so the
        # debate is about THIS video, not a generic score-prediction ask
        # (owner 2026-08-17: "make the reel comments relevant to the post")
        c1 = await _story_comment(manifest)
    if not c1:
        if len(names) == 2:
            c1 = (f"🔥 {names[0]} vs {names[1]} — drop your score prediction "
                  f"below! Best prediction gets a shoutout 👇⚽")
        elif names:
            c1 = (f"🔥 {names[0]} fans — where are you?! Rate this squad's "
                  f"chances below 👇⚽")
        else:
            c1 = "🔥 PSL family — what's your take? Drop it below 👇⚽"
    c2 = ("📲 Follow GENESIS NEWS for lineups before kickoff, full-time results "
          "and every big PSL story — Chiefs, Pirates, Sundowns and more. 🇿🇦⚽")
    c3 = ("▶️ More PSL videos on our YouTube channel — subscribe: "
          "https://www.youtube.com/@GenesisNewsPSL")

    for msg in (c1, c2, c3):
        await post_comment(comment_target, msg, NICHE)

    # YouTube Shorts — the rebranded Genesis News channel (@GenesisNewsPSL).
    # Guarded on the channel token so a missing token can never mispost.
    yt_id = ""
    if (Path("tokens") / f"youtube_token_{NICHE}.json").exists():
        try:
            from modules.uploader_youtube import upload_to_youtube
            yt = await upload_to_youtube(
                video_path=manifest["video_path"],
                title=manifest["title"],
                description=manifest["description"],
                tags=manifest.get("tags", []),
                niche=NICHE,
                thumbnail_path=manifest.get("thumb_path"),
                is_short=True,
                srt_path=manifest.get("srt_path"),
            )
            yt_id = (yt or {}).get("video_id", "")
            _log(f"YouTube: {yt.get('status')} {yt_id}")
            if yt_id:
                try:
                    from modules.playlists import add_youtube
                    add_youtube(yt_id, shorts=True)
                except Exception as e:
                    _log(f"playlist skipped: {e}")
                _seed_youtube_comments(yt_id, c1)
        except Exception as e:
            _log(f"YouTube upload failed: {e}")
    else:
        _log("YouTube skipped — no channel token")

    # TikTok + Instagram — same reel, two more audiences. Both best-effort:
    # a dead TikTok session or IG hiccup must never block the FB/YT post.
    try:
        from modules.uploader_tiktok import upload_to_tiktok
        tt = await upload_to_tiktok(
            video_path=manifest["video_path"],
            description=manifest.get("caption", manifest["title"])[:150],
            hashtags=manifest.get("tags", [])[:5], niche=NICHE)
        _log(f"TikTok: {(tt or {}).get('status')}")
    except Exception as e:
        _log(f"TikTok skipped: {e}")
    try:
        # Instagram needs THREE things, and it silently logged "failed" when
        # any were absent: cloud hosting for a public URL, a linked IG
        # business account, and a token carrying instagram_basic. Say which.
        if not (os.getenv("INSTAGRAM_USER_ID")
                and os.getenv("INSTAGRAM_ACCESS_TOKEN")):
            _log("Instagram: not configured — run setup_instagram.py "
                 "(account must be linked to the page first)")
            raise RuntimeError("instagram not configured")
        from modules.cloud_storage import is_cloud_storage_configured
        if is_cloud_storage_configured():
            from modules.uploader_instagram import upload_to_instagram_local
            from modules.cloud_storage import upload_to_cloud
            ig = await upload_to_instagram_local(
                video_path=manifest["video_path"],
                caption=manifest.get("caption", manifest["title"]),
                hashtags=manifest.get("tags", [])[:8],
                upload_to_cloud_fn=upload_to_cloud)
            _log(f"Instagram: {(ig or {}).get('status')}")
    except RuntimeError:
        pass                      # already logged with the exact reason
    except Exception as e:
        _log(f"Instagram skipped: {e}")

    manifest["uploaded"] = True
    manifest["fb_post_id"] = post_id
    manifest["youtube_id"] = yt_id
    mp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(f"posted + 2 comments: {post_id}")
    return fb


if __name__ == "__main__":
    # Never start behind a dead build: a music orphan held the GPU on
    # 23 and 24 Aug and froze this script at TTS both times, costing two
    # posting slots. Reap first, then wait for VRAM.
    try:
        from modules.gpu_guard import preflight
        preflight("build_psl_news.py")
    except Exception as _e:
        print(f"[GPUGuard] skipped: {_e}")
    os.environ.setdefault("FORCE_STILLS_ONLY", "true")
    os.environ.setdefault("DISABLE_RUNPOD_WAN", "true")
    try:
        asyncio.run(main())
    except Exception as e:
        # a build dying silently cost us two posting slots on 2026-08-16 —
        # the owner must KNOW the machine skipped a beat
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure("reel-build",
                           f"GENESIS BUILD FAILED: {type(e).__name__}: {str(e)[:150]}")
        except Exception:
            pass
        raise
