"""
Character images for the dancing reels — unique every time, same standard every time.

Owner call 2026-08-30: "we need 3 or 4 templates which can be used to create
different images ... make sure we always have a unique dance yet we have a
standard of posting, and able to rotate so it is not boring."

Those two things pull against each other, and the profile's own numbers say
which way to resolve the tension. The reels that carry this page — 2.7M, then
1.2M three times — all star the SAME small cast. Zinhle and Zintle work
because people recognise them; a new face every post is a stranger every post,
and a stranger cannot have a running joke. So novelty must NOT come from new
characters.

It comes from the combination instead:

    CAST      fixed and locked. Each character's physical description never
              changes, word for word, so the same person shows up on Friday as
              showed up on Tuesday. This is the standard.
    TEMPLATE  the shot structure, lifted from what actually worked — the
              walk-in, the stand-still, the two-hander, the crowd reaction.
    SETTING   where it happens. This is where South Africa does the work:
              a Saturday car wash, a braai, a taxi rank, church.

Five characters x four templates x eight settings is 160 combinations. At
three posts a day that is roughly seven weeks before anything repeats — and
the ledger below refuses to repeat one until every combination has been used,
so it is fresh by construction rather than by luck. Same engine as
modules/lineup_variety.py, which was built for exactly this problem on the
PSL side.

Images are generated on Cloudflare Workers AI, deliberately NOT RunPod: the
RunPod credit is reserved for motion transfer (see modules/runpod_guard.py),
and stills are the cheap half of this pipeline.

MODEL CHOICE, measured 2026-08-30 on this account:

    stable-diffusion-xl-lightning   768x1344 portrait, full body head-to-feet,
                                    ~3.1s. THE ONE WE USE.
    flux-1-schnell                  visibly more photoreal, ~2.8s, but REJECTS
                                    width/height - it is locked to 1024x1024
                                    square and frames to the chest.

Motion transfer needs the whole body in portrait or it has no legs to drive,
so geometry beats realism here and SDXL wins. The cost of that choice is that
SDXL drifts on appearance when a description is loose — the first test turned
a South African grandfather noticeably light-skinned — which is exactly why
every cast entry below spells appearance out rather than relying on the model
to infer it.
"""
import base64
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "dance_variety.json"
OUT_DIR = ROOT / "assets" / "dance_cast"

# MODEL — measured on this account 2026-08-30, same prompt, same size.
#
#   leonardo/lucid-origin           photographic, gritty, documentary. ~5.4s,
#                                   750KB. DEFAULT.
#   leonardo/phoenix-1.0            equally clean, brighter and more staged,
#                                   best at holding the SETTING. ~3.8s, 751KB.
#   bytedance/sdxl-lightning        what this started on. ~3.1s but only ~200KB
#                                   of detail: soft, smeared, visibly rendered.
#                                   Owner's verdict was "not clean or clear",
#                                   and he was right - it was the wrong model,
#                                   not the wrong prompt.
#   black-forest-labs/flux-1-schnell more photoreal than SDXL but REJECTS
#                                   width/height - locked to 1024 square, and
#                                   a square crop loses the legs.
#   black-forest-labs/flux-2-dev    requires a multipart request this client
#                                   does not speak; revisit if needed.
#
# The jump from SDXL Lightning to Leonardo is roughly 4x the file size at the
# same resolution, which is the detail the owner could see missing.
MODELS = {
    "lucid":   "@cf/leonardo/lucid-origin",
    "phoenix": "@cf/leonardo/phoenix-1.0",
    "sdxl":    "@cf/bytedance/stable-diffusion-xl-lightning",
}
MODEL = MODELS["lucid"]

WIDTH, HEIGHT = 768, 1344          # portrait, matches the 9:16 the reels post in

# ---------------------------------------------------------------------------
# THE CAST — locked. Editing a description here changes who the audience sees,
# so treat these lines as identity, not as prompt text to tune casually.
# ---------------------------------------------------------------------------
CAST = {
    "mkhulu": {
        "name": "Mkhulu",
        "look": ("a South African grandfather, 70 years old, deep brown skin, "
                 "short grey hair, full grey beard, kind lined face, slim build, "
                 "wearing a pressed short-sleeve shirt, grey slacks and a flat cap"),
    },
    "gogo": {
        "name": "Gogo",
        "look": ("a South African grandmother, 68 years old, deep brown skin, "
                 "grey hair under a bright doek headwrap, round warm face, "
                 "wearing a printed shweshwe dress and an apron"),
    },
    "auntie": {
        "name": "Auntie Thandi",
        "look": ("a South African woman, 45 years old, rich dark brown skin, "
                 "braided hair tied up, confident smile, curvy build, "
                 "wearing a bold print dress and gold hoop earrings"),
    },
    "cousin": {
        "name": "Cousin Sbu",
        "look": ("a young South African man, 24 years old, dark brown skin, "
                 "short fade haircut, lean athletic build, "
                 "wearing an oversized football shirt, cargo pants and white sneakers"),
    },
    "kids": {
        "name": "Zinhle and Zintle",
        "look": ("two identical South African twin toddler girls, 3 years old, "
                 "deep brown skin, hair in neat beaded braids, chubby cheeks, "
                 "one in a gold sequin dress and one in a silver sequin dress"),
    },
}

