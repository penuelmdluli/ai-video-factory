#!/usr/bin/env python
"""$0 finisher for a SAGA OF THE NORTH episode: take the cut visuals + the saga script, add a deep
saga-teller narrator (Kokoro af_heart — the tech-news female voice) over ducked battle audio and a
score bed, brand it, then burn
the full on-screen pack — episode badge, hook, synced captions, comment bait, lesson card on the
freeze frame, and the next-episode tease. No Veo re-generation.

  python finish_short.py <dir_with_visuals.mp4>

The mix is the part that matters. The old build had to choose between the narrator and the Veo
battle audio; this one sidechains them, so the roars, hammer blows and shield crashes play at full
weight and only duck while the narrator is actually speaking.
"""
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import imageio_ffmpeg

from modules.wild_brand import brand_video
from modules.subtitles import add_subs_and_follow
from modules.voice_generator import generate_voice_kokoro, generate_voice_elevenlabs

# The saga-teller. Locked to the SAME female voice Tech Pulse Africa (tech_news) narrates with —
# Kokoro `af_heart` (see modules/voice_generator.py kokoro_voices["tech_news"]). Kokoro is the free
# local engine and runs by default; ElevenLabs stays available as an optional premium override via
# SAGA_NARRATOR=elevenlabs, but the default no longer uses a male voice.
NARRATOR_ENGINE = os.getenv("SAGA_NARRATOR", "kokoro")
ELEVEN_VOICE_ID = os.getenv("SAGA_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")   # Rachel — female (if EL used)
KOKORO_VOICE = os.getenv("SAGA_KOKORO_VOICE", "af_heart")              # tech-news female voice, free

NAME, EMOJI, HANDLE = "SAGA OF THE NORTH", "\U0001FA93", "@SagaOfTheNorth"
MUSIC = ROOT / "assets" / "ai_music_cache" / "bgm_tech_news.mp3"
GOLD = (224, 164, 0)

OFFSET = 0.35     # narration starts here, so the first shot lands before the voice does
# Kokoro shifts timbre at any speed other than 1.0 (see the warning in voice_generator.py) — the
# gravitas has to come from the voice and the mix, not from slowing the engine down.
NARR_SPEED = 1.0
NARR_LUFS = -14   # broadcast-ish target; raw Kokoro lands near -25 and vanishes under the battle

SAGA = ("They came from the cold north, where the sea itself screams. And when the storm broke... "
        "the Northmen did not pray. They attacked.")
COMMENT = "Would you sail with him?"

AFMT = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"


def _dur(p):
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(p)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 16.0


def _fmt(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _even_srt(text, dur, path, per=4):
    """Distribute the saga text as evenly-timed captions across `dur` (no voice needed)."""
    words = text.replace("...", " ").split()
    groups = [words[i:i + per] for i in range(0, len(words), per)]
    g = max(1, len(groups))
    slot = dur / g
    blocks = []
    for i, grp in enumerate(groups):
        blocks.append(f"{i+1}\n{_fmt(i*slot)} --> {_fmt((i+1)*slot)}\n{' '.join(grp)}\n")
    Path(path).write_text("\n".join(blocks), encoding="utf-8")
    return path


def _loudnorm(src, out, target=NARR_LUFS):
    """Bring a narration take up to a fixed loudness.

    Raw Kokoro output sits around -25 LUFS while Veo's battle audio measures about -20, so the
    narrator was mixed in already losing by 5 LU — no amount of sidechain ducking rescues that.
    Normalising each take first means the voice is the loudest thing in the episode by design.
    """
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(src),
                        "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11", str(out)],
                       capture_output=True)
    if not Path(out).exists():
        print(f"  loudnorm failed ({r.returncode}), using raw take", flush=True)
        Path(src).replace(out)
    return out


def narrate(text, out_mp3, out_srt):
    """Speak one line as the saga-teller, premium engine first, free local engine as backup."""
    if NARRATOR_ENGINE == "elevenlabs":
        res = asyncio.run(generate_voice_elevenlabs(text, out_mp3, voice_id=ELEVEN_VOICE_ID,
                                                    output_subs=out_srt))
        if res and Path(out_mp3).exists():
            # ElevenLabs alignment is per-character; fall back to whisper if it gave us no SRT
            if not Path(out_srt).exists():
                _whisper_or_estimate(text, out_mp3, out_srt)
            return out_mp3
        print("  ElevenLabs unavailable — falling back to Kokoro", flush=True)
    asyncio.run(generate_voice_kokoro(text, out_mp3, voice=KOKORO_VOICE, speed=NARR_SPEED,
                                      output_subs=out_srt))
    return out_mp3


