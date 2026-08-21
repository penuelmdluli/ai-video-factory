"""
Post one piece of owner footage as a Genesis reel.

For clips the owner sends that carry their own story — a passing move, a
save, a goal celebration. The hook ASKS rather than asserts: we do not count
passes ourselves, so we never state a number we have not verified. Inviting
the count is also the stronger engagement play on a page whose best posts are
all arguments.

    python build_owner_reel.py --video path\to\clip.mp4 --dry-run
    python build_owner_reel.py --video path\to\clip.mp4 --post
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

OUT = Path("output/owner_reel")
NICHE = "sa_pulse"

HOOK = "COUNT THE PASSES"
KICKER = "Chiefs v Sundowns"
NARRATION = (
    "Watch this Kaizer Chiefs move against Mamelodi Sundowns. "
    "Count the passes before the ball is lost. "
    "Drop your number in the comments — we want to see who gets it right. "
    "Subscribe to Genesis News, we post the moments everyone argues about."
)
CAPTION = (
    "⚽ COUNT THE PASSES — Chiefs v Sundowns\n\n"
    "One move, one question: how many passes before Chiefs lose the ball?\n\n"
    "Drop your number 👇 — we will settle it in the comments.\n\n"
    "#KaizerChiefs #Amakhosi #MamelodiSundowns #PSL #BetwayPremiership"
)


async def main(video: str, post: bool):
    src = Path(video)
    if not src.exists():
        print(f"[Owner] file not found: {src}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    from moviepy import (AudioFileClip, CompositeAudioClip,
                         CompositeVideoClip, VideoFileClip)
    from modules.thumb_engine import make_reel_cover
    from modules.voice_generator import generate_voice
    from PIL import Image

    clip = VideoFileClip(str(src))
    s = max(1080 / clip.w, 1920 / clip.h)
    fit = clip.resized(s)
    fit = fit.cropped(x_center=fit.w / 2, y_center=fit.h / 2,
                      width=1080, height=1920)
    print(f"[Owner] source {clip.w}x{clip.h} {clip.duration:.1f}s -> 1080x1920")

    # cover from a real frame of the move itself
    frame_at = min(1.5, max(0.2, clip.duration * 0.25))
    still = OUT / "frame.jpg"
    Image.fromarray(fit.get_frame(frame_at)).convert("RGB").save(still,
                                                                 quality=92)
    cover = make_reel_cover(OUT / "cover.jpg", hook=HOOK, kicker=KICKER,
                            chip="How many? 👇", photo=str(still),
                            brand="genesis", focus=0.5)

    v = await generate_voice(NARRATION, OUT, "owner_reel", "short", NICHE)
    audio = (v or {}).get("audio_path")
    out = OUT / "reel.mp4"
    final = CompositeVideoClip([fit], size=(1080, 1920))
    if audio:
        va = AudioFileClip(audio)
        # keep the crowd noise under the narration
        beds = [va] + ([fit.audio.with_volume_scaled(0.25)]
                       if fit.audio else [])
        final = final.with_audio(CompositeAudioClip(beds))
    final.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", logger=None)
    print(f"[Owner] reel: {out}")

    if not post:
        print("[Owner] built only — not posted")
        return 0

    from modules.uploader_facebook import post_comment, upload_to_facebook
    fb = await upload_to_facebook(video_path=str(out),
                                  title="Count the passes — Chiefs v Sundowns",
                                  description=CAPTION, niche=NICHE,
                                  is_reel=True, thumbnail_path=cover)
    print(f"[Owner] Facebook: {fb.get('status')} {fb.get('post_id')}")
    vid = fb.get("video_id") or fb.get("post_id")
    if vid and fb.get("status") == "uploaded":
        await post_comment(vid, "How many did you count? First correct "
                                "answer gets pinned 👇", NICHE)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.video, a.post and not a.dry_run)))
