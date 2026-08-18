"""
Halftime analysis DEMO — builds only, never posts.

Takes real match footage and cuts a studio-style analysis beat:
    play -> slow motion -> freeze + telestration -> back to full speed
Players are detected in the freeze frame so the spotlights land on real
bodies. Nothing is claimed as a statistic; the graphics point at what is
visibly happening on screen.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from moviepy import (VideoFileClip, CompositeVideoClip, ImageClip,
                     concatenate_videoclips)

from modules.halftime import detect_players, overlay_clip, W, H

SRC = "assets/owner_media/normalized/2026-08-17T08-06-15_video_part3.mp4"
OUT = "output/halftime_demo.mp4"
FREEZE_AT = 5.0          # the moment we stop on
LEAD = 3.0               # normal-speed run-in
SLOW = 2.2               # seconds of source played slowly
HOLD = 6.5               # freeze + telestration
TAIL = 2.5               # release back to full speed


def _fit(clip):
    s = max(W / clip.w, H / clip.h)
    c = clip.resized(s)
    return c.cropped(x_center=c.w / 2, y_center=c.h / 2, width=W, height=H)


def find_tactical_moment(src, dur):
    """Pick a WIDE frame with many players — not a close-up.

    Freezing at a fixed timestamp landed on a two-man close-up while the
    analyst note talked about space between the lines: the graphic asserting
    something the footage did not show. Scan instead, and freeze where the
    most players are actually visible.
    """
    best, best_n = None, -1
    lo = SLOW + 0.5
    hi = max(lo + 1, dur - TAIL - 0.5)
    step = max(1.0, (hi - lo) / 18)
    t = lo
    while t < hi:
        n = len(detect_players(Image.fromarray(src.get_frame(t)), max_n=8))
        if n > best_n:
            best, best_n = t, n
        t += step
    print(f"[Demo] scanned for a wide shot -> {best:.1f}s "
          f"with {best_n} players visible")
    return (best if best_n >= 2 else min(FREEZE_AT, hi)), best_n


def main():
    src = _fit(VideoFileClip(SRC).without_audio())
    dur = src.duration
    fz, n_seen = find_tactical_moment(src, dur)

    lead = src.subclipped(max(0, fz - LEAD - SLOW), max(0.01, fz - SLOW))
    slow = src.subclipped(max(0, fz - SLOW), fz).with_speed_scaled(0.4)
    still = Image.fromarray(src.get_frame(fz))
    tail = src.subclipped(fz, min(dur, fz + TAIL))

    print(f"[Demo] source {dur:.1f}s, freezing at {fz:.1f}s")

    # --- find the players in the frozen frame -------------------------------
    boxes = detect_players(still, max_n=3)
    print(f"[Demo] players detected in freeze frame: {len(boxes)}")
    marks = []
    labels = ["THE BALL CARRIER", "THE SPARE MAN", "THE COVER"]
    for i, (x, y, bw, bh, wt) in enumerate(boxes):
        marks.append({"kind": "ring", "x": int(x + bw / 2),
                      "y": int(y + bh * 0.92), "r": int(max(90, bw * 1.5)),
                      "label": labels[i] if i < len(labels) else "",
                      "colour": (60, 220, 255) if i == 0 else (255, 200, 0)})
    if boxes:
        x, y, bw, bh, _ = boxes[0]
        marks.append({"kind": "arrow",
                      "from": (int(x + bw / 2), int(y + bh * 0.6)),
                      "to": (int(min(W - 90, x + bw / 2 + 380)),
                             int(max(200, y - 170))), "colour": (255, 200, 0)})
    if len(boxes) > 1:
        marks.append({"kind": "zone",
                      "box": (int(W * 0.08), int(H * 0.60),
                              int(W * 0.62), int(H * 0.72)),
                      "colour": (235, 70, 60)})

    # Notes describe only what the frame actually shows. The demo must not
    # assert a tactical claim the footage cannot support.
    NOTE_SLOW = "Slowing it down — watch how the shape holds as play develops."
    NOTE_FREEZE = (f"Frozen here with {n_seen} players in frame. "
                   "Look at the distances between them.")

    parts = [
        CompositeVideoClip([lead, overlay_clip((W, H), lead.duration, "play",
                                               "", "")], size=(W, H)),
        CompositeVideoClip([slow, overlay_clip((W, H), slow.duration, "slow",
                                               "", NOTE_SLOW)], size=(W, H)),
        CompositeVideoClip([ImageClip(str(_save(still))).with_duration(HOLD),
                            overlay_clip((W, H), HOLD, "freeze", "",
                                         NOTE_FREEZE, marks)], size=(W, H)),
        CompositeVideoClip([tail, overlay_clip((W, H), tail.duration,
                                               "release", "", "")],
                           size=(W, H)),
    ]
    final = concatenate_videoclips(parts, method="compose")
    final.write_videofile(OUT, fps=30, codec="libx264", audio=False,
                          logger=None)
    print(f"[Demo] wrote {OUT} ({final.duration:.1f}s)")


def _save(img):
    p = Path("output/_halftime_freeze.png")
    img.save(p)
    return p


if __name__ == "__main__":
    main()