def _whisper_or_estimate(text, mp3, srt):
    from modules.voice_generator import _whisper_srt, _generate_estimated_srt
    if not _whisper_srt(Path(mp3), text, Path(srt)):
        _generate_estimated_srt(text, _dur(mp3), Path(srt))


def _narrate_beats(d, beats, action_dur):
    """Narrate one line per shot and place each beat on the shot it describes.

    A single 45-word take runs ~13s and leaves half a 24s episode in silence. Spreading the script
    across the cuts means the voice lands on the image it is talking about — and the gaps between
    beats are where the battle audio comes back up to full weight. That alternation is the whole
    reason the thing feels like a film instead of a slideshow with a podcast over it.

    Returns (placed, narr_end) where placed is [(mp3_path, start_seconds, srt_path)].
    """
    takes = []
    for i, line in enumerate(beats):
        raw, mp3, srt = d / f"raw_{i}.mp3", d / f"narr_{i}.mp3", d / f"narr_{i}.srt"
        narrate(line, raw, srt)
        if raw.exists():
            _loudnorm(raw, mp3)
            takes.append((mp3, srt, _dur(mp3)))
        else:
            print(f"  beat {i} narration failed", flush=True)
    if not takes:
        return [], 0.0

    slot = action_dur / len(takes)
    placed, cursor = [], 0.0
    for i, (mp3, srt, length) in enumerate(takes):
        want = i * slot + (OFFSET if i == 0 else 0.55)
        if i == len(takes) - 1:
            # The closing line is the lesson. Pull it earlier if needed so it finishes exactly as
            # the freeze frame arrives — otherwise the card sits on a dead frozen tail waiting
            # for him to stop talking.
            want = min(want, action_dur - length)
        start = max(want, cursor)
        placed.append((mp3, start, srt))
        cursor = start + length + 0.35
    return placed, cursor - 0.35


def _merge_srt(placed, out):
    """Combine the per-beat SRTs into one, shifting each into its slot on the timeline."""
    blocks, n = [], 0
    for _, start, srt in placed:
        try:
            txt = Path(srt).read_text(encoding="utf-8")
        except Exception:
            continue
        for b in re.split(r"\n\s*\n", txt.strip()):
            lines = b.strip().splitlines()
            tline = next((l for l in lines if "-->" in l), None)
            if not tline:
                continue
            a, c = tline.split("-->")

            def _p(x):
                x = x.strip().replace(",", ".")
                h, m, s = x.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)

            body = " ".join(l for l in lines if "-->" not in l and not l.strip().isdigit())
            n += 1
            blocks.append(f"{n}\n{_fmt(_p(a) + start)} --> {_fmt(_p(c) + start)}\n{body}\n")
    Path(out).write_text("\n".join(blocks), encoding="utf-8")
    return out


def _mix(ff, visuals, placed, dur, pad, out):
    """Narration beats over sidechain-ducked Veo battle audio + a low score bed.

    `pad` extends the (already frozen) tail so the narration always finishes inside the video.
    """
    total = dur + pad
    ins = ["-i", str(visuals)]
    for mp3, _, _ in placed:
        ins += ["-i", str(mp3)]
    vfilt = f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.2f}[v]" if pad > 0.05 else None

    fc = f"[0:a]{AFMT},volume=0.80,apad,atrim=0:{total:.2f}[bat];"
    for i, (_, start, _) in enumerate(placed):
        ms = int(start * 1000)
        # Each take is already loudness-normalised; the compressor here just keeps the quiet
        # consonants up so every word survives a phone speaker.
        fc += (f"[{i+1}:a]{AFMT},adelay={ms}|{ms},"
               f"acompressor=threshold=-18dB:ratio=3:attack=8:release=180:makeup=2,"
               f"bass=g=3:f=110,treble=g=2:f=3500,"
               f"aecho=0.85:0.9:38:0.10[n{i}];")
    nb = len(placed)
    if nb > 1:
        fc += "".join(f"[n{i}]" for i in range(nb)) + \
              f"amix=inputs={nb}:normalize=0:duration=longest[narsum];"
    else:
        fc += "[n0]anull[narsum];"
    fc += ("[narsum]asplit=2[nar][sc];"
           # battle audio plays full and dips hard the moment he speaks, then comes straight back
           "[bat][sc]sidechaincompress=threshold=0.02:ratio=14:attack=10:release=260[duck];")

    amix, n = "[duck][nar]", 2
    if MUSIC.exists():
        ins += ["-i", str(MUSIC)]
        fc += (f"[{nb+1}:a]{AFMT},volume=0.11,aloop=loop=-1:size=200000000,atrim=0:{total:.2f},"
               f"afade=t=out:st={max(0, total-1.4):.2f}:d=1.4[mus];")
        amix += "[mus]"
        n = 3
    # A final limiter so the sum never clips once the booms and the roar land together.
    fc += (f"{amix}amix=inputs={n}:normalize=0:duration=first,"
           f"alimiter=limit=0.95:level=disabled,aformat=sample_rates=44100[a]")
    if vfilt:
        fc = vfilt + ";" + fc

    cmd = [ff, "-y", *ins, "-filter_complex", fc,
           "-map", "[v]" if vfilt else "0:v", "-map", "[a]"]
    cmd += (["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p"]
            if vfilt else ["-c:v", "copy"])
    cmd += ["-c:a", "aac", str(out)]
    subprocess.run(cmd, capture_output=True)
    return total


