"""
Sound design, synthesised locally. No files to license, no downloads to break.

Owner call 2026-08-27: "add the best sounds needed and also have that as we do
editing within our videos". assets/sfx was empty, and the two ways to fill it
are a library we have to license and keep, or generating the sounds ourselves.
These are simple sounds - a lock, a riser, an impact - and a few hundred lines
of numpy makes them exactly as long as the beat they mark, which a stock file
never is. Nothing to download, nothing to attribute, and the timing is right
by construction.

The palette is deliberately small, because a reveal only needs three things:

    riser   tension while something is loading. Rises in pitch, gets busier
    lock    a name landing. Short, dry, slightly pitched so six in a row
            read as a sequence and not a stutter
    impact  the crest. Low, with a tail
    bed     a quiet pulse under everything so silence never feels like a
            dropout on a muted-by-default platform

Everything is mixed UNDER the narration - the voice is the message and this is
punctuation. Levels are set low on purpose; if the effects are noticeable as
effects, they are too loud.
"""
import math
import struct
import wave
from pathlib import Path

import numpy as np

SR = 44100


def _env(n, attack=0.005, release=0.25, curve=2.0):
    """Attack/release envelope, release shaped so tails feel natural."""
    a = max(1, int(SR * attack))
    r = max(1, int(SR * release))
    e = np.ones(n)
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a)
    r = min(r, n)
    e[n - r:] = np.linspace(1, 0, r) ** curve
    return e


def _sine(freq, n, phase=0.0):
    t = np.arange(n) / SR
    return np.sin(2 * math.pi * freq * t + phase)


def _noise(n):
    return np.random.default_rng(7).standard_normal(n)


def _lowpass(x, cutoff):
    """One-pole lowpass - enough to take the fizz off white noise."""
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def lock(pitch=1.0, dur=0.16):
    """A name landing. Dry click plus a short pitched body."""
    n = int(SR * dur)
    body = (_sine(420 * pitch, n) * 0.6
            + _sine(840 * pitch, n) * 0.25
            + _sine(1260 * pitch, n) * 0.1)
    click = _noise(n) * np.exp(-np.arange(n) / (SR * 0.004)) * 0.5
    return (body * _env(n, 0.002, dur * 0.8, 2.4) + click) * 0.42


def riser(dur=3.0, f0=110, f1=520):
    """Tension while the scan works. Pitch and density both climb."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    sweep = f0 * (f1 / f0) ** (t / dur)
    phase = 2 * math.pi * np.cumsum(sweep) / SR
    tone = np.sin(phase) * 0.5 + np.sin(phase * 2) * 0.18
    air = _lowpass(_noise(n), 1400) * np.linspace(0.02, 0.34, n)
    swell = np.linspace(0.15, 1.0, n) ** 1.6
    return (tone + air) * swell * 0.3


def impact(dur=1.4):
    """The crest. Low hit with a tail you can feel more than hear."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    drop = 120 * np.exp(-t * 7) + 42
    phase = 2 * math.pi * np.cumsum(drop) / SR
    low = np.sin(phase) * np.exp(-t * 3.2)
    crack = _lowpass(_noise(n), 2600) * np.exp(-t * 26) * 0.5
    return (low * 0.9 + crack) * 0.5


def bed(dur, hz=1.05):
    """A slow pulse so quiet stretches still feel alive."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    pulse = 0.5 + 0.5 * np.sin(2 * math.pi * hz * t / 4)
    tone = (_sine(58, n) * 0.55 + _sine(87, n) * 0.25
            + _sine(116, n) * 0.12)
    return tone * (0.25 + 0.35 * pulse) * 0.11


def mix(duration, events, with_bed=True):
    """events = [(at_seconds, samples)] -> one normalised track."""
    n = int(SR * duration)
    track = bed(duration) if with_bed else np.zeros(n)
    if len(track) < n:
        track = np.pad(track, (0, n - len(track)))
    track = track[:n]
    for at, samples in events:
        i = int(SR * at)
        if i >= n:
            continue
        seg = samples[:max(0, n - i)]
        track[i:i + len(seg)] += seg
    peak = float(np.max(np.abs(track))) or 1.0
    if peak > 0.92:
        track = track / peak * 0.92
    return track


def write_wav(samples, out_path):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))
    return str(out)


def score_reveal(out_path, duration, scan_end, crest_end, per_name, count):
    """The whole track for a reveal reel, built from its own timings.

    Each name gets a slightly higher lock than the one before, so six in a row
    climb instead of repeating - the ear hears a list being completed rather
    than the same noise six times.
    """
    events = [(0.0, riser(max(0.6, scan_end))),
              (scan_end, impact())]
    for i in range(count):
        at = crest_end + i * per_name + per_name * 0.86
        events.append((at, lock(pitch=1.0 + i * 0.055)))
    # a softer hit when the shortlist is complete
    events.append((crest_end + count * per_name, impact(1.0) * 0.55))
    return write_wav(mix(duration, events), out_path)


def under_voice(video_path, music_path, out_path, music_db=-19.0):
    """Lay the score under the existing narration with ffmpeg.

    Mixed low deliberately: the voice carries the message. amix alone would
    halve the voice, so the score is attenuated first and the voice keeps its
    own level.
    """
    import subprocess
    # loudnorm to -15 LUFS on the way out. Our first mix measured -26.2, which
    # is roughly a quarter as loud as everything else in a feed - a viewer
    # reaches for the volume, and most of them just scroll instead. Platforms
    # target about -14, so this lands us alongside the posts around us rather
    # than under them.
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video_path), "-i", str(music_path),
           "-filter_complex",
           f"[1:a]volume={music_db}dB,afade=t=in:st=0:d=0.4[m];"
           f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:"
           f"normalize=0[x];[x]loudnorm=I=-15:TP=-1.5:LRA=11[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("[Sound] mix failed: " + (r.stderr or "")[:200])
        return None
    return str(out_path)
