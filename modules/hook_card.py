"""Kinetic hook card — a fast word-by-word typographic intro (first ~1.5s pattern
interrupt). Stopping the scroll in the first 2 seconds is the single biggest retention
lever. Cheap MoviePy/PIL, $0.

    from modules.hook_card import make_hook_card
    make_hook_card("This strait controls the world", "hook.mp4", size=(704, 1280))
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


def _font(size):
    from modules.thumbnail_pro import _font as pf
    return pf(size, "news")


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _outline(d, xy, text, fnt, rgba, ow, oc=(12, 14, 20)):
    x, y = xy
    a = rgba[3] if len(rgba) > 3 else 255
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=(oc[0], oc[1], oc[2], a))
    d.text((x, y), text, font=fnt, fill=rgba)


def make_hook_card(text, out_path, duration=1.6, size=(704, 1280), accent="#FF3131",
                   bg_image=None, fps=30):
    """Render a word-by-word kinetic hook card. Returns out_path or None."""
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    words = [w for w in str(text).upper().split() if w][:12] or ["BREAKING"]

    # background: darkened hero, or a deep ground
    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 175))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    # font sized to wrap to <= 4 lines within 88% width
    dmy = ImageDraw.Draw(bg)

    def wrap(fnt):
        lines, cur = [], []
        for w in words:
            if dmy.textlength(" ".join(cur + [w]), font=fnt) <= W * 0.88 or not cur:
                cur.append(w)
            else:
                lines.append(cur); cur = [w]
        if cur:
            lines.append(cur)
        return lines

    fs = int(W * 0.16); font = _font(fs); lines = wrap(font)
    while len(lines) > 4 and fs > int(W * 0.07):
        fs -= int(W * 0.008); font = _font(fs); lines = wrap(font)
    # also shrink until every line (incl. a single long word) fits the safe width — no cut-off
    while any(dmy.textlength(" ".join(l), font=font) > W * 0.9 for l in lines) and fs > int(W * 0.06):
        fs -= int(W * 0.006); font = _font(fs); lines = wrap(font)
    lh = int(fs * 1.08)

    # word layout (centered lines) with a global index for the pop stagger
    space = dmy.textlength(" ", font=font)
    positions, gi = [], 0
    total_h = lh * len(lines); y0 = (H - total_h) // 2
    for li, line in enumerate(lines):
        lw = sum(dmy.textlength(w, font=font) for w in line) + space * (len(line) - 1)
        x = (W - lw) // 2; y = y0 + li * lh
        for w in line:
            positions.append((w, x, y, gi)); gi += 1
            x += dmy.textlength(w, font=font) + space
    nwords = len(positions)
    reveal_span = 0.62 * duration; pop = 0.30 * duration; per = reveal_span / max(1, nwords)
    ow = max(4, int(fs * 0.05))

    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="hook_"))
    try:
        for i in range(n):
            t = i / (n - 1) * duration
            frame = bg.copy()
            d = ImageDraw.Draw(frame, "RGBA")
            # accent flash on the first ~0.18s — the pattern interrupt
            flash_dur = 0.18 * duration
            if t < flash_dur:
                d.rectangle([0, 0, W, H], fill=ac + (int(110 * (1 - t / flash_dur)),))
            for (w, x, y, g) in positions:
                p = _ease((t - g * per) / pop)
                if p <= 0:
                    continue
                a = int(255 * p); yo = int((1 - p) * fs * 0.45)   # fade + rise
                _outline(d, (x, y - yo), w, font, (255, 255, 255, a), ow)
            frame.save(tmp / f"f{i:05d}.png")

        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 6000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_hook_card("This strait controls the world's oil", "output/hook_demo.mp4", size=(704, 1280))
    print("wrote output/hook_demo.mp4")