def finish(dir_, saga=SAGA, beats=None, comment=COMMENT, hook=None, lesson=None, badge=None,
           next_tease=None, name=NAME, emoji=EMOJI, handle=HANDLE, voiceover=True, hold=1.6):
    """Finish an episode. `hold` is the freeze-frame tail the impact edit left for the lesson card.

    `beats` is one narration line per shot; without it the whole `saga` is read as a single take.
    """
    d = Path(dir_)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    visuals = d / "visuals.mp4"
    if not visuals.exists():
        print(f"no visuals.mp4 in {d}", flush=True)
        return
    dur = _dur(visuals)
    srt = d / "narr.srt"
    mixed = d / "mixed.mp4"
    total, offset = dur, 0.0

    if voiceover:
        lines = beats or [saga]
        print(f"  narrating {len(lines)} beat(s) ({KOKORO_VOICE})...", flush=True)
        placed, narr_end = _narrate_beats(d, lines, max(4.0, dur - hold))
        if not placed:
            print("  narration failed", flush=True)
            return
        _merge_srt(placed, srt)
        print("  beats at " + ", ".join(f"{s:.1f}s" for _, s, _ in placed) +
              f" (voice ends {narr_end:.1f}s)", flush=True)
        # Extend the frozen tail if he is still talking when the action runs out, so the lesson
        # card always lands on his last word instead of cutting him off.
        pad = max(0.0, (narr_end + 0.3) - (dur - hold))
        total = _mix(ff, visuals, placed, dur, pad, mixed)
    else:
        # keep the ORIGINAL Veo sound; just a LOW music bed under it; subtitles from even timing
        print("  no voiceover — keeping original Veo audio + low music", flush=True)
        _even_srt(saga, max(1.0, dur - hold), srt)
        ins = ["-i", str(visuals)]
        if MUSIC.exists():
            ins += ["-i", str(MUSIC)]
            fc = (f"[0:a]{AFMT},volume=1.0[a0];"
                  f"[1:a]{AFMT},volume=0.09,aloop=loop=-1:size=200000000,atrim=0:{dur:.2f},"
                  f"afade=t=out:st={max(0, dur-1.2):.2f}:d=1.2[a1];"
                  f"[a0][a1]amix=inputs=2:normalize=0:duration=first[a]")
        else:
            fc = "[0:a]anull[a]"
        subprocess.run([ff, "-y", *ins, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", str(mixed)], capture_output=True)

    if not mixed.exists():
        print("  mix failed", flush=True)
        return

    branded = d / "branded.mp4"
    brand_video(str(mixed), str(branded), name=name, emoji=emoji, follow=False)
    final = d / "final.mp4"
    add_subs_and_follow(str(branded), str(srt), str(final), handle=handle, accent=GOLD,
                        comment=comment, hook=hook, lesson=lesson, badge=badge,
                        next_tease=next_tease, offset=offset, hold=hold)
    print(f"FINAL -> {final}  ({total:.1f}s)", flush=True)
    return final


if __name__ == "__main__":
    finish(sys.argv[1] if len(sys.argv) > 1 else max(
        (p for p in (ROOT / "output").glob("viking_*")), key=lambda p: p.stat().st_mtime))
