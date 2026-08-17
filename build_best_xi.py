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


def _xi_overlay(out: Path) -> str:
    """Transparent 1080x1920 overlay: the FULL XI floating over the footage —
    the lineup must be readable for the whole video (owner note 2026-08-17:
    'only the starting 11 visible over the video, playing')."""
    from PIL import Image, ImageDraw, ImageFont

    def font(sz, bold=True):
        return ImageFont.truetype(
            f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}", sz)

    W, H = 1080, 1920
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # header
    d.rounded_rectangle([40, 210, W - 40, 330], radius=22, fill=(10, 10, 12, 200))
    d.text((70, 228), "OUR BEST KAIZER CHIEFS XI", font=font(46),
           fill=(255, 200, 0, 255))
    d.text((70, 284), "4-3-3  ·  the debate starts now", font=font(28, False),
           fill=(235, 235, 235, 255))

    rows = [
        ([("17", "VELEBAYI"), ("11", "BAARTMAN"), ("70", "PHILI")], 430),
        ([("5", "MTHETHWA"), ("6", "MABOE"), ("8", "NDLOVU")], 700),
        ([("2", "MONYANE"), ("84", "MIGUEL"), ("4", "MACHEKE"),
          ("39", "FROSLER")], 970),
        ([("16", "LEANER")], 1240),
    ]
    nf, cf = font(30), font(34)
    for players, y in rows:
        step = W // (len(players) + 1)
        for i, (no, name) in enumerate(players):
            cx = step * (i + 1)
            d.ellipse([cx - 44, y - 44, cx + 44, y + 44],
                      fill=(255, 193, 7, 255), outline=(255, 255, 255, 255),
                      width=3)
            w_no = d.textlength(no, font=cf)
            d.text((cx - w_no / 2, y - 22), no, font=cf, fill=(15, 15, 15, 255))
            w_nm = d.textlength(name, font=nf)
            d.rounded_rectangle([cx - w_nm / 2 - 16, y + 54,
                                 cx + w_nm / 2 + 16, y + 104], radius=12,
                                fill=(10, 10, 12, 220))
            d.text((cx - w_nm / 2, y + 62), name, font=nf,
                   fill=(255, 255, 255, 255))

    bench = "BENCH: Petersen · Moloisane · Solomons · Chislett · Vilakazi · Shabalala · Silva"
    bf = font(26)
    while d.textlength(bench, font=bf) > W - 100 and bf.size > 20:
        bf = font(bf.size - 2)
    bw = d.textlength(bench, font=bf)
    d.rounded_rectangle([(W - bw) / 2 - 20, 1395, (W + bw) / 2 + 20, 1455],
                        radius=14, fill=(10, 10, 12, 210))
    d.text(((W - bw) / 2, 1408), bench, font=bf, fill=(235, 238, 242, 255))
    im.save(out)
    return str(out)


async def assemble_xi_over_video(script: dict, voice: dict, work: Path,
                                 clip_path: str) -> str:
    """Owner footage FULL-SCREEN with the XI overlay riding on top for the
    entire duration — footage behind, lineup always readable."""
    from moviepy import (AudioFileClip, ImageClip, VideoFileClip, ColorClip,
                         CompositeVideoClip, CompositeAudioClip,
                         concatenate_videoclips as _cat)
    from modules.caption_generator import (parse_subtitle_to_segments,
                                           group_words_into_phrases)
    from modules.caption_align import align_captions
    from modules.script_writer import get_full_narration
    from build_psl_news import _caption_clips, _subscribe_strip

    W, H = 1080, 1920
    audio = AudioFileClip(voice["audio_path"])
    duration = float(audio.duration) + 0.5

    src = VideoFileClip(clip_path).without_audio()
    if src.duration < duration:
        src = _cat([src] * (int(duration // src.duration) + 1))
    s = max(W / src.w, H / src.h)
    bg = (src.subclipped(0, duration).resized(s)
          .cropped(x_center=src.w * s / 2, y_center=src.h * s / 2,
                   width=W, height=H))
    dim = ColorClip(size=(W, H), color=(0, 0, 0)).with_opacity(0.45) \
        .with_duration(duration)
    xi = ImageClip(_xi_overlay(work / "xi_overlay.png")) \
        .with_duration(duration)

    layers = [bg, dim, xi]
    try:
        sub = _subscribe_strip(work)
        layers.append(ImageClip(sub).with_start(max(0, duration - 4.0))
                      .with_duration(min(4.0, duration))
                      .with_position(("center", 1730)))
    except Exception:
        pass

    try:
        segments = parse_subtitle_to_segments(voice["subtitle_path"])
        segments = align_captions(get_full_narration(script), segments)
        phrases = group_words_into_phrases(segments, max_words=4)
        layers += _caption_clips(phrases, W, work)
    except Exception as e:
        print(f"[BestXI] captions skipped: {e}")

    video = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    video = video.with_audio(CompositeAudioClip([audio]).with_duration(duration))
    out = work / "final.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", logger=None,
                          preset="medium", threads=4)
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
    if post and "--video-only" not in sys.argv:
        r = await _post_photo(card, CAPTION, COMMENT)
        print(f"[BestXI] photo post: {r.get('status')} "
              f"{r.get('photo_id') or r.get('post_id')}")

    # 2) VIDEO — owner footage FULL-SCREEN, the complete XI floating over it
    # for the whole reel (the lineup IS the content; nothing may cover it)
    voice = await make_voice(SCRIPT, work)
    from modules.owner_media import pick_owner_video
    cc_clip = pick_owner_video([CLUB])
    if not cc_clip:
        raise RuntimeError("no owner footage for the background")
    print(f"[BestXI] owner clip: {Path(cc_clip['path']).name}")

    video = await assemble_xi_over_video(SCRIPT, voice, work, cc_clip["path"])
    images = [{"path": card, "credit": "Genesis News", "archive_year": "",
               "club": CLUB, "real": True, "owner": True}]
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
