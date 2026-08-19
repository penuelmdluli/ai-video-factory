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
WINDOW_HOURS = 30          # how far ahead we are willing to count down
MIN_HOURS = 1.0            # too close to kick-off to be worth posting


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


async def next_fixture():
    """The most important fixture inside the window that we have not done."""
    now = datetime.now(SAST)
    done = _state()
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
            if best is None or priority(f) > priority(best[0]):
                best = (f, when)
    return best


async def build_and_post(dry=False, force=False):
    got = await next_fixture()
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

    from modules.motion_kit import countdown, attach_voice
    short = (lambda n: n.replace("Mamelodi ", "").replace("Orlando ", "")
             .replace("Kaizer ", "").replace(" FC", "").upper())
    clip = countdown(out,
                     title=f"{short(f['home'])} v {short(f['away'])}",
                     when=when.strftime("%A %d %B · %H:%M").upper(),
                     clubs=(f.get("home_key") or "chiefs",
                            f.get("away_key") or "pirates"),
                     start_secs=secs, duration=7.0)

    venue = f.get("venue") or ""
    call = (f"{f['home']} against {f['away']}. "
            f"Kick-off {when:%A} at {when:%H:%M}"
            + (f", at {venue}. " if venue else ". ")
            + "Who takes it? Drop your score in the comments. "
              "Subscribe to Genesis News — we call every game before kick-off.")
    voiced = await attach_voice(str(clip), call,
                                str(out).replace(".mp4", "_voiced.mp4"))

    if dry:
        print(f"[Countdown] dry run — {voiced}")
        return 0

    from modules.uploader_facebook import upload_to_facebook, post_comment
    cap = (f"⏳ COUNTDOWN — {f['home']} v {f['away']}\n"
           f"{when:%A %d %B} · {when:%H:%M}"
           + (f" · {venue}" if venue else "")
           + "\n\nYour score prediction 👇⚽\n"
             "#PSL #BetwayPremiership #KaizerChiefs #OrlandoPirates "
             "#MamelodiSundowns")
    fb = await upload_to_facebook(video_path=voiced,
                                  title=f"Countdown: {f['home']} v {f['away']}",
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
            title=f"Countdown: {f['home']} v {f['away']} #Shorts"[:95],
            description=cap, tags=["PSL", "countdown", f["home"], f["away"]],
            niche="sa_pulse", is_short=True, privacy="public")
        print(f"[Countdown] YouTube: {yt.get('video_id')}")
    except Exception as e:
        print(f"[Countdown] youtube skipped: {str(e)[:120]}")

    if not force:
        _mark(f["id"])
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    sys.exit(asyncio.run(build_and_post(a.dry_run, a.force)))
