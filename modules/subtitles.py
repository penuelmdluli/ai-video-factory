"""Best-in-class subtitles + series furniture for the Veo shorts ($0 edit layer, no re-generation).

Burns bold, high-contrast captions synced to the narration SRT, plus everything that makes a short
read as EPISODE 5 OF A SERIES rather than a loose clip:

    EP.5 THE SHIELD WALL   episode badge, top          — "there are more of these"
    THEY BROKE. HE DIDN'T. hook card, first ~3s        — buys the scroll-stop
    ...synced captions...  mid-lower, gold power words — works on mute
    Would you hold?        comment bait, early         — drives comments
    LESSON CARD            on the freeze frame         — the screenshot/share moment
    NEXT EP.6 THE BETRAYAL end card                    — the reason to follow
"""
import re
import tempfile
from pathlib import Path

GOLD = (224, 164, 0)

# Words that carry the punch — rendered in the accent colour so the eye lands on them on mute.
POWER = {
    "not", "never", "no", "nobody", "alone", "storm", "fear", "strength", "wall", "shield",
    "blood", "fire", "iron", "oath", "north", "valhalla", "charge", "stood", "stand", "rise",
    "broke", "broken", "forged", "first", "go", "keep", "row", "rowing", "build", "earn",
    "odds", "shows", "up", "dead", "death", "war", "battle", "axe", "hold", "held", "line",
    "you", "your", "yours", "must", "will", "won't", "can't", "everything", "now",
}


def _ts(x):
    x = x.strip().replace(",", ".")
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _phrases(srt_path, per=4, offset=0.0):
    """Read an SRT into (start, end, text) phrase groups, shifted by `offset` seconds."""
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
            out.append((grp[0][0] + offset, grp[-1][1] + offset, " ".join(w for _, _, w in grp)))
    return out


def _font(sz):
    from modules.thumbnail_pro import _font as pf
    return pf(sz, "news")


def _outline(d, x, y, s, f, ow, fill=(255, 255, 255, 255)):
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), s, font=f, fill=(0, 0, 0, 255))
    d.text((x, y), s, font=f, fill=fill)


