"""MoviePy v2 assembly — BROADCAST edition. Concat shots, mix narration + ducked
music + synthesized ambient bed + whoosh SFX, burn karaoke captions, and add
broadcast graphics: flag lower-thirds, a LIVE bug, a breaking-news ticker, and
the 'AI VISUALIZATION' tag."""
import glob
import os
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy import (VideoFileClip, AudioFileClip, ImageClip,
                     CompositeVideoClip, CompositeAudioClip,
                     concatenate_videoclips, concatenate_audioclips)

FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
FONT_REG = r"C:\Windows\Fonts\arial.ttf"


def _font(size, bold=True):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except Exception:
        return ImageFont.load_default()


def _duck(aclip, factor):
    try:
        return aclip.with_volume_scaled(factor)
    except Exception:
        from moviepy import afx
        return aclip.with_effects([afx.MultiplyVolume(factor)])


# ---------------- captions ----------------
def group_words(words, max_words=4, max_gap=0.6):
    phrases, cur = [], []
    for w in words:
        txt = (w.get("word") or w.get("text") or "").strip()
        if not txt:
            continue
        s, e = float(w.get("start", 0)), float(w.get("end", 0))
        if cur and (len(cur) >= max_words or s - cur[-1][2] > max_gap):
            phrases.append((cur[0][1], cur[-1][2], " ".join(x[0] for x in cur))); cur = []
        cur.append((txt, s, e))
    if cur:
        phrases.append((cur[0][1], cur[-1][2], " ".join(x[0] for x in cur)))
    return phrases


def _fallback_phrases(text, dur):
    words = (text or "").split()
    if not words:
        return []
    chunks = [words[i:i + 4] for i in range(0, len(words), 4)]
    per = dur / len(chunks)
    return [(i * per, (i + 1) * per, " ".join(c)) for i, c in enumerate(chunks)]


CAP_H = 260   # fixed caption band (text vertically centered) — fits up to 2 wrapped lines
_TWIMG = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
def _tw(t, font):
    return _TWIMG.textlength(t, font=font)

# Words that carry the punch — highlighted in the accent colour per phrase.
_POWER_WORDS = {
    "WAR", "CRISIS", "ATTACK", "STRIKE", "STRIKES", "DEAD", "KILLED", "NUCLEAR", "ALERT",
    "URGENT", "COLLAPSE", "SANCTIONS", "THREAT", "POWER", "OIL", "TRADE", "MILITARY",
    "MISSILE", "DRONE", "TROOPS", "ESCALATE", "ESCALATES", "TENSIONS", "CONFLICT",
    "BREAKING", "EXPLOSION", "CHAOS", "SHOCK", "WARNING", "DANGER", "BILLION", "MILLION",
    "TRILLION", "AFRICA", "CHINA", "RUSSIA", "IRAN", "ISRAEL", "NATO", "BRICS", "CONTROL",
}


def _is_key(word):
    wc = word.strip(".,!?:;\"'()").upper()
    if not wc:
        return False
    if any(ch.isdigit() for ch in wc) or "%" in word or "$" in word:
        return True
    return wc in _POWER_WORDS


def render_caption_png(text, W, path, accent=(255, 226, 89)):
    """Wrapped (<=2 lines, never cut off), upscaled, with only the KEY words in accent."""
    words = text.upper().split()
    if not words:
        Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0)).save(path); return path
    max_w = int(W * 0.86)

    def layout(font):
        lines, cur = [], []
        for w in words:
            if _tw(" ".join(cur + [w]), font) <= max_w or not cur:
                cur.append(w)
            else:
                lines.append(cur); cur = [w]
        if cur:
            lines.append(cur)
        return lines

    fs = 72; font = _font(fs); lines = layout(font)
    while len(lines) > 2 and fs > 44:                       # keep it big; wrap not shrink
        fs -= 4; font = _font(fs); lines = layout(font)
    while any(_tw(" ".join(l), font) > max_w for l in lines) and fs > 32:
        fs -= 3; font = _font(fs); lines = layout(font)

    keys = set(w for line in lines for w in line if _is_key(w))
    if not keys:
        keys = {max(words, key=len)}                        # fall back: highlight the longest

    lh = int(fs * 1.16); total = lh * len(lines)
    img = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    space = _tw(" ", font)
    y = (CAP_H - total) // 2
    for line in lines:
        lw = sum(_tw(w, font) for w in line) + space * (len(line) - 1)
        x = (W - lw) // 2
        for w in line:
            col = accent if w in keys else (255, 255, 255)
            for dx in (-3, 0, 3):
                for dy in (-3, 0, 3):
                    d.text((x + dx, y + dy), w, font=font, fill=(0, 0, 0, 235))
            d.text((x, y), w, font=font, fill=col + (255,))
            x += _tw(w, font) + space
        y += lh
    img.save(path); return path


