"""Versus device — a two-panel comparison (bad ❌ vs good ✅, or A vs B) with a VS badge.
Great for "what most people do vs what works", head-to-heads, before/after. Cheap PIL, $0.

    from modules.versus import make_versus_clip
    make_versus_clip({"label": "MOST PEOPLE", "text": "React to the news"},
                     {"label": "WINNERS", "text": "Follow the money"},
                     "vs.mp4", title="THE DIFFERENCE", size=(704, 1280))
"""
import subprocess
import tempfile
from pathlib import Path

BAD = (200, 58, 52)     # red
GOOD = (34, 160, 100)   # green


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
    return lines[:3]


def _panel(d, x0, y0, x1, y1, color, a):
    d.rectangle([x0, y0, x1, y1], fill=color + (int(a * 0.30),))
    d.rectangle([x0, y0, x0 + int((x1 - x0) * 0.02), y1], fill=color + (a,))


def make_versus_clip(left, right, out_path, title="", duration=4.0, size=(704, 1280),
                     accent="#FF3131", fps=30, bg_image=None):
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    lcol = _hex(left.get("color")) if left.get("color") else BAD
    rcol = _hex(right.get("color")) if right.get("color") else GOOD

    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height); bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2; bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 185))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    tf = _font(int(W * 0.055)); lf = _font(int(W * 0.052)); bf = _font(int(W * 0.05), "default"); vf = _font(int(W * 0.09))
    mid = H // 2
    pm = int(W * 0.05)
    top0, top1 = int(H * 0.18), mid - int(H * 0.02)
    bot0, bot1 = mid + int(H * 0.02), int(H * 0.92)
    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="vs_"))
    try:
        for f in range(n):
            t = f / (n - 1)
            frame = bg.copy(); d = ImageDraw.Draw(frame, "RGBA")
            if title:
                tt = title.upper(); tw = d.textlength(tt, font=tf)
                _outline(d, ((W - tw) / 2, int(H * 0.08)), tt, tf, (255, 255, 255, 255), 4)
            # top panel (left / bad) slides down; bottom (right / good) slides up
            pl = _ease(t / 0.5); pr = _ease((t - 0.15) / 0.5)
            if pl > 0:
                xo = int((1 - pl) * W * 0.5); a = int(255 * pl)
                _panel(d, pm - xo, top0, W - pm - xo, top1, lcol, a)
                _mark(d, pm + int(W * 0.05) - xo, top0 + int(H * 0.05), int(W * 0.05), lcol, a, "x")
                _text_block(d, left, pm + int(W * 0.16) - xo, top0, top1, W - 2 * pm - int(W * 0.18), lf, bf, a)
            if pr > 0:
                xo = int((1 - pr) * W * 0.5); a = int(255 * pr)
                _panel(d, pm + xo, bot0, W - pm + xo, bot1, rcol, a)
                _mark(d, pm + int(W * 0.05) + xo, bot0 + int(H * 0.05), int(W * 0.05), rcol, a, "v")
                _text_block(d, right, pm + int(W * 0.16) + xo, bot0, bot1, W - 2 * pm - int(W * 0.18), lf, bf, a)
            # VS badge
            pv = _ease((t - 0.35) / 0.3)
            if pv > 0:
                r = int(W * 0.10 * pv)
                cx, cy = W // 2, mid
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ac + (255,), outline=(255, 255, 255, 255), width=max(2, int(W * 0.006)))
                vt = "VS"; vw = d.textlength(vt, font=vf)
                if pv > 0.6:
                    _outline(d, (cx - vw / 2, cy - vf.size * 0.62), vt, vf, (255, 255, 255, 255), 3)
            frame.save(tmp / f"f{f:05d}.png")
        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def _mark(d, x, y, s, color, a, kind):
    """Draw an X (bad) or check (good) mark."""
    w = max(4, int(s * 0.22))
    if kind == "x":
        d.line([(x, y), (x + s, y + s)], fill=(255, 255, 255, a), width=w)
        d.line([(x + s, y), (x, y + s)], fill=(255, 255, 255, a), width=w)
    else:
        d.line([(x, y + s * 0.55), (x + s * 0.4, y + s), (x + s, y)], fill=(255, 255, 255, a), width=w, joint="curve")


def _text_block(d, side, x, y0, y1, max_w, lf, bf, a):
    lab = str(side.get("label", "")).upper()
    if lab:
        _outline(d, (x, y0 + int((y1 - y0) * 0.14)), lab, lf, (255, 255, 255, a), 3)
    txt = str(side.get("text", ""))
    from PIL import Image, ImageDraw
    lines = _wrap(d, txt, bf, max_w)
    ty = y0 + int((y1 - y0) * 0.36)
    for ln in lines:
        _outline(d, (x, ty), ln, bf, (235, 240, 245, a), 2)
        ty += int(bf.size * 1.2)


if __name__ == "__main__":
    make_versus_clip({"label": "Most people", "text": "React to the headlines"},
                     {"label": "Winners", "text": "Follow the money quietly"},
                     "output/versus_demo.mp4", title="The difference", size=(704, 1280))
    print("wrote output/versus_demo.mp4")