def _cap_png(text, W, out, accent=GOLD):
    """A caption line — white, heavy outline, with the power words in the accent colour."""
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
    space = d.textlength(" ", font=f)
    for li, ln in enumerate(lines):
        lw = d.textlength(" ".join(ln), font=f)
        x = (W - lw) // 2
        y = y0 + li * lh
        for w in ln:
            hot = re.sub(r"[^A-Z']", "", w).lower() in POWER
            _outline(d, x, y, w, f, ow, accent + (255,) if hot else (255, 255, 255, 255))
            x += d.textlength(w, font=f) + space
        # accent underline anchors the line to the frame
        d.rounded_rectangle([(W - lw) // 2, y + lh - int(fs * 0.16),
                             (W - lw) // 2 + lw, y + lh - int(fs * 0.16) + max(3, int(fs * 0.06))],
                            radius=3, fill=accent + (235,))
    img.save(out)
    return out


def _hook_png(text, W, out, accent=GOLD):
    """The opening line — the biggest text in the video. Its only job is to stop the scroll."""
    from PIL import Image, ImageDraw
    fs = int(W * 0.098)
    f = _font(fs)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    words, lines, cur = text.upper().split(), [], []
    for w in words:
        if probe.textlength(" ".join(cur + [w]), font=f) <= W * 0.86 or not cur:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    if cur:
        lines.append(cur)
    lh = int(fs * 1.14)
    img = Image.new("RGBA", (W, lh * len(lines) + int(fs * 0.7)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ow = max(4, int(fs * 0.11))
    for li, ln in enumerate(lines):
        s = " ".join(ln)
        lw = d.textlength(s, font=f)
        _outline(d, (W - lw) // 2, int(fs * 0.35) + li * lh, s, f, ow)
    img.save(out)
    return out


def _badge_png(text, W, out, accent=GOLD):
    """EP.5 THE SHIELD WALL — the pill that tells a new viewer this is a series."""
    from PIL import Image, ImageDraw
    fs = int(W * 0.034)
    f = _font(fs)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(text.upper(), font=f)
    pad = int(fs * 0.8)
    w, h = int(tw + pad * 2), int(fs * 1.85)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=int(fs * 0.32), fill=(10, 12, 16, 215))
    d.rounded_rectangle([0, 0, w, h], radius=int(fs * 0.32), outline=accent + (255,), width=3)
    d.text((pad, (h - fs) // 2 - int(fs * 0.08)), text.upper(), font=f, fill=accent + (255,))
    img.save(out)
    return out


def _lesson_png(text, W, out, accent=GOLD):
    """The quote card that holds on the freeze frame — the thing people screenshot."""
    from PIL import Image, ImageDraw
    lines = [l.strip() for l in text.upper().split("\n") if l.strip()]
    fs = int(W * 0.086)
    f = _font(fs)
    lh = int(fs * 1.22)
    pad = int(fs * 0.85)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = max(probe.textlength(l, font=f) for l in lines)
    w = min(int(W * 0.94), int(tw + pad * 2))
    h = lh * len(lines) + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=int(fs * 0.28), fill=(8, 10, 14, 205))
    d.rounded_rectangle([0, 0, w, h], radius=int(fs * 0.28), outline=accent + (255,), width=4)
    ow = max(3, int(fs * 0.08))
    for li, ln in enumerate(lines):
        lw = d.textlength(ln, font=f)
        _outline(d, (w - lw) // 2, pad + li * lh, ln, f, ow)
    img.save(out)
    return out


def _next_png(text, W, out, accent=GOLD):
    """NEXT EP.6 THE BETRAYAL — the binge hook."""
    from PIL import Image, ImageDraw
    fs = int(W * 0.046)
    f = _font(fs)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(text.upper(), font=f)
    pad = int(fs * 0.75)
    w, h = int(tw + pad * 2), int(fs * 1.9)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=accent + (240,))
    d.text((pad, (h - fs) // 2 - int(fs * 0.08)), text.upper(), font=f, fill=(15, 15, 18, 255))
    img.save(out)
    return out


def _follow_png(handle, W, out, accent=GOLD):
    from PIL import Image, ImageDraw
    fs = int(W * 0.05)
    f = _font(fs)
    label = f"FOLLOW  {handle}"
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(label, font=f)
    pad = int(fs * 0.7)
    tri = int(fs * 0.62)                       # play glyph, drawn rather than typed —
    gap = int(fs * 0.42)                       # the font has no ▶ and renders it as a tofu box
    w = int(tw + pad * 2 + tri + gap)
    h = int(fs * 1.9)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=accent + (240,))
    ty = (h - tri) // 2
    d.polygon([(pad, ty), (pad, ty + tri), (pad + int(tri * 0.86), ty + tri // 2)],
              fill=(15, 15, 18, 255))
    d.text((pad + tri + gap, (h - fs) // 2 - int(fs * 0.08)), label, font=f, fill=(15, 15, 18, 255))
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


def _comment_png(text, W, out, accent=GOLD):
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


def add_subs_and_follow(video, srt, out_path, handle="@SagaOfTheNorth", accent=GOLD,
                        comment="Would you sail with him?", hook=None, lesson=None,
                        badge=None, next_tease=None, offset=0.0, hold=1.6):
    """Burn the full on-screen pack onto `video`.

    hook / badge / lesson / next_tease are the series furniture; `hold` is how long the tail of the
    video is a held freeze frame (that window is where the lesson + next-episode cards live).
    `offset` shifts the SRT to match narration that starts late in the mix.
    """
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    work = Path(tempfile.mkdtemp(prefix="subs_"))
    v = VideoFileClip(video)
    W, H, D = v.w, v.h, v.duration
    overlays = []

    # captions — stop them before the freeze so the lesson card owns the ending
    cap_end = max(0.0, D - hold)
    for j, (s, e, txt) in enumerate(_phrases(srt, offset=offset)):
        if s >= cap_end:
            break
        png = _cap_png(txt, W, str(work / f"c{j}.png"), accent)
        overlays.append(ImageClip(png).with_start(s)
                        .with_duration(max(0.4, min(e, cap_end) - s))
                        .with_position(("center", int(H * 0.66))))

    # episode badge — the whole reason this reads as a series
    if badge:
        overlays.append(ImageClip(_badge_png(badge, W, str(work / "b.png"), accent))
                        .with_duration(D).with_position(("center", int(H * 0.093))))

    # Persistent handle watermark, bottom-left. It sits low because the top of the frame already
    # carries the brand badge and the episode badge — three stacked labels up there is clutter.
    # It also drops out once the FOLLOW pill appears — that pill already carries the handle.
    overlays.append(ImageClip(_handle_png(handle, W, str(work / "h.png")))
                    .with_duration(max(1.0, D - 3.5))
                    .with_position((int(W * 0.04), int(H * 0.935))))

    # the hook — biggest text in the video, first three seconds
    if hook:
        overlays.append(ImageClip(_hook_png(hook, W, str(work / "hk.png"), accent))
                        .with_start(0.3).with_duration(min(2.9, max(1.0, D - hold - 0.3)))
                        .with_position(("center", int(H * 0.28))))

    # comment bait, once the hook has cleared
    if comment:
        cb = ImageClip(_comment_png(comment, W, str(work / "cb.png"), accent))
        overlays.append(cb.with_start(3.4).with_duration(min(4.0, max(1.0, D - hold - 3.6)))
                        .with_position(("center", int(H * 0.82))))

    # the lesson card, held on the freeze frame — the payoff and the screenshot
    if lesson and hold > 0.4:
        overlays.append(ImageClip(_lesson_png(lesson, W, str(work / "ls.png"), accent))
                        .with_start(max(0.0, D - hold)).with_duration(min(hold, D))
                        .with_position(("center", int(H * 0.34))))

    # next-episode tease, sitting under the lesson
    if next_tease and hold > 0.4:
        overlays.append(ImageClip(_next_png(next_tease, W, str(work / "nx.png"), accent))
                        .with_start(max(0.0, D - hold)).with_duration(min(hold, D))
                        .with_position(("center", int(H * 0.62))))

    # follow prompt over the last stretch
    fb = ImageClip(_follow_png(handle, W, str(work / "f.png"), accent))
    overlays.append(fb.with_start(max(0.0, D - min(3.5, D))).with_duration(min(3.5, D))
                    .with_position(("center", int(H * 0.87))))

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
