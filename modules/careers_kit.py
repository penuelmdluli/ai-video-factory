"""
Mzansi Careers kit — VERIFIED opportunity alerts for the go-to SA careers
page. Same broadcast machine as Genesis News, pointed at jobs.

job_alert(): siren slam -> employer + programme -> detail chips punch in ->
closing-date countdown ticks -> VERIFIED badge + official-source line.
Every post MUST carry the official source; aggregator text is never copied.
"""
import math
from pathlib import Path

from modules.motion_kit import (_base, _font, _ease, _over, _render, icon,
                                DARK, W, H)

GREEN = (46, 200, 113)


def make_job_card(out, employer="TRANSNET",
                  programme="Work Integrated Learning Programme",
                  details=("18-month programme with a stipend",
                           "TVET students & graduates (N4–N6)",
                           "Cape Town · Saldanha · Durban · Ngqura · PE",
                           "Engineering, logistics & procurement fields"),
                  closes="CLOSES 24 AUGUST 2026",
                  apply_line="Apply FREE on the official Transnet careers portal",
                  bg_photo=None,
                  photo_credit="") -> str:
    """Static shareable card — the image-post twin of the job_alert reel."""
    from PIL import Image, ImageDraw, ImageFilter
    CW, CH = 1080, 1350
    im = Image.new("RGB", (CW, CH), DARK)
    if bg_photo and Path(bg_photo).exists():
        ph = Image.open(bg_photo).convert("RGB")
        s = max(CW / ph.width, 640 / ph.height)
        ph = ph.resize((int(ph.width * s), int(ph.height * s)))
        ph = ph.crop(((ph.width - CW) // 2, 0,
                      (ph.width - CW) // 2 + CW, 640))
        im.paste(ph, (0, 130))
        fade = Image.new("L", (CW, 240), 0)
        for yy in range(240):
            fade.paste(int(255 * (yy / 240)), (0, yy, CW, yy + 1))
        dark = Image.new("RGB", (CW, 240), DARK)
        im.paste(dark, (0, 530), fade)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, CW, 130], fill=(10, 10, 12))
    d.text((44, 30), "MZANSI CAREERS", font=_font(44), fill=(255, 255, 255))
    d.text((46, 88), "VERIFIED OPPORTUNITY", font=_font(24, False),
           fill=GREEN)
    chip = "JOB ALERT"
    cf = _font(34)
    cw2 = d.textlength(chip, font=cf)
    d.rounded_rectangle([44, 560, 44 + cw2 + 48, 630], radius=16, fill=GREEN)
    d.text((68, 574), chip, font=cf, fill=(10, 10, 12))
    d.text((44, 660), employer, font=_font(84), fill=(255, 255, 255))
    d.text((44, 775), programme, font=_font(36, False), fill=(220, 224, 228))
    y = 860
    for det in details:
        d.ellipse([50, y + 10, 74, y + 34], fill=GREEN)
        d.text((96, y), det, font=_font(32), fill=(235, 238, 242))
        y += 62
    d.rounded_rectangle([44, y + 20, CW - 44, y + 110], radius=18,
                        fill=(220, 50, 50))
    clf = _font(44)
    clw = d.textlength(closes, font=clf)
    d.text(((CW - clw) / 2, y + 40), closes, font=clf, fill=(255, 255, 255))
    af = _font(28, False)
    aw = d.textlength(apply_line, font=af)
    d.text(((CW - aw) / 2, y + 132), apply_line, font=af, fill=GREEN)
    foot = "We verify every post — no scams, no fees, ever."
    ff = _font(26, False)
    fw = d.textlength(foot, font=ff)
    d.text(((CW - fw) / 2, y + 186), foot, font=ff, fill=(200, 205, 210))
    if photo_credit:
        pf = _font(20, False)
        pw2 = d.textlength(photo_credit, font=pf)
        d.text((CW - pw2 - 20, 148), photo_credit, font=pf,
               fill=(210, 214, 220))
    out = Path(out)
    im.save(out, quality=95)
    return str(out)