# ---------------- broadcast graphics ----------------
FLAG_COLORS = {
    # simplified drawn flags
    "US": "stripes_us", "IR": "tricolor_iran", "UN": "un_blue", "EU": "eu_blue",
}


def _draw_flag(d, x, y, w, h, code):
    code = code.upper()
    if code == "US":
        stripe = h / 7
        for i in range(7):
            col = (178, 34, 52) if i % 2 == 0 else (255, 255, 255)
            d.rectangle([x, y + i * stripe, x + w, y + (i + 1) * stripe], fill=col)
        d.rectangle([x, y, x + w * 0.4, y + stripe * 4], fill=(60, 59, 110))
    elif code == "IR":
        d.rectangle([x, y, x + w, y + h / 3], fill=(35, 159, 64))
        d.rectangle([x, y + h / 3, x + w, y + 2 * h / 3], fill=(255, 255, 255))
        d.rectangle([x, y + 2 * h / 3, x + w, y + h], fill=(218, 0, 0))
    elif code == "EU":
        d.rectangle([x, y, x + w, y + h], fill=(0, 51, 153))
    else:  # generic / UN
        d.rectangle([x, y, x + w, y + h], fill=(30, 90, 150))
    d.rectangle([x, y, x + w, y + h], outline=(255, 255, 255, 200), width=2)


def render_lowerthird_png(flags, label, W, path):
    """Bottom-left lower-third: flag chips + a label bar."""
    img = Image.new("RGBA", (W, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    fx, fy, fw, fh = 24, 40, 66, 44
    n = len(flags)
    d.rounded_rectangle([16, 32, 16 + n * (fw + 10) + 20 + d.textbbox((0, 0), label, font=_font(30))[2],
                         96], radius=10, fill=(140, 0, 0, 210))
    x = fx
    for code in flags:
        _draw_flag(d, x, fy, fw, fh, code)
        x += fw + 10
    d.text((x + 8, 46), label.upper(), font=_font(30), fill=(255, 255, 255, 255))
    img.save(path); return path


def render_live_png(path):
    img = Image.new("RGBA", (170, 56), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 169, 55], radius=10, fill=(0, 0, 0, 150))
    d.ellipse([16, 20, 36, 40], fill=(230, 30, 30))
    d.text((46, 13), "LIVE", font=_font(30), fill=(255, 255, 255))
    img.save(path); return path


def render_tag_png(text, W, path):
    # Subtle disclosure — small, semi-transparent corner chip (not a banner).
    font = _font(18)
    tw = ImageDraw.Draw(Image.new("RGBA", (10, 10))).textbbox((0, 0), text, font=font)[2]
    img = Image.new("RGBA", (tw + 34, 30), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, tw + 33, 29], radius=8, fill=(0, 0, 0, 90))
    d.ellipse([8, 11, 18, 21], fill=(120, 200, 255, 180))
    d.text((23, 6), text, font=font, fill=(230, 240, 255, 200))
    img.save(path); return path


def render_ticker_png(text, W, path):
    """Red breaking-news strip across the bottom."""
    h = 52
    img = Image.new("RGBA", (W, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, h], fill=(150, 0, 0, 235))
    d.rectangle([0, 0, 190, h], fill=(20, 20, 20, 255))
    d.text((18, 12), "BREAKING", font=_font(26), fill=(255, 220, 60))
    d.text((210, 13), text.upper(), font=_font(24, bold=False), fill=(255, 255, 255))
    img.save(path); return path


# ---------------- audio: whoosh + ambient bed ----------------
def _synth_whoosh(tmp):
    out = str(Path(tmp) / "_whoosh.wav"); sr = 44100
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    env = np.sin(np.pi * t / 0.5) ** 2
    sweep = np.sin(2 * np.pi * (200 + 1800 * t / 0.5) * t) * 0.3
    sig = (np.random.randn(len(t)) * 0.6 + sweep) * env
    sig = np.clip(sig / (np.max(np.abs(sig)) + 1e-6), -1, 1)
    _write_wav(out, sig, sr); return out


