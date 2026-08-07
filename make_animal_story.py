#!/usr/bin/env python
"""$0 talking-animal story prototype.

Cast portraits + distinct character voices + witty dialogue + captions + quick cuts + music + SFX
+ an audio-reactive "talking" motion (the image leans/zooms on speech). Realistic lip-sync comes
later via serverless (LivePortrait animal mode / a paid talking-animal API); this proves the
concept: characters, voices, comedy, editing — all local, ~$0.

    python make_animal_story.py
"""
import asyncio
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
ANIM = ROOT / "assets" / "animals"

W, H, FPS = 1080, 1920, 30

CAST = {
    "lion":   {"img": "lion.png",   "name": "LION",   "emoji": "\U0001F981", "voice": "am_onyx", "accent": (224, 164, 0)},
    "tiger":  {"img": "tiger.png",  "name": "TIGER",  "emoji": "\U0001F42F", "voice": "am_adam", "accent": (255, 122, 26)},
    "rabbit": {"img": "rabbit.png", "name": "RABBIT", "emoji": "\U0001F430", "voice": "af_sky",  "accent": (150, 200, 255)},
}

TITLE = "IF ANIMALS COULD TALK…"
SCRIPT = [
    ("lion",   "Explain something to me about the humans."),
    ("lion",   "Every morning they wake and stare at a small glowing rectangle."),
    ("rabbit", "Before water! Before anything! Every single morning!"),
    ("tiger",  "It tells them how to feel about the day. And they obey it."),
    ("lion",   "We rule by strength. They are ruled by a rectangle."),
    ("rabbit", "Sometimes they talk to it... and it talks back!"),
    ("tiger",  "The strongest human has the most followers."),
    ("lion",   "Followers? A lion has a pride. What is a follower?"),
    ("rabbit", "I do not think they know either."),
]


def _font(sz):
    from modules.thumbnail_pro import _font as pf
    return pf(sz, "news")


def _crop_fill(img):
    s = max(W / img.width, H / img.height)
    im = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((l, t, l + W, t + H))


def _prep_base(path):
    """Crop-fill to 9:16 and darken the bottom for caption legibility."""
    base = _crop_fill(Image.open(path).convert("RGB")).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    band = int(H * 0.42)
    for i in range(band):
        y = H - band + i
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(210 * (i / band))))
    return Image.alpha_composite(base, ov).convert("RGB")


def _outline(d, xy, text, f, fill, ow, oc=(8, 10, 14)):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=f, fill=oc + (fill[3],) if len(oc) == 3 else oc)
    d.text((x, y), text, font=f, fill=fill)


