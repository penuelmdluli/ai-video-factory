"""Flow / process steps device — numbered boxes reveal top→bottom with connecting arrows
("how X works"). Cheap PIL, $0.

    from modules.flow_steps import make_flow_clip
    make_flow_clip(["Oil loads at the Gulf","Ships pass the strait","The world gets fuel"],
                   "flow.mp4", title="HOW IT WORKS", size=(704,1280))
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


def make_flow_clip(steps, out_path, title="", duration=4.0, size=(704, 1280),
                   accent="#FF3131", fps=30, bg_image=None):
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    steps = [str(s) for s in steps][:4]
    if not steps:
        return None
    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height); bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2; bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 175))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    tf = _font(int(W * 0.056)); nf = _font(int(W * 0.05)); bf = _font(int(W * 0.044), "default")
    ns = len(steps)
    m = int(W * 0.08)
    top = int(H * 0.26)
    box_h = int(H * 0.11); gap = int(H * 0.05)
    box_w = W - m * 2
    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="flow_"))
    try:
        for f in range(n):
            t = f / (n - 1)
            frame = bg.copy(); d = ImageDraw.Draw(frame, "RGBA")
            if title:
                tt = title.upper(); tw = d.textlength(tt, font=tf)
                _outline(d, ((W - tw) / 2, int(H * 0.16)), tt, tf, (255, 255, 255, 255), 4)
            for i, step in enumerate(steps):
                p = _ease((t - (i / ns) * 0.8) / 0.28)
                if p <= 0:
                    continue
                y = top + i * (box_h + gap); a = int(255 * p); yo = int((1 - p) * H * 0.03)
                yy = y - yo
                # connecting arrow from the previous box
                if i > 0:
                    ax = m + int(W * 0.09)
                    d.line([(ax, y - gap - yo), (ax, yy)], fill=ac + (a,), width=max(3, int(W * 0.008)))
                    d.polygon([(ax - int(W * 0.02), yy - int(W * 0.02)), (ax + int(W * 0.02), yy - int(W * 0.02)),
                               (ax, yy + int(W * 0.005))], fill=ac + (a,))
                # box
                d.rounded_rectangle([m, yy, m + box_w, yy + box_h], radius=int(H * 0.018),
                                    fill=(22, 30, 40, min(235, a)))
                # number badge
                br = int(box_h * 0.36); bx = m + int(W * 0.06); by = yy + box_h // 2
                d.ellipse([bx - br, by - br, bx + br, by + br], fill=ac + (a,))
                num = str(i + 1); nw = d.textlength(num, font=nf)
                _outline(d, (bx - nw / 2, by - nf.size * 0.62), num, nf, (255, 255, 255, a), 2)
                # step text (wrapped)
                tx = bx + br + int(W * 0.04); mw = m + box_w - tx - int(W * 0.03)
                lines = _wrap(d, step, bf, mw)
                ty = by - (len(lines) * int(W * 0.05)) // 2
                for ln in lines:
                    _outline(d, (tx, ty), ln, bf, (255, 255, 255, a), 2)
                    ty += int(W * 0.05)
            frame.save(tmp / f"f{f:05d}.png")
        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_flow_clip(["Oil loads at the Gulf ports", "Tankers pass through the narrow strait",
                    "The world receives its fuel"], "output/flow_demo.mp4", title="How it works", size=(704, 1280))
    print("wrote output/flow_demo.mp4")
