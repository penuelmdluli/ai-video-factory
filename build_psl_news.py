"""
Genesis News — PSL news reel builder. Static images only, no video generation.

The full pipeline is built to generate video, and every stall in this project has
come from that: RunPod hung, WaveSpeed hung, local SVD ran ~47s/step for an hour.
A news page does not need generated video. It needs one or two REAL, recent,
correctly-credited images, edited into news cards, with voice, subtitles and
music over the top.

Pipeline:
  1. live sourced headlines   (modules/psl_news)
  2. script + fact guards     (modules/script_writer — Claude subscription CLI)
  3. voice + SRT              (modules/voice_generator — Kokoro af_heart)
  4. 1-2 real photos          (modules/free_press_images — CC-licensed, credited)
                              falling back to Cloudflare FLUX matchday b-roll
  5. news cards               (modules/news_card — headline, kicker, credit, logo)
  6. assemble                 (Ken Burns + karaoke subtitles + music)
  7. upload_manifest.json     so the existing uploader can post it

Usage:
    python build_psl_news.py              # build only
    python build_psl_news.py --post       # build then post to the Genesis News page
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import NICHES, OUTPUT_DIR
from modules.club_brand import resolve_club, resolve_clubs, CLUB_BRAND

NICHE = "sa_pulse"
MAX_CARDS = 2          # "one or two real recent images and we are done"


def _log(msg):
    print(f"[PSL] {msg}", flush=True)


async def pick_topic() -> str:
    from modules.topic_generator import generate_trending_topic_ai
    topic = await generate_trending_topic_ai(NICHE)
    if not topic:
        pin = NICHES[NICHE].get("topic_pin") or "Kaizer Chiefs latest news"
        topic = f"{pin}: what the latest team news means"
        _log(f"topic generation failed — using pin fallback")
    _log(f"topic: {topic}")
    return topic


async def write_script(topic: str) -> dict:
    from modules.script_writer import generate_script
    script = await generate_script(topic, NICHE, "short")
    if not script:
        raise RuntimeError("script generation failed")
    _log(f"script: {script.get('title', '')[:70]} ({len(script.get('scenes', []))} scenes)")
    return script


async def make_voice(script: dict, work: Path) -> dict:
    from modules.voice_generator import generate_voice
    from modules.script_writer import get_full_narration
    narration = get_full_narration(script)
    result = await generate_voice(narration, work, "voiceover", "short",
                                  NICHE, script.get("scenes"))
    if not result:
        raise RuntimeError("voice generation failed")
    _log(f"voice: {result.get('engine')}/{result.get('voice')} "
         f"{result.get('duration_estimate', 0):.0f}s")
    return result


_NAME_STOP = {
    # club/league words + sentence-starters that look like "Firstname Surname"
    "kaizer", "chiefs", "orlando", "pirates", "mamelodi", "sundowns", "amakhosi",
    "amazulu", "chippa", "united", "durban", "city", "golden", "arrows", "magesi",
    "marumo", "gallants", "orbit", "college", "polokwane", "richards", "bay",
    "sekhukhune", "siwelele", "stellenbosch", "galaxy", "south", "africa",
    "african", "premier", "soccer", "league", "betway", "premiership", "soweto",
    "derby", "genesis", "news", "the", "what", "why", "how", "this", "that",
    "here", "watch", "live", "breaking", "latest", "caf", "champions", "cup",
    "fnb", "stadium", "loftus", "versfeld", "moses", "mabhida", "coach", "boss",
}


def _player_names(*texts: str) -> list[str]:
    """Capitalised first-last pairs that aren't club/league words — probable players."""
    seen, out = set(), []
    for t in texts:
        for m in re.finditer(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z']{2,})\b", t or ""):
            cand = f"{m.group(1)} {m.group(2)}"
            if any(w.lower() in _NAME_STOP for w in cand.split()):
                continue
            if cand.lower() not in seen:
                seen.add(cand.lower())
                out.append(cand)
    return out


def _frames_from_clip(clip: dict, work: Path, need: int) -> list[dict]:
    """
    Still frames from a recent CC-BY highlight video — REAL, days-old imagery
    of the actual club, which beats years-old Commons photos every time. The
    video's CC licence covers stills, and the same creator credit is burned in.
    """
    import subprocess
    out = []
    dur_probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", clip["path"]], capture_output=True, text=True)
    try:
        dur = float(dur_probe.stdout.strip())
    except Exception:
        dur = 10.0
    offsets = [dur * f for f in (0.35, 0.7, 0.5, 0.85)][:max(need * 2, 2)]
    for i, t in enumerate(offsets):
        if len(out) >= need:
            break
        p = work / "photos" / f"ccframe_{i+1}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
             "-i", clip["path"], "-frames:v", "1", "-q:v", "2", str(p)],
            capture_output=True)
        if r.returncode == 0 and p.exists() and p.stat().st_size > 30_000:
            out.append({"path": str(p),
                        "credit": f"still: {clip['channel']} (CC BY, via YouTube)",
                        "archive_year": "", "club": clip.get("club", ""),
                        "real": True})
    if out:
        _log(f"cc video stills: {len(out)} from '{clip['title'][:40]}'")
    return out


