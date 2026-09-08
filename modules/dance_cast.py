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
# WELL DRESSED, NOT POOR. Owner call 2026-08-31.
#
# The wardrobe was written township-realist — an apron, scuffed takkies, a
# replica shirt — and it read as hardship rather than as style. That is the
# wrong aspiration for a page selling a premium product: the audience should
# want to BE these people. Every look below is now sharp, clean, current and
# expensive-looking, while staying recognisably South African rather than
# generic-American. The identities themselves are unchanged; only what they
# are wearing is.
CAST = {
    "mkhulu": {
        "active": False,
        "name": "Mkhulu",
        "look": ("a distinguished South African grandfather, 70 years old, deep "
                 "brown skin, neat silver hair, immaculate white beard, warm "
                 "dignified face, wearing a crisp tailored linen shirt, pressed "
                 "chinos, polished leather shoes and a stylish flat cap, "
                 "gold watch, looking sharp and expensive"),
    },
    "gogo": {
        "active": False,
        "name": "Gogo",
        "look": ("an elegant South African grandmother, 68 years old, deep brown "
                 "skin, silver hair under a beautifully tied designer doek in "
                 "South African flag colours, radiant warm face, wearing a "
                 "luxurious tailored shweshwe print dress with gold jewellery "
                 "and smart heeled sandals, glamorous and immaculate"),
    },
    "auntie": {
        "active": False,
        "name": "Auntie Thandi",
        "look": ("a striking South African woman, 45 years old, rich dark brown "
                 "skin, long braided hair styled up, flawless makeup, confident "
                 "smile, glamorous curvy figure, wearing a fitted designer "
                 "African print dress, large gold hoop earrings, gold bangles "
                 "and heels, looking wealthy and beautiful"),
    },
    "cousin": {
        "active": False,
        "name": "Cousin Sbu",
        "look": ("a handsome young South African man, 24 years old, dark brown "
                 "skin, sharp fresh fade haircut, lean athletic build, wearing a "
                 "designer bomber jacket over a crisp white tee, slim black "
                 "jeans and pristine white designer sneakers, gold chain, "
                 "stylish and well groomed"),
    },
    "kids": {
        "name": "Zinhle and Zintle",
        # TWO children in one still, so motion transfer cannot use them — the
        # animator has no single unambiguous body to drive, and Kling refuses
        # the input outright ("Too many subjects detected"). Same reason
        # two_hander carries motion_safe: False. They stay in the roster
        # because they still work as a static post, and Zinhle is the name the
        # 2.7M reel made famous.
        "motion_safe": False,
        "look": ("two identical South African twin toddler girls, 3 years old, "
                 "deep brown skin, hair in neat beaded braids, chubby cheeks, "
                 "one in a gold sequin dress and one in a silver sequin dress"),
    },
    # 4-8 YEAR OLDS. Added 2026-08-31 on the owner's call.
    #
    # Kept as separate entries rather than widening the twins, because CAST is
    # identity: Zinhle is a named 3-year-old the audience already knows from
    # the 63.4K reel, and quietly ageing her would change who they are watching.
    # Lwazi and Naledi are the same names the SA Family Studio presets use, so
    # the roster stays consistent across the product.
    #
    # Every look here is a SINGLE child, head to shoes, dressed sharply. A solo
    # subject matters more for these than for the adults: motion transfer
    # refuses a reference with more than one clear figure, and a child plus a
    # hovering parent is the shot the model reaches for unless told otherwise.
    "lwazi": {
        "name": "Lwazi",
        "look": ("a small young child, a 6 year old South African boy, tiny "
                 "and short with the chubby cheeks and big head-to-body "
                 "proportions of a small child, deep brown skin, fresh neat "
                 "haircut, cheeky bright smile, wearing a designer tracksuit "
                 "in South African flag colours and box-fresh white sneakers"),
    },
    "naledi": {
        "name": "Naledi",
        "look": ("a small young child, an 8 year old South African girl, short "
                 "and small with a round childlike face, warm dark brown skin, "
                 "immaculate beaded box braids with gold clips, bright smile, "
                 "wearing a stylish denim jacket over a pretty designer dress "
                 "and clean white sneakers"),
    },
    "thabo": {
        "name": "Thabo",
        "look": ("a small young child, an 8 year old South African boy, short "
                 "and small with round childlike cheeks, dark brown skin, "
                 "sharp fresh fade, confident little face, wearing a premium "
                 "black and gold tracksuit with crisp high-top sneakers"),
    },
    "amahle": {
        "name": "Amahle",
        "look": ("a tiny young child, a 5 year old South African girl, very "
                 "small and short with chubby cheeks and a toddler build, deep "
                 "brown skin, hair in two neat puff buns with gold ribbons, "
                 "round joyful face, wearing a beautiful yellow and gold party "
                 "dress with shiny gold shoes"),
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
                 "well clear of a stylish crowd of well-dressed South Africans who "
                 "are standing back and filling the whole background behind "
                 "them, some filming on phones"),
    },
    "stand_still": {
        "note": "1.2M — stands alone, dead still, stares straight down the lens",
        # "turning to look" as a trailing clause rendered as a crowd walking
        # away with their backs to her (2026-08-31). The crowd watching IS the
        # format — a crowd of backs is just a busy street — so the attention is
        # now stated as a fact about every face, not as an afterthought.
        # "surrounded by" asked for the exact thing the framing forbids — a
        # crowd closing in around the subject. The crowd belongs BEHIND, at a
        # distance, still watching. Owner call 2026-08-31: the dancer must
        # always be clear of the crowd, there must always be space.
        "shot": ("standing completely still facing the camera, arms at their "
                 "sides, direct eye contact, a crowd of well-dressed South Africans "
                 " standing well back behind them who have all stopped "
                 "and turned to face them, every face in the background looking "
                 "directly at them, watching intently, some filming on phones"),
    },
    "two_hander": {
        "note": "1.2M / 921K — two of them, one committed, one not bothered",
        # NOT USABLE AS A MOTION-TRANSFER STILL. Kling refuses an input with
        # more than one clear figure ("Too many subjects detected"), and even
        # when it passes, a two-person frame gives the animator no unambiguous
        # body to drive. This stays in the roster because it still earns as a
        # static post; motion_safe is what keeps the dance rotation off it.
        "motion_safe": False,
        "shot": ("standing beside a second person who is ignoring them "
                 "completely, both fully visible head to feet, a dense crowd of "
                 "family and neighbours filling the background behind them"),
    },
    "crowd_reaction": {
        "note": "1.2M — aunties screaming, gogo ululating, uncles recording",
        # This template fights the framing and keeps winning. "Filling the
        # background" pulls the camera in until the subject is a waist-up
        # portrait — it cropped at the knees before, and on 2026-08-31 it came
        # back with the feet cut off again despite the negative prompt. The
        # crowd now gets an explicit DISTANCE, and the subject an explicit
        # amount of empty ground beneath her, because the model needs to be
        # told where the camera stands, not just what is in the shot.
        "shot": ("standing alone several metres in front of a big delighted "
                 "crowd of well-dressed South Africans laughing, clapping, cheering "
                 "and filming on phones, the crowd well behind them in the "
                 "distance, the dancer small in the frame and completely "
                 "unblocked with empty ground visible beneath their shoes"),
    },
}