def job_alert(out, employer="TRANSNET", programme="Work Integrated Learning",
              details=("18 months", "TVET N4-N6", "5 coastal cities"),
              closes="24 AUGUST", days_left=7,
              source="Verified on the official Transnet careers portal",
              bg_photo=None, photo_credit="", duration=9.0):
    from PIL import Image, ImageDraw, ImageFilter
    siren = icon("siren", 150)
    star = icon("star", 90)
    photo = None
    if bg_photo and Path(bg_photo).exists():
        ph = Image.open(bg_photo).convert("RGB")
        s = max(W / ph.width, H / ph.height)
        ph = ph.resize((int(ph.width * s), int(ph.height * s)))
        photo = ph.crop(((ph.width - W) // 2, (ph.height - H) // 2,
                         (ph.width - W) // 2 + W, (ph.height - H) // 2 + H))
        photo = photo.filter(ImageFilter.GaussianBlur(2))

    def frame(t):
        if photo is not None:
            im = photo.copy()
            dk = Image.new("RGBA", (W, H), (8, 10, 12, 195))
            im = Image.alpha_composite(im.convert("RGBA"), dk).convert("RGB")
            d = ImageDraw.Draw(im, "RGBA")
            d.rectangle([0, 0, W, 170], fill=(10, 10, 12, 240))
            d.text((44, 40), "MZANSI CAREERS", font=_font(42),
                   fill=(255, 255, 255))
        else:
            im = Image.new("RGB", (W, H), DARK)
            d = ImageDraw.Draw(im, "RGBA")
            _base(d)
        d.text((46, 96), "VERIFIED OPPORTUNITY — WE CHECK EVERY POST",
               font=_font(28, False), fill=GREEN)
        # green pulse frame
        pulse = int(50 + 35 * abs(math.sin(t * 3)))
        for wdt in range(3):
            d.rectangle([wdt * 10, wdt * 10, W - wdt * 10, H - wdt * 10],
                        outline=(*GREEN, max(0, pulse - wdt * 14)), width=8)
        # siren slam
        u = _ease(min(1, t / 0.45))
        if siren:
            s = 2.6 - 1.6 * u
            ic2 = siren.resize((max(1, int(150 * s)),) * 2)
            im.paste(ic2, (W // 2 - ic2.width // 2, 300 - ic2.height // 2),
                     ic2)
        if t > 0.4:
            g = _over(min(1, (t - 0.4) / 0.4))
            jf = _font(int(94 * g))
            jw = d.textlength("JOB ALERT!", font=jf)
            d.text(((W - jw) / 2, 430), "JOB ALERT!", font=jf, fill=GREEN)
        if t > 0.9:
            g = _over(min(1, (t - 0.9) / 0.35))
            ef = _font(int(84 * g))
            ew = d.textlength(employer, font=ef)
            d.text(((W - ew) / 2, 620), employer, font=ef,
                   fill=(255, 255, 255))
            pf = _font(40, False)
            pw = d.textlength(programme, font=pf)
            d.text(((W - pw) / 2, 750), programme, font=pf,
                   fill=(220, 224, 228))
        # detail chips punch in
        y = 880
        for i, det in enumerate(details):
            tu = _over(min(1, max(0, (t - 1.5 - i * 0.45) / 0.35)))
            if tu <= 0:
                continue
            cf = _font(int(38 * tu))
            cw = d.textlength(det, font=cf)
            d.rounded_rectangle([(W - cw) / 2 - 28, y,
                                 (W + cw) / 2 + 28, y + 78], radius=18,
                                fill=(19, 22, 28, 235),
                                outline=(*GREEN, 160), width=3)
            d.text(((W - cw) / 2, y + 16), det, font=cf,
                   fill=(255, 255, 255))
            y += 110
        # closing countdown
        if t > 3.2:
            g = _over(min(1, (t - 3.2) / 0.4))
            shown_days = int(round(days_left * min(1, (t - 3.2) / 1.2)))
            big = _font(int(110 * g))
            txt = f"{shown_days} DAYS LEFT"
            tw2 = d.textlength(txt, font=big)
            d.rounded_rectangle([(W - tw2) / 2 - 36, 1280,
                                 (W + tw2) / 2 + 36, 1440], radius=24,
                                fill=(220, 50, 50, 235))
            d.text(((W - tw2) / 2, 1305), txt, font=big,
                   fill=(255, 255, 255))
            clf = _font(34)
            clw = d.textlength(f"CLOSES {closes}", font=clf)
            d.text(((W - clw) / 2, 1460), f"CLOSES {closes}", font=clf,
                   fill=(255, 200, 0))
        # verified badge + source
        if t > 4.5:
            g = _over(min(1, (t - 4.5) / 0.4))
            if star:
                s2 = star.resize((max(1, int(90 * g)),) * 2)
                im.paste(s2, (W // 2 - s2.width // 2, 1540), s2)
            sf = _font(26, False)
            sw2 = d.textlength(source, font=sf)
            d.text(((W - sw2) / 2, 1650), source, font=sf,
                   fill=(200, 205, 210))
        if photo_credit:
            cf = _font(20, False)
            cw2 = d.textlength(photo_credit, font=cf)
            d.text((W - cw2 - 30, H - 40), photo_credit, font=cf,
                   fill=(150, 155, 162))
        return im
    return _render(frame, out, duration)
