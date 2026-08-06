"""Timeline device — dated nodes reveal down a vertical track ("how we got here").
Turns a reel into a story arc. Cheap PIL, $0.

    from modules.timeline import make_timeline_clip
    make_timeline_clip([("2019","Route opens"),("2022","Crisis hits"),("2026","Boom")],
                       "timeline.mp4", title="HOW WE GOT HERE", size=(704,1280))
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
    a = rgba[3] if len(rgba) > 3 else 255
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=(oc[0], oc[1], oc[2], a))
    d.text((x, y), text, font=fnt, fill=rgba)


def _wrap(d, text, fnt, max_w):
    lines, cur = [], []
    for w in text.split():
        if d.textlength(" ".join(cur + [w]), font=fnt) <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur)); cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines[:2]


def make_timeline_clip(events, out_path, title="", duration=5.0, size=(704, 1280),
                       accent="#FF3131", fps=30, bg_image=None):
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    events = [(str(dte), str(txt)) for dte, txt in events][:5]
    if not events:
        return None
    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height); bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2; bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 175))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    tf = _font(int(W * 0.058)); df = _font(int(W * 0.05)); bf = _font(int(W * 0.044), "default")
    line_x = int(W * 0.14)
    top = int(H * 0.26); bot = int(H * 0.86)
    ne = len(events)
    ys = [int(top + i * (bot - top) / max(1, ne - 1)) for i in range(ne)] if ne > 1 else [(top + bot) // 2]
    txt_x = line_x + int(W * 0.06)
    max_w = W - txt_x - int(W * 0.06)
    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="tl_"))
    try:
        for f in range(n):
            t = f / (n - 1)
            frame = bg.copy(); d = ImageDraw.Draw(frame, "RGBA")
            if title:
                tt = title.upper(); tw = d.textlength(tt, font=tf)
                _outline(d, ((W - tw) / 2, int(H * 0.16)), tt, tf, (255, 255, 255, 255), 4)
            # growing vertical line
            grow = _ease(t / 0.9)
            ly = int(top + (bot - top) * grow)
            d.line([(line_x, top), (line_x, ly)], fill=ac + (255,), width=max(3, int(W * 0.008)))
            for i, (dte, txt) in enumerate(events):
                p = _ease((t - (i / ne) * 0.85) / 0.25)
                if p <= 0:
                    continue
                y = ys[i]; a = int(255 * p); xo = int((1 - p) * W * 0.05)
                r = int(W * 0.018)
                d.ellipse([line_x - r, y - r, line_x + r, y + r], fill=ac + (a,))
                d.ellipse([line_x - r * 0.4, y - r * 0.4, line_x + r * 0.4, y + r * 0.4], fill=(255, 255, 255, a))
                _outline(d, (txt_x + xo, y - int(W * 0.062)), dte, df, ac + (a,), 3)
                for li, ln in enumerate(_wrap(d, txt, bf, max_w)):
                    _outline(d, (txt_x + xo, y - int(W * 0.008) + li * int(W * 0.058)), ln, bf, (255, 255, 255, a), 2)
            frame.save(tmp / f"f{f:05d}.png")
        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_timeline_clip([("2019", "The route opens to global trade"), ("2022", "A crisis chokes supply"),
                        ("2026", "Africa's ports take center stage")],
                       "output/timeline_demo.mp4", title="How we got here", size=(704, 1280))
    print("wrote output/timeline_demo.mp4")