# Where it happens. This is the half that makes it recognisably Mzansi.
#
# One-liners rendered generic — the first car_wash came back as an ordinary
# busy street with a woman standing in it. The model fills in whatever it
# already knows about "South Africa" unless it is given the specific objects
# that only exist in the real place. Concrete nouns make it Mzansi; adjectives
# make it stock.
#
# ASPIRATION, NOT HARDSHIP. Owner call 2026-08-31: "show like in the mall ...
# not looking poor but good and beautiful ... Sandton or Maponya Mall or any
# other place that are popular."
#
# The old list was a taxi rank, a spaza, a backyard washing line — real, but it
# framed the cast as struggling. These are the places South Africans actually
# recognise and aspire to, named specifically because "a shopping mall" renders
# as Anywhere, USA while "Maponya Mall, Soweto" renders as home. Two outdoor
# celebration settings stay so the reels are not all polished marble.
SETTINGS = {
    # TWO malls, not five. The first upmarket pass replaced every township
    # setting with a shopping centre, and five of the eight were malls — so
    # Thabo at Mall of Africa and Amahle at Maponya came out as the same
    # photograph: polished floor, glass balustrade, crowd lining a walkway.
    # Aspiration was the right instruction; "aspiration means a mall" was my
    # wrong reading of it. These two stay because they are the ones South
    # Africans name; the other six are upmarket AND look nothing alike.
    "sandton":    ("inside Sandton City in Johannesburg, polished marble floors, glass "
                   "balustrades, designer flagship storefronts, luxury shoppers with bags, "
                   "bright upmarket indoor light"),
    "maponya":    ("inside Maponya Mall in Soweto, the bright open atrium, glass escalators "
                   "and modern shopfronts, South African flag bunting overhead, "
                   "well-dressed shoppers, clean polished floors"),
    "stadium":    ("on the pitchside track at FNB Stadium in Johannesburg, the vast tiered "
                   "stands packed with fans in team colours, floodlights on, green grass "
                   "and running track, huge open sky"),
    "beachfront": ("on the Durban Golden Mile beachfront promenade, palm trees, white sand "
                   "and the Indian Ocean behind, joggers and families, bright coastal sun"),
    "vilakazi":   ("on Vilakazi Street in Soweto, the restaurant strip with outdoor tables "
                   "and umbrellas, colourful street murals, tourists and locals eating, "
                   "warm afternoon light"),
    "waterfront": ("at the V&A Waterfront in Cape Town, the harbour and boats behind, Table "
                   "Mountain on the skyline, upmarket promenade, golden afternoon light"),
    "rooftop":    ("at a stylish Johannesburg rooftop party, city skyline behind, festoon "
                   "lights strung overhead, well-dressed young crowd with drinks, warm "
                   "sunset light"),
    "celebration": ("at an upmarket South African garden celebration, white marquee, gold and "
                    "flag-coloured decor, elegantly dressed guests, catered tables, "
                    "golden late afternoon light"),
}