def _caption_png(text, out):
    img = Image.new("RGBA", (W, int(H * 0.22)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = int(W * 0.064)
    f = _font(fs)
    words, lines, cur = text.split(), [], []
    for w in words:
        if d.textlength(" ".join(cur + [w]), font=f) <= W * 0.86 or not cur:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    if cur:
        lines.append(cur)
    lines = lines[:2]
    lh = int(fs * 1.15)
    y0 = (img.height - lh * len(lines)) // 2
    ow = max(3, int(fs * 0.07))
    for li, ln in enumerate(lines):
        s = " ".join(ln)
        lw = d.textlength(s, font=f)
        _outline(d, ((W - lw) // 2, y0 + li * lh), s, f, (255, 255, 255, 255), ow)
    img.save(out)
    return out


def _label_png(c, out):
    fs = int(W * 0.052)
    f = _font(fs)
    from modules.emoji_util import render_emoji
    em = render_emoji(c["emoji"], px=int(fs * 1.25))
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(c["name"], font=f)
    pad = int(fs * 0.55)
    esz = int(fs * 1.15)
    w = int(pad * 2 + (esz + int(fs * 0.35) if em else 0) + tw)
    h = int(fs * 1.7)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ac = c["accent"]
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=(ac[0], ac[1], ac[2], 240))
    x = pad
    if em:
        em = em.resize((esz, esz), Image.LANCZOS)
        img.paste(em, (x, (h - esz) // 2), em)
        x += esz + int(fs * 0.35)
    d.text((x, (h - fs) // 2 - int(fs * 0.08)), c["name"], font=f, fill=(15, 15, 18, 255))
    img.save(out)
    return out


def _envelope(audio_clip):
    """Per-frame (fps) loudness envelope 0..1 from the voice, smoothed — drives the talk motion."""
    try:
        snd = audio_clip.to_soundarray(fps=FPS)
        if snd.ndim > 1:
            snd = snd.mean(axis=1)
        n = len(snd)
        win = max(1, n // max(1, int(audio_clip.duration * FPS)))
        env = np.sqrt(np.convolve(snd ** 2, np.ones(win) / win, mode="same"))
        env = env[:: max(1, win)]
        env = env / (env.max() + 1e-6)
        # smooth
        k = 3
        env = np.convolve(env, np.ones(k) / k, mode="same")
        return env
    except Exception:
        return np.zeros(int(audio_clip.duration * FPS) + 2)


def build():
    from moviepy import (ImageClip, AudioFileClip, CompositeVideoClip,
                         concatenate_videoclips, CompositeAudioClip, afx)
    from modules.voice_generator import generate_voice_kokoro

    stamp = time.strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"animals_{stamp}"
    work.mkdir(parents=True, exist_ok=True)
    print("=== TALKING ANIMAL STORY ($0 prototype) ===", flush=True)

    # prep bases + labels once per character
    bases, labels = {}, {}
    for k, c in CAST.items():
        p = ANIM / c["img"]
        if not p.exists():
            raise SystemExit(f"missing cast image: {p}")
        bp = work / f"base_{k}.png"; _prep_base(str(p)).save(bp); bases[k] = str(bp)
        labels[k] = _label_png(c, str(work / f"label_{k}.png"))

    clips, beat_marks, tcur = [], [], 0.0

    # intro title card over the lion
    intro_dur = 1.9
    intro_cap = work / "intro_cap.png"
    _caption_png(TITLE, intro_cap)
    intro_base = ImageClip(bases["lion"]).with_duration(intro_dur)
    intro = CompositeVideoClip([
        intro_base.resized(lambda t: 1.04 + 0.04 * t / intro_dur).with_position("center"),
        ImageClip(str(intro_cap)).with_duration(intro_dur).with_position(("center", int(H * 0.44))),
    ], size=(W, H)).with_duration(intro_dur)
    clips.append(intro)
    beat_marks.append((0.02, "ding"))
    tcur += intro_dur

    # dialogue beats
    for i, (spk, line) in enumerate(SCRIPT):
        c = CAST[spk]
        wav = work / f"v{i}.wav"
        try:
            asyncio.run(generate_voice_kokoro(line, str(wav), voice=c["voice"], speed=1.0,
                                              output_subs=str(work / f"v{i}.srt")))
        except Exception as e:
            print(f"  voice {i} failed: {e}", flush=True)
        if not wav.exists():
            continue
        aud = AudioFileClip(str(wav))
        dur = aud.duration               # match video to voice exactly (avoids reading past audio)
        env = _envelope(aud)

        def zoom(t, env=env, dur=dur):
            e = float(env[min(len(env) - 1, int(t * FPS))])
            return 1.05 + 0.05 * (t / dur) + 0.035 * e

        def pos(t, env=env, dur=dur):
            e = float(env[min(len(env) - 1, int(t * FPS))])
            zt = 1.05 + 0.05 * (t / dur) + 0.035 * e
            return ((W - W * zt) / 2, (H - H * zt) / 2 - 10 * e)

        vis = ImageClip(bases[spk]).with_duration(dur).resized(zoom).with_position(pos)
        cap = ImageClip(_caption_png(line, str(work / f"cap_{i}.png"))).with_duration(dur).with_position(("center", int(H * 0.72)))
        lbl = ImageClip(labels[spk]).with_duration(dur).with_position((44, 80))
        beat = CompositeVideoClip([vis, cap, lbl], size=(W, H)).with_audio(aud).with_duration(dur)
        clips.append(beat)
        beat_marks.append((tcur, "whoosh"))
        tcur += dur

    # outro
    outro_dur = 1.8
    outro_cap = work / "outro_cap.png"
    _caption_png("FOLLOW FOR MORE \U0001F43E", outro_cap)
    outro = CompositeVideoClip([
        ImageClip(bases["tiger"]).with_duration(outro_dur).resized(lambda t: 1.05 + 0.04 * t / outro_dur).with_position("center"),
        ImageClip(str(outro_cap)).with_duration(outro_dur).with_position(("center", int(H * 0.5))),
    ], size=(W, H)).with_duration(outro_dur)
    clips.append(outro)
    beat_marks.append((tcur, "whoosh"))
    tcur += outro_dur

    reel = concatenate_videoclips(clips, method="compose")
    total = reel.duration

    # music bed (dramatic, low)
    music = ROOT / "assets" / "ai_music_cache" / "bgm_tech_news.mp3"
    if music.exists():
        try:
            m = AudioFileClip(str(music)).with_effects([
                afx.AudioLoop(duration=total), afx.MultiplyVolume(0.12),
                afx.AudioFadeIn(0.4), afx.AudioFadeOut(0.8)])
            reel = reel.with_audio(CompositeAudioClip([reel.audio, m]))
        except Exception as e:
            print(f"  music skipped: {e}", flush=True)

    base_out = work / "story_base.mp4"
    reel.write_videofile(str(base_out), fps=FPS, codec="libx264", audio_codec="aac",
                         preset="veryfast", logger=None)
    for c in clips:
        try:
            c.close()
        except Exception:
            pass

    # SFX layer (whoosh cuts + ding) mixed via ffmpeg
    final = work / "story.mp4"
    try:
        import imageio_ffmpeg
        from modules.sfx_synth import arrays as sfx_arrays, SR, write_stereo_wav
        sfx = sfx_arrays()
        buf = np.zeros(int(total * SR) + SR, dtype="float32")
        vol = {"whoosh": 0.4, "ding": 0.42}
        for tstart, kind in beat_marks:
            a = sfx.get(kind)
            if a is None:
                continue
            off = int(max(0.0, tstart - (0.08 if kind == "whoosh" else 0.0)) * SR)
            end = min(len(buf), off + len(a))
            if end > off:
                buf[off:end] += a[:end - off] * vol.get(kind, 0.4)
        sfx_wav = write_stereo_wav(str(work / "sfx.wav"), buf)
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff, "-y", "-i", str(base_out), "-i", sfx_wav,
                        "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(final)],
                       capture_output=True)
        if not (final.exists() and final.stat().st_size > 10000):
            final = base_out
    except Exception as e:
        print(f"  sfx skipped: {e}", flush=True)
        final = base_out

    print(f"BUILT -> {final}  ({total:.1f}s)", flush=True)
    return str(final)


if __name__ == "__main__":
    build()
