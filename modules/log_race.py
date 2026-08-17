"""
The Log Race v2 — the table as a GAME. After a matchweek, movers climb ONE
AT A TIME: their row lifts, glows, slides past rivals with their result chip
("W 3-0 +3") riding along, points tick up and pop on landing. Crests on
every row, big-three in club colours.

Usage:
    from modules.log_race import render_log_race
    render_log_race(rows, prev_ranks, "out.mp4")
"""
import math
from pathlib import Path

W, H = 1080, 1920
ROW_H = 92
TOP = 344
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
                    results: dict | None = None,
                    duration: float | None = None, fps: int = 30) -> str:
    """rows: final standings (get_log(16)); prev_ranks: {key: old_rank};
    results: optional {team_key: 'W 3-0'} chips for the movers."""
    import numpy as np
    from PIL import Image, ImageDraw
    from moviepy import VideoClip
    from modules.club_brand import official_badge

    results = results or {}
    final_by_key = {(r.get("team_key") or r["name"]): r for r in rows}
    keys = list(final_by_key.keys())

    # movers, biggest climb first — they animate ONE AT A TIME
    movers = [k for k in keys
              if prev_ranks.get(k, final_by_key[k]["rank"])
              != final_by_key[k]["rank"]]
    movers.sort(key=lambda k: (prev_ranks.get(k, 99)
                               - final_by_key[k]["rank"]), reverse=True)
    movers = movers[:5]

    T_INTRO = 2.4
    T_PER = 2.3
    T_END = 2.6
    total = duration or (T_INTRO + T_PER * len(movers) + T_END)

    crests = {}
    for k in keys:
        p = official_badge(k)
        if p:
            im = Image.open(p).convert("RGBA")
            r = 60 / max(im.width, im.height)
            crests[k] = im.resize((int(im.width * r), int(im.height * r)))

    def rank_at(k, t):
        """current visual rank (float) for team k at time t"""
        old = prev_ranks.get(k, final_by_key[k]["rank"])
        new = final_by_key[k]["rank"]
        if k not in movers:
            # non-movers get displaced when a mover passes them: approximate
            # by interpolating old->new across the whole movers window
            u = _ease((t - T_INTRO) / max(T_PER * len(movers), 1e-6))
            return old + (new - old) * u
        i = movers.index(k)
        t0 = T_INTRO + i * T_PER
        u = _ease((t - t0) / (T_PER * 0.75))
        return old + (new - old) * u

    def frame(t):
        im = Image.new("RGB", (W, H), (12, 14, 18))
        d = ImageDraw.Draw(im, "RGBA")
        for i in range(150):
            a = 1 - i / 150
            d.line([(0, i), (W, i)],
                   fill=(int(30 * a) + 12, int(60 * a) + 14, int(30 * a) + 18))
        d.text((44, 40), "GENESIS NEWS", font=_font(42), fill=(255, 255, 255))
        d.text((46, 96), "THE LOG RACE", font=_font(28, False),
               fill=(255, 193, 7))
        # intro stamp
        if t < T_INTRO:
            u = _ease(min(1, t / 0.4)) * _ease(min(1, (T_INTRO - t) / 0.4))
            sf = _font(44)
            msg = "RESULTS ARE IN — WATCH THE TABLE MOVE"
            swid = d.textlength(msg, font=sf)
            d.rounded_rectangle([(W - swid) / 2 - 24, 210,
                                 (W + swid) / 2 + 24, 292], radius=16,
                                fill=(255, 193, 7, int(235 * u)))
            d.text(((W - swid) / 2, 226), msg, font=sf,
                   fill=(12, 12, 12, int(255 * u)))

        # which mover is active
        active = None
        if T_INTRO <= t < T_INTRO + T_PER * len(movers):
            active = movers[int((t - T_INTRO) // T_PER)]

        for k in sorted(keys, key=lambda kk: (kk == active)):  # mover ON TOP
            r = final_by_key[k]
            vis = rank_at(k, t)
            y = TOP + (vis - 1) * ROW_H
            hot = k in BIG
            moving = k == active
            lift = -10 if moving else 0
            row_col = BIG[k] if hot else (19, 22, 28, 235)
            fg = (12, 12, 12) if hot else (232, 236, 242)
            if moving:                          # glow behind active mover
                pulse = 0.5 + 0.5 * abs(math.sin(t * 5))
                d.rounded_rectangle([36, y - 8 + lift, W - 36,
                                     y + ROW_H - 4 + lift], radius=20,
                                    fill=(90, 200, 255, int(90 * pulse)))
            d.rounded_rectangle([44, y + lift, W - 44,
                                 y + ROW_H - 12 + lift],
                                radius=16, fill=row_col)
            shown_rank = int(round(vis))
            d.text((74, y + 18 + lift), str(shown_rank), font=_font(36),
                   fill=fg)
            if k in crests:
                im.paste(crests[k], (150, int(y + 8 + lift)), crests[k])
            d.text((236, y + 18 + lift), str(r["name"])[:16],
                   font=_font(36), fill=fg)
            # points tick up as the mover lands
            old_r = prev_ranks.get(k, r["rank"])
            climbed = old_r != r["rank"]
            pts = r["points"]
            if k in movers:
                i = movers.index(k)
                t_land = T_INTRO + i * T_PER + T_PER * 0.6
                u = _ease(min(1, max(0, (t - t_land) / 0.5)))
                chip_txt = results.get(k, "")
                gained = 3 if chip_txt.startswith("W") else \
                    1 if chip_txt.startswith("D") else 3
                pts_from = max(0, r["points"] - gained)
                pts = int(round(pts_from + (r["points"] - pts_from) * u))
            pw = d.textlength(f"{pts} pts", font=_font(34))
            d.text((W - 210 - pw, y + 20 + lift), f"{pts} pts",
                   font=_font(34), fill=fg)
            # movement arrow + result chip
            if climbed and t > T_INTRO:
                up = r["rank"] < old_r
                col = (60, 190, 90) if up else (215, 65, 65)
                cx, cy = W - 120, y + ROW_H // 2 - 6 + lift
                tri = [(cx - 15, cy + 9), (cx + 15, cy + 9), (cx, cy - 13)] \
                    if up else [(cx - 15, cy - 13), (cx + 15, cy - 13),
                                (cx, cy + 9)]
                d.polygon(tri, fill=col)
                chip = results.get(k, "")
                if chip and moving:
                    cf = _font(28)
                    cw2 = d.textlength(chip, font=cf)
                    d.rounded_rectangle([W - 44 - cw2 - 24, y - 44 + lift,
                                         W - 44, y - 2 + lift], radius=10,
                                        fill=(60, 190, 90, 235))
                    d.text((W - 56 - cw2, y - 38 + lift), chip, font=cf,
                           fill=(255, 255, 255))

        if t > total - T_END:
            u = _ease(min(1, (t - (total - T_END)) / 0.4))
            foot = "Where does YOUR team land next week? 👇"
            ff = _font(32)
            fw = d.textlength(foot.replace("👇", ""), font=ff)
            d.rounded_rectangle([(W - fw) / 2 - 24, H - 150,
                                 (W + fw) / 2 + 24, H - 84], radius=14,
                                fill=(255, 193, 7, int(235 * u)))
            d.text(((W - fw) / 2, H - 138), foot.replace(" 👇", ""),
                   font=ff, fill=(12, 12, 12, int(255 * u)))
        return np.array(im)

    clip = VideoClip(frame, duration=total)
    clip.write_videofile(str(out_path), fps=fps, codec="libx264",
                         audio=False, logger=None, preset="medium")
    return str(out_path)
