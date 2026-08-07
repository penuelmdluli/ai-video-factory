"""$0 local SFX synthesis (numpy) — whoosh / pop / tick / ding for the faceless reels.

No assets, no API: each sound is generated procedurally. `arrays()` returns mono float signals
so the caller can place them on a full-length track and mix once via ffmpeg (robust to channel
layouts). Used by synced_reel to punctuate cuts, emoji landings, and counting numbers.
"""
import wave

import numpy as np

SR = 44100


def _whoosh_sig(dur=0.34):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.sin(np.pi * t / dur) ** 2
    sweep = np.sin(2 * np.pi * (280 + 2200 * t / dur) * t) * 0.3
    return (np.random.randn(len(t)) * 0.5 + sweep) * env * 0.7


def _pop_sig(dur=0.14):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-t * 32)
    f = 480 + 520 * np.exp(-t * 45)
    return np.sin(2 * np.pi * f * t) * env * 0.85


def _tick_sig(dur=0.05):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-t * 120)
    return (np.sin(2 * np.pi * 2300 * t) + np.random.randn(len(t)) * 0.2) * env * 0.6


def _ding_sig(dur=0.6):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-t * 6)
    return (np.sin(2 * np.pi * 880 * t) + 0.5 * np.sin(2 * np.pi * 1320 * t)
            + 0.3 * np.sin(2 * np.pi * 1760 * t)) * env * 0.5


def arrays():
    """Mono float signals keyed by name, for placement on a mix track."""
    return {"whoosh": _whoosh_sig(), "pop": _pop_sig(), "tick": _tick_sig(), "ding": _ding_sig()}


def write_stereo_wav(path, sig, sr=SR):
    """Write a mono float signal as a 16-bit STEREO wav (duplicated channels)."""
    pcm = (np.clip(sig, -1.0, 1.0) * 32767.0).astype(np.int16)
    inter = np.column_stack([pcm, pcm]).ravel()
    with wave.open(str(path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(inter.tobytes())
    return str(path)
