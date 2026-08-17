"""
OUR BEST XI — editorial lineup debate content (image post + narrated reel).

Owner spec (2026-08-17): pick the BEST Kaizer Chiefs starting eleven with
bold calls (Leaner over captain Petersen in goal), name the bench, post an
image + a video, seed the debate in the comments.

Usage: python build_best_xi.py [--no-post]
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

CLUB = "chiefs"

# Editorial XI (4-3-3) — every name verified against the ACTUAL team sheets
# of the last matches (fact-checked with the owner 2026-08-17: Cele,
# Ditlhokwe, Du Preez are gone; Shabalala stays). Two debates baked in:
#   1. Leaner (new signing, 9 clean sheets at Sekhukhune) over captain Petersen
#   2. fan favourite Shabalala on the BENCH
XI = [
    "16 Leaner",
    "2 Monyane", "84 Miguel", "4 Macheke", "39 Frosler",
    "5 Mthethwa", "6 Maboe", "8 Ndlovu",
    "17 Velebayi", "11 Baartman", "70 Phili",
]
BENCH = ["1 Petersen", "42 Moloisane", "18 Solomons", "23 Chislett",
         "28 Vilakazi", "7 Shabalala", "77 Silva"]

TITLE = "Our Best Chiefs XI: Leaner In, Shabalala Benched?"
CAPTION = (
    "OUR BEST KAIZER CHIEFS XI (4-3-3) — two bold calls:\n"
    "🧤 Renaldo Leaner gets the gloves over captain Brandon Petersen — "
    "9 clean sheets in 18 games last season earns that.\n"
    "🔥 Mdu Shabalala starts on the BENCH.\n\n"
    "XI: Leaner; Monyane, Inácio Miguel, Macheke, Frosler; Mthethwa, Maboe, "
    "Ndlovu; Velebayi, Baartman, Phili\n"
    "Bench: Petersen, Moloisane, Solomons, Chislett, Vilakazi, Shabalala, "
    "Silva\n\n"
    "Too bold? Drop YOUR eleven below 👇⚽\n"
    "#PSL #BetwayPremiership #KaizerChiefs #Amakhosi"
)
COMMENT = ("Two fights in one post: the keeper call AND Shabalala on the "
           "bench 👇 Convince us we're wrong — best fan XI gets pinned.")

SCRIPT = {
    "title": TITLE,
    "caption": CAPTION,
    "scenes": [
        {"narration": "We picked our best Kaizer Chiefs eleven, and we start "
                      "with a bold call. Renaldo Leaner takes the gloves "
                      "ahead of captain Brandon Petersen. Nine clean sheets "
                      "in eighteen games last season earns that shirt."},
        {"narration": "The back four: Monyane, Inacio Miguel, Macheke and "
                      "Frosler. In midfield, Mthethwa anchors while Maboe "
                      "and Ndlovu run the game."},
        {"narration": "Up front: Velebayi, Baartman and Phili. And yes, "
                      "Mdu Shabalala starts on the bench, alongside Petersen, "
                      "Moloisane, Solomons, Chislett, Vilakazi and Silva."},
        {"narration": "Two bold calls. Drop your eleven in the comments, and "
                      "follow Genesis News for daily P S L."},
    ],
}


def _pad_card(src: str, out: Path) -> str:
    """Lineup card (1080x1350) onto the reel canvas (1080x1920), dark stage."""
    from PIL import Image
    canvas = Image.new("RGB", (1080, 1920), (12, 14, 18))
    card = Image.open(src).convert("RGB")
    canvas.paste(card, (0, (1920 - card.height) // 2))
    canvas.save(out, quality=95)
    return str(out)


async def main(post: bool = True):
    from modules.lineup_card import make_lineup_card
    from build_psl_news import (make_voice, assemble, write_manifest,
                                post_to_page)
    from matchday import _post_photo

    work = Path("output") / f"bestxi_{datetime.now():%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)

    card = make_lineup_card(
        work / "bestxi_card.png", club=CLUB, players=XI, formation="4-3-3",
        competition="OUR BEST XI — the debate starts now",
        predicted=False)
    if not card:
        raise RuntimeError("lineup card failed")
    print(f"[BestXI] card: {card}")

    # 1) IMAGE POST — the card + the full argument in the caption
    if post:
        r = await _post_photo(card, CAPTION, COMMENT)
        print(f"[BestXI] photo post: {r.get('status')} "
              f"{r.get('photo_id') or r.get('post_id')}")

    # 2) VIDEO — narrated debate reel: owner footage window card, then the XI
    voice = await make_voice(SCRIPT, work)
    from modules.owner_media import pick_owner_video
    cc_clip = pick_owner_video([CLUB])
    if cc_clip:
        cc_clip = {**cc_clip, "club": CLUB}
        print(f"[BestXI] owner clip: {Path(cc_clip['path']).name}")

    from build_psl_news import build_cards
    images = [{"path": card, "credit": "Genesis News", "archive_year": "",
               "club": CLUB, "real": True, "owner": True}]
    card1 = build_cards(SCRIPT, images, {}, work,
                        video_cards=1 if cc_clip else 0)
    padded = _pad_card(card, work / "card_xi.png")
    cards = ([card1[0]] if card1 else []) + [padded]

    video = await assemble(SCRIPT, voice, cards, work, cc_clip=cc_clip)
    write_manifest(SCRIPT, video, work, voice, images)
    print(f"[BestXI] video: {video}")

    if post:
        await post_to_page(work)
        print("[BestXI] POSTED")


if __name__ == "__main__":
    try:
        asyncio.run(main("--no-post" not in sys.argv))
    except Exception as e:
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure("best-xi", f"BEST XI BUILD FAILED: "
                           f"{type(e).__name__}: {str(e)[:130]}")
        except Exception:
            pass
        raise
