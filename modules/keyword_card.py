"""Keyword-illustration card — the core faceless device.

Shows one spoken line as a big KEYWORD + a matching color emoji that pops in, with the full
line as a clean fading subtitle underneath. Paired with a per-line voiceover (see synced_reel),
the voice says exactly what's on screen — the baby-channel formula for grown-up content. $0.

    from modules.keyword_card import make_keyword_card
    make_keyword_card("Africa sits at the center", "AFRICA", "🌍", "kw.mp4", duration=2.2)
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


def _back(t):
    """ease-out-back for a lively emoji pop."""
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _outline(d, xy, text, fnt, rgba, ow, oc=(12, 14, 20)):
    x, y = xy
    a = rgba[3] if len(rgba) > 3 else 255
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=(oc[0], oc[1], oc[2], a))
    d.text((x, y), text, font=fnt, fill=rgba)


def _wrap(dmy, words, fnt, maxw):
    lines, cur = [], []
    for w in words:
        if dmy.textlength(" ".join(cur + [w]), font=fnt) <= maxw or not cur:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    if cur:
        lines.append(cur)
    return lines


def make_keyword_card(say, keyword, emoji, out_path, duration=2.2, size=(1080, 1920),
                      accent="#FF3131", fps=30, bg_provider=None, frame_offset=0):
    """Render a keyword card: emoji pop + big keyword + fading subtitle of `say`. Returns path/None.
    If `bg_provider` is given (see motion_bg), an animated background is drawn per frame; else a
    static deep-navy glow. `frame_offset` keeps animated motion continuous across beats."""
    from PIL import Image, ImageDraw
    from modules.emoji_util import render_emoji, pick_emoji, pick_keyword
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    keyword = (keyword or pick_keyword(say) or "").upper()
    emoji = emoji or pick_emoji(say)

    # static ground (used when no animated provider): deep near-black with a faint accent radial
    bg = Image.new("RGB", (W, H), (11, 15, 21))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = W // 2, int(H * 0.36)
    for r in range(int(W * 0.55), 0, -12):
        a = int(26 * (1 - r / (W * 0.55)))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ac + (a,))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")

    dmy = ImageDraw.Draw(bg)

    # emoji raster (big, centered upper third)
    em_px = int(W * 0.30)
    em_img = render_emoji(emoji, px=em_px)
    em_y = int(H * 0.20)

    # keyword font: fit to 90% width
    kfs = int(W * 0.15); kfont = _font(kfs)
    while dmy.textlength(keyword, font=kfont) > W * 0.9 and kfs > int(W * 0.06):
        kfs -= int(W * 0.006); kfont = _font(kfs)
    kw_y = int(H * 0.50)

    # subtitle: full spoken line, <=2 lines, ~78% H
    sfs = int(W * 0.058); sfont = _font(sfs)
    words = str(say).split()
    slines = _wrap(dmy, words, sfont, W * 0.84)
    while len(slines) > 2 and sfs > int(W * 0.04):
        sfs -= int(W * 0.004); sfont = _font(sfs); slines = _wrap(dmy, words, sfont, W * 0.84)
    slh = int(sfs * 1.16)
    sub_y0 = int(H * 0.78)
    ow = max(3, int(kfs * 0.045))
    sow = max(2, int(sfs * 0.06))

    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="kw_"))
    try:
        for i in range(n):
            t = i / (n - 1) * duration
            fr = t / duration
            frame = bg_provider(i, n, W, H, frame_offset).copy() if bg_provider else bg.copy()
            d = ImageDraw.Draw(frame, "RGBA")

            # emoji pop (0 -> 0.32)
            if em_img is not None:
                p = _back(t / (0.32 * duration)) if t < 0.32 * duration else 1.0
                p = max(0.05, p)
                ew = max(1, int(em_img.width * p)); eh = max(1, int(em_img.height * p))
                es = em_img.resize((ew, eh), Image.LANCZOS)
                frame.paste(es, (cx - ew // 2, em_y + (em_px - eh) // 2), es)

            # keyword rise+fade (0.12 -> 0.44)
            kp = _ease((t - 0.12 * duration) / (0.32 * duration))
            if kp > 0:
                a = int(255 * kp); yo = int((1 - kp) * kfs * 0.4)
                kw_w = dmy.textlength(keyword, font=kfont)
                _outline(d, ((W - kw_w) // 2, kw_y - yo), keyword, kfont, ac + (a,), ow)

            # subtitle fade-in (0.10 -> 0.30) and fade-out (last 0.18)
            fade_in = min(1.0, (t) / (0.22 * duration))
            fade_out = min(1.0, (duration - t) / (0.20 * duration))
            sa = int(255 * max(0.0, min(fade_in, fade_out)))
            if sa > 6:
                for li, line in enumerate(slines):
                    txt = " ".join(line)
                    lw = dmy.textlength(txt, font=sfont)
                    _outline(d, ((W - lw) // 2, sub_y0 + li * slh), txt, sfont, (240, 240, 245, sa), sow)
            frame.save(tmp / f"f{i:05d}.png")

        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 6000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_keyword_card("Africa sits at the center of a new money war", "AFRICA", "🌍",
                      "output/kw_demo.mp4", duration=2.4, size=(1080, 1920))
    print("wrote output/kw_demo.mp4")