async def gather_images(script: dict, briefing: dict, work: Path) -> tuple[list[dict], dict | None]:
    """
    One or two REAL images, correctly credited, plus the CC clip for motion.
    Priority: recent photo of a NAMED player -> still frames from a recent
    CC-BY highlight video (real + days old) -> club-first Commons photo ->
    generated matchday b-roll. Never a scraped press photo.
    """
    from modules.free_press_images import photos_for_club, photos_for_player, download
    from modules.ai_images import generate_image_cloudflare

    title = script.get("title", "")
    narrations = " ".join(s.get("narration", "") for s in script.get("scenes", []))
    club = resolve_club(title) or resolve_club(narrations) or "generic"
    _log(f"club context: {club}")

    raw_dir = work / "photos"
    out = []

    # 1) The players the story is actually about — newest photo first.
    heads = " ".join(i.get("title", "") for k in briefing or {}
                     if isinstance(briefing.get(k), list)
                     for i in briefing[k][:3] if isinstance(i, dict))
    players = _player_names(title, narrations, heads)[:8]
    story_clubs = []

    # Validate against CURRENT squads — title-case headlines make the
    # capitalised-bigram heuristic hallucinate "players" like "Warning Means".
    # A candidate only survives if a real squad member matches it.
    try:
        from modules.psl_squads import get_squad
        from modules.club_brand import resolve_clubs
        story_clubs = resolve_clubs(f"{title} {narrations} {heads}") or [club]
        roster = {}
        for ck in story_clubs[:3]:
            for p in await get_squad(ck):
                roster[p["name"].split()[-1].lower()] = p["name"]
        verified = []
        for cand in players:
            canon = roster.get(cand.split()[-1].lower())
            if canon:
                verified.append(canon)      # use the squad's canonical spelling
        players = list(dict.fromkeys(verified))[:4]
    except Exception as e:
        _log(f"squad validation skipped: {e}")
        players = players[:4]
    if players:
        _log(f"player candidates (squad-verified): {players}")
    def _archive(hit) -> str:
        # Stamp ARCHIVE only when the photo is genuinely old — a shot from this
        # season or last is current coverage, not archive material.
        y = hit.get("year") or 0
        return str(y) if y and y < datetime.now().year - 1 else ""

    for name in players:
        if len(out) >= MAX_CARDS:
            break
        for hit in await photos_for_player(name, 1):
            path = await download(hit, raw_dir / f"photo_{len(out)+1}.jpg")
            if path:
                out.append({"path": path, "credit": hit["credit"],
                            "archive_year": _archive(hit),
                            "club": club, "real": True})
                _log(f"player photo: {name} ({hit.get('year') or 'undated'})")

    # 2) Still frames from a recent CC-BY highlight video of this club —
    #    real footage from THIS WEEK beats an old Commons photo. The local
    #    clip library (daily sweep) answers instantly; live fetch is fallback.
    cc_clip = None
    try:
        from modules.clip_library import get_clips
        # any club in the story can supply the live window — Chiefs footage
        # is valid on a Chiefs-vs-Sundowns story even when Sundowns lead it
        for ck in ([club] + [c for c in story_clubs if c != club]):
            lib = get_clips(ck, 1)
            if lib:
                cc_clip = {**lib[0], "club": ck}
                _log(f"clip from library ({ck}): {lib[0]['title'][:45]}")
                break
    except Exception as e:
        _log(f"clip library skipped: {e}")
    if not cc_clip:
        try:
            from modules.cc_clips import fetch_cc_clip
            club_name = CLUB_BRAND.get(club, {}).get("name", "PSL")
            cc_clip = await fetch_cc_clip(f"{club_name} highlights", work / "cc")
            if cc_clip:
                cc_clip["club"] = club
        except Exception as e:
            _log(f"cc clip lookup skipped: {e}")
    if cc_clip and len(out) < MAX_CARDS:
        out += _frames_from_clip(cc_clip, work, MAX_CARDS - len(out))

    # 3) Club/matchday photos to fill the remainder. A photo whose title lists
    #    ANOTHER team first ("Go Ahead Eagles - Mamelodi Sundowns ...") is shot
    #    from the opponent's side — it reads as the wrong club on a card, so
    #    the on-brand generated matchday visual below beats it.
    club_words = CLUB_BRAND.get(club, {}).get("name", club).lower().split()
    if len(out) < MAX_CARDS:
        for hit in await photos_for_club(club, (MAX_CARDS - len(out)) + 2):
            head = hit["title"].split("-")[0].lower()
            if not any(w in head for w in club_words):
                _log(f"photo skipped (opponent-first): {hit['title'][:50]}")
                continue
            path = await download(hit, raw_dir / f"photo_{len(out)+1}.jpg")
            if path:
                out.append({"path": path, "credit": hit["credit"],
                            "archive_year": _archive(hit),
                            "club": club, "real": True})
            if len(out) >= MAX_CARDS:
                break
    _log(f"licensed photos: {len(out)}")

    while len(out) < MAX_CARDS:
        n = len(out) + 1
        brand = CLUB_BRAND.get(club, {})
        colours = brand.get("prompt_colors", "team colours")
        prompt = (
            f"RAW press photograph, packed South African football stadium at night under "
            f"floodlights, ecstatic anonymous supporters in {colours}, vuvuzelas raised, "
            f"makarapa helmets, motion blur, long lens sports photography, no logos, "
            f"no badges, no text"
        )
        p = raw_dir / f"generated_{n}.png"
        got = await generate_image_cloudflare(prompt, p, niche=NICHE,
                                              orientation="portrait", enhance=False)
        if not got:
            break
        out.append({"path": got, "credit": "Genesis News illustration",
                    "archive_year": "", "club": club, "real": False})
    _log(f"images total: {len(out)}")
    return out, cc_clip


