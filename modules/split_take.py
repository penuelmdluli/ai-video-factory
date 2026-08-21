"""
Split-take — the clip on top, our analysis underneath.

The format that lets a page build on footage without simply reposting it:
the top of the frame plays a short excerpt, the bottom carries Genesis
branding and our actual reading of the moment, timed so each point lands
while the relevant thing is on screen.

That split IS the transformation — the viewer is watching our analysis, with
the clip as evidence, rather than watching someone else's video with a
caption bolted on. The source is credited on screen throughout.
"""
import numpy as np
from PIL import Image, ImageDraw

from modules.motion_kit import _ease, _font

W, H = 1080, 1920
TOP_Y, TOP_H = 150, 1000            # where the clip plays
GOLD = (255, 200, 0)
INK = (10, 12, 16)


def _wrap(d, text, font, max_w):
    words, line, out = text.split(), "", []
    for w in words:
        t = (line + " " + w).strip()
        if d.textlength(t, font=font) <= max_w:
            line = t
        else:
            out.append(line)
            line = w
    out.append(line)
    return [x for x in out if x]


def panel_clip(hook, points, credit, duration, kicker="GENESIS ANALYSIS"):
    """The branded lower panel: hook, then each point as it becomes relevant."""
    from moviepy import VideoClip

    def draw(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im, "RGBA")

        # masthead above the clip
        d.rectangle([0, 0, W, TOP_Y], fill=(*INK, 250))
        d.text((44, 34), "GENESIS NEWS", font=_font(44), fill=(255, 255, 255))
        d.text((46, 92), kicker, font=_font(26, False), fill=GOLD)

        # analysis panel below the clip
        py = TOP_Y + TOP_H
        d.rectangle([0, py, W, H], fill=(*INK, 252))
        d.rectangle([0, py, W, py + 6], fill=GOLD)

        hf = _font(70)
        hy = py + 46
        for ln in _wrap(d, hook.upper(), hf, W - 90)[:2]:
            d.text((46, hy), ln, font=hf, fill=(255, 255, 255))
            hy += 78

        # points appear one at a time, spread across the clip
        step = max(1.6, (duration - 2.0) / max(1, len(points)))
        y = hy + 26
        pf = _font(38, False)
        for i, p in enumerate(points):
            u = _ease(min(1, max(0, (t - (1.2 + i * step)) / 0.4)))
            if u <= 0:
                continue
            d.rectangle([46, y + 8, 46 + int(8 * u), y + 44], fill=GOLD)
            for ln in _wrap(d, p, pf, W - 130)[:2]:
                d.text((70, y), ln, font=pf,
                       fill=(int(235 * u), int(238 * u), int(242 * u)))
                y += 46
            y += 16

        if credit:
            cf = _font(22, False)
            d.text((46, H - 52), credit, font=cf, fill=(150, 156, 164))
        return im

    def frame(t):
        return np.array(draw(t).convert("RGB"))

    def mask(t):
        return np.array(draw(t).split()[-1]).astype(float) / 255.0

    c = VideoClip(frame, duration=duration)
    c.mask = VideoClip(mask, duration=duration, is_mask=True)
    return c


def build(video_path, out_path, hook, points, credit, narration=None,
          start=0.0, length=None, kicker="GENESIS ANALYSIS"):
    """Compose the split take. Returns the output path."""
    from moviepy import CompositeVideoClip, VideoFileClip

    src = VideoFileClip(str(video_path))
    end = min(src.duration, start + (length or src.duration))
    clip = src.subclipped(start, end)

    # fill the top window without letterboxing
    s = max(W / clip.w, TOP_H / clip.h)
    fit = clip.resized(s)
    fit = fit.cropped(x_center=fit.w / 2, y_center=fit.h / 2,
                      width=W, height=TOP_H).with_position((0, TOP_Y))

    dur = fit.duration
    panel = panel_clip(hook, points, credit, dur, kicker)
    layers = [fit.with_start(0), panel.with_start(0)]
    final = CompositeVideoClip(layers, size=(W, H)).with_duration(dur)

    if narration:
        from moviepy import AudioFileClip, CompositeAudioClip
        beds = [AudioFileClip(narration)]
        if fit.audio:
            beds.append(fit.audio.with_volume_scaled(0.22))
        final = final.with_audio(CompositeAudioClip(beds))

    final.write_videofile(str(out_path), fps=30, codec="libx264",
                          audio_codec="aac", logger=None)
    return str(out_path)
