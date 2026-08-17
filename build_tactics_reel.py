"""
Tactics reel — the flagship: animated Tactics Board + narration + captions.

First edition: "How Pirates Demolished Chippa 3-0" — the real XI from the
team sheet, the three real goals (Lungu 60', Seema 64', Msendami 87')
animated with ball movement, arrows and broadcast stat stamps.

Usage: python build_tactics_reel.py [--no-post]
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

SCRIPT = {
    "title": "How Pirates Demolished Chippa: 3-0 on the Tactics Board",
    "caption": (
        "THE TACTICS BOARD 📋 How Orlando Pirates took Chippa apart — "
        "Lungu 60', Seema 64', Msendami 87', all three goals animated.\n\n"
        "Which goal was your favourite? 👇⚽\n"
        "#PSL #BetwayPremiership #OrlandoPirates #OnceAlways"
    ),
    "scenes": [
        {"narration": "Welcome to the Genesis News tactics board. This is how "
                      "Orlando Pirates demolished Chippa United, three nil, "
                      "with the real starting eleven from the team sheet."},
        {"narration": "Goal one, minute sixty. Maswanganyi finds Lungu "
                      "drifting off the right wing, and Ghamphani Lungu "
                      "finishes. One nil."},
        {"narration": "Four minutes later, a corner drops to Lebone Seema at "
                      "the far post. Two nil, and Kings Park goes quiet."},
        {"narration": "Then super sub Msendami runs the channel in minute "
                      "eighty seven to make it three. Clinical."},
        {"narration": "Pirates go top of the log with this win. Follow "
                      "Genesis News for the tactics board after every big "
                      "P S L match."},
    ],
}


def build_board(duration: float):
    from modules.tactics_board import Board

    players = {
        "gk": {"no": "24", "name": "CHAINE"},
        "rb": {"no": "36", "name": "SEBELEBELE"},
        "cb1": {"no": "7", "name": "HOTTO"},
        "cb2": {"no": "33", "name": "MOKOBODI"},
        "lb": {"no": "6", "name": "SEEMA"},
        "dm1": {"no": "5", "name": "SIBISI"},
        "am": {"no": "28", "name": "MASWANGANYI"},
        "dm2": {"no": "46", "name": "DANSIN"},
        "rw": {"no": "23", "name": "LUNGU"},
        "st": {"no": "9", "name": "MBUTHUMA"},
        "lw": {"no": "12", "name": "APPOLLIS"},
        "sub": {"no": "45", "name": "MSENDAMI"},
    }
    b = Board(players, accent=(235, 235, 235),
              title="PIRATES 3-0 CHIPPA",
              subtitle="Real XI · real goals · Genesis News Tactics Board")

    base = {"gk": (.5, .95), "rb": (.85, .78), "cb1": (.63, .80),
            "cb2": (.37, .80), "lb": (.15, .78), "dm1": (.62, .62),
            "dm2": (.38, .62), "am": (.5, .48), "rw": (.82, .34),
            "lw": (.18, .34), "st": (.5, .26)}
    t_intro = duration * 0.16
    t_g1 = duration * 0.42
    t_g2 = duration * 0.62
    t_g3 = duration * 0.84

    b.keyframe(0.5, base)
    b.keyframe(t_intro, base)
    # goal 1: Maswanganyi -> Lungu cutting in
    g1 = dict(base)
    g1["am"] = (.55, .38)
    g1["rw"] = (.68, .16)
    b.keyframe(t_g1 - 1.5, g1)
    b.keyframe(t_g2 - 2.0, g1)
    b.ball([(t_intro + 0.5, (.5, .48)), (t_g1 - 2.6, (.55, .40)),
            (t_g1 - 1.6, (.68, .18)), (t_g1 - 1.0, (.52, .04))])
    b.arrow(t_intro + 0.8, t_g1 - 2.2, (.82, .34), (.70, .18),
            label="LUNGU DRIFTS IN")
    b.stat(t_g1 - 0.8, t_g1 + 2.2, "1-0", "LUNGU 60'")
    # goal 2: corner to Seema far post
    g2 = dict(g1)
    g2["lb"] = (.38, .12)
    b.keyframe(t_g2 - 0.8, g2)
    b.keyframe(t_g3 - 2.2, g2)
    b.ball([(t_g2 - 2.4, (.95, .06)), (t_g2 - 1.4, (.42, .10)),
            (t_g2 - 0.9, (.5, .03))])
    b.ring(t_g2 - 2.2, t_g2, "lb")
    b.stat(t_g2 - 0.6, t_g2 + 2.4, "2-0", "SEEMA 64' — corner, far post")
    # goal 3: Msendami channel run
    g3 = dict(g2)
    g3["sub"] = (.68, .30)
    b.keyframe(t_g3 - 2.0, {**g3, "sub": (.75, .55)})
    b.keyframe(t_g3 - 0.6, g3)
    b.arrow(t_g3 - 2.0, t_g3 - 0.8, (.75, .55), (.66, .28),
            label="MSENDAMI'S RUN")
    b.ball([(t_g3 - 1.6, (.4, .40)), (t_g3 - 0.9, (.64, .28)),
            (t_g3 - 0.4, (.48, .04))])
    b.stat(t_g3 - 0.2, t_g3 + 2.6, "3-0", "MSENDAMI 87'")
    return b


async def main(post: bool = True):
    from build_psl_news import (make_voice, write_manifest, post_to_page,
                                _caption_clips, _subscribe_strip)
    from modules.caption_generator import (parse_subtitle_to_segments,
                                           group_words_into_phrases)
    from modules.caption_align import align_captions
    from modules.script_writer import get_full_narration
    from moviepy import (AudioFileClip, ImageClip, VideoFileClip,
                         CompositeVideoClip, CompositeAudioClip)

    work = Path("output") / f"tactics_{datetime.now():%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)

    voice = await make_voice(SCRIPT, work)
    audio = AudioFileClip(voice["audio_path"])
    duration = float(audio.duration) + 0.6
    print(f"[Tactics] narration: {duration:.1f}s")

    board = build_board(duration)
    board_mp4 = board.render(work / "board.mp4", duration=duration)
    print(f"[Tactics] board rendered")

    bg = VideoFileClip(board_mp4)
    layers = [bg]
    try:
        sub = _subscribe_strip(work)
        layers.append(ImageClip(sub).with_start(max(0, duration - 4.0))
                      .with_duration(min(4.0, duration))
                      .with_position(("center", 1730)))
    except Exception:
        pass
    try:
        segments = parse_subtitle_to_segments(voice["subtitle_path"])
        segments = align_captions(get_full_narration(SCRIPT), segments)
        phrases = group_words_into_phrases(segments, max_words=4)
        layers += _caption_clips(phrases, 1080, work)
    except Exception as e:
        print(f"[Tactics] captions skipped: {e}")

    video = CompositeVideoClip(layers, size=(1080, 1920)) \
        .with_duration(duration) \
        .with_audio(CompositeAudioClip([audio]).with_duration(duration))
    out = work / "final.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", logger=None,
                          preset="medium", threads=4)

    images = [{"path": str(work / "board.mp4"), "credit": "Genesis News",
               "archive_year": "", "club": "pirates", "real": True}]
    write_manifest(SCRIPT, str(out), work, voice, images)
    print(f"[Tactics] video: {out}")

    if post:
        await post_to_page(work)
        print("[Tactics] POSTED")


if __name__ == "__main__":
    try:
        asyncio.run(main("--no-post" not in sys.argv))
    except Exception as e:
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure("tactics-reel", f"TACTICS REEL FAILED: "
                           f"{type(e).__name__}: {str(e)[:130]}")
        except Exception:
            pass
        raise
