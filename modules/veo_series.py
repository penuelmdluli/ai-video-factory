"""Frame-chained Veo episodes — director-level continuity.

Shot 0 locks the cast to a reference image (REFERENCE_2_VIDEO). Every later shot starts from the
LAST FRAME of the previous shot (image-to-video), so the background, lighting, and character
positions carry over seamlessly — it flows like one continuous scene instead of independent clips.
"""
import subprocess
from pathlib import Path

import imageio_ffmpeg

from modules.veo_kie import generate_veo, upload_image


def _last_frame(video, out_png):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-sseof", "-0.15", "-i", video, "-update", "1", "-frames:v", "1",
                    out_png], capture_output=True)
    if not Path(out_png).exists():   # fallback: first-pass decode
        subprocess.run([ff, "-y", "-i", video, "-vf", "select='eq(n\\,0)'", "-frames:v", "1",
                        out_png], capture_output=True)
    return out_png


def build_chained_episode(prompts, cast_image, out_dir, model="veo3_lite", resolution="720p",
                          duration=8, aspect="9:16", start_image=None):
    """Generate a frame-chained episode. Returns the list of shot clip paths (in order).
    If `start_image` is given (e.g. the last frame of the previous EPISODE), shot 0 continues
    from it (cross-episode continuity); otherwise shot 0 locks the cast via REFERENCE_2_VIDEO."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cast_url = upload_image(str(cast_image))
    start_url = upload_image(str(start_image)) if start_image else None
    clips = []
    prev_frame_url = None
    for i, prompt in enumerate(prompts):
        c = str(out_dir / f"shot_{i}.mp4")
        try:
            if i == 0 and start_url:
                generate_veo(prompt, c, model=model, aspect=aspect, resolution=resolution,
                             duration=duration, image_urls=[start_url])
            elif i == 0:
                generate_veo(prompt, c, model=model, aspect=aspect, resolution=resolution,
                             duration=duration, image_urls=[cast_url],
                             generation_type="REFERENCE_2_VIDEO")
            else:
                # continue from the previous shot's last frame -> same background + positions
                generate_veo(prompt, c, model=model, aspect=aspect, resolution=resolution,
                             duration=duration, image_urls=[prev_frame_url])
            clips.append(c)
        except Exception as e:
            print(f"[series] shot {i} failed: {e}", flush=True)
            if i == 0:
                return clips
            break
        if i < len(prompts) - 1:
            fp = _last_frame(c, str(out_dir / f"frame_{i}.png"))
            try:
                prev_frame_url = upload_image(fp)
            except Exception as e:
                print(f"[series] frame upload {i} failed ({e}) — stopping chain", flush=True)
                break
    return clips
