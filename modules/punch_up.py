"""Cinematic punch-up for Veo episodes — the $0 edit layer that kills the "static/boring" feel:
bold captions of each spoken line (retention + works muted), whoosh SFX on every cut, and a low
tension music bed. Takes the raw Veo shot clips + the line per shot; returns a punched-up video.
"""
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from modules.thumbnail_pro import _font


def _caption_png(line, W, H, out):
    img = Image.new("RGBA", (W, int(H * 0.20)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = int(W * 0.060)
    f = _font(fs, "news")
    words, lines, cur = line.split(), [], []
    for w in words:
        if d.textlength(" ".join(cur + [w]), font=f) <= W * 0.9 or not cur:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    if cur:
        lines.append(cur)
    lines = lines[:2]
    lh = int(fs * 1.15)
    y0 = (img.height - lh * len(lines)) // 2
    ow = max(3, int(fs * 0.09))
    for li, ln in enumerate(lines):
        s = " ".join(ln)
        lw = d.textlength(s, font=f)
        x = (W - lw) // 2
        y = y0 + li * lh
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1):
                if dx * dx + dy * dy <= ow * ow:
                    d.text((x + dx, y + dy), s, font=f, fill=(0, 0, 0, 240))
        d.text((x, y), s, font=f, fill=(255, 255, 255, 255))
    img.save(out)
    return out


def punch_up(clip_paths, lines, out_path, music=None, W=1080, H=1920, fps=24):
    """Concat the Veo clips, overlay a bold caption per shot, add a tension music bed + whoosh SFX
    on every cut. Returns out_path."""
    from moviepy import (VideoFileClip, concatenate_videoclips, ImageClip, AudioFileClip,
                         CompositeVideoClip, CompositeAudioClip, afx)
    work = Path(tempfile.mkdtemp(prefix="punch_"))
    clips = [VideoFileClip(c) for c in clip_paths]
    base = concatenate_videoclips(clips, method="compose")
    total = base.duration

    overlays, cut_times, t = [], [], 0.0
    for i, c in enumerate(clips):
        dur = c.duration
        line = lines[i] if i < len(lines) else None
        if line:
            png = _caption_png(line, W, H, str(work / f"cap_{i}.png"))
            overlays.append(ImageClip(png).with_start(t + 0.25)
                            .with_duration(max(0.5, dur - 0.45))
                            .with_position(("center", int(H * 0.72))))
        if i > 0:
            cut_times.append(t)
        t += dur

    final = CompositeVideoClip([base] + overlays, size=(W, H)) if overlays else base
    tracks = [base.audio] if base.audio is not None else []
    if music and Path(music).exists():
        try:
            tracks.append(AudioFileClip(music).with_effects([
                afx.AudioLoop(duration=total), afx.MultiplyVolume(0.09),
                afx.AudioFadeIn(0.4), afx.AudioFadeOut(0.8)]))
        except Exception:
            pass
    if len(tracks) > 1:
        final = final.with_audio(CompositeAudioClip(tracks))

    base_out = work / "punched_base.mp4"
    final.write_videofile(str(base_out), fps=fps, codec="libx264", audio_codec="aac",
                          preset="veryfast", logger=None)
    for c in clips:
        try:
            c.close()
        except Exception:
            pass

    # whoosh SFX on every cut, mixed via ffmpeg (channel-safe)
    out_path = str(out_path)
    try:
        from modules.sfx_synth import arrays as sfx_arrays, SR, write_stereo_wav
        wh = sfx_arrays()["whoosh"]
        buf = np.zeros(int(total * SR) + SR, dtype="float32")
        for ct in cut_times:
            off = int(max(0.0, ct - 0.08) * SR)
            end = min(len(buf), off + len(wh))
            if end > off:
                buf[off:end] += wh[:end - off] * 0.45
        sfx_wav = write_stereo_wav(str(work / "sfx.wav"), buf)
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff, "-y", "-i", str(base_out), "-i", sfx_wav, "-filter_complex",
                        "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", out_path],
                       capture_output=True)
        if not (Path(out_path).exists() and Path(out_path).stat().st_size > 10000):
            import shutil
            shutil.copy(str(base_out), out_path)
    except Exception:
        import shutil
        shutil.copy(str(base_out), out_path)
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    return out_path