def _loud_voice(wav, tmp):
    """Compress + loudnorm the narration to a loud, punchy broadcast level so the
    voiceover is never soft. Returns a new wav path (falls back to original)."""
    import subprocess, imageio_ffmpeg
    out = str(Path(tmp) / "_voice_loud.wav")
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    af = "acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=3,loudnorm=I=-11:TP=-1.0:LRA=9"
    r = subprocess.run([ff, "-y", "-i", str(wav), "-af", af, "-ar", "44100", out], capture_output=True)
    return out if (r.returncode == 0 and Path(out).exists() and Path(out).stat().st_size > 1000) else str(wav)


def _synth_boom(tmp):
    """Deep cinematic impact/boom for the open and cuts."""
    out = str(Path(tmp) / "_boom.wav"); sr = 44100
    t = np.linspace(0, 1.2, int(sr * 1.2), endpoint=False)
    env = np.exp(-t * 4.5)
    sub = np.sin(2 * np.pi * (60 * np.exp(-t * 2) + 30) * t)  # descending sub thump
    body = np.sin(2 * np.pi * 90 * t) * 0.4
    sig = (sub + body) * env
    sig = np.clip(sig / (np.max(np.abs(sig)) + 1e-6), -1, 1)
    _write_wav(out, sig, sr); return out


def _speed(clip, f):
    """Speed the footage up for energy."""
    try:
        return clip.with_speed_scaled(f)
    except Exception:
        try:
            from moviepy import vfx
            return clip.with_effects([vfx.MultiplySpeed(f)])
        except Exception:
            return clip


def _kenburns(clip, W, H, i):
    """Punch-in on the cut + continuous drift zoom — high energy, never static."""
    dur = clip.duration
    base = clip.resized((W, H))

    def z(t):
        # gentle settle-in on the cut, then a slow smooth drift — NO shake
        punch = 1.10 - 0.10 * min(t / 0.35, 1.0)
        drift = 0.10 * (t / max(dur, 0.1)) if i % 2 == 0 else 0.10 * (1 - t / max(dur, 0.1))
        return max(1.03, punch + drift)

    def pos(t):                                                  # smooth centre — no jitter
        zt = z(t)
        return ((W - W * zt) / 2, (H - H * zt) / 2)

    zc = base.resized(z).with_position(pos)
    return CompositeVideoClip([zc], size=(W, H)).with_duration(dur)


def _synth_ambient(tmp, dur):
    """Ocean-swell + wind + low rumble bed to make the scene feel alive."""
    out = str(Path(tmp) / "_ambient.wav"); sr = 22050
    n = int(sr * dur); t = np.arange(n) / sr
    pink = np.cumsum(np.random.randn(n)); pink /= np.max(np.abs(pink)) + 1e-6  # brown-ish noise = wind/ocean
    swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.12 * t)  # slow ocean swell LFO
    ocean = pink * swell
    rumble = np.sin(2 * np.pi * 45 * t) * 0.15 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t))  # low rumble
    sig = ocean * 0.7 + rumble
    sig = np.clip(sig / (np.max(np.abs(sig)) + 1e-6), -1, 1)
    _write_wav(out, sig, sr); return out


def _write_wav(path, sig, sr):
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((sig * 32767 * 0.9).astype(np.int16).tobytes())


