"""
Act one of the CONFIRMED XI reel — our morning call, marked in public.

The predicted reel opens on the whole squad narrowing to eleven. Repeating
that when the real sheet lands would waste the opening, because by then the
eleven is not a question any more. What IS a question at half past six is
whether the page got it right, and we are the only page that can answer it —
everyone else just reposts the same team-sheet graphic.

So: the eleven we named, each one ticked or crossed as the real sheet is laid
over it, ending on a score. Green for called, red for missed, and the men we
never saw coming arriving underneath.

    from modules.verdict_card import build_ctx, frame
"""

GOOD = (46, 168, 92)
BAD = (206, 56, 56)


def _font(size, bold=True):
    from PIL import ImageFont
    for f in ((r"C:\Windows\Fonts\arialbd.ttf" if bold
               else r"C:\Windows\Fonts\arial.ttf"),
              r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _surname(entry: str) -> str:
    parts = str(entry).split(None, 1)
    return (parts[1] if len(parts) > 1 else str(entry)).strip()


def build_ctx(predicted: list[str], verdict: dict, size, accent, crest=None):
    """One row per man we named, in the order we named him."""
    W, H = size
    hit = {_surname(h).lower() for h in verdict["hits"]}
    rows = []
    top = 250
    pitch = max(52, min(74, int((H - top - 330) / max(1, len(predicted)))))
    for i, p in enumerate(predicted):
        rows.append({"label": str(p).upper(),
                     "ok": _surname(p).lower() in hit,
                     "y": top + i * pitch})
    return {"rows": rows, "size": (W, H), "accent": tuple(accent),
            "crest": crest, "verdict": verdict, "top": top, "pitch": pitch}


def frame(t: float, dur: float, ctx: dict):
    from PIL import Image, ImageDraw
    W, H = ctx["size"]
    accent = ctx["accent"]
    v = ctx["verdict"]
    rows = ctx["rows"]
    im = Image.new("RGB", (W, H), (11, 12, 16))
    d = ImageDraw.Draw(im, "RGBA")
    p = max(0.0, min(1.0, t / max(0.001, dur)))

    # ── header ──────────────────────────────────────────────────────────
    if ctx.get("crest") is not None:
        c = ctx["crest"]
        cc = c.resize((92, int(c.height * 92 / c.width)))
        im.paste(cc, (40, 52), cc)
        d = ImageDraw.Draw(im, "RGBA")
    d.text((156, 56), "WE CALLED IT", font=_font(50), fill=(255, 255, 255))
    d.text((158, 116), "our XI from this morning, marked",
           font=_font(26, False), fill=accent)

    # ── the marking sweep ───────────────────────────────────────────────
    # Each man is judged in turn over the first 70% so the score at the end
    # is arrived at rather than announced.
    judged = p / 0.70 * len(rows)
    for i, r in enumerate(rows):
        u = _ease(judged - i)
        if u <= 0.0:
            shown, col, mark = 0.35, (34, 37, 44), ""
        else:
            shown = 1.0
            col = (GOOD if r["ok"] else BAD)
            mark = "OK" if r["ok"] else "X"
        y = r["y"]
        bx0, bx1 = 60, W - 60
        d.rounded_rectangle([bx0, y, bx1, y + ctx["pitch"] - 10], radius=12,
                            fill=(26, 29, 36))
        if u > 0:
            d.rounded_rectangle([bx0, y, bx0 + 10, y + ctx["pitch"] - 10],
                                radius=5, fill=col + (int(255 * u),))
        f = _font(30)
        d.text((bx0 + 32, y + 12), r["label"], font=f,
               fill=(255, 255, 255) if u > 0 else (110, 116, 126))
        if mark:
            mf = _font(27)
            mw = d.textlength(mark, font=mf)
            d.ellipse([bx1 - 30 - mw / 2 - 20, y + 8,
                       bx1 - 30 + mw / 2 + 20, y + ctx["pitch"] - 18],
                      fill=col + (int(230 * u),))
            d.text((bx1 - 30 - mw / 2, y + 12), mark, font=mf,
                   fill=(255, 255, 255, int(255 * u)))

    # ── the score, once the marking is done ─────────────────────────────
    su = _ease((p - 0.70) / 0.18)
    if su > 0:
        sf = _font(96)
        txt = v["score"]
        tw = d.textlength(txt, font=sf)
        y = H - 250
        d.rounded_rectangle([W // 2 - tw / 2 - 46, y - 14,
                             W // 2 + tw / 2 + 46, y + 116], radius=22,
                            fill=accent + (int(255 * su),))
        d.text((W // 2 - tw / 2, y), txt, font=sf,
               fill=(18, 18, 20, int(255 * su)))
        lf = _font(28, False)
        lab = "we got this many right"
        lw = d.textlength(lab, font=lf)
        d.text((W // 2 - lw / 2, y + 132), lab, font=lf,
               fill=(210, 216, 226, int(230 * su)))

    # ── who we never saw coming ─────────────────────────────────────────
    gu = _ease((p - 0.86) / 0.14)
    if gu > 0 and v["surprises"]:
        names = ", ".join(_surname(s).upper() for s in v["surprises"][:3])
        gf = _font(29)
        txt = f"IN INSTEAD: {names}"
        while d.textlength(txt, font=gf) > W - 120 and gf.size > 18:
            gf = _font(gf.size - 2)
        tw = d.textlength(txt, font=gf)
        d.rounded_rectangle([W // 2 - tw / 2 - 24, H - 96,
                             W // 2 + tw / 2 + 24, H - 40], radius=14,
                            fill=BAD + (int(220 * gu),))
        d.text((W // 2 - tw / 2, H - 82), txt, font=gf,
               fill=(255, 255, 255, int(255 * gu)))
    return im