# ---------------------------------------------------------------------------
# THE TEMPLATES — read off the four best-performing reels on the profile, not
# invented. The view counts are why these four and not others.
# ---------------------------------------------------------------------------
TEMPLATES = {
    "walk_in": {
        "note": "2.7M — walks out, sees the crowd, decides to show them something",
        "shot": ("walking forward towards the camera, mid-stride, confident, "
                 "a dense crowd of South African neighbours filling the whole "
                 "background behind them, some filming on phones"),
    },
    "stand_still": {
        "note": "1.2M — stands alone, dead still, stares straight down the lens",
        "shot": ("standing completely still facing the camera, arms at their "
                 "sides, direct eye contact, a dense busy crowd of South African "
                 "people filling the background behind them, turning to look"),
    },
    "two_hander": {
        "note": "1.2M / 921K — two of them, one committed, one not bothered",
        "shot": ("standing beside a second person who is ignoring them "
                 "completely, both fully visible head to feet, a dense crowd of "
                 "family and neighbours filling the background behind them"),
    },
    "crowd_reaction": {
        "note": "1.2M — aunties screaming, gogo ululating, uncles recording",
        "shot": ("with a big delighted South African family filling the background "
                 "behind them, laughing, clapping, ululating and filming on "
                 "phones, the dancer clear and unblocked in front of them"),
    },
}

# Where it happens. This is the half that makes it recognisably Mzansi.
SETTINGS = {
    "braai":      "at a backyard braai, smoke rising off the grill, golden late afternoon light",
    "car_wash":   "at a township car wash on a Saturday, soapy water on the tar, bright midday sun",
    "church":     "outside a township church after the service, candles and choir robes, warm evening light",
    "taxi_rank":  "at a busy South African taxi rank, minibus taxis and hawkers, hard morning sun",
    "spaza":      "outside a colourful spaza shop, hand-painted signage, dusty street",
    "sandton":    "inside a polished Sandton City shopping mall, glass and marble, cool bright light",
    "backyard":   "in a sunlit Soweto backyard, washing line and corrugated fence, blue sky",
    "street":     "on a township street with painted houses, neighbours in doorways, warm afternoon light",
}

# FRAMING — this leads every prompt, before the character, because SDXL
# weights the opening tokens hardest and framing is the thing we cannot lose.
# Owner call 2026-08-30: "the dancer must always be clearly visible, currently
# this is a bit close up." The crowd_reaction template had been cropping at the
# knees even with cut-off-legs in the negative prompt - the crowd instruction
# was pulling the camera in. A cropped subject is not just worse looking here,
# it is USELESS: motion transfer with no legs in frame has no legs to drive.
FRAMING = ("full length photograph, the entire body from head to shoes inside "
           "the frame with nothing cropped, wide shot of a busy crowded scene")

# The STANDARD. Everything after the subject, so it never competes with framing.
STYLE = ("candid documentary photograph, real people, photojournalism, "
         "natural imperfect available light, realistic skin texture, "
         "vertical 9:16 phone photo, slightly grainy, unposed, "
         "authentic South African street photography")

NEGATIVE = ("close-up, closeup, portrait crop, headshot, bust shot, "
            "cropped at knees, cropped at waist, cut off legs, cut off feet, "
            "feet out of frame, subject too large in frame, face filling frame, "
            "zoomed in, empty background, alone, no people, "
            "blurry, distorted hands, extra limbs, extra fingers, text, "
            "watermark, cartoon, illustration, 3d render, cgi, painting, "
            "airbrushed, plastic skin, deformed face")

# ---------------------------------------------------------------------------
# Rotation ledger — same contract as modules/lineup_variety.py
# ---------------------------------------------------------------------------
def _load() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict) -> None:
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _key(character: str, template: str, setting: str) -> str:
    return f"{character}|{template}|{setting}"


def used() -> list:
    return _load().get("used", [])


def combinations() -> list:
    return [(c, t, s) for c in CAST for t in TEMPLATES for s in SETTINGS]


def pick() -> tuple:
    """Return (character, template, setting) that has not been posted yet.

    Least-used-first once every combination has been spent, so a long run
    keeps rotating instead of stalling — the lesson the PSL slot router
    learned the hard way when its debate groups ran out.
    """
    st = _load()
    spent = set(st.get("used", []))
    fresh = [c for c in combinations() if _key(*c) not in spent]
    if fresh:
        # Spread across ALL THREE axes, not just the character. Ranking on
        # character and template alone put the first twenty posts at the same
        # braai - every combination technically unique, and the page visibly
        # stuck in one backyard for a week. The setting is the axis a viewer
        # actually notices, so it is weighted first.
        counts = st.get("counts", {})
        return min(fresh, key=lambda c: (counts.get(c[2], 0),      # setting
                                         counts.get(c[0], 0),      # character
                                         counts.get(c[1], 0)))     # template
    counts = st.get("counts", {})
    return min(combinations(), key=lambda c: counts.get(_key(*c), 0))