# ---------------- main ----------------
def assemble(clip_paths, narration_wav, music_wav, words, text, out_dir, W, H, FPS, target,
             flags=("US", "IR"), lowerthird_label="Global powers on alert",
             ticker="Naval forces converge in the Red Sea as tensions escalate  •  world watches shipping lanes",
             live=True, tag_text="AI VISUALIZATION", shot_audios=None, intro_clips=0, hook_clips=0):
    out_dir = Path(out_dir); tmp = out_dir / "_cap"; tmp.mkdir(parents=True, exist_ok=True)
    n = max(1, len(clip_paths)); per = max(2.0, (target or 28.0) / n)

    vclips = []
    for i, p in enumerate(clip_paths):
        raw = _speed(VideoFileClip(str(p)), 1.3)                 # faster motion = more energy
        c = raw.subclipped(0, min(per, raw.duration))
        # the leading graphic scenes (hook/map/stat) already carry their own text — don't
        # Ken-Burns-zoom them (would crop the text); keep them clean & full-frame.
        if i >= intro_clips:
            c = _kenburns(c, W, H, i)                            # punch-in + drift + shake
        else:
            c = c.resized((W, H))
        vclips.append(c)
    video = concatenate_videoclips(vclips, method="compose")
    hook_dur = sum(c.duration for c in vclips[:max(0, hook_clips)])   # ONLY the hook is caption-free

    narr = AudioFileClip(_loud_voice(narration_wav, tmp))  # compressed + loudnorm = punchy, never soft
    vdur = min(video.duration, max(narr.duration + 0.4, target or 28.0))
    video = video.subclipped(0, min(video.duration, vdur)); vdur = video.duration

    # --- audio tracks — VOICE-FORWARD MIX ---
    # Narration already at broadcast loudness; beds sit well underneath.
    tracks = [narr]
    # Per-shot FOLEY (real synced sound), ducked LOW so it colours the scene
    # without masking speech.
    if shot_audios:
        for i, ap in enumerate(shot_audios):
            if not ap or not Path(ap).exists():
                continue
            try:
                st = min(i * per, vdur - 0.1)
                fa = AudioFileClip(str(ap)).subclipped(0, min(per, AudioFileClip(str(ap)).duration))
                tracks.append(_duck(fa, 0.18).with_start(st))
            except Exception as e:
                print(f"  shot foley {i} skipped: {e}", flush=True)
    else:
        amb = _synth_ambient(tmp, vdur + 2)
        ac = AudioFileClip(amb)
        tracks.append(_duck(ac.subclipped(0, min(vdur, ac.duration)), 0.10))
    if music_wav and Path(music_wav).exists():
        m = AudioFileClip(str(music_wav))
        if m.duration < vdur:
            m = concatenate_audioclips([m] * (int(vdur / m.duration) + 1))
        tracks.append(_duck(m.subclipped(0, vdur), 0.17))   # music present under the voice (was 0.05)
    # DRAMA: opening boom + a punchy impact on each cut
    boom = _synth_boom(tmp)
    tracks.append(_duck(AudioFileClip(boom), 0.6).with_start(0))
    for i in range(1, len(vclips)):
        try:
            tracks.append(_duck(AudioFileClip(boom).subclipped(0, 0.5), 0.35).with_start(min(i * per, vdur - 0.1)))
        except Exception:
            pass
    video = video.with_audio(CompositeAudioClip(tracks))

    overlays = []
    # captions
    phrases = group_words(words) if words else _fallback_phrases(text, vdur)
    CAP_LEAD = 0.22   # show a touch BEFORE the word — whisper boundaries run late, so this syncs it
    for i, (s, e, txt) in enumerate(phrases):
        if s >= vdur:
            break
        if s < hook_dur:                       # keep ONLY the hook caption-free
            continue
        s2 = max(hook_dur, s - CAP_LEAD)
        png = render_caption_png(txt, W, str(tmp / f"cap_{i}.png"))
        overlays.append(ImageClip(png).with_start(s2).with_duration(max(0.4, min(e, vdur) - s2))
                        .with_position(("center", int(H * 0.80) - CAP_H // 2)))   # proper reel caption zone
    # flag chyron — moved UP to the top (bottom is left clean for captions; no ticker)
    lt = render_lowerthird_png(list(flags), lowerthird_label, W, str(tmp / "lt.png"))
    overlays.append(ImageClip(lt).with_duration(vdur).with_position((0, int(H * 0.11))))
    # LIVE bug (top-right)
    if live:
        lv = render_live_png(str(tmp / "live.png"))
        overlays.append(ImageClip(lv).with_duration(vdur).with_position((W - 190, int(H * 0.04))))
    # AI tag (top-left)
    if tag_text:
        tg = render_tag_png(tag_text, W, str(tmp / "tag.png"))
        overlays.append(ImageClip(tg).with_duration(vdur).with_position((int(W * 0.02), int(H * 0.04))))

    final = CompositeVideoClip([video] + overlays)
    out = out_dir / "final_30s.mp4"
    # Temp audio beside this build, not in the repo root. Every other renderer
    # gets this from modules/safe_render.py via modules/__init__.py, but this
    # script imports no modules.* at all, so it has to say so itself. See the
    # 2026-09-02 role-slot failure: MoviePy names the temp file after the
    # OUTPUT basename and drops it in the CWD, so two builds running at once
    # delete it out from under each other mid-encode.
    final.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac",
                          bitrate="6000k", threads=4, preset="medium",
                          temp_audiofile_path=str(out.parent),
                          ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    return out