# FRAMING — this leads every prompt, before the character, because SDXL
# weights the opening tokens hardest and framing is the thing we cannot lose.
# Owner call 2026-08-30: "the dancer must always be clearly visible, currently
# this is a bit close up." The crowd_reaction template had been cropping at the
# knees even with cut-off-legs in the negative prompt - the crowd instruction
# was pulling the camera in. A cropped subject is not just worse looking here,
# it is USELESS: motion transfer with no legs in frame has no legs to drive.
FRAMING = ("full length photograph, the entire body from head to shoes inside "
           "the frame with nothing cropped, wide shot of a busy crowded scene, "
           "the subject standing alone in clear open space with several metres "
           "of empty ground between them and the nearest person, nobody "
           "touching or overlapping them")

# The STANDARD. Everything after the subject, so it never competes with framing.
#
# "Slightly grainy phone photo" was holding the image DOWN — it reads as an
# instruction to degrade, and the thumbnail is what wins or loses the scroll.
# What actually makes these read real is not low quality, it is the light and
# the skin: hard highlights, true shadow, visible pores and sweat. So the grain
# is gone and the detail language is explicit, while the candid, unposed,
# available-light framing that keeps it from looking like stock photography
# stays exactly as it was.
STYLE = ("candid documentary photograph, real people, photojournalism, "
         "beautiful natural light, flattering, attractive and photogenic, "
         "realistic skin texture, glowing healthy skin, "
         "sharp focus on the subject, fine detail in fabric and hair, "
         "shallow depth of field, vertical 9:16, unposed, "
         "shot on a full frame camera at 35mm, "
         "upmarket South African lifestyle photography, aspirational, "
         "premium editorial quality, vibrant colour")

