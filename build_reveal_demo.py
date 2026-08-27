"""
The reveal treatment, built as a real reel from real squad data.

Structure, and why it is in this order:

  0.0-2.6   the scan       something is visibly working. Nobody has been
                           promised anything yet, which is what buys the wait
  2.6-3.4   the crest      silhouette, then lit. Recognition, no words needed
  3.4-...   the names      one at a time, each on a slot wheel that slows
  last 2s   the question   the reel ends on a job for the viewer

The progress rail runs throughout: X OF 6, and how many are still to come.
That line is the whole retention mechanism - a viewer who knows three names
are left has a reason not to scroll, and it works with the sound off.

    python build_reveal_demo.py --club chiefs --group midfield
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from modules.motion_kit import W, H, GOLD, DARK, _font, _ease  # noqa: E402
from modules.reveal_kit import (  # noqa: E402
    ambient, hold_hook, progress_rail, scan_loader, silhouette_pop,
    slot_reveal)

SCAN_END = 2.6
CREST_END = 3.4
PER_NAME = 1.15
TAIL = 2.4


def _stage(t, seed=0):
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    for i in range(200):
        a = 1 - i / 200
        d.line([(0, i), (W, i)],
               fill=(int(26 * a) + 12, int(30 * a) + 14, int(38 * a) + 18))
    ambient(d, t, seed=seed)
    return im, d


def _header(d, title, sub):
    f = _font(40)
    d.text((90, 150), title.upper(), font=f, fill=GOLD)
    f2 = _font(30, False)
    d.text((90, 202), sub.upper(), font=f2, fill=(150, 158, 170))
    d.line([(90, 250), (W - 90, 250)], fill=(46, 50, 58), width=2)


def build(club, group, men, opponent, out_path):
    names = [m["name"].upper() for m in men]
    surnames = [n.split()[-1] for n in names]
    total = len(men)
    duration = CREST_END + total * PER_NAME + TAIL

    def frame(t):
        im, d = _stage(t)
        _header(d, f"{group} watch", f"{club} v {opponent}")

        if t < SCAN_END:
            scan_loader(d, t, label="READING THE TEAM SHEET",
                        cy=H // 2 - 60, done=min(1.0, t / SCAN_END),
                        club=club)
            hold_hook(d, t, "WHO MAKES THE CUT?", y=H // 2 + 300)
            progress_rail(d, 0, total, label="SEARCHING")
            return np.array(im)

        if t < CREST_END:
            silhouette_pop(d, (t - SCAN_END) / (CREST_END - SCAN_END),
                           club, W // 2, H // 2 - 60, size=340)
            progress_rail(d, 0, total, label="FOUND THEM")
            return np.array(im)

        idx = int((t - CREST_END) / PER_NAME)
        u_local = ((t - CREST_END) % PER_NAME) / PER_NAME

        shown = min(idx, total)
        # Centre the block on the stage. Fixed at 380 it sat under the header
        # with a third of the frame empty below the last name, which on a
        # phone reads as a video that has finished before it has.
        row_h = 148
        y0 = max(360, (H - 300 - total * row_h) // 2 + 120)
        for i in range(min(shown + 1, total)):
            y = y0 + i * row_h
            live = (i == idx and idx < total)
            u = u_local if live else 1.0
            # number chip
            chip_a = _ease(min(1.0, u * 1.6))
            cw = int(96 * chip_a)
            if cw > 2:
                d.rounded_rectangle([90, y, 90 + cw, y + 92], radius=14,
                                    fill=GOLD if live else (44, 49, 58))
                nf = _font(46)
                num = men[i]["no"] or "-"
                d.text((90 + cw / 2 - d.textlength(num, font=nf) / 2, y + 22),
                       num, font=nf, fill=DARK if live else GOLD)
            # A locked-in name stays bright. Dimming it made the finished
            # rows look like placeholders rather than answers.
            slot_reveal(d, u, surnames, surnames[i], 214, y + 14, size=76,
                        colour=(255, 255, 255) if live else (234, 239, 246))
            if live and u > 0.86:
                g = (u - 0.86) / 0.14
                d.line([(214, y + 104), (214 + int(420 * g), y + 104)],
                       fill=GOLD, width=4)

        progress_rail(d, min(shown + (1 if idx < total else 0), total), total)

        if idx >= total:
            k = (t - (CREST_END + total * PER_NAME)) / TAIL
            hold_hook(d, t, "WHO STARTS? TELL US BELOW", y=H - 420)
            if k > 0.35:
                f = _font(44)
                msg = "COMMENT YOUR XI"
                a = _ease(min(1.0, (k - 0.35) / 0.4))
                c = tuple(int(255 * a + DARK[i] * (1 - a)) for i in range(3))
                d.text((W / 2 - d.textlength(msg, font=f) / 2, H - 340),
                       msg, font=f, fill=c)
        return np.array(im)

    from moviepy import VideoClip
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    VideoClip(frame, duration=duration).write_videofile(
        str(out_path), fps=30, codec="libx264", audio=False, logger=None,
        preset="medium")
    return str(out_path), duration


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--group", default="midfield")
    ap.add_argument("--out", default="output/reveal_demo/reveal.mp4")
    a = ap.parse_args()

    from build_debate_video import contenders, GROUPS
    pos, title, label = GROUPS[a.group]
    # Gate the FULL list, then take six. Slicing first meant two men held back
    # left a four-name reel with confirmed players still sitting unused.
    men = contenders(a.club, pos)
    if not men:
        print("no squad data")
        return 1

    import asyncio
    from modules.availability import confirmed_available
    men, held, ev = asyncio.run(confirmed_available(a.club, men))
    for m, why in held:
        print("held back: " + m["name"] + " - " + why)
    men = men[:6]

    opp = "SIWELELE"
    try:
        from modules.psl_fixtures import next_fixture
        f = asyncio.run(next_fixture(a.club))
        if f:
            opp = (f["away"] if f.get("home_key") == a.club
                   else f["home"]).upper()
    except Exception:
        pass

    p, dur = build(a.club, label, men, opp, a.out)
    print(f"built {p}  ({dur:.1f}s, {len(men)} names)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
