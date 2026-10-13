"""
Matchday countdown — the recurring format that gives people a reason to
come back before kick-off.

Runs several times a day, finds the next fixture worth counting down to, and
posts a countdown reel ONCE per fixture. Everything on screen comes from the
live fixture list: the clubs, the kick-off time, the real seconds remaining.

    python build_countdown.py            # post if a fixture is due
    python build_countdown.py --dry-run  # build only
    python build_countdown.py --force    # ignore the "already posted" state
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from modules.psl_fixtures import fixtures_for, priority, SAST  # noqa: E402

STATE = Path("data/countdown_posted.json")
OUT = Path("output/countdown")
WINDOW_HOURS = 26          # matchday and the evening before, no further
MIN_HOURS = 1.0            # too close to kick-off to be worth posting
# Shared page with the traderadar-ai engine: never post within this many minutes of ANY post on the page
# (owner 2026-10-13: quiet window + storylock apply across both pipelines). Game days use a short window.
QUIET_MIN = float(__import__("os").getenv("COUNTDOWN_QUIET_MIN", "45"))
LEAD_CLUB = "chiefs"       # Chiefs priority on Genesis News (owner 2026-10-12)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark(fid: str):
    st = _state()
    st[fid] = datetime.now().isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def _rank(f) -> tuple:
    return (priority(f), LEAD_CLUB in (f.get("home_key"), f.get("away_key")))


async def next_fixture(force: bool = False, club: str | None = None):
    """The most important fixture inside the window that we have not done."""
    now = datetime.now(SAST)
    done = {} if force else _state()      # --force also ignores the state
    best = None
    for dd in range(0, 3):
        for f in (await fixtures_for(now + timedelta(days=dd))) or []:
            ko = f.get("kickoff_iso")
            if not ko:
                continue
            try:
                when = datetime.fromisoformat(ko)
            except ValueError:
                continue
            hours = (when - now).total_seconds() / 3600
            if not (MIN_HOURS <= hours <= WINDOW_HOURS):
                continue
            if f.get("id") in done:
                continue
            if club and club not in (f.get("home_key"), f.get("away_key")):
                continue
            try:  # a game the covered game-day fixture outranks gets no pre-match volume (Chiefs priority)
                from modules.page_guard import gameday_owns
                if gameday_owns(f.get("id"), "prematch"):
                    continue
            except Exception:
                pass
            # Extra volume belongs on OUR game days. A countdown to two clubs
            # our audience does not follow is just another post competing
            # with the three daily reels for the same reach.
            if priority(f) < 1:
                continue
            if best is None or _rank(f) > _rank(best[0]):
                best = (f, when)
    return best


async def build_and_post(dry=False, force=False, club=None, no_quiet=False):
    got = await next_fixture(force, club)
    if not got:
        print("[Countdown] no fixture due in the window — nothing to post")
        return 1
    f, when = got
    now = datetime.now(SAST)
    secs = int((when - now).total_seconds())
    hrs = secs / 3600
    ko_txt = when.strftime("%a %d %b %H:%M")
    print(f"[Countdown] {f['home']} v {f['away']} — kick-off {ko_txt} "
          f"({hrs:.1f}h away)")

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"countdown_{f['id']}.mp4"

    from modules.motion_kit import countdown
    from modules.voice_generator import generate_voice
    from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
    short = (lambda n: n.replace("Mamelodi ", "").replace("Orlando ", "")
             .replace("Kaizer ", "").replace(" FC", "").upper())

    venue = f.get("venue") or ""
    if not dry and not no_quiet:
        from modules.page_guard import quiet_ok
        if not quiet_ok("sa_pulse", QUIET_MIN):
            print("[Countdown] quiet window - the next countdown slot retries")
            return 3
    # The 2026-10-12 countdown that reached ~14k plays (median reel ~360) is the template: ~14 s, crest VS card,
    # live clock, ONE fan question up front. 2026-10-13: the question is now on screen in the first 3 s and the
    # first caption line, captions are burned in, and the TradeRadar soft line closes the voice before the card.
    sh_home, sh_away = short(f["home"]).title(), short(f["away"]).title()
    hook = f"{short(f['home'])} OR {short(f['away'])}? PREDICT THE SCORE"
    same_day = when.date() == now.date()
    day_word = ("tonight" if when.hour >= 17 else "today") if same_day else when.strftime("%A")
    call = (f"Predict the score! {f['home']} against {f['away']}, {day_word} at {when.strftime('%H:%M')}"
            + (f", {venue}. " if venue else ". ")
            + "Drop your score in the comments. "
            + "And protect your trading account: free tools at gettraderadar.com.")

    # VOICE FIRST, then size the animation to it. Rendering a fixed 7s clip
    # and attaching a 15s narration cut the voice off mid-sentence.
    v = await generate_voice(call, OUT, f"countdown_{f['id']}", "short",
                             "sa_pulse")
    audio_p = (v or {}).get("audio_path")
    vdur = AudioFileClip(audio_p).duration if audio_p else 7.0
    print(f"[Countdown] narration {vdur:.1f}s — timer runs the full length")

    from modules.motion_kit import srt_caption_groups
    caps = srt_caption_groups((v or {}).get("subtitle_path") or "", 3)
    clip = countdown(out,
                     title=f"{short(f['home'])} VS {short(f['away'])}",
                     when=when.strftime("%A %d %B · %H:%M").upper(),
                     clubs=(f.get("home_key") or "chiefs",
                            f.get("away_key") or "pirates"),
                     start_secs=secs, duration=vdur + 1.0,
                     hook=hook, captions=caps)

    voiced = str(out).replace(".mp4", "_voiced.mp4")
    if audio_p:
        (VideoFileClip(str(clip))
         .with_audio(CompositeAudioClip([AudioFileClip(audio_p)]))
         .write_videofile(voiced, fps=30, codec="libx264",
                          audio_codec="aac", logger=None))
    else:
        voiced = str(clip)

    if dry:
        print(f"[Countdown] dry run — {voiced}")
        return 0

    from modules.uploader_facebook import upload_to_facebook, post_comment
    cap = (f"{sh_home} or {sh_away}? Predict the score 👇⚽\n\n"
           f"⏳ COUNTDOWN — {f['home']} VS {f['away']}\n"
           f"{when:%A %d %B} · {when:%H:%M}"
           + (f" · {venue}" if venue else "")
           + "\n\n#PSL #BetwayPremiership #KaizerChiefs #OrlandoPirates "
             "#MamelodiSundowns")
    fb = await upload_to_facebook(video_path=voiced,
                                  title=f"Countdown: {f['home']} VS {f['away']}",
                                  description=cap, niche="sa_pulse",
                                  is_reel=True)
    vid = fb.get("video_id") or fb.get("post_id")
    print(f"[Countdown] Facebook: {fb.get('status')} {vid}")
    if vid and fb.get("status") == "uploaded":
        await post_comment(vid, "Score prediction? Winner gets the bragging "
                                "rights in the replies 👇", "sa_pulse")
    try:
        from modules.uploader_youtube import upload_to_youtube
        yt = await upload_to_youtube(
            video_path=voiced,
            title=f"Countdown: {f['home']} VS {f['away']} #Shorts"[:95],
            description=cap, tags=["PSL", "countdown", f["home"], f["away"]],
            niche="sa_pulse", is_short=True, privacy="public")
        print(f"[Countdown] YouTube: {yt.get('video_id')}")
    except Exception as e:
        print(f"[Countdown] youtube skipped: {str(e)[:120]}")

    try:
        from modules.page_guard import claim
        claim("sa_pulse", f"Countdown {f['home']} vs {f['away']}", "countdown", slug=f"countdown-{f['id']}")
    except Exception:
        pass
    if not force:
        _mark(f["id"])
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--club", help="only this club's fixture (e.g. chiefs)")
    ap.add_argument("--no-quiet", action="store_true", help="skip the shared-page quiet window (hand runs)")
    a = ap.parse_args()
    sys.exit(asyncio.run(build_and_post(a.dry_run, a.force, a.club, a.no_quiet)))