NEGATIVE = (
            # Aspiration, not hardship — the wardrobe and the location are
            # meant to look like somewhere the audience wants to be.
            # The kids render as teenagers unless this is said out loud.
            "teenager, teen, adolescent, adult, grown up, tall, "
            "long limbs, mature face, older child, "
            "poor, shabby, dirty, worn out clothes, torn clothing, "
            "run down, slum, poverty, drab, dull, washed out, "
            "close-up, closeup, portrait crop, headshot, bust shot, "
            "cropped at knees, cropped at waist, cut off legs, cut off feet, "
            "feet out of frame, subject too large in frame, face filling frame, "
            "zoomed in, empty background, alone, no people, "
            # The crowd must be an audience, not pedestrians.
            "crowd facing away, backs turned, back of heads, "
            "people walking away, crowd ignoring the subject, "
            # ...and an audience, not a scrum. The subject needs room to dance.
            "crowd crowding the subject, people pressed against the subject, "
            "bystanders overlapping the subject, person standing in front, "
            "obscured by people, no space around subject, "
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


def motion_templates() -> list:
    """Templates that can drive a motion-transfer render (single subject)."""
    return [k for k, v in TEMPLATES.items() if v.get("motion_safe", True)]


def motion_characters() -> list:
    """
    Characters eligible for a motion-transfer reel.

    Two gates. `motion_safe` is permanent and physical — the twins are two
    bodies in one still and no transfer can drive that. `active` is editorial
    and temporary: owner call 2026-09-01 to run kids only for now, so the
    adults are switched off rather than deleted, and switching them back on is
    one field each.
    """
    return [k for k, v in CAST.items()
            if v.get("motion_safe", True) and v.get("active", True)]


# HOW MUCH EVIDENCE BEFORE A NUMBER GETS A VOTE.
#
# Owner 2026-09-08: "can we prioritise the videos that work." Yes - but on
# 8 Sep the answer was 17 scored posts, and the two that mattered were single
# reels: lwazi|crowd_reaction|sandton took 149,000 while lwazi|walk_in|sandton
# took 2,000. A median over two posts that far apart is not a measurement, and
# ranking settings on it would have chased one lucky reel around the roster.
#
# So a setting only gets promoted or demoted once MIN_EVIDENCE posts have
# actually been measured for it. Below that it sits in the middle tier with
# everything unknown, and the fairness rotation decides - which is exactly
# what this picker did before. The bias turns itself on, per setting, as the
# posts accumulate. Nothing to remember to enable.
MIN_EVIDENCE = 3     # measured posts before a setting is judged
MIN_RANKED = 3       # settings that must qualify before any are


def _setting_tier():
    """A function setting -> 0 proven good, 1 unproven, 2 proven weak.

    Ranked against the MEDIAN of the settings that have enough evidence, so
    "good" means better than a typical post rather than better than zero.
    Returns an all-unproven ranking if the stats module or its ledger is
    missing, which keeps this picker working on a machine that has never
    scraped anything.
    """
    try:
        from modules.profile_stats import scores, _runs, _reel_id, _perf
        perf = _perf()
        counts = {}
        for row in _runs():
            if not row.get("posted") or _reel_id(row) not in perf:
                continue
            parts = (row.get("combo") or "").split("|")
            if len(parts) == 3:
                counts[parts[2]] = counts.get(parts[2], 0) + 1
        med = scores().get("setting", {})
        ranked = {k: v for k, v in med.items()
                  if counts.get(k, 0) >= MIN_EVIDENCE}
        # A COMPARISON NEEDS SOMETHING TO COMPARE AGAINST. With one qualifying
        # setting the median IS that setting, so it scores at-or-above itself
        # and gets promoted for no reason. On 8 Sep that was stadium - the
        # only setting with three measured posts and, at a 2,100 median, one
        # of the WEAKEST on the profile. The first version of this promoted it
        # and the picker started steering there, which is the exact opposite
        # of what was asked for. Rank nothing until a real field exists.
        if len(ranked) < MIN_RANKED:
            return lambda s: 1
        vals = sorted(ranked.values())
        mid = vals[len(vals) // 2]
        return lambda s: (1 if s not in ranked
                          else (0 if ranked[s] >= mid else 2))
    except Exception:
        return lambda s: 1


def pick(motion_only: bool = False) -> tuple:
    """Return (character, template, setting) that has not been posted yet.

    motion_only drops templates that put a second person in the frame, which
    a motion-transfer render cannot use.

    Least-used-first once every combination has been spent, so a long run
    keeps rotating instead of stalling — the lesson the PSL slot router
    learned the hard way when its debate groups ran out.
    """
    st = _load()
    spent = set(st.get("used", []))
    allowed = motion_templates() if motion_only else list(TEMPLATES)
    cast_ok = motion_characters() if motion_only else list(CAST)
    pool = [c for c in combinations() if c[1] in allowed and c[0] in cast_ok]
    fresh = [c for c in pool if _key(*c) not in spent]
    tier = _setting_tier()
    if fresh:
        # Spread across ALL THREE axes, not just the character. Ranking on
        # character and template alone put the first twenty posts at the same
        # braai - every combination technically unique, and the page visibly
        # stuck in one backyard for a week. The setting is the axis a viewer
        # actually notices, so it is weighted first.
        counts = st.get("counts", {})
        # Proven settings first, then the same fairness order INSIDE each
        # tier. Rotation still does the work of spreading posts around; the
        # tier only decides which group gets spread through first, so the
        # profile cannot get stuck in one location the way it did in August.
        return min(fresh, key=lambda c: (tier(c[2]),               # evidence
                                         counts.get(c[2], 0),      # setting
                                         counts.get(c[0], 0),      # character
                                         counts.get(c[1], 0)))     # template
    counts = st.get("counts", {})
    return min(pool, key=lambda c: counts.get(_key(*c), 0))


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

    # RETRY, because a single 408 must not lose a scheduled slot.
    #
    # Cloudflare answered one generation with HTTP 408 "AiError: Request
    # timeout" on 2026-08-31 and the call simply returned None. By hand that is
    # a shrug and a re-run; inside an unattended 07:00 build it fails the whole
    # reel and the post never happens. Transient status codes and connection
    # errors are worth another go; a 400 or a 401 is not, so those still fail
    # immediately rather than burning three attempts on a bad request.
    RETRYABLE = {408, 429, 500, 502, 503, 504}
    r = None
    for attempt in range(3):
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
            if attempt == 2:
                return None
            time.sleep(5 * (attempt + 1))
            continue

        if r.status_code == 200:
            break
        if r.status_code in RETRYABLE and attempt < 2:
            print(f"[DanceCast] HTTP {r.status_code}, retrying "
                  f"({attempt + 1}/3)")
            time.sleep(5 * (attempt + 1))
            continue
        print(f"[DanceCast] HTTP {r.status_code}: {r.text[:200]}")
        return None

    if r is None or r.status_code != 200:
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
