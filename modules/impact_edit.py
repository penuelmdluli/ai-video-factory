"""Impact edit for the Veo shorts — the $0 layer that turns raw generations into a cut that hits.

Plain concat wastes good footage: the clips are graded flat, the joins are invisible, and the last
frame vanishes before the lesson lands. This module does five things, all in ffmpeg:

  1. GRADE      teal-orange contrast push — cold shadows, fire-warm highlights (the Hollywood look)
  2. FLASH CUT  a 3-frame white flash at every join, so cuts read as hits instead of edits
  3. SHAKE      a short handheld jolt on the designated impact shot (the collision, the hammer)
  4. BOOM       a sub-bass thud dropped on each cut, under the Veo battle audio
  5. FREEZE     the final frame held, giving the lesson card somewhere to live

Every stage degrades to plain concat rather than failing the build.
"""
import math
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

W, H, FPS = 1080, 1920, 24

# Teal shadows + warm highlights, a contrast push and a light sharpen. Tuned to survive
# Facebook/TikTok re-encoding, which flattens anything subtle.
GRADE = ("eq=contrast=1.14:saturation=1.16:gamma=0.97,"
         "colorbalance=rs=-0.05:bs=0.07:rm=0.02:bm=-0.02:rh=0.07:bh=-0.05,"
         "unsharp=5:5:0.5:5:5:0.0")


def _ff():
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path):
    r = subprocess.run([_ff(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 8.0


def _shake_filter(strength=11, dur=0.55):
    """Handheld jolt: overscan 5%, then wobble the crop window on a decaying sine for `dur`."""
    decay = f"exp(-t*4.5)"
    x = (f"(iw-ow)/2+if(lt(t,{dur}),{strength}*{decay}*sin(t*78),0)")
    y = (f"(ih-oh)/2+if(lt(t,{dur}),{int(strength*0.8)}*{decay}*sin(t*103),0)")
    return f"scale=iw*1.05:ih*1.05,crop={W}:{H}:x='{x}':y='{y}'"


def _make_boom(path, freq=48, dur=0.75):
    """A short sub-bass thud used to punctuate cuts."""
    subprocess.run([
        _ff(), "-y", "-f", "lavfi", "-t", str(dur), "-i",
        f"sine=frequency={freq}:sample_rate=44100",
        "-af", f"afade=t=out:st=0.02:d={dur - 0.02},volume=1.0,aformat=channel_layouts=stereo",
        str(path)], capture_output=True)
    return path if Path(path).exists() else None


def _plain_concat(clips, out):
    """Last-resort join: scale, pad, concat. No grade, no flash, no boom."""
    ff = _ff()
    ins = []
    for c in clips:
        ins += ["-i", str(c)]
    n = len(clips)
    filt = ";".join(
        f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v{i}]" for i in range(n))
    fc = filt + ";" + "".join(f"[v{i}][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    subprocess.run([ff, "-y", *ins, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-c:a", "aac", "-pix_fmt", "yuv420p", str(out)], capture_output=True)
    return str(out) if Path(out).exists() else None


def impact_concat(clips, out, impact=None, freeze=1.6, boom=True, grade=True):
    """Join `clips` into `out` with the impact treatment applied.

    impact: index of the shot that gets the shake (the collision / the hammer / the fall).
    freeze: seconds of held final frame at the end — where the lesson card sits.
    Returns the output path, or None if even plain concat failed.
    """
    clips = [str(c) for c in clips]
    if not clips:
        return None
    out = str(out)
    work = Path(out).parent
    ff = _ff()
    n = len(clips)
    last = n - 1

    ins = []
    for c in clips:
        ins += ["-i", str(c)]

    vparts, aparts = [], []
    for i in range(n):
        v = (f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
             f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}")
        if grade:
            v += "," + GRADE
        if impact is not None and i == impact:
            v += "," + _shake_filter()
        # Open on a black fade; every later join opens on a white flash so the cut reads as a hit.
        v += ",fade=t=in:st=0:d=0.30:color=black" if i == 0 else ",fade=t=in:st=0:d=0.11:color=white"
        if i == last and freeze > 0:
            v += f",tpad=stop_mode=clone:stop_duration={freeze:.2f}"
        vparts.append(v + f"[v{i}]")

        a = f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
        if i == last and freeze > 0:
            a += f",apad=pad_dur={freeze:.2f}"
        aparts.append(a + f"[a{i}]")

    fc = (";".join(vparts + aparts) + ";"
          + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    raw = work / "_impact_raw.mp4"
    r = subprocess.run([ff, "-y", *ins, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                        "-c:a", "aac", "-pix_fmt", "yuv420p", str(raw)], capture_output=True)
    if not raw.exists():
        print("  impact edit failed, falling back to plain concat", flush=True)
        if r.stderr:
            print("   " + r.stderr.decode("utf-8", "ignore").strip().splitlines()[-1], flush=True)
        return _plain_concat(clips, out)

    if not boom:
        Path(raw).replace(out)
        return out

    # Drop a sub-bass thud on each cut (and on the first frame) under the Veo battle audio.
    cuts, t = [0.0], 0.0
    for c in clips[:-1]:
        t += duration(c)
        cuts.append(t)
    bp = _make_boom(work / "_boom.wav")
    if not bp:
        Path(raw).replace(out)
        return out

    bins, chain, mix = [], [], "[0:a]"
    for j, ct in enumerate(cuts[:5]):
        bins += ["-i", str(bp)]
        ms = int(max(0.0, ct - 0.05) * 1000)
        chain.append(f"[{j+1}:a]volume=0.45,adelay={ms}|{ms}[b{j}]")
        mix += f"[b{j}]"
    fc2 = ";".join(chain) + ";" + mix + f"amix=inputs={len(cuts[:5])+1}:normalize=0:duration=first[a]"
    subprocess.run([ff, "-y", "-i", str(raw), *bins, "-filter_complex", fc2,
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", out],
                   capture_output=True)
    if not Path(out).exists():
        Path(raw).replace(out)
    else:
        Path(raw).unlink(missing_ok=True)
    Path(bp).unlink(missing_ok=True)
    return out