async def _make_prediction(title: str, log_rows: list) -> str:
    """
    "OUR CALL: CHIEFS 2-1 — BAARTMAN TO SCORE" for two-club stories.
    Favourite = higher log position; scorer = the favourite's most-started
    forward. Pure labelled opinion built from real data — never a stated fact.
    """
    clubs = resolve_clubs(title)
    if len(clubs) < 2:
        return ""
    from modules.psl_squads import recent_starts, get_squad
    rank = {r.get("team_key"): r.get("rank", 99) for r in log_rows or []}
    a, b = clubs[:2]
    fav = a if rank.get(a, 99) <= rank.get(b, 99) else b

    def sur(n: str) -> str:
        w = n.split()
        if len(w) >= 2 and w[-2].lower() in ("du", "de", "van", "von", "le", "da", "dos"):
            return " ".join(w[-2:])
        return w[-1] if w else n

    starts, _f = await recent_starts(fav)
    squad = await get_squad(fav)
    fws = sorted([p for p in squad if p["pos"] == "FW"],
                 key=lambda p: -starts.get(sur(p["name"]).lower(), 0))
    scorer = sur(fws[0]["name"]).upper() if fws else ""
    short = CLUB_BRAND.get(fav, {}).get("name", fav).upper() \
        .replace("KAIZER ", "").replace("MAMELODI ", "").replace("ORLANDO ", "")
    txt = f"OUR CALL: {short} 2-1"
    if scorer:
        txt += f" — {scorer} TO SCORE"
    return txt


def build_cards(script: dict, images: list[dict], briefing: dict, work: Path,
                prediction: str = "", log_rows: list | None = None) -> list[str]:
    """Turn each image into a branded news card carrying the headline + credit."""
    from modules.news_card import make_news_card

    club = images[0]["club"] if images else "generic"
    kicker = CLUB_BRAND.get(club, {}).get("name", "PSL")
    headline = script.get("title", "")

    # Second card leads on the strongest sourced headline, so the two cards say
    # different things instead of repeating the title.
    lead = ""
    for key in (club, "chiefs", "premiership"):
        items = briefing.get(key) or []
        if items:
            lead = items[0]["title"]
            break

    cards = []
    for i, img in enumerate(images):
        text = headline if i == 0 else (lead or headline)
        credit = img["credit"]
        if img["real"]:
            credit = f"photo: {credit}"
        out = work / f"card_{i+1}.png"
        made = make_news_card(img["path"], out, headline=text, kicker=kicker,
                              credit=credit, club=club,
                              archive_year=img.get("archive_year", ""),
                              prediction=prediction if i == 0 else "",
                              log_rows=log_rows if (i == 1 or len(images) == 1)
                              else None)
        if made:
            cards.append(made)
    _log(f"news cards: {len(cards)}")
    return cards


