#!/usr/bin/env python
"""AI NEWS ANCHOR (hybrid flagship) — the best of both:

  * a realistic Veo 3 anchor delivers the day's REAL trending hook (native audio, "is this real?")
  * our $0 engine carries the story body with maps / stats / keyword graphics (af_heart voice)
  * branded engagement pack, then posted to Tech Pulse Africa

Cost ~ one Veo shot (~$1.20 on veo3_fast) — realism where it counts, graphics for the rest.
Facts come from the grounded news brain; Veo provides an illustrative presenter, never fake
footage of real events.

  python make_news_anchor.py            # build (no post) so you can review
  python make_news_anchor.py --post     # build + post to Tech Pulse
  python make_news_anchor.py --model veo3 --resolution 1080p   # max anchor quality
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

W, H, FPS = 1080, 1920, 30


def anchor_prompt(hook):
    return ("Photorealistic professional television news anchor, waist-up, seated at a sleek modern "
            "news desk in a high-end broadcast studio, soft glowing screens bokeh behind, looking "
            "directly into the camera with calm confident delivery, broadcast studio lighting, "
            "shallow depth of field, cinematic 4k. The anchor says clearly and naturally: "
            f'"{hook}"')


def concat_scaled(clips, out):
    """Scale/pad every clip to WxH and concat (keeps audio from each)."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs = []
    for c in clips:
        inputs += ["-i", c]
    n = len(clips)
    filt = []
    for i in range(n):
        filt.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v{i}]")
    concat = "".join(f"[v{i}][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    fc = ";".join(filt) + ";" + concat
    subprocess.run([ff, "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", out], capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--model", default="veo3_lite", choices=["veo3_lite", "veo3_fast", "veo3"])
    ap.add_argument("--resolution", default="720p", choices=["720p", "1080p"])
    a = ap.parse_args()

    from modules.veo_kie import generate_veo, check_key
    if not check_key():
        print("KIE_API_KEY not set — add it to .env (https://kie.ai).", flush=True)
        return

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"anchor_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    print("=== AI NEWS ANCHOR (Veo hero + $0 graphics body) ===", flush=True)

    from news_topic_generator import get_fresh_topic, log_posted
    pkg = get_fresh_topic()
    pkg["niche"] = "tech_news"
    hook = pkg.get("hook_line") or pkg.get("title", "Breaking news")
    print(f"  TOPIC: {pkg.get('title')}\n  HOOK: {hook}", flush=True)

    # 1. Veo anchor hero shot delivering the real hook
    anchor = out / "anchor.mp4"
    try:
        generate_veo(anchor_prompt(hook), str(anchor), model=a.model, aspect="9:16",
                     resolution=a.resolution, duration=8)
    except Exception as e:
        print(f"  anchor shot FAILED: {e}", flush=True)
        return

    # 2. graphics body from the rest of the narration (drop the hook beat — anchor said it)
    from modules.beats import build_beats
    from modules.synced_reel import make_synced_reel
    beats = build_beats(pkg, handle="Tech Pulse Africa")
    body_beats = beats[1:] if len(beats) > 2 else beats     # drop hook, keep body + outro
    body = out / "body.mp4"
    music = ROOT / "assets" / "ai_music_cache" / "bgm_tech_news.mp3"
    r = make_synced_reel(body_beats, str(body), size=(W, H), accent="#FF3131", fps=FPS,
                         breaking=True, label="BREAKING", handle="TechPulseAfrica", follow=True,
                         comment_prompt=pkg.get("comment_prompt", "What do you think?"),
                         niche="tech_news", music=str(music) if music.exists() else None)
    if not r:
        print("  body render failed", flush=True)
        return
    print(f"  body -> {r['path']} ({r['duration']:.1f}s)", flush=True)

    # 3. stitch anchor hero + graphics body
    final = out / "news_anchor.mp4"
    concat_scaled([str(anchor), r["path"]], str(final))
    print(f"  BUILT -> {final}", flush=True)

    if not a.post:
        print("  (not posting — review it; re-run with --post to publish)", flush=True)
        return

    import asyncio
    from modules.uploader_facebook import upload_to_facebook
    desc = pkg.get("caption", pkg.get("title", "")) + "\n\n\U0001F3AC AI-generated visualization"
    res = asyncio.run(upload_to_facebook(video_path=str(final), title=pkg.get("title", ""),
                                         description=desc, niche="tech_news",
                                         hashtags=["Africa", "News", "Breaking", "Reels", "AIgenerated"],
                                         is_reel=True))
    print("  POST:", res, flush=True)
    if isinstance(res, dict) and res.get("status") == "uploaded":
        log_posted(pkg)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
