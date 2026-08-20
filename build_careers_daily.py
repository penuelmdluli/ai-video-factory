"""
Mzansi Careers daily runner — one verified opportunity per slot.

Pulls the next employer due from the feed, renders the reel and the card, and
publishes. If nothing verifies this slot it posts NOTHING and says so: an
empty slot costs us a view, a wrong post costs us the page's whole promise.

    python build_careers_daily.py            # build + post one opportunity
    python build_careers_daily.py --dry-run  # build assets only
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from build_careers_post import publish                    # noqa: E402
from modules.careers_feed import next_opportunity         # noqa: E402
from modules.careers_kit import job_alert                 # noqa: E402

OUT = Path("output")


def _closing(op):
    """(label, days_left) from the source's own closing date, or ('', None).

    Never invented: if the source states no date the countdown stays off.
    """
    from datetime import datetime, date
    raw = (op.get("closes") or "").strip()
    if not raw:
        return "", None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            d = datetime.strptime(raw, fmt).date()
            return raw.upper(), max(0, (d - date.today()).days)
        except ValueError:
            continue
    return raw.upper(), None


async def make_reel(op) -> str | None:
    """Voiced job alert for this opportunity."""
    from modules.voice_generator import generate_voice
    from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
    lines = " ".join(op["card_details"][:3])
    narr = (f"Opportunity alert, Mzansi. {op['employer'].title()} — "
            f"{op['programme']}. {lines} "
            "The official link is in the comments. "
            "Follow Mzansi Careers. We only share what we verify.")
    work = OUT / f"careers_{op['key']}"
    work.mkdir(parents=True, exist_ok=True)
    v = await generate_voice(narr, work, "voiceover", "short", "motivation")
    if not v:
        return None
    audio = v.get("audio_path") if isinstance(v, dict) else v
    dur = AudioFileClip(str(audio)).duration
    # The circular publishes a real closing date, so show the countdown.
    closes, days = _closing(op)

    # Genesis Studio reel first: the position count is the hook and the type
    # cannot overflow. PIL job_alert stays as the fallback so a renderer
    # problem never stops a verified opportunity going out.
    silent = None
    try:
        from modules.studio import render_video, stage_asset, available
        if available():
            silent = render_video("JobReel", {
                "employer": op["employer"],
                "role": op["programme"],
                "positions": op.get("positions", 1),
                "details": op["card_details"],
                "closes": (f"CLOSES {closes}" if closes else ""),
                "entryLevel": bool(op.get("no_degree")),
                "source": op.get("source", ""),
                "photo": (stage_asset(op["bg_photo"])
                          if op.get("bg_photo") else None),
                "durationInSeconds": round(dur + 1.4, 2),
            }, work / "alert_studio.mp4")
            if silent:
                print(f"[Careers] reel: Genesis Studio ({dur + 1.4:.1f}s)")
    except Exception as e:
        print(f"[Careers] studio reel skipped: {e}")

    if not silent:
        silent = job_alert(work / "alert.mp4", employer=op["employer"],
                           programme=op["programme"],
                           details=op["reel_details"], closes=closes,
                           days_left=days,
                           source=op["source"], duration=dur + 1.4)
        print("[Careers] reel: PIL fallback")
    out = work / "reel.mp4"
    (VideoFileClip(str(silent))
     .with_audio(CompositeAudioClip([AudioFileClip(str(audio))]))
     .write_videofile(str(out), fps=30, codec="libx264",
                      audio_codec="aac", logger=None))
    return str(out)


async def run(dry=False):
    op = next_opportunity()
    if not op:
        print("[Careers] nothing verified this slot — posting nothing")
        return 1
    print(f"[Careers] {op['employer']} — {len(op['card_details'])} verified "
          f"lines from {op['apply_url']}")
    reel = await make_reel(op)
    if dry:
        print(f"[Careers] dry run — reel at {reel}")
        return 0
    await publish(op, reel)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(run(ap.parse_args().dry_run)))
