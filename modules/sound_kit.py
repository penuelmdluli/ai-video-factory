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


def music_bed(dur, bpm=92, root=55.0):
    """A generative music bed - bass, pad and a soft pulse, in a minor key.

    Owner asked for music as well as effects. Licensed loops mean a library to
    keep, a claim risk on YouTube, and a fixed length that never matches the
    reel. Generating it means the bed is exactly as long as the video, cannot
    be claimed by anyone, and can be keyed to the mood of the format.

    Deliberately plain: two chords, a root pulse and a wash. This sits under
    narration for thirty seconds and must not compete with it - anything more
    interesting would be a distraction, not a benefit.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    beat = 60.0 / bpm
    out = np.zeros(n)

    # i - VI alternation, four bars each
    bar = beat * 4
    chords = [(1.0, 1.2, 1.5), (0.8, 1.0, 1.25)]     # ratios off the root
    seg = int(SR * bar * 2)
    for start in range(0, n, seg):
        end = min(n, start + seg)
        m = end - start
        idx = (start // seg) % len(chords)
        tt = np.arange(m) / SR
        # The DARK root, with harmonics a phone can actually reproduce.
        #
        # The owner could not hear the music, so the root was moved up an
        # octave - which fixed audibility and lost the character he actually
        # wanted. Root 55 is back, and the upper partials carry the level
        # instead. Pitch and audibility are separate controls: the
        # fundamental sets how dark it sounds, the harmonic stack sets
        # whether a phone speaker reproduces any of it.
        #
        # A note on how this was diagnosed, because the first measurement was
        # wrong and nearly sent the fix the wrong way. Comparing the MEAN
        # magnitude of a 40Hz-wide band against a 600Hz-wide one makes the
        # wide band look empty - it is diluted by near-zero bins - and that
        # reading said the mids were dead when they were not. Energy SHARE is
        # the honest metric: this voicing puts 29% of total energy in
        # 200-800Hz and 15.5% above 300Hz, which is quiet but real. Measure
        # bands by share, never by mean.
        pad = np.zeros(m)
        for r in chords[idx]:
            pad += np.sin(2 * math.pi * root * r * tt) * 0.30
            pad += np.sin(2 * math.pi * root * r * 2 * tt) * 0.22
            pad += np.sin(2 * math.pi * root * r * 4 * tt) * 0.30
            pad += np.sin(2 * math.pi * root * r * 8 * tt) * 0.28
            pad += np.sin(2 * math.pi * root * r * 12 * tt) * 0.14
        swell = 0.55 + 0.45 * np.sin(math.pi * tt / max(0.01, bar * 2))
        out[start:end] += pad * swell * 0.19

    # pulse on the beat - fundamental for feel, octaves so it is heard
    step = int(SR * beat)
    for i in range(0, n, step):
        m = min(step, n - i)
        tt = np.arange(m) / SR
        env = np.exp(-tt * 6.5)
        hit = (np.sin(2 * math.pi * root * tt) * 0.30
               + np.sin(2 * math.pi * root * 2 * tt) * 0.22
               + np.sin(2 * math.pi * root * 4 * tt) * 0.14)
        out[i:i + m] += hit * env

    # a breath of air so it is not purely tonal
    out += _lowpass(_noise(n), 900) * 0.012
    fade = min(int(SR * 1.2), n // 4)
    if fade > 0:
        out[:fade] *= np.linspace(0, 1, fade)
        out[-fade:] *= np.linspace(1, 0, fade)
    return out * 0.6


def mix(duration, events, with_bed=True, with_music=False, bpm=92):
    """events = [(at_seconds, samples)] -> one normalised track."""
    n = int(SR * duration)
    track = bed(duration) if with_bed else np.zeros(n)
    if with_music:
        m = music_bed(duration, bpm=bpm)
        track = track + (m[:n] if len(m) >= n else np.pad(m, (0, n - len(m))))
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


def score_reveal(out_path, duration, scan_end, crest_end, per_name,
                 count, music=True, bpm=92):
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
    return write_wav(mix(duration, events, with_music=music, bpm=bpm),
                     out_path)


def under_voice(video_path, music_path, out_path, music_db=-12.0):
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
