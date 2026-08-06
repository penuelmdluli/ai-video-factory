"""Line-chart draw-on device — a trend line draws in left→right with an area fill and a
moving endpoint value. Finance/trends. Cheap PIL, $0.

    from modules.line_chart import make_line_chart_clip
    make_line_chart_clip([("2015",100),("2020",240),("2026",880)], "chart.mp4",
                         title="R1,000 INVESTED", prefix="R", size=(704,1280))
"""
import subprocess
import tempfile
from pathlib import Path


def _ff():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _font(size, kind="news"):
    from modules.thumbnail_pro import _font as pf
    return pf(size, kind)


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _outline(d, xy, text, fnt, rgba, ow=3, oc=(12, 14, 20)):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=oc)
    d.text((x, y), text, font=fnt, fill=rgba)


def make_line_chart_clip(points, out_path, title="", duration=4.0, size=(704, 1280),
                         accent="#FF3131", prefix="", suffix="", fps=30, bg_image=None):
    """points: list of (x_label, value). Line draws in; endpoint value counts up."""
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    pts = [(str(l), float(v)) for l, v in points]
    if len(pts) < 2:
        return None
    vals = [v for _, v in pts]
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or 1.0

    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height); bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2; bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 175))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    tf = _font(int(W * 0.058)); vf = _font(int(W * 0.075)); lf = _font(int(W * 0.038), "default")
    m = int(W * 0.10)
    x0, x1 = m, W - m
    y0, y1 = int(H * 0.34), int(H * 0.72)          # chart area (top=high value)

    def px(i): return x0 + (x1 - x0) * i / (len(pts) - 1)
    def py(v): return y1 - (y1 - y0) * (v - vmin) / span
    xy = [(px(i), py(v)) for i, (_, v) in enumerate(pts)]

    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="chart_"))
    try:
        for f in range(n):
            t = f / (n - 1); prog = _ease(t)
            frame = bg.copy(); d = ImageDraw.Draw(frame, "RGBA")
            if title:
                tt = title.upper(); tw = d.textlength(tt, font=tf)
                _outline(d, ((W - tw) / 2, int(H * 0.2)), tt, tf, (255, 255, 255), 4)
            # faint grid
            for gy in range(4):
                yy = y0 + (y1 - y0) * gy / 3
                d.line([(x0, yy), (x1, yy)], fill=(255, 255, 255, 22), width=1)
            # points drawn up to prog along the polyline
            seg = prog * (len(xy) - 1)
            drawn = [xy[0]]
            for i in range(1, len(xy)):
                if seg >= i:
                    drawn.append(xy[i])
                else:
                    frac = seg - (i - 1)
                    if frac > 0:
                        ax, ay = xy[i - 1]; bx, by = xy[i]
                        drawn.append((ax + (bx - ax) * frac, ay + (by - ay) * frac))
                    break
            if len(drawn) >= 2:
                # area fill under the drawn line
                poly = drawn + [(drawn[-1][0], y1), (drawn[0][0], y1)]
                d.polygon(poly, fill=ac + (60,))
                d.line(drawn, fill=ac + (255,), width=max(3, int(W * 0.008)), joint="curve")
            tip = drawn[-1]
            r = int(W * 0.014)
            d.ellipse([tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r], fill=(255, 255, 255, 255))
            # endpoint value derived from the current tip height
            curv = vmin + span * ((y1 - tip[1]) / (y1 - y0)) if (y1 - y0) else vmax
            vtxt = f"{prefix}{curv:,.0f}{suffix}"
            _outline(d, (min(tip[0] + int(W * 0.02), W - m - d.textlength(vtxt, font=vf)), tip[1] - int(W * 0.09)),
                     vtxt, vf, ac + (255,), 4)
            # x labels
            for i, (lab, _v) in enumerate(pts):
                lw = d.textlength(lab, font=lf)
                _outline(d, (px(i) - lw / 2, y1 + int(H * 0.02)), lab, lf, (220, 228, 236), 2)
            frame.save(tmp / f"f{f:05d}.png")
        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_line_chart_clip([("2015", 100), ("2018", 210), ("2021", 380), ("2026", 880)],
                         "output/chart_demo.mp4", title="R1,000 invested", prefix="R", size=(704, 1280))
    print("wrote output/chart_demo.mp4")
