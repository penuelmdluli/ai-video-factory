"""
The XI with holes in it — let the supporters pick the rest.

Owner call 2026-08-26: "post a post with missing players on the lineup, ask the
support to just who should fill it".

This is the cheapest engagement on the page and the most honest. A predicted XI
invites people to disagree with a finished opinion, which some will not bother
to do. A team sheet with three empty shirts asks a question that has no wrong
answer, and the only way to answer it is to comment. The gaps are left in the
positions people actually argue about — never the goalkeeper, never a shirt we
have already made a big call on.

A photo post, not a reel: it is a question, and a still image is read in the
half second it takes to scroll past.

    python build_fill_the_gaps.py --club chiefs
    python build_fill_the_gaps.py --club chiefs --post --gaps 3
"""
import argparse
import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
NICHE = "sa_pulse"


def _log(m):
    print(f"[Gaps] {m}", flush=True)


def _surname(entry: str) -> str:
    parts = str(entry).split(None, 1)
    return (parts[1] if len(parts) > 1 else str(entry)).strip()


def pick_gaps(xi: list[str], formation: str, n: int = 3) -> list[int]:
    """Which shirts to leave empty.

    Never the keeper — "who should be in goal" is a different post and a
    weaker one, because most fans have the same answer. The gaps are spread
    across different lines so the question is about the whole side rather
    than one argument, and the attacking end is always represented because
    that is where this page's comments actually come from.
    """
    parts = [int(x) for x in str(formation).split("-") if x.strip().isdigit()]
    if not parts:
        parts = [4, 3, 3]
    lines, i = [], 1                       # index 0 is the keeper
    for count in parts:
        lines.append(list(range(i, min(11, i + count))))
        i += count

    rng = random.Random(datetime.now().strftime("%Y%m%d"))
    gaps = []
    # one from the forward line first, then spread backwards
    for line in reversed(lines):
        if len(gaps) >= n or not line:
            continue
        gaps.append(rng.choice([k for k in line if k not in gaps]))
    # top up from anywhere outfield if the shape did not give us enough
    pool = [k for k in range(1, len(xi)) if k not in gaps]
    rng.shuffle(pool)
    while len(gaps) < n and pool:
        gaps.append(pool.pop())
    return sorted(gaps[:n])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--gaps", type=int, default=0,
                    help="0 = let the mode decide")
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "fill", "replace", "start"],
                    help="which question to ask; auto rotates by day")
    ap.add_argument("--post", action="store_true",
                    help="post the card to Facebook")
    ap.add_argument("--skip-facebook", dest="skip_facebook",
                    action="store_true",
                    help="the card is already on the page — video surfaces only")
    ap.add_argument("--as-reel", dest="as_reel", action="store_true",
                    help="post the video to Facebook as a reel instead of "
                         "posting the still card")
    ap.add_argument("--video", action="store_true",
                    help="also render a vertical short for YouTube and TikTok")
    a = ap.parse_args()

    from modules.psl_fixtures import next_fixture
    from modules.club_brand import CLUB_BRAND

    fx = await next_fixture(a.club)
    if not fx:
        _log("no upcoming fixture")
        return 1
    fid = str(fx.get("id", ""))
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
    home = fx["home_key"] == a.club
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_name = CLUB_BRAND.get(opp_key, {}).get("name",
                                               opp_key.replace("_", " ").title())

    # Build the holes into the side we have ALREADY published for this
    # fixture, so the page is asking about one team rather than inventing a
    # second one an hour after the first.
    xi, formation, pred = [], "4-3-3", {}
    try:
        pp = ROOT / "data" / "xi_predictions.json"
        pred = (json.loads(pp.read_text(encoding="utf-8")).get(fid) or {}) \
            if pp.exists() else {}
        xi, formation = pred.get("xi") or [], pred.get("formation") or formation
    except Exception:
        pass
    if not xi:
        from build_lineup_video import pick_xi_real
        xi, real_f, _prov, _bench = await pick_xi_real(a.club)
        formation = real_f or formation
    if len(xi) < 11:
        _log("no usable XI")
        return 1

    # WHICH QUESTION. Owner call 2026-08-26: ask consistently, and vary it —
    # who fills, who replaces, who starts. One format asked the same way every
    # time stops being a question and becomes wallpaper, and the three are not
    # interchangeable: "who fills three empty shirts" is a team-building
    # question, "who replaces him" is about one man, and "who starts here" is
    # a straight two-way argument, which is the one that historically draws
    # the most comments on this page.
    MODES = ["fill", "replace", "start"]
    mode = a.mode
    if mode == "auto":
        mode = MODES[datetime.now().timetuple().tm_yday % len(MODES)]
    n_gaps = a.gaps or (3 if mode == "fill" else 1)

    gaps = pick_gaps(xi, formation, n_gaps)
    missing = [_surname(xi[g]) for g in gaps]
    _log(f"mode: {mode.upper()} ({n_gaps} shirt{'s' if n_gaps != 1 else ''})")

    # two names to argue between, for the straight two-way question
    rivals = []
    if mode == "start":
        try:
            from modules.rotation import coldness
            cold = await coldness(a.club)
        except Exception:
            cold = {}
        pool = [b for b in (pred.get("bench") or []) if str(b).strip()]
        if not pool:
            from build_lineup_video import pick_xi_real
            _x, _f, _p, _b = await pick_xi_real(a.club)
            pool = _b or []
        pool.sort(key=lambda b: -cold.get(_surname(b).lower(), 0))
        rivals = [missing[0]] + [_surname(b) for b in pool[:1]]
        rivals = [r for r in rivals if r]
    holed = [("" if i in gaps else p) for i, p in enumerate(xi)]
    _log(f"gaps at {gaps} — holding out {', '.join(missing)}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"gaps_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    from modules.lineup_card import make_lineup_card
    card = work / "gaps.png"
    kickoff = " · ".join(x for x in (fx.get("kickoff_sast", ""),
                                     fx.get("venue", "")) if x)
    p = make_lineup_card(card, club=a.club, players=holed, opponent=opp_key,
                         formation=formation, kickoff=kickoff,
                         competition="Betway Premiership", predicted=True,
                         pending=True,   # the empty shirts must be VISIBLE
                         badge={"fill": "YOU PICK THE REST",
                                "replace": "WHO REPLACES HIM?",
                                "start": "WHO STARTS HERE?"}[mode])
    if not p:
        _log("card failed")
        return 1
    _log(f"card: {card}")

    where = f"{'vs' if home else 'away to'} {opp_name}"
    tail = (f"{chr(10)}{chr(10)}#KaizerChiefs #Amakhosi #Khosi4Life #PSL "
            f"#BetwayPremiership")
    if mode == "fill":
        caption = (
            f"YOU PICK THE REST. 👇{chr(10)}{chr(10)}"
            f"{len(gaps)} shirts are empty in our {club_name} side {where} — "
            f"{formation}, {kickoff}.{chr(10)}{chr(10)}"
            f"Who fills them? Drop the names in the comments and we will read "
            f"the most-backed eleven back to you before kickoff." + tail)
        say = (f"{len(gaps)} shirts are empty in our {club_name} eleven "
               f"{where} tonight. Who fills them? Tell us in the comments, "
               f"and we will read the most backed eleven back to you before "
               f"kick off.")
    elif mode == "replace":
        who = missing[0]
        caption = (
            f"WHO REPLACES {who.upper()}? 👇{chr(10)}{chr(10)}"
            f"Take him out of our {club_name} side {where} — "
            f"{formation}, {kickoff} — and the shirt is yours to fill."
            f"{chr(10)}{chr(10)}"
            f"One name in the comments. We will count them." + tail)
        say = (f"Take {who} out of our {club_name} eleven {where} tonight. "
               f"Who replaces him? One name in the comments. We will count "
               f"them.")
    else:
        pair = " or ".join(r.upper() for r in rivals) if len(rivals) > 1             else missing[0].upper()
        caption = (
            f"WHO STARTS HERE? {pair} 👇{chr(10)}{chr(10)}"
            f"One shirt, two names, {club_name} {where} — "
            f"{formation}, {kickoff}.{chr(10)}{chr(10)}"
            f"Pick one and say why. No fence-sitting." + tail)
        say = (f"One shirt, two names. "
               + (f"{rivals[0]}, or {rivals[1]}? " if len(rivals) > 1
                  else f"Who starts in this shirt? ")
               + f"For {club_name} {where} tonight. Pick one in the comments, "
                 f"and say why.")

    (work / "post_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "card": str(card), "caption": caption,
         "gaps": gaps, "withheld": missing, "formation": formation,
         "mode": mode, "rivals": rivals,
         "fixture": fid, "built_at": datetime.now().isoformat()},
        indent=2, ensure_ascii=False), encoding="utf-8")

    # ── the short, for the surfaces that cannot take a still ────────────
    # Facebook gets the card, because the question is read in the half second
    # it takes to scroll past. YouTube and TikTok have no photo surface worth
    # posting to, so the same question becomes a short — the empty shirts
    # carrying the live loader they already use in the reveal, which is
    # exactly the "we are waiting on you" the caption is asking for.
    video = None
    if a.video:
        from build_lineup_video import _live_loader
        from modules.motion_kit import _render, DARK, attach_voice
        from modules.club_brand import CLUB_BRAND as _CB
        from PIL import Image
        accent = tuple(_CB.get(a.club, {}).get("colors", {})
                       .get("primary", (255, 193, 7)))
        base_card = Image.open(card).convert("RGB")
        W, H = 1080, 1920
        cy = (H - base_card.height) // 2

        dur = max(13.0, len(say.split()) / 2.8 + 3.0)

        def _candidates(img, t):
            """The contested shirt flicks between the two names.

            A spinning loader says "a name is coming". For a straight two-way
            argument the name is NOT coming — both are already on the table,
            and the shirt belongs to whichever one the viewer picks. So it
            alternates, with the one currently showing lit and the other
            ghosted underneath.
            """
            from PIL import ImageDraw
            from modules.tactics_motion import base_positions, _font
            try:
                spots, _ = base_positions(formation, False)
            except Exception:
                return img
            d = ImageDraw.Draw(img, "RGBA")
            for i in gaps:
                if i >= len(spots):
                    continue
                x, y = spots[i]
                y -= 26
                turn = int(t * 1.15) % 2          # ~0.9s each
                shown = rivals[turn % len(rivals)].upper()
                other = rivals[(turn + 1) % len(rivals)].upper()
                r = 37
                from modules.lineup_card import _jersey
                from modules.club_brand import CLUB_BRAND as _CB2
                trim = tuple(_CB2.get(a.club, {}).get("colors", {})
                             .get("secondary", (10, 10, 10)))
                # the contested shirt is a SHIRT, same as every other one on
                # the card — with a question mark where the number goes
                _jersey(d, x, y, r, accent, trim, "?", _font(34),
                        ring=(214, 40, 48))
                nf = _font(27)
                nw = d.textlength(shown, font=nf)
                d.rounded_rectangle([x - nw / 2 - 14, y + r + 6,
                                     x + nw / 2 + 14, y + r + 44],
                                    radius=10, fill=(16, 18, 22))
                d.text((x - nw / 2, y + r + 11), shown, font=nf,
                       fill=(255, 255, 255))
                gf = _font(21)
                gw = d.textlength(other, font=gf)
                d.text((x - gw / 2, y + r + 52), other, font=gf,
                       fill=(120, 126, 136, 190))
            return img

        def _f(t):
            base = Image.new("RGB", (W, H), DARK)
            img = base_card.copy()
            if mode == "start" and len(rivals) > 1:
                img = _candidates(img, t)
            else:
                img = _live_loader(img, t, formation, False, 0, accent,
                                   indices=gaps)
            base.paste(img, (0, cy))
            return base

        silent = work / "gaps_silent.mp4"
        _render(_f, silent, duration=dur, fps=24)
        voiced = await attach_voice(silent, say, work / "gaps_voiced.mp4")
        from modules.music_bed import add_bed
        video = add_bed(voiced, work / "gaps_final.mp4", NICHE, dur, log=_log)
        _log(f"short: {video} ({dur:.0f}s)")

    if a.post and not a.skip_facebook and not a.as_reel:
        from modules.uploader_facebook import upload_photo, post_comment
        r = await upload_photo(str(card), caption, NICHE)
        _log(f"posted: {(r or {}).get('status')} {(r or {}).get('post_id', '')}")
        if (r or {}).get("status") == "uploaded":
            # Seed the thread. An empty comment box is a harder ask than one
            # that already has a name in it to argue with.
            target = r.get("photo_id") or r.get("post_id")
            try:
                await post_comment(
                    target,
                    "Reply with your names for the empty shirts — position "
                    "first, e.g. \"RW: Duba\"." + chr(10) +
                    "▶️ More on YouTube: "
                    "https://www.youtube.com/@GenesisNewsPSL", NICHE)
                _log("first comment seeded")
            except Exception as e:
                _log(f"first comment failed: {str(e)[:90]}")

            # Remember WHICH post asked the question.
            #
            # Every one of these captions promises "we will read the most
            # backed eleven back to you before kickoff" and "we will count
            # them". Nothing in the repo ever did - no module reads these
            # comments, and the manifest is written before the post exists, so
            # the post id was logged to the console and thrown away. The page
            # has been making a promise to supporters on every gaps post and
            # keeping it zero times. build_gaps_verdict.py answers it, and it
            # needs this id to find the answers.
            try:
                from modules.gaps_ledger import record_asked
                record_asked(a.club, target, fid, gaps, missing, xi,
                             formation, mode, kickoff)
            except Exception as e:
                _log(f"gaps ledger not updated: {str(e)[:90]}")

    # A two-way argument is better WATCHED than read — the shirt flicking
    # between the names is the question. The other two are better read: a
    # still card is taken in during the half second it takes to scroll past.
    # The router does not have to know any of this, because the builder picks
    # the mode, so the builder picks the shape that mode wants.
    # Owner call 2026-08-28: "we did not post a video". Only the two-way
    # question went out as a reel; fill and replace put a still card on
    # Facebook on the theory that a question is read in half a second. The
    # page's own numbers say otherwise — today's reels ran into the thousands
    # of views while the fill card sat on zero. Facebook surfaces reels and
    # buries photos, so every fan question goes out as video there now.
    if a.video:
        a.as_reel = True

    if a.post and a.as_reel and video and Path(video).exists():
        # One question, one piece of media, everywhere. Used when the ask is
        # better watched than read — a two-way argument wants the shirt to
        # flick between the names, which a still cannot do.
        from modules.publish_reel import publish
        r = await publish(video, ({"fill": f"YOU PICK THE REST — {club_name} XI",
                                   "replace": f"WHO REPLACES {missing[0].upper()}?",
                                   "start": f"WHO STARTS HERE? {club_name}"}[mode]
                                  + f" {where}")[:95],
                          caption, str(card), niche=NICHE,
                          tags=["KaizerChiefs", "Amakhosi", "PSL", "TeamNews",
                                "BetwayPremiership"])
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
        return 0

    if a.post and video and Path(video).exists():
        title = (f"YOU PICK THE REST — {club_name} XI "
                 f"{'vs' if home else 'away to'} {opp_name}")
        tags = ["KaizerChiefs", "Amakhosi", "PSL", "TeamNews",
                "BetwayPremiership"]
        # Facebook already has the card. Posting the short there too would
        # be the same question twice on one feed.
        if (ROOT / "tokens" / f"youtube_token_{NICHE}.json").exists():
            try:
                from modules.uploader_youtube import upload_to_youtube
                yt = await upload_to_youtube(
                    video_path=str(video), title=title[:95],
                    description=caption, tags=tags, niche=NICHE,
                    thumbnail_path=str(card), is_short=True)
                vid = (yt or {}).get("video_id", "")
                _log(f"YouTube: {(yt or {}).get('status')} {vid}")
                if vid:
                    from modules.playlists import add_youtube
                    add_youtube(vid, shorts=True)
            except Exception as e:
                _log(f"YouTube failed: {str(e)[:120]}")
        else:
            _log("YouTube skipped — no channel token")
        try:
            from modules.uploader_tiktok import upload_to_tiktok
            tt = await upload_to_tiktok(video_path=str(video),
                                        description=caption[:150],
                                        hashtags=tags[:5], niche=NICHE)
            _log(f"TikTok: {(tt or {}).get('status')}")
        except Exception as e:
            _log(f"TikTok failed: {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
