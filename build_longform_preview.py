"""
Three-minute matchday preview — proper 16:9 YouTube, not a Short.

Owner call 2026-08-25: a long-form build off the line-up and analysis, showing
the movement, the expectation, the bench, and a real selection argument.

Why 16:9 and not the vertical card letterboxed: YouTube search and suggested
serve long-form horizontally, and a 9:16 clip pillarboxed into a 16:9 frame
wastes two-thirds of the screen. The layout is broadcast-shaped instead — pitch
on the left, a panel on the right that changes with the segment, so there is
always something to read while the shape moves.

WHAT IS REAL, and therefore what this is allowed to say:
  · the XI, the bench and the formation      -> the actual ESPN team sheet
  · the fixture, venue and kickoff           -> the fixture feed
  · league position, points, games played    -> the standings cache
Nothing else exists in this pipeline. No goals, no assists, no minutes, no
ratings. Three minutes is long enough that the temptation to pad with invented
numbers is real — do not. The segments below are sized so the honest material
fills the runtime.

    python build_longform_preview.py --club chiefs
    python build_longform_preview.py --club chiefs --post
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
W, H = 1920, 1080
PITCH_W = 980                      # left column
PANEL_X = PITCH_W + 40             # right column origin


def _log(m):
    print(f"[Longform] {m}", flush=True)


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


def _ord(n):
    """2 -> 2nd. It was printing "2th" because the suffix was hard-coded."""
    try:
        n = int(n)
    except Exception:
        return str(n)
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def standings(club: str):
    """(rank, points, played) for a club, or None."""
    try:
        rows = json.loads((ROOT / "data" / "psl_standings_cache.json")
                          .read_text(encoding="utf-8")).get("rows", [])
    except Exception:
        return None
    for r in rows:
        if r.get("team_key") == club:
            return r.get("rank"), r.get("points"), r.get("played")
    return None


def pitch_positions(formation: str, phase: str):
    """Player coords inside the LEFT column, mirroring tactics_motion."""
    from modules.tactics_motion import shape
    pts = shape(formation, phase, bench=False)      # 1080x1350 space
    out = []
    for x, y in pts:
        # scale that portrait pitch into the 16:9 left column
        nx = 40 + x * (PITCH_W - 80) / 1080
        ny = 90 + (y - 420) * (H - 190) / (1230 - 420)
        out.append([nx, ny])
    return out


def draw_pitch(d, accent):
    x1, y1, x2, y2 = 40, 90, PITCH_W - 40, H - 60
    d.rounded_rectangle([x1, y1, x2, y2], radius=20, fill=(18, 92, 48))
    for i, yy in enumerate(range(int(y1), int(y2), 62)):
        if i % 2 == 0:
            d.rectangle([x1 + 4, yy, x2 - 4, min(yy + 62, y2 - 4)],
                        fill=(20, 100, 53))
    d.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=14,
                        outline=(255, 255, 255), width=3)
    cy = (y1 + y2) // 2
    d.line([x1 + 14, cy, x2 - 14, cy], fill=(255, 255, 255), width=3)
    d.ellipse([(x1 + x2) // 2 - 84, cy - 84, (x1 + x2) // 2 + 84, cy + 84],
              outline=(255, 255, 255), width=3)
    for yy in (y1 + 14, y2 - 14 - 120):
        d.rectangle([(x1 + x2) // 2 - 150, yy, (x1 + x2) // 2 + 150, yy + 120],
                    outline=(255, 255, 255), width=3)


def frame_for(seg, t_in, ctx):
    """Render one frame for segment `seg` at t_in seconds into it."""
    from PIL import Image, ImageDraw
    from modules.tactics_motion import _ease, _arrow, effective_formation

    accent = ctx["accent"]
    im = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(im, "RGBA")

    # ── header bar ──
    d.rectangle([0, 0, W, 92], fill=accent)
    # This is a Kaizer Chiefs page — the crest belongs in frame at all times,
    # not just on the cover. It was missing from the long-form entirely.
    hx = 24
    try:
        from modules.club_brand import official_badge
        bp = official_badge(ctx["club"])
        if bp:
            bi = Image.open(bp).convert("RGBA")
            r = 76 / max(bi.width, bi.height)
            bi = bi.resize((int(bi.width * r), int(bi.height * r)))
            im.paste(bi, (hx, 8), bi)
            hx += bi.width + 18
    except Exception:
        pass
    gf = _font(38)
    d.text((hx, 12), "GENESIS NEWS", font=gf, fill=(20, 20, 20))
    # measured, not guessed — "GENESIS NEWS" was running straight through it
    d.text((hx, 56), "MATCHDAY PREVIEW", font=_font(22), fill=(80, 68, 34))
    hdr = ctx["fixture_line"]
    hf = _font(26)
    d.text((W - d.textlength(hdr, font=hf) - 36, 33), hdr, font=hf,
           fill=(30, 28, 20))

    draw_pitch(d, accent)

    # ── which shape, and how many men are showing ──
    phase, reveal = seg["phase"], seg.get("reveal", 11)
    if seg.get("morph"):
        a = pitch_positions(ctx["formation"], seg["morph"][0])
        b = pitch_positions(ctx["formation"], seg["morph"][1])
        u = _ease(min(1.0, t_in / max(0.001, seg["dur"] * 0.6)))
        pos = [[a[i][0] + (b[i][0] - a[i][0]) * u,
                a[i][1] + (b[i][1] - a[i][1]) * u] for i in range(len(a))]
        fade = 1.0 - abs(u * 2 - 1)
        if fade > 0.05:
            for i in range(len(a)):
                _arrow(d, a[i][0], a[i][1], b[i][0], b[i][1],
                       (255, 255, 255, int(180 * fade)), width=max(3, int(6 * fade)))
        shape_txt = effective_formation(ctx["formation"], seg["morph"][1])
    else:
        pos = pitch_positions(ctx["formation"], phase)
        shape_txt = effective_formation(ctx["formation"], phase)

    for i, (x, y) in enumerate(pos):
        if i >= reveal:
            continue
        rr = 30
        is_call = i in ctx["marks"] and seg.get("show_calls", True)
        ring = (214, 40, 48) if is_call else (255, 255, 255)
        if is_call:
            d.ellipse([x - rr - 6, y - rr - 6, x + rr + 6, y + rr + 6],
                      outline=ring, width=4)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=accent, outline=ring, width=3)
        raw = ctx["xi"][i] if i < len(ctx["xi"]) else ""
        parts = str(raw).split(None, 1)
        num = parts[0] if parts and parts[0].isdigit() else ""
        nm = (parts[1] if len(parts) > 1 else raw).upper()
        if num:
            nw = d.textlength(num, font=_font(23))
            d.text((x - nw / 2, y - 12), num, font=_font(23), fill=(20, 20, 20))
        if nm:
            # Real spacing is (pitch width)/(men+1), not /men — for a back
            # five that is 150px, not 180. Sizing against the wrong number left
            # MOLOISANE and MACHEKE half-covered by the pill next to them.
            gap = (PITCH_W - 80) / (max(3, ctx["row_max"]) + 1)
            f = _font(19)
            while d.textlength(nm, font=f) > gap - 34 and f.size > 11:
                f = _font(f.size - 1)
            w = d.textlength(nm, font=f)
            d.rounded_rectangle([x - w / 2 - 6, y + rr + 4, x + w / 2 + 6, y + rr + 30],
                                radius=7, fill=(8, 10, 14, 215))
            d.text((x - w / 2, y + rr + 8), nm, font=f, fill=(255, 255, 255))

    # shape badge, bottom-left of the pitch
    bf = _font(26)
    bw = d.textlength(shape_txt, font=bf)
    d.rounded_rectangle([60, H - 130, 60 + bw + 34, H - 86], radius=10, fill=accent)
    d.text((77, H - 122), shape_txt, font=bf, fill=(20, 20, 20))

    # ── right panel ──
    d.rounded_rectangle([PANEL_X, 100, W - 36, H - 60], radius=18, fill=(20, 24, 30))
    d.text((PANEL_X + 28, 124), seg["panel_title"], font=_font(34), fill=accent)
    y = 186
    for line in seg["panel_lines"]:
        style, txt = (line if isinstance(line, tuple) else ("body", line))
        if style == "head":
            d.text((PANEL_X + 28, y), txt, font=_font(27), fill=(150, 158, 168))
            y += 40
        elif style == "big":
            d.text((PANEL_X + 28, y), txt, font=_font(40), fill=(255, 255, 255))
            y += 56
        elif style == "call":
            d.rounded_rectangle([PANEL_X + 22, y - 6, W - 60, y + 44], radius=10,
                                fill=(48, 20, 24))
            d.text((PANEL_X + 34, y + 2), txt, font=_font(26), fill=(240, 120, 124))
            y += 60
        else:
            f = _font(25, False)
            while d.textlength(txt, font=f) > (W - 60) - (PANEL_X + 28) and f.size > 15:
                f = _font(f.size - 1, False)
            d.text((PANEL_X + 28, y), txt, font=f, fill=(214, 220, 228))
            y += 40
    return im


def segments(ctx):
    """The running order. Each dict is one on-screen chapter."""
    xi, bench, calls = ctx["xi"], ctx["bench"], ctx["calls"]
    st, opp_st = ctx["standings"], ctx["opp_standings"]
    segs = []

    log_lines = []
    if st:
        log_lines = [("head", "IN THE LEAGUE"),
                     ("big", f"{ctx['club_name']} — {_ord(st[0])}, {st[1]} pts"),
                     f"Played {st[2]}."]
        if opp_st:
            log_lines.append(f"{ctx['opp_name']} — {_ord(opp_st[0])} on {opp_st[1]} "
                             f"points from {opp_st[2]}.")
    segs.append({"phase": "base", "reveal": 0, "dur": 14,
                 "panel_title": "THE FIXTURE",
                 "panel_lines": [("big", ctx["opp_name"]), ctx["kickoff"],
                                 ""] + log_lines})

    per = 3.4
    for n in range(1, len(xi) + 1):
        segs.append({"phase": "base", "reveal": n, "dur": per,
                     "panel_title": "THE ELEVEN",
                     "panel_lines": [("head", ctx["provenance"].upper())]
                     + [("big" if i == n - 1 else "body",
                         p.split(None, 1)[-1].upper())
                        for i, p in enumerate(xi[:n])][-7:]})

    shape_panel = [("head", "WITHOUT THE BALL"), ("big", ctx["formation"]),
                   "Two banks, compact and narrow.",
                   "The wing-backs tuck in to make a five."]
    segs.append({"phase": "defend", "morph": ("base", "defend"), "dur": 26,
                 "panel_title": "DEFENSIVE SHAPE", "panel_lines": shape_panel})

    atk = [("head", "WITH THE BALL"),
           ("big", "3-5-2"),
           "The wing-backs push on and the block becomes a three.",
           "One centre-half steps into midfield to screen."]
    segs.append({"phase": "attack", "morph": ("defend", "attack"), "dur": 28,
                 "panel_title": "ATTACKING SHAPE", "panel_lines": atk})

    if calls:
        cl = [("head", "OUR TWO BIG CALLS")]
        for c in calls:
            cl.append(("call", f"{c['in'].split(None,1)[-1]} IN for "
                               f"{c['out'].split(None,1)[-1]}"))
        cl.append("Marked in red on the pitch.")
        cl.append("Disagree? That is the point — tell us below.")
        segs.append({"phase": "base", "morph": ("attack", "base"), "dur": 26,
                     "panel_title": "THE ARGUMENT", "panel_lines": cl})

    if bench:
        segs.append({"phase": "base", "dur": 20, "panel_title": "THE BENCH",
                     "panel_lines": [("head", "NAMED AS COVER")]
                     + [b.upper() for b in bench[:7]]})

    segs.append({"phase": "base", "dur": 14, "panel_title": "OVER TO YOU",
                 "panel_lines": [("head", "GENESIS NEWS"),
                                 "Who starts? Who sits?",
                                 "Comment your XI.",
                                 "",
                                 "Subscribe for the team sheets",
                                 "the moment they land."]})
    return segs


def narration(ctx):
    xi, bench, calls = ctx["xi"], ctx["bench"], ctx["calls"]
    st, opp_st = ctx["standings"], ctx["opp_standings"]
    L = [f"{ctx['club_name']} are back in action.",
         f"{ctx['kickoff']}, against {ctx['opp_name']}."]
    if st:
        L.append(f"{ctx['club_name']} sit {_ord(st[0])} on {st[1]} points from "
                 f"{st[2]} games.")
    if opp_st:
        L.append(f"{ctx['opp_name']} are {_ord(opp_st[0])} on {opp_st[1]}.")
    L.append(f"Here is the eleven Genesis News expects.")
    if ctx["provenance"]:
        L.append(f"It starts from the side that started {ctx['provenance']}.")
    for p in xi:
        L.append(p.split(None, 1)[-1] + ".")
    L += ["Without the ball this is a back five.",
          "Two compact banks, the wing-backs tucked in, very little space "
          "between the lines.",
          "With the ball it becomes a three at the back.",
          "Both wing-backs push high and wide, and one centre-half steps into "
          "midfield to screen behind them.",
          "That is the shape this side lives in."]
    if calls:
        L.append("And we are making two big calls.")
        for c in calls:
            L.append(f"{c['in'].split(None,1)[-1]} comes in for "
                     f"{c['out'].split(None,1)[-1]}.")
        L.append("They are marked in red. Disagree with us in the comments.")
    if bench:
        L.append("On the bench: "
                 + ", ".join(b.split(None, 1)[-1] for b in bench[:6]) + ".")
    L += ["We do not have shot counts or ratings, so we are not going to "
          "pretend we do.",
          "That is the team sheet, the shape and our call.",
          "The argument is yours. Comment your eleven.",
          "Subscribe to Genesis News — we post the team sheets the moment "
          "they land."]
    return " ".join(L)


def render(segs, ctx, out):
    from modules.motion_kit import _render
    total = sum(s["dur"] for s in segs)
    bounds, acc = [], 0.0
    for s in segs:
        bounds.append((acc, acc + s["dur"], s))
        acc += s["dur"]

    def frame_fn(t):
        for a, b, s in bounds:
            if t < b:
                return frame_for(s, t - a, ctx)
        return frame_for(bounds[-1][2], bounds[-1][2]["dur"], ctx)

    _render(frame_fn, out, duration=total, fps=24)
    return total


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_longform_preview.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    from modules.club_brand import CLUB_BRAND
    from modules.psl_fixtures import next_fixture, last_lineup
    from modules.injuries import filter_xi
    from modules.bold_calls import pick as pick_calls, apply as apply_calls

    fx = await next_fixture(a.club)
    if not fx:
        _log("no upcoming fixture — refusing to preview a played game")
        return 1
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]

    sheet = await last_lineup(a.club)
    if not sheet:
        _log("no published team sheet to build from")
        return 1
    xi, bench = sheet["players"], sheet.get("bench", [])
    xi, swaps = filter_xi(a.club, xi, bench)
    for o, i, why in swaps:
        _log(f"INJURY: {o} out ({why}) — {i or 'no cover'} in")
    bench = [b for b in bench if b not in xi]
    calls = pick_calls(a.club, xi, bench, n=2)
    marks = []
    if calls:
        xi, marks = apply_calls(xi, calls)
        for c in calls:
            _log(f"BIG CALL: {c['in']} in for {c['out']}")
        bench = [b for b in bench if b not in xi]

    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_name = CLUB_BRAND.get(opp_key, {}).get(
        "name", opp_key.replace("_", " ").title())
    ctx = {
        "club_name": club_name, "opp_name": opp_name,
        "accent": tuple(CLUB_BRAND.get(a.club, {}).get("colors", {})
                        .get("primary", (255, 193, 7))),
        "formation": sheet["formation"], "xi": xi, "bench": bench,
        "calls": calls, "marks": marks,
        "kickoff": " · ".join(x for x in (fx.get("kickoff_sast", ""),
                                          fx.get("venue", "")) if x),
        "fixture_line": f"{fx.get('home')} v {fx.get('away')}",
        "provenance": f"v {sheet['match'].split(' v ')[-1]} ({sheet['date']})",
        "standings": standings(a.club), "opp_standings": standings(opp_key),
        "club": a.club,
        "row_max": max([1] + [int(v) for v in sheet["formation"].split("-")
                              if v.strip().isdigit()]),
    }
    _log(f"{club_name} v {opp_name} | {ctx['formation']} | XI {len(xi)} | "
         f"bench {len(bench)} | calls {len(calls)}")

    segs = segments(ctx)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"longform_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    silent = work / "preview_silent.mp4"
    total = render(segs, ctx, silent)
    _log(f"video: {total:.0f}s across {len(segs)} segments (16:9 {W}x{H})")

    text = narration(ctx)
    _log(f"narration: {len(text.split())} words")
    from modules.motion_kit import attach_voice
    final = await attach_voice(silent, text, work / "final.mp4")

    cover = work / "cover.jpg"
    from PIL import Image
    frame_for(segs[len(segs) // 2], 1.0, ctx).save(cover, quality=94)

    title = f"{club_name} vs {opp_name}: Predicted XI, Tactics & Two Big Calls"
    desc = (f"{club_name} face {opp_name} — {ctx['kickoff']}.\n\n"
            f"Predicted XI, the shape with and without the ball, the bench, "
            f"and our two big calls.\n\n"
            f"Based on the side that started {ctx['provenance']}.\n"
            f"Genesis News opinion — not the official team sheet.\n\n"
            f"#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")
    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "longform", "is_short": False,
         "video_path": str(final), "thumbnail": str(cover),
         "title": title, "description": desc,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.uploader_youtube import upload_to_youtube
        yt = await upload_to_youtube(
            video_path=str(final), title=title[:95], description=desc,
            tags=["PSL", "Kaizer Chiefs", "Amakhosi", "Predicted XI",
                  "Betway Premiership", "South African football"],
            niche=NICHE, thumbnail_path=str(cover), is_short=False)
        _log(f"YouTube: {(yt or {}).get('status')} {(yt or {}).get('video_id','')}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