def record_posted(character: str, template: str, setting: str) -> bool:
    """Record a combination AFTER it has actually gone out.

    Recording at pick() time is the bug this project has already paid for
    twice: a build that fails, or a card made by hand, either burns a
    combination that never reached the page or is invisible to the ledger.
    Idempotent, so calling it twice costs nothing.
    """
    st = _load()
    k = _key(character, template, setting)
    st.setdefault("used", [])
    if k in st["used"]:
        return False
    st["used"].append(k)
    counts = st.setdefault("counts", {})
    for token in (character, template, setting, k):
        counts[token] = counts.get(token, 0) + 1
    st["last"] = {"combo": k, "at": time.strftime("%Y-%m-%d %H:%M")}
    _save(st)
    return True


def reset() -> None:
    """Clear the ledger. Only for when the cast or templates change shape."""
    _save({})


# ---------------------------------------------------------------------------
# Prompt + generation
# ---------------------------------------------------------------------------
def build_prompt(character: str, template: str, setting: str) -> str:
    if character not in CAST:
        raise KeyError(f"unknown character {character!r} — have {sorted(CAST)}")
    if template not in TEMPLATES:
        raise KeyError(f"unknown template {template!r} — have {sorted(TEMPLATES)}")
    if setting not in SETTINGS:
        raise KeyError(f"unknown setting {setting!r} — have {sorted(SETTINGS)}")
    return (f"{FRAMING}, of {CAST[character]['look']}, "
            f"{TEMPLATES[template]['shot']}, {SETTINGS[setting]}, {STYLE}")


def generate(character: str, template: str, setting: str,
             out_path: str | Path | None = None, steps: int = 6,
             model: str = "") -> Path | None:
    """Render one character still on Cloudflare Workers AI. Returns the path.

    Returns None rather than raising on a failed call: a missing still should
    stand the post down, not crash the run that was going to build it.
    """
    import requests
    from dotenv import load_dotenv
    load_dotenv(override=True)

    token = os.getenv("CF_API_TOKEN", "").strip()
    account = os.getenv("CF_ACCOUNT_ID", "").strip()
    if not (token and account):
        print("[DanceCast] no CF_API_TOKEN / CF_ACCOUNT_ID in .env")
        return None

    prompt = build_prompt(character, template, setting)
    chosen = MODELS.get(model, model) or MODEL
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{chosen}"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"prompt": prompt, "negative_prompt": NEGATIVE,
                  "width": WIDTH, "height": HEIGHT},
            timeout=180)
    except Exception as e:
        print(f"[DanceCast] request failed: {str(e)[:120]}")
        return None

    if r.status_code != 200:
        print(f"[DanceCast] HTTP {r.status_code}: {r.text[:200]}")
        return None

    # SDXL returns raw PNG bytes; the JSON/base64 branch is here because
    # Cloudflare returns that shape for some models and a silent switch would
    # otherwise write an unopenable file.
    if "json" in r.headers.get("content-type", ""):
        img = (r.json().get("result") or {}).get("image")
        if not img:
            print(f"[DanceCast] no image in response: {r.text[:160]}")
            return None
        data = base64.b64decode(img)
    else:
        data = r.content

    if out_path is None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"{character}_{template}_{setting}_{int(time.time())}.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    print(f"[DanceCast] {character} / {template} / {setting} -> "
          f"{out_path.name} ({len(data)//1024}KB)")
    return out_path


def next_still(out_path: str | Path | None = None) -> tuple:
    """Pick the next unused combination and render it.

    Returns (path, character, template, setting). The caller records it with
    record_posted() only once the post is confirmed live.
    """
    c, t, s = pick()
    return generate(c, t, s, out_path), c, t, s


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate a dancing-reel character still")
    ap.add_argument("--character", choices=sorted(CAST))
    ap.add_argument("--template", choices=sorted(TEMPLATES))
    ap.add_argument("--setting", choices=sorted(SETTINGS))
    ap.add_argument("--next", action="store_true", help="use the rotation")
    ap.add_argument("--plan", type=int, metavar="N",
                    help="show the next N combinations without generating")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()

    if a.stats:
        st = _load()
        total = len(combinations())
        print(f"{len(st.get('used', []))} of {total} combinations used")
        print(f"last: {st.get('last')}")
    elif a.plan:
        st = _load()
        spent = set(st.get("used", []))
        counts = dict(st.get("counts", {}))
        for i in range(a.plan):
            fresh = [c for c in combinations() if _key(*c) not in spent]
            pool = fresh or combinations()
            c = min(pool, key=lambda x: (counts.get(x[2], 0), counts.get(x[0], 0),
                                         counts.get(x[1], 0)))
            print(f"  {i+1:>2}. {c[0]:<8} {c[1]:<15} {c[2]}")
            spent.add(_key(*c))
            for token in c:
                counts[token] = counts.get(token, 0) + 1
    elif a.next:
        print(next_still())
    elif a.character and a.template and a.setting:
        generate(a.character, a.template, a.setting)
    else:
        ap.error("pass --next, --plan N, --stats, or all three of "
                 "--character --template --setting")
