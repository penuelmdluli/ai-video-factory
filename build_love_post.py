"""KHOSI NATION — ask the supporters for their love, then put it on a wall.

Owner call 2026-09-02: "fans love to send love for the love of the club, make
this better."

Two halves of one loop, and the second half is the point.

    python build_love_post.py --ask            # the question
    python build_love_post.py --wall           # their answers, on a card
    python build_love_post.py --ask --post

The ASK rotates. "Show your love for Amakhosi" posted every week is wallpaper -
it is the same question, so it gets the same forty hearts from the same forty
people and tells the page nothing. A question with a SPECIFIC answer gets a
specific reply: a year, a city, one word, a name. Those are answers worth
printing, and they are answers only a real supporter can give. Least-used
first, so the page cannot ask the same thing twice in a row.

The WALL is what makes it more than a like-farm. Supporters are quoted in their
own words, first name attached, with the number of people who replied. It is
the one post a fan SHARES rather than merely likes, because part of it is
theirs - and the page did not have to write a word of it.

Refuses rather than invents: no ask on record, or too few supporters, and
nothing is posted. A wall of made-up affection would be obvious and grim.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "sa_pulse"
STATE = ROOT / "data" / "love_asks.json"

# Each asks for something only a real supporter can answer, and each produces a
# DIFFERENT kind of card: years make a timeline, cities make a map, one-worders
# make a wall of shouting. Variety of ANSWER, not just of wording.
PROMPTS = [
    {"key": "since",
     "headline": "HOW LONG HAVE YOU BEEN KHOSI?",
     "ask": "Drop the year you started supporting Amakhosi. Just the year.",
     "say": "How long have you been Khosi? Drop the year you started "
            "supporting Amakhosi, just the year."},
    {"key": "oneword",
     "headline": "ONE WORD FOR AMAKHOSI",
     "ask": "One word. Not two. What is Kaizer Chiefs to you?",
     "say": "One word for Amakhosi. Not two. What is Kaizer Chiefs to you?"},
    {"key": "where",
     "headline": "WHERE DO YOU WATCH FROM?",
     "ask": "Drop your city or your township. Let us see how far Khosi "
            "Nation reaches.",
     "say": "Where do you watch from? Drop your city or your township, and "
            "let us see how far Khosi Nation reaches."},
    {"key": "who",
     "headline": "WHO MADE YOU LOVE CHIEFS?",
     "ask": "A parent, a neighbour, a player? Say who, and say why.",
     "say": "Who made you love Chiefs? A parent, a neighbour, a player? "
            "Say who, and say why."},
    {"key": "because",
     "headline": "I LOVE AMAKHOSI BECAUSE...",
     "ask": "Finish the sentence in the comments. We will put the best ones "
            "on a card with your name.",
     "say": "Finish this sentence. I love Amakhosi because. We will put the "
            "best ones on a card with your name on it."},
]

MIN_SUPPORTERS = 4


def _log(m):
    print(f"[Love] {m}", flush=True)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"asks": [], "used": []}


def _save(d: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                     encoding="utf-8")


def next_prompt() -> dict:
    """Least-used prompt, so the same question is never asked twice running."""
    d = _state()
    counts = {p["key"]: 0 for p in PROMPTS}
    for k in d.get("used", []):
        if k in counts:
            counts[k] += 1
    return min(PROMPTS, key=lambda p: (counts[p["key"]],
                                       [x["key"] for x in PROMPTS].index(p["key"])))


async def _card(out_path: Path, club: str, headline: str, lines: list,
                footer: str, count_line: str = "") -> Path | None:
    """A 1080x1350 card in club colours. Quotes if given, else the question.

    Rendered by Chromium (modules/love_card_html) so the card can carry the
    crest, a gradient ground and raised quote panels - the owner's note on the
    last one was "no crest no nothing", which was a fair description of what
    ImageDraw is able to produce.

    The PIL card stays as the fallback and is not dead code. This runs at
    night on a scheduler; if the browser fails to launch the page still gets
    its post in the old design rather than nothing at all.
    """
    try:
        from modules.love_card_html import render_love_card
        await render_love_card(out_path, club, headline, lines, footer,
                               count_line)
        print("[Love] card rendered in browser")
        return out_path
    except Exception as e:
        print(f"[Love] browser card failed ({str(e)[:110]}) - drawing it")
    return _card_pil(out_path, club, headline, lines, footer, count_line)


def _card_pil(out_path: Path, club: str, headline: str, lines: list,
              footer: str, count_line: str = "") -> Path | None:
    """The original hand-drawn card. Fallback only."""
    from PIL import Image, ImageDraw
    from modules.typeface import font as _tf

    def _font(size, _kind="news"):
        return _tf(size)
    from modules.club_brand import CLUB_BRAND

    brand = CLUB_BRAND.get(club, {})
    gold = tuple(brand.get("colors", {}).get("primary", (255, 193, 7)))
    ink = (10, 10, 10)
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), ink)
    d = ImageDraw.Draw(img)

    # A gold bar top and bottom rather than a gold background: the club's black
    # is half its identity, and white text on gold is unreadable at thumbnail
    # size, which is the size most people will see this at.
    d.rectangle([0, 0, W, 18], fill=gold)
    d.rectangle([0, H - 18, W, H], fill=gold)

    y = 90
    f_kicker = _font(44, "news")
    d.text((70, y), brand.get("wordmark", "AMAKHOSI"), font=f_kicker, fill=gold)
    y += 78

    f_head = _font(72, "news")
    for line in _wrap(d, headline, f_head, W - 140):
        d.text((70, y), line, font=f_head, fill=(255, 255, 255))
        y += 84
    y += 30

    if count_line:
        f_count = _font(40, "news")
        d.text((70, y), count_line, font=f_count, fill=gold)
        y += 74

    f_body = _font(38, "news")
    f_name = _font(32, "news")
    for item in lines:
        if isinstance(item, dict):
            for line in _wrap(d, f'"{item["text"]}"', f_body, W - 190):
                d.text((104, y), line, font=f_body, fill=(240, 240, 240))
                y += 50
            d.text((104, y), f'— {item["name"]}', font=f_name, fill=gold)
            y += 66
        else:
            for line in _wrap(d, str(item), f_body, W - 140):
                d.text((70, y), line, font=f_body, fill=(230, 230, 230))
                y += 52
            y += 18
        if y > H - 200:
            break

    f_foot = _font(34, "news")
    d.text((70, H - 110), footer, font=f_foot, fill=gold)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)
    # NOT watermarked, deliberately. modules.brand defaults to the owner's
    # PERSONAL handle (@penuel.mdluli.7) when no brand is passed, so the first
    # version of this stamped the profile's mark onto a Kaizer Chiefs card -
    # a different page, a different audience, and the one handle that must
    # never appear here. It was also a no-op: watermark_image writes a NEW
    # _branded.png and returns its path, so the card being posted was the
    # unmarked original regardless. No other Genesis builder watermarks; the
    # card carries the club's colours and GENESIS NEWS in the footer instead.
    return out_path


def _wrap(draw, text, font, max_w):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


async def do_ask(a) -> int:
    p = next_prompt()
    _log(f"prompt: {p['key']} — {p['headline']}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"love_ask_{a.club}_{stamp}"
    card = await _card(work / "ask.png", a.club, p["headline"], [p["ask"]],
                 "COMMENT BELOW · KHOSI NATION")
    if not card:
        _log("card failed")
        return 1
    _log(f"card: {card}")

    nl = chr(10)
    caption = (f"{p['headline']} 👇{nl}{nl}{p['ask']}{nl}{nl}"
               f"We read every one, and the best go on a card with your name "
               f"on it.{nl}{nl}"
               f"#KaizerChiefs #Amakhosi #Khosi4Life #KhosiNation #PSL")
    if not a.post:
        _log("dry run — pass --post to publish")
        print(nl + caption + nl)
        return 0

    from modules.uploader_facebook import upload_photo
    r = await upload_photo(str(card), caption, NICHE)
    _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
    if (r or {}).get("status") != "uploaded":
        return 1
    pid = r.get("photo_id") or r.get("post_id")
    d = _state()
    d["asks"].append({"club": a.club, "post_id": str(pid), "prompt": p["key"],
                      "headline": p["headline"],
                      "asked_at": datetime.now().isoformat(timespec="seconds"),
                      "answered_at": ""})
    d["used"] = (d.get("used", []) + [p["key"]])[-40:]
    d["asks"] = d["asks"][-60:]
    _save(d)
    _log(f"ask recorded on post {pid} — the wall can answer it")
    return 0


async def do_wall(a) -> int:
    from modules.love_wall import gather

    d = _state()
    open_asks = [x for x in d.get("asks", [])
                 if not x.get("answered_at") and x["club"] == a.club]
    if not open_asks:
        _log("no unanswered love post on record — nothing to build a wall from")
        return 1
    ask = open_asks[-1]
    _log(f"reading {ask['prompt']} thread (post {ask['post_id']})")

    res = await gather(a.club, ask["post_id"])
    if res.get("error"):
        _log(f"cannot read the thread: {res['error']}")
        return 1
    _log(f"{res['comments']} comments, {res['supporters']} supporters sent love")
    for q in res["quotes"]:
        _log(f"   {q['score']:>3}  {q['name']}: {q['text'][:60]}")

    if res["supporters"] < a.min_supporters:
        _log(f"only {res['supporters']} — below the {a.min_supporters} floor. "
             f"Not building a wall out of nothing.")
        return 2
    if not res["quotes"]:
        _log("nobody left words worth quoting — no wall")
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"love_wall_{a.club}_{stamp}"
    card = await _card(work / "wall.png", a.club, "KHOSI NATION",
                 res["quotes"], "YOUR WORDS · GENESIS NEWS",
                 count_line=f"{res['supporters']} supporters answered")
    if not card:
        _log("card failed")
        return 1
    _log(f"card: {card}")

    nl = chr(10)
    names = ", ".join(q["name"] for q in res["quotes"])
    caption = (
        f"KHOSI NATION. 💛🖤{nl}{nl}"
        f"We asked, and {res['supporters']} of you answered. These are your "
        f"words, not ours — {names}, this one is yours.{nl}{nl}"
        f"Not on the card? Say it below and you are on the next one.{nl}{nl}"
        f"#KaizerChiefs #Amakhosi #Khosi4Life #KhosiNation #PSL")

    (work / "post_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "card": str(card), "caption": caption,
         "result": res, "ask": ask, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")

    if not a.post:
        _log("dry run — pass --post to publish")
        print(nl + caption + nl)
        return 0

    from modules.uploader_facebook import upload_photo, post_comment
    r = await upload_photo(str(card), caption, NICHE)
    _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
    if (r or {}).get("status") != "uploaded":
        _log("post failed — ask stays OPEN for a retry")
        return 1
    ask["answered_at"] = datetime.now().isoformat(timespec="seconds")
    _save(d)
    try:
        await post_comment(ask["post_id"],
                           f"Your words are up on the page now — "
                           f"{res['supporters']} of you answered. 💛🖤", NICHE)
    except Exception as e:
        _log(f"could not reply on the original post: {str(e)[:90]}")
    return 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--ask", action="store_true", help="post the question")
    ap.add_argument("--wall", action="store_true", help="post their answers")
    ap.add_argument("--min-supporters", type=int, default=MIN_SUPPORTERS)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    if not a.ask and not a.wall:
        a.ask = True
    return await (do_wall(a) if a.wall else do_ask(a))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
