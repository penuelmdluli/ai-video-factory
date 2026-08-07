"""Best-in-class subtitles + follow CTA for the Veo shorts ($0 edit layer, no re-generation).

Burns bold, high-contrast captions synced to the narration SRT (word-timed via whisper), plus a
persistent @handle watermark and a FOLLOW prompt near the end. Works on mute; converts views.
"""
import re
import tempfile
from pathlib import Path


def _ts(x):
    x = x.strip().replace(",", ".")
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _phrases(srt_path, per=4):
    try:
        txt = Path(srt_path).read_text(encoding="utf-8")
    except Exception:
        return []
    words = []
    for b in re.split(r"\n\s*\n", txt.strip()):
        lines = b.strip().splitlines()
        tline = next((l for l in lines if "-->" in l), None)
        if not tline:
            continue
        a, c = tline.split("-->")
        try:
            s, e = _ts(a), _ts(c)
        except Exception:
            continue
        wtext = " ".join(l for l in lines if "-->" not in l and not l.strip().isdigit())
        for w in wtext.split():
            words.append((s, e, w))
    out = []
    for i in range(0, len(words), per):
        grp = words[i:i + per]
        if grp:
            out.append((grp[0][0], grp[-1][1], " ".join(w for _, _, w in grp)))
    return out


def _font(sz):
    from modules.thumbnail_pro import _font as pf
    return pf(sz, "news")


def _cap_png(text, W, out, accent=(224, 164, 0)):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, int(W * 0.34)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = int(W * 0.072)
    f = _font(fs)
    words, lines, cur = text.upper().split(), [], []
    for w in words:
        if d.textlength(" ".join(cur + [w]), font=f) <= W * 0.9 or not cur:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    if cur:
        lines.append(cur)
    lines = lines[:2]
    lh = int(fs * 1.16)
    y0 = (img.height - lh * len(lines)) // 2
    ow = max(3, int(fs * 0.10))
    for li, ln in enumerate(lines):
        s = " ".join(ln)
        lw = d.textlength(s, font=f)
        x = (W - lw) // 2
        y = y0 + li * lh
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1):
                if dx * dx + dy * dy <= ow * ow:
                    d.text((x + dx, y + dy), s, font=f, fill=(0, 0, 0, 255))
        d.text((x, y), s, font=f, fill=(255, 255, 255, 255))
        # gold accent underline
        d.rounded_rectangle([x, y + lh - int(fs * 0.16), x + lw, y + lh - int(fs * 0.16) + max(3, int(fs * 0.06))],
                            radius=3, fill=accent + (235,))
    img.save(out)
    return out


def _follow_png(handle, W, out, accent=(224, 164, 0)):
    from PIL import Image, ImageDraw
    fs = int(W * 0.05)
    f = _font(fs)
    label = f"▶  FOLLOW  {handle}"
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(label, font=f)
    pad = int(fs * 0.7)
    w = int(tw + pad * 2)
    h = int(fs * 1.9)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=accent + (240,))
    d.text((pad, (h - fs) // 2 - int(fs * 0.08)), label, font=f, fill=(15, 15, 18, 255))
    img.save(out)
    return out


def _handle_png(handle, W, out):
    from PIL import Image, ImageDraw
    fs = int(W * 0.036)
    f = _font(fs)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(handle, font=f)
    img = Image.new("RGBA", (int(tw) + 20, int(fs * 1.6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            d.text((10 + dx, 6 + dy), handle, font=f, fill=(0, 0, 0, 200))
    d.text((10, 6), handle, font=f, fill=(255, 255, 255, 235))
    img.save(out)
    return out


def _comment_png(text, W, out, accent=(224, 164, 0)):
    from PIL import Image, ImageDraw
    from modules.emoji_util import render_emoji
    fs = int(W * 0.044)
    f = _font(fs)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(text, font=f)
    em = render_emoji("\U0001F4AC", px=int(fs * 1.2))   # speech balloon
    esz = int(fs * 1.1)
    pad = int(fs * 0.6)
    w = int(pad * 2 + (esz + int(fs * 0.3) if em else 0) + tw)
    h = int(fs * 1.9)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=int(fs * 0.4), fill=(12, 14, 20, 220))
    d.rounded_rectangle([0, 0, w, h], radius=int(fs * 0.4), outline=accent + (255,), width=3)
    x = pad
    if em:
        em = em.resize((esz, esz), Image.LANCZOS)
        img.paste(em, (x, (h - esz) // 2), em)
        x += esz + int(fs * 0.3)
    d.text((x, (h - fs) // 2 - int(fs * 0.08)), text, font=f, fill=(255, 255, 255, 255))
    img.save(out)
    return out


def add_subs_and_follow(video, srt, out_path, handle="@SagaOfTheNorth", accent=(224, 164, 0),
                        comment="Would you sail with him?"):
    """Burn synced subtitles (from srt) + @handle watermark + FOLLOW prompt + a comment-bait question."""
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    work = Path(tempfile.mkdtemp(prefix="subs_"))
    v = VideoFileClip(video)
    W, H = v.w, v.h
    overlays = []
    for j, (s, e, txt) in enumerate(_phrases(srt)):
        if s >= v.duration:
            break
        png = _cap_png(txt, W, str(work / f"c{j}.png"), accent)
        overlays.append(ImageClip(png).with_start(s).with_duration(max(0.4, min(e, v.duration) - s))
                        .with_position(("center", int(H * 0.66))))
    # persistent handle watermark (top-left)
    overlays.append(ImageClip(_handle_png(handle, W, str(work / "h.png")))
                    .with_duration(v.duration).with_position((int(W * 0.04), int(H * 0.05))))
    # comment-bait question near the start (drives comments)
    if comment:
        cb = ImageClip(_comment_png(comment, W, str(work / "cb.png"), accent))
        overlays.append(cb.with_start(1.2).with_duration(min(4.5, max(1.0, v.duration - 4.5)))
                        .with_position(("center", int(H * 0.82))))
    # follow prompt in the last 3.5s
    fb = ImageClip(_follow_png(handle, W, str(work / "f.png"), accent))
    overlays.append(fb.with_start(max(0.0, v.duration - 3.5)).with_duration(min(3.5, v.duration))
                    .with_position(("center", int(H * 0.85))))
    final = CompositeVideoClip([v] + overlays, size=(W, H))
    final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac",
                          preset="veryfast", logger=None)
    try:
        v.close()
    except Exception:
        pass
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    return out_path
