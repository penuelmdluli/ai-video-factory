"""Podcast assembly — concat host talking-clips (cut between hosts), overlay name
lower-thirds + captions + music bed + subtle AI tag."""
from pathlib import Path

from PIL import Image, ImageDraw
from moviepy import (VideoFileClip, AudioFileClip, ImageClip, ColorClip, CompositeVideoClip,
                     CompositeAudioClip, concatenate_videoclips, concatenate_audioclips)

from assemble_full import _font, _duck, render_caption_png, render_tag_png


def _fit(c, W, H):
    """CONTAIN — fit the whole subject, never crop it. Square/other content sits
    centered on the reel canvas with graphics bands top/bottom (no cut visuals)."""
    scale = min(W / c.w, H / c.h)                       # contain (was max = cover/crop)
    fg = c.resized(scale).with_position(("center", "center"))
    bg = ColorClip(size=(W, H), color=(12, 14, 20)).with_duration(c.duration)
    return CompositeVideoClip([bg, fg], size=(W, H)).with_duration(c.duration)


def _name_png(name, W, path):
    font = _font(34)
    tw = ImageDraw.Draw(Image.new("RGBA", (10, 10))).textbbox((0, 0), name, font=font)[2]
    img = Image.new("RGBA", (tw + 60, 56), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, tw + 59, 55], radius=12, fill=(190, 30, 40, 230))
    d.rectangle([0, 0, 8, 55], fill=(255, 210, 60))
    d.text((22, 10), name, font=font, fill=(255, 255, 255))
    img.save(path); return path


def assemble_podcast(clips, music, out_dir, W, H, FPS, title="Podcast"):
    out_dir = Path(out_dir); tmp = out_dir / "_pod"; tmp.mkdir(parents=True, exist_ok=True)

    vclips, segs, t = [], [], 0.0
    for path, name, text in clips:
        c = _fit(VideoFileClip(str(path)), W, H)
        vclips.append(c)
        segs.append((t, t + c.duration, name, text))
        t += c.duration
    video = concatenate_videoclips(vclips, method="compose")
    vdur = video.duration

    # audio: dialogue (already in the clips) boosted + music bed under it
    tracks = [_duck(video.audio, 1.4)]
    if music and Path(music).exists():
        m = AudioFileClip(str(music))
        if m.duration < vdur:
            m = concatenate_audioclips([m] * (int(vdur / m.duration) + 1))
        tracks.append(_duck(m.subclipped(0, vdur), 0.12))
    video = video.with_audio(CompositeAudioClip(tracks))

    overlays = []
    for i, (s, e, name, text) in enumerate(segs):
        npng = _name_png(name, W, str(tmp / f"name_{i}.png"))
        overlays.append(ImageClip(npng).with_start(s).with_duration(e - s).with_position((int(W * 0.04), int(H * 0.78))))
        cpng = render_caption_png(text, W, str(tmp / f"cap_{i}.png"))
        overlays.append(ImageClip(cpng).with_start(s).with_duration(e - s).with_position(("center", int(H * 0.85))))
    tag = render_tag_png("AI", W, str(tmp / "tag.png"))
    overlays.append(ImageClip(tag).with_duration(vdur).with_position((int(W * 0.03), int(H * 0.03))))

    final = CompositeVideoClip([video] + overlays)
    out = out_dir / "podcast_final.mp4"
    # Temp audio beside this build, not in the repo root - this script imports
    # no modules.*, so modules/safe_render.py is not live here and it has to
    # scope the temp file itself. See the 2026-09-02 role-slot failure.
    final.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", bitrate="6000k",
                          threads=4, preset="medium",
                          temp_audiofile_path=str(out.parent),
                          ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    return out