CANVAS = (1080, 1920)
CAPTION_BOTTOM_MARGIN = 300     # keeps subs clear of the card's own headline block


def _caption_clips(segments, video_w, work: Path):
    """
    Tech Pulse Africa caption style — the SAME renderer the tech_news reels use
    (assemble_full.render_caption_png): PIL-drawn, wrapped to max 2 lines, font
    shrunk until every line fits inside 86% of the frame width (never cut off),
    key words highlighted in accent, heavy black outline. MoviePy TextClip was
    clipping words at the frame edge; this can't.
    """
    from moviepy import ImageClip
    from assemble_full import render_caption_png, CAP_H
    clips = []
    cap_dir = work / "captions"
    cap_dir.mkdir(exist_ok=True)
    for i, seg in enumerate(segments):
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start + 1))
        if end <= start:
            continue
        try:
            png = render_caption_png(txt, video_w, str(cap_dir / f"cap_{i}.png"))
            clips.append(
                ImageClip(png).with_start(start).with_duration(end - start)
                .with_position(("center",
                                CANVAS[1] - CAPTION_BOTTOM_MARGIN - CAP_H // 2)))
        except Exception as e:
            print(f"[PSL] caption clip skipped: {e}")
    return clips


def _credit_strip(text: str, work: Path) -> str:
    """Small semi-transparent credit bar for real-footage segments."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    except Exception:
        f = ImageFont.load_default()
    img = Image.new("RGBA", (CANVAS[0], 56), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = d.textlength(text, font=f)
    d.rounded_rectangle([CANVAS[0] / 2 - w / 2 - 24, 0,
                         CANVAS[0] / 2 + w / 2 + 24, 52], radius=14,
                        fill=(0, 0, 0, 170))
    d.text((CANVAS[0] / 2 - w / 2, 10), text, font=f, fill=(235, 240, 245, 255))
    p = work / "cc_credit.png"
    img.save(p)
    return str(p)


async def assemble(script: dict, voice: dict, cards: list[str], work: Path,
                   cc_clip: dict | None = None) -> str:
    """
    Compose the reel directly — NO Ken Burns, NO zoom, NO cinematic effects.

    The cards are already finished 1080x1920 artwork with the logo, headline and
    credit positioned exactly. The main assembler applies a 1.5x Ken Burns zoom,
    which cropped straight through all of it: the wordmark vanished, the kicker
    and headline were cut off at both edges, and the attribution was clipped.
    A pre-composed card must be shown 1:1.
    """
    from moviepy import (AudioFileClip, ImageClip, CompositeVideoClip,
                         CompositeAudioClip, concatenate_videoclips)
    from modules.caption_generator import parse_subtitle_to_segments, group_words_into_phrases
    from modules.caption_align import align_captions
    from modules.script_writer import get_full_narration

    voice_audio = AudioFileClip(voice["audio_path"])
    duration = voice_audio.duration

    segments = parse_subtitle_to_segments(voice["subtitle_path"])
    # The SRT is a transcription and mangles SA names ("Kiser", "Maim Lodi").
    # Respell every word from the narration text — timing from the SRT,
    # spelling from the script.
    segments = align_captions(get_full_narration(script), segments)
    captions = group_words_into_phrases(segments, max_words=4)

    # Timeline: cards held static (a news frame wants to be read). Real
    # CC-licensed footage PLAYS INSIDE the card's photo window — the zone
    # between the top bar and the headline block — so the title, log and
    # credits stay on screen while live match video runs above them.
    per = duration / max(1, len(cards))
    stills = [ImageClip(str(c)).with_duration(per).resized(CANVAS) for c in cards]
    base = concatenate_videoclips(stills, method="compose").with_duration(duration)

    overlay_layers = []
    if cc_clip:
        try:
            from moviepy import VideoFileClip
            WIN_Y, WIN_H = 307, 650          # photo zone: below brand bar, above kicker
            vc = VideoFileClip(cc_clip["path"]).without_audio()
            emb_dur = float(min(vc.duration, per - 0.6, 9.0))
            s = max(CANVAS[0] / vc.w, WIN_H / vc.h)
            emb = vc.subclipped(0, emb_dur).resized(s)
            x1 = max(0, int((emb.w - CANVAS[0]) / 2))
            y1 = max(0, int((emb.h - WIN_H) / 2))
            emb = (emb.cropped(x1=x1, y1=y1, width=CANVAS[0], height=WIN_H)
                   .with_start(0.5).with_position((0, WIN_Y)))
            overlay_layers.append(emb)
            overlay_layers.append(
                ImageClip(_credit_strip(cc_clip["credit"], work))
                .with_start(0.5).with_duration(emb_dur)
                .with_position(("center", WIN_Y + WIN_H - 70)))
            _log(f"live window: {emb_dur:.1f}s of real footage in card 1")
        except Exception as e:
            _log(f"cc clip window skipped: {e}")

    layers = [base] + overlay_layers + _caption_clips(captions, CANVAS[0], work)
    video = CompositeVideoClip(layers, size=CANVAS).with_duration(duration)

    # Music bed under the voice, quiet enough to stay a news read.
    audio_tracks = [voice_audio]
    try:
        from modules.video_assembler import _get_music_track
        mp = _get_music_track(niche=NICHE)
        if mp and Path(mp).exists():
            bed = AudioFileClip(mp)
            if bed.duration < duration:
                from moviepy import concatenate_audioclips
                reps = int(duration // bed.duration) + 1
                bed = concatenate_audioclips([bed] * reps)
            audio_tracks.append(bed.subclipped(0, duration).with_volume_scaled(0.10))
            _log("music bed added")
    except Exception as e:
        _log(f"music skipped: {e}")

    video = video.with_audio(CompositeAudioClip(audio_tracks).with_duration(duration))

    out = work / "final.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac",
                          preset="medium", threads=4, logger=None)
    for c in stills:
        c.close()
    voice_audio.close()
    _log(f"assembled (static, no zoom): {out}")
    return str(out)


def write_manifest(script: dict, video_path: str, work: Path, voice: dict, images: list | None = None, prediction: str = "", log_rows: list | None = None) -> Path:
    hashtags = NICHES[NICHE]["hashtags"]
    caption = script.get("caption") or script.get("title", "")

    # Reel cover: BOTH club badges, huge — a badge-first thumbnail out-pulls a
    # photo card at feed size (owner rule 2026-08-14).
    # Cover = the card_2 look the owner picked: real photo, crests, live log,
    # headline — with the Genesis logo BIG in the top space (cover_mode).
    thumb = str(work / "card_1.png")
    try:
        from modules.news_card import make_news_card
        clubs = resolve_clubs(script.get("title", "") + " " + caption)
        bg, bg_credit = None, ""
        for img in images or []:
            if Path(img.get("path", "")).exists():
                bg, bg_credit = img["path"], img.get("credit", "")
                break
        if bg:
            kicker = CLUB_BRAND.get(clubs[0] if clubs else "", {}).get("name", "PSL")
            c = make_news_card(bg, work / "cover.png",
                               headline=script.get("title", ""), kicker=kicker,
                               credit=bg_credit, club=clubs[0] if clubs else "",
                               log_rows=log_rows or None, cover_mode=True)
            if c:
                thumb = c
    except Exception as e:
        _log(f"cover skipped: {e}")
    manifest = {
        "niche": NICHE,
        "format_type": "short",
        "is_short": True,
        "uploaded": False,
        "built_at": datetime.now().isoformat(),
        "video_path": str(video_path),
        "title": script.get("title", "PSL News"),
        "description": script.get("description") or caption,
        "caption": caption,
        "tags": [h.lstrip("#") for h in hashtags],
        "comment_hashtags": [],
        "srt_path": voice.get("subtitle_path", ""),
        "thumb_path": thumb,
        "prediction": prediction,
    }
    p = work / "upload_manifest.json"
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(f"manifest: {p}")
    return p


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="post to the Genesis News page after building")
    args = ap.parse_args()

    from modules.psl_news import get_psl_briefing
    briefing = await get_psl_briefing()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(OUTPUT_DIR) / f"{NICHE}_short_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    topic = await pick_topic()
    script = await write_script(topic)
    voice = await make_voice(script, work)
    images, cc_clip = await gather_images(script, briefing, work)
    if not images:
        raise RuntimeError("no usable images — refusing to build")
    # Live log + our score/scorer call — the extras that make a card shareable.
    log_rows, prediction = [], ""
    try:
        from modules.psl_standings import get_log
        log_rows = await get_log(6)
    except Exception as e:
        _log(f"standings skipped: {e}")
    try:
        prediction = await _make_prediction(script.get("title", ""), log_rows)
        if prediction:
            _log(f"prediction: {prediction}")
    except Exception as e:
        _log(f"prediction skipped: {e}")

    cards = build_cards(script, images, briefing, work, prediction, log_rows)
    video = await assemble(script, voice, cards, work, cc_clip=cc_clip)
    write_manifest(script, video, work, voice, images, prediction, log_rows)

    _log("BUILD COMPLETE")
    if args.post:
        await post_to_page(work)
        _log("POST COMPLETE")


async def post_to_page(work: Path) -> dict | None:
    """
    Post the built reel DIRECTLY to the Genesis News page (no YouTube/TikTok
    fan-out — this page is the product), then seed the comment section:
      1. an engagement comment (score prediction / opinion bait), and
      2. a follow CTA — first comments from the page lift reach and set the tone.
    """
    from modules.uploader_facebook import upload_to_facebook, post_comment
    from modules.club_brand import resolve_clubs, CLUB_BRAND

    mp = work / "upload_manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    if manifest.get("uploaded"):
        _log("already posted — skipping")
        return None

    fb = await upload_to_facebook(
        video_path=manifest["video_path"],
        title=manifest["title"],
        description=manifest["description"],
        niche=NICHE,
        hashtags=manifest.get("tags", []),
        is_reel=True,
        thumbnail_path=manifest.get("thumb_path"),
    )
    if fb.get("status") != "uploaded":
        _log(f"FB upload failed: {fb}")
        return fb

    post_id = fb.get("post_id")
    comment_target = fb.get("video_id") or post_id   # reels only accept comments on the video id
    clubs = resolve_clubs(manifest.get("title", ""))
    names = [CLUB_BRAND.get(c, {}).get("name", c.title()) for c in clubs[:2]]
    pred = manifest.get("prediction", "")
    if pred:
        # our call, stated openly — the first comment IS the debate starter
        c1 = f"🔮 {pred}. Agree or are we dreaming? Drop YOUR scoreline 👇⚽"
    elif len(names) == 2:
        c1 = (f"🔥 {names[0]} vs {names[1]} — drop your score prediction below! "
              f"Best prediction gets a shoutout 👇⚽")
    elif names:
        c1 = f"🔥 {names[0]} fans — where are you?! Rate this squad's chances below 👇⚽"
    else:
        c1 = "🔥 PSL family — what's your take? Drop it below 👇⚽"
    c2 = ("📲 Follow GENESIS NEWS for lineups before kickoff, full-time results "
          "and every big PSL story — Chiefs, Pirates, Sundowns and more. 🇿🇦⚽")
    c3 = ("▶️ More PSL videos on our YouTube channel — subscribe: "
          "https://www.youtube.com/@GenesisNewsPSL")

    for msg in (c1, c2, c3):
        await post_comment(comment_target, msg, NICHE)

    # YouTube Shorts — the rebranded Genesis News channel (@GenesisNewsPSL).
    # Guarded on the channel token so a missing token can never mispost.
    yt_id = ""
    if (Path("tokens") / f"youtube_token_{NICHE}.json").exists():
        try:
            from modules.uploader_youtube import upload_to_youtube
            yt = await upload_to_youtube(
                video_path=manifest["video_path"],
                title=manifest["title"],
                description=manifest["description"],
                tags=manifest.get("tags", []),
                niche=NICHE,
                thumbnail_path=manifest.get("thumb_path"),
                is_short=True,
                srt_path=manifest.get("srt_path"),
            )
            yt_id = (yt or {}).get("video_id", "")
            _log(f"YouTube: {yt.get('status')} {yt_id}")
        except Exception as e:
            _log(f"YouTube upload failed: {e}")
    else:
        _log("YouTube skipped — no channel token")

    manifest["uploaded"] = True
    manifest["fb_post_id"] = post_id
    manifest["youtube_id"] = yt_id
    mp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(f"posted + 2 comments: {post_id}")
    return fb


if __name__ == "__main__":
    os.environ.setdefault("FORCE_STILLS_ONLY", "true")
    os.environ.setdefault("DISABLE_RUNPOD_WAN", "true")
    asyncio.run(main())
