"""
Weekly OUR CALLS card — publish the prediction record, win or lose.

"3/5 winners called, 2 scorers hit — think you can beat us? Comments." Honest
accuracy published weekly is what turns predictions into a franchise fans
return to argue with.

Usage: python build_calls_card.py [--post]     (scheduled Sundays 17:00)
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
LOGO = Path("assets/youtube_branding/logo_sa_pulse.png")


def _font(size, bold=True):
    try:
        return ImageFont.truetype(
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def build_card(s: dict) -> str | None:
    if not s["total"]:
        print("[Calls] nothing settled this week — no card")
        return None
    img = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(img)
    for i in range(150):
        a = 1 - i / 150
        d.line([(0, i), (W, i)], fill=(int(255 * a * 0.25) + 12,
                                       int(193 * a * 0.25) + 14,
                                       int(7 * a * 0.12) + 18))
    try:
        lg = Image.open(LOGO).convert("RGBA").resize((110, 110))
        img.paste(lg, (44, 34), lg)
    except Exception:
        pass
    d.text((172, 48), "GENESIS NEWS", font=_font(40), fill=(255, 255, 255))
    d.text((174, 98), "OUR CALLS — THE WEEK", font=_font(24, False),
           fill=(200, 205, 210))

    big = _font(150)
    score = f"{s['wins']}/{s['total']}"
    w = d.textlength(score, font=big)
    d.text(((W - w) / 2 + 4, 230 + 4), score, font=big, fill=(0, 0, 0))
    d.text(((W - w) / 2, 230), score, font=big, fill=(255, 193, 7))
    sub = _font(40)
    t = "WINNERS CALLED CORRECTLY"
    d.text(((W - d.textlength(t, font=sub)) / 2, 420), t, font=sub,
           fill=(255, 255, 255))
    t2 = f"{s['scorer_hits']} scorer pick(s) hit the net"
    f2 = _font(32, False)
    d.text(((W - d.textlength(t2, font=f2)) / 2, 490), t2, font=f2,
           fill=(200, 205, 212))

    y = 610
    lf = _font(30, False)
    tag_f = _font(26)
    for line, won in s["lines"][:8]:
        while d.textlength(line, font=lf) > W - 300 and len(line) > 10:
            line = line[:-4] + "…"
        d.rounded_rectangle([60, y, W - 60, y + 66], radius=14, fill=(20, 23, 29))
        dot = (60, 180, 90) if won else (210, 60, 60)
        d.ellipse([84, y + 22, 106, y + 44], fill=dot)
        d.text((124, y + 16), line, font=lf, fill=(230, 234, 240))
        tag = "HIT" if won else "MISS"
        tw = d.textlength(tag, font=tag_f)
        d.text((W - 96 - tw, y + 18), tag, font=tag_f, fill=dot)
        y += 82

    foot = "Think you can beat us? Drop YOUR calls in the comments"
    ff = _font(28)
    d.text(((W - d.textlength(foot, font=ff)) / 2, H - 110), foot, font=ff,
           fill=(255, 193, 7))
    out = Path("output/matchday") / f"calls_{datetime.now():%Y%m%d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95)
    print(f"[Calls] card -> {out}")
    return str(out)


async def main(post: bool):
    from modules.call_tracker import weekly_summary
    s = weekly_summary()
    card = build_card(s)
    if card and post:
        from matchday import _post_photo
        caption = (f"🔮 OUR CALLS THIS WEEK: {s['wins']}/{s['total']} winners, "
                   f"{s['scorer_hits']} scorer hits ⚽\n\nWe publish the record — "
                   f"win or lose. #PSL #BetwayPremiership")
        await _post_photo(card, caption,
                          "Beat our record next week — drop your calls now 👇")


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    try:
        asyncio.run(main("--post" in sys.argv))
    except Exception as e:
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure('calls-card', f"CALLS CARD FAILED: {type(e).__name__}: {str(e)[:140]}")
        except Exception:
            pass
        raise
