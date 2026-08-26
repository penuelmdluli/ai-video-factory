"""
The whole squad, narrowed to the eleven — the opening act of the line-up reel.

Owner call 2026-08-26: "a list of all the squad and motion, from the whole
pool to the starting eleven". The reel used to open on an empty pitch, which
gives away nothing about the size of the decision. Showing all thirty-eight
names first and then burning thirty-seven of them away makes the eleven feel
chosen rather than listed — and it puts every fringe player's name on screen,
which is exactly the kind of detail this page's fans go looking for.

Three beats:
  · THE FULL SQUAD  — every name in the cache, in position order
  · the cut         — the ones who miss out grey out and fall away
  · THE ELEVEN      — the survivors close up into a clean block

    from modules.squad_funnel import frame
    img = frame(t, dur, ctx)     # ctx from build_ctx(...)
"""
import math

POS_ORDER = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
POS_LABEL = {"GK": "GOALKEEPERS", "DF": "DEFENDERS",
             "MF": "MIDFIELDERS", "FW": "FORWARDS"}


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


def build_ctx(squad: list[dict], xi: list[str], size, accent, crest=None):
    """Lay the squad out once, so every frame draws the same grid.

    squad: [{no, pos, name}] straight from the squad cache
    xi:    the chosen eleven as they appear on the card ("16 Leaner")
    """
    W, H = size
    chosen = {_surname(p).lower() for p in xi if str(p).strip()}

    rows = sorted(squad, key=lambda p: (POS_ORDER.get(
        (p.get("pos") or "").upper()[:2], 9), int(p.get("no") or 999)))

    # Four columns keeps a 38-man squad inside one screen at a readable size.
    cols = 4
    cw = (W - 80) // cols
    top = 210
    # Row pitch is derived from how many rows there actually are, so a 37-man
    # squad fills the frame instead of stopping two thirds of the way down and
    # leaving a third of the screen empty.
    import math as _m
    n_rows = max(1, _m.ceil(len(squad) / cols))
    ch = max(58, min(96, int((H - top - 190) / n_rows)))
    items = []
    for i, p in enumerate(rows):
        sn = (p.get("name") or "").split()[-1]
        no = str(p.get("no") or "").strip()
        r, c = divmod(i, cols)
        items.append({
            "no": no, "name": sn.upper(),
            "pos": (p.get("pos") or "").upper()[:2],
            "x": 40 + c * cw + cw // 2,
            "y": top + r * ch,
            "in": sn.lower() in chosen,
            "seed": (i * 7919 % 1000) / 1000.0,
        })
    return {"items": items, "size": (W, H), "accent": tuple(accent),
            "crest": crest, "n_total": len(items),
            "n_in": sum(1 for i in items if i["in"]),
            "cw": cw, "ch": ch, "top": top}


def frame(t: float, dur: float, ctx: dict):
    """One funnel frame. t in [0, dur]."""
    from PIL import Image, ImageDraw
    W, H = ctx["size"]
    accent = ctx["accent"]
    im = Image.new("RGB", (W, H), (11, 12, 16))
    d = ImageDraw.Draw(im, "RGBA")

    p = max(0.0, min(1.0, t / max(0.001, dur)))
    # 0.00-0.40 the full squad reads   0.40-0.80 the cut   0.80-1.00 the block
    cut = _ease((p - 0.40) / 0.40)
    close = _ease((p - 0.80) / 0.20)

    # ── header ──────────────────────────────────────────────────────────
    if ctx.get("crest") is not None:
        c = ctx["crest"]
        cs = 96
        cc = c.resize((cs, int(c.height * cs / c.width)))
        im.paste(cc, (40, 54), cc)
        d = ImageDraw.Draw(im, "RGBA")

    hf = _font(52)
    title = "THE FULL SQUAD" if cut < 0.55 else "THE ELEVEN"
    d.text((160, 62), title, font=hf, fill=(255, 255, 255))
    sf = _font(28, False)
    left = int(ctx["n_total"] - (ctx["n_total"] - ctx["n_in"]) * cut)
    d.text((162, 124), f"{left} players", font=sf, fill=accent)

    # a thin progress rule that empties as the squad is cut
    d.rounded_rectangle([40, 178, W - 40, 184], radius=3, fill=(38, 42, 50))
    span = (W - 80) * (left / max(1, ctx["n_total"]))
    d.rounded_rectangle([40, 178, 40 + span, 184], radius=3, fill=accent)

    # ── the names ───────────────────────────────────────────────────────
    keepers = [i for i in ctx["items"] if i["in"]]
    kcols, kcw, kch = 3, (W - 100) // 3, 96
    for it in ctx["items"]:
        if it["in"]:
            # survivors close up into a tidy block once the cut is done
            k = keepers.index(it)
            r, c = divmod(k, kcols)
            tx = 50 + c * kcw + kcw // 2
            ty = ctx["top"] + 40 + r * kch
            x = it["x"] + (tx - it["x"]) * close
            y = it["y"] + (ty - it["y"]) * close
            alpha, scale = 255, 1.0 + 0.22 * close
            fill = accent
            txt = (18, 18, 20)
        else:
            # the ones who miss out grey out, drift down and go
            a = 1.0 - _ease(max(0.0, (cut - it["seed"] * 0.45) / 0.55))
            if a <= 0.02:
                continue
            x = it["x"]
            y = it["y"] + (1.0 - a) * 70
            alpha, scale = int(230 * a), 1.0
            fill = (30, 33, 40, alpha)
            txt = (150, 155, 165, alpha)

        label = f"{it['no']} {it['name']}".strip()
        f = _font(int(27 * scale))
        tw = d.textlength(label, font=f)
        bw, bh = tw + 34 * scale, 44 * scale
        box = [x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2]
        if it["in"]:
            d.rounded_rectangle([box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4],
                                radius=13, fill=(0, 0, 0, 120))
        d.rounded_rectangle(box, radius=11, fill=fill)
        d.text((x - tw / 2, y - 15 * scale), label, font=f, fill=txt)

    # ── the line that says what is happening ────────────────────────────
    ff = _font(30)
    msg = ("EVERY MAN IN THE SQUAD" if cut < 0.15 else
           "WHO MAKES THE CUT?" if cut < 0.75 else
           "THIS IS THE SIDE WE EXPECT")
    mw = d.textlength(msg, font=ff)
    d.rounded_rectangle([W // 2 - mw / 2 - 26, H - 108,
                        W // 2 + mw / 2 + 26, H - 50], radius=14,
                        fill=(255, 255, 255, 20))
    d.text((W // 2 - mw / 2, H - 94), msg, font=ff, fill=(235, 238, 244))
    return im
