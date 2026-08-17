"""
The Log Race — the Betway table as ANIMATED drama: rows glide from last
week's positions to this week's, points count up, movement arrows pulse,
the big three glow. Monday's static log card, but alive.

Usage:
    from modules.log_race import render_log_race
    path = render_log_race(rows, prev_ranks, "out.mp4", duration=18)
    # rows: get_log(16) output; prev_ranks: {team_key: old_rank}
"""
from pathlib import Path

W, H = 1080, 1920
ROW_H = 92
TOP = 330
BIG = {"chiefs": (255, 193, 7), "pirates": (235, 235, 235),
       "sundowns": (255, 205, 30)}


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _font(sz, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(
        f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}", sz)


def render_log_race(rows: list[dict], prev_ranks: dict, out_path,
                    duration: float = 18.0, fps: int = 30) -> str:
    """rows are FINAL standings; each team starts at prev rank and glides."""
    import math
    import numpy as np
    from PIL import Image, ImageDraw
    from moviepy import VideoClip

    n = len(rows)
    t_hold = 2.2          # show old table
    t_move = 3.2          # glide window
    final_by_key = {r.get("team_key") or r["name"]: r for r in rows}
    order = [(r.get("team_key") or r["name"]) for r in rows]

    def frame(t):
        im = Image.new("RGB", (W, H), (12, 14, 18))
        d = ImageDraw.Draw(im, "RGBA")
        for i in range(140):
            a = 1 - i / 140
            d.line([(0, i), (W, i)],
                   fill=(int(30 * a) + 12, int(60 * a) + 14, int(30 * a) + 18))
        d.text((44, 40), "GENESIS NEWS", font=_font(42), fill=(255, 255, 255))
        d.text((46, 96), "THE LOG RACE — this week's movers",
               font=_font(28, False), fill=(255, 193, 7))
        u = _ease((t - t_hold) / t_move)
        cnt = _ease(min(1, max(0, (t - t_hold) / (t_move + 1.0))))

        # draw lowest-priority first so risers glide OVER
        for key in sorted(order, key=lambda k: -final_by_key[k]["rank"]):
            r = final_by_key[key]
            new_i = r["rank"] - 1
            old_i = (prev_ranks.get(key, r["rank"])) - 1
            y = TOP + (old_i + (new_i - old_i) * u) * ROW_H
            hot = key in BIG
            moved = new_i != old_i
            if hot:
                acc = BIG[key]
                d.rounded_rectangle([44, y, W - 44, y + ROW_H - 12],
                                    radius=16, fill=acc)
                fg = (12, 12, 12)
            else:
                d.rounded_rectangle([44, y, W - 44, y + ROW_H - 12],
                                    radius=16, fill=(19, 22, 28, 235))
                fg = (232, 236, 242)
            d.text((74, y + 18), str(new_i + 1 if u >= 1 else old_i + 1
                                     if u <= 0 else new_i + 1),
                   font=_font(36), fill=fg)
            d.text((190, y + 18), str(r["name"])[:18], font=_font(36), fill=fg)
            pts_old = r["points"] - (3 if moved and new_i < old_i else 0)
            pts = int(round(pts_old + (r["points"] - pts_old) * cnt))
            pw = d.textlength(f"{pts} pts", font=_font(34))
            d.text((W - 200 - pw, y + 20), f"{pts} pts", font=_font(34), fill=fg)
            if moved and t > t_hold:
                pulse = 0.6 + 0.4 * abs(math.sin(t * 3))
                up = new_i < old_i
                col = (60, 190, 90, int(255 * pulse)) if up \
                    else (215, 65, 65, int(255 * pulse))
                cx = W - 110
                cy = y + ROW_H // 2 - 6
                pts_tri = [(cx - 16, cy + 10), (cx + 16, cy + 10),
                           (cx, cy - 14)] if up else \
                    [(cx - 16, cy - 14), (cx + 16, cy - 14), (cx, cy + 10)]
                d.polygon(pts_tri, fill=col)

        foot = "Where does YOUR team land next week? Follow Genesis News"
        ff = _font(30)
        fw = d.textlength(foot, font=ff)
        d.text(((W - fw) / 2, H - 120), foot, font=ff, fill=(255, 193, 7))
        return np.array(im)

    clip = VideoClip(frame, duration=duration)
    clip.write_videofile(str(out_path), fps=fps, codec="libx264",
                         audio=False, logger=None, preset="medium")
    return str(out_path)
