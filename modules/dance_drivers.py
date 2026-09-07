"""
The driving-video half of the dance rotation.

modules/dance_cast.py rotates WHO dances and WHERE. This rotates WHAT THEY
DANCE — the reference clip whose motion gets transferred onto the character
still. Same ledger contract: least-used first, recorded only once a post is
confirmed live.

WHY A DRIVER NEEDS PREPARING FIRST
----------------------------------
A published reel is not a usable driver. Kling refuses a reference clip whose
subject is small in frame — "No complete upper body detected in the video" —
and the reels that earn are shot wide, with the dancer maybe a third of frame
height under a burned-in hook. The 2.7M reel was rejected twice on 2026-08-31
before it was cropped.

So each driver is prepared once: crop to the dancer, scale back to 720x1280,
keep the audio, drop the burned-in text along the way. prepare() does that;
after it, the clip rotates freely and costs nothing to reuse.

NEVER DELOGO OVER THE DANCER.
-----------------------------
whodis_hall was prepared with an ffmpeg delogo pass to erase an emoji strip
burned across the dancer's shins, because no crop could avoid it. It looked
acceptable frame by frame and it ruined the transfer: the render came back
6.25s SHORT of its 25.2s source and the character barely moved, while the two
clean drivers landed within 0.33s of theirs and followed the dance exactly.
Delogo smears the pixels it replaces, and those pixels were the legs the pose
detector needed. A clip whose overlays sit on the subject is not a driver -
drop it and find another. Removed 2026-09-01 after it produced a reel the
owner deleted.

Length is the cost lever. The motion-control model silently ignores its own
`duration` field — output length follows the driver — so a 25s driver costs
roughly 1.7x a 15s one. Record the real duration here so a caller can choose.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "driver_rotation.json"
DRIVER_DIR = ROOT / "assets" / "dance_drivers" / "prepared"

# THE LIBRARY. One entry per prepared driver.
#
# `source` is the post it came from, kept so a human can check the moves
# against what actually earned. `views` is why it is in here at all — this
# library is meant to hold the best performers, not every clip we own.
DRIVERS = {
    "zinhle_plaza": {
        "look": "green_tracksuit_kid",
        "file": "driver_full_25s.mp4",
        "source": "https://www.facebook.com/reel/950392301187379",
        "views": 2_700_000,
        "seconds": 25.2,
        "note": "Zinhle outside the mall — the routine the profile was built on",
    },
    "pantsula_carwash": {
        "look": "yellow_pantsula_boy",
        "file": "driver_pantsula_16s.mp4",
        "source": "https://www.facebook.com/reel/938667402249371",
        "views": 520_000,
        "seconds": 15.9,
        "note": "2-year-old hitting the pantsula at Skhokho Car Wash",
    },
    "sandton_green": {
        "look": "green_tracksuit_kid",
        "file": "driver_sandton_green_25s.mp4",
        "source": "https://www.facebook.com/reel/4164918383770049",
        "views": 1_200_000,
        "seconds": 25.3,
        "note": "green-black tracksuit outside Sandton City — cleanest of the set",
    },
    "gold_skirt_hall": {
        "look": "gold_skirt_girl",
        "file": "driver_gold_skirt_18s.mp4",
        "source": "https://www.facebook.com/reel/801023699213119",
        "views": 1_100_000,
        "seconds": 13.8,
        "note": "white top and gold skirt, hall, seated crowd clapping behind",
    },
    "gold_skirt_lounge": {
        "look": "gold_skirt_girl",
        "file": "driver_gold_skirt_lounge_19s.mp4",
        "source": "https://www.facebook.com/reel/1900300160597138",
        "views": 501_000,
        "seconds": 19.3,
        "note": "white top and gold skirt again, lounge, family on the couch",
    },
    "church_white_dress": {
        "look": "white_dress_girl",
        "file": "driver_church_white_30s.mp4",
        "source": "https://www.facebook.com/reel/1311673157487428",
        "views": 431_000,
        "seconds": 29.8,
        "note": "white dress praise dance in church, candles",
    },
    # ── Added 2026-09-05, owner-supplied ──────────────────────────────────
    #
    # These two came from the owner's own downloads rather than from a reel
    # this repo tracks, so `source` and `views` are unknown and are recorded
    # as such. Every other entry carries a view count because the library is
    # meant to hold proven performers; inventing numbers for these two would
    # make that column a lie and would quietly outrank clips whose figures are
    # real. They are here because the owner asked for them, which is reason
    # enough - it is just not the same reason.
    #
    # The rotation reaches them next because pick() takes the LEAST-USED
    # driver and these start at zero while everything else sits at 2 or 3 -
    # not because of where they appear in this dict. Position only breaks the
    # tie BETWEEN these two, which is why the vibes clip is written first.
    # Expect them to take the next four slots before the counts level up.
    "vibes_tee_lounge": {
        "look": "vibes_tee_girl",
        "file": "driver_vibes_tee_30s.mp4",
        "source": "owner download 2026-09-05",
        "views": 0,
        "seconds": 30.0,
        "note": "girl in white VIBES tee and blue cargo jeans, bright lounge; "
                "no crop needed - already 720x1280 and full-body centred. "
                "LONGEST driver in the library, so the priciest to render",
    },
    # PARKED 2026-09-07 after two rejections. Added 5 Sep, picked on the 07:00
    # and 13:00 runs, and both came back 14.7s against a 16.6s driver - 11.4%
    # adrift, past the 10% guard, deterministic across both attempts. The file
    # itself is sound (498 frames, exact 16.6s, start_time 0), so this is the
    # transfer genuinely not following it, which is what the guard is for.
    #
    # The likely reason is the preparation: the source was 720x982, so it was
    # cropped to 552 wide and then UPSCALED 1.3x to reach 720x1280. Every
    # driver that works was native or downscaled. vibes_tee_lounge, added the
    # same day at a native 720x1280, posted first time.
    #
    # Renaming the file key rather than deleting the entry: available() only
    # lists drivers whose file exists, so pointing at a name that is not on
    # disk takes it out of rotation while leaving the record of why. It cost
    # $2.32 in failed transfers before it was caught.
    "school_tracksuit_car__parked": {
        "look": "school_tracksuit_boy",
        "file": "PARKED_driver_school_tracksuit_16s.mp4",
        "source": "owner download 2026-09-05",
        "views": 0,
        "seconds": 16.6,
        "note": "boy in navy school tracksuit and backpack dancing by a red "
                "car; source was 720x982 so cropped to 9:16, and the first "
                "1.5s dropped - he starts crouched half outside the left edge",
    },
    # Added 2026-09-07, owner-supplied: "the recent posted start to perform
    # better, post this one now."
    #
    # The source has TWO dancers on a court, and going in whole it was refused
    # outright: "No complete upper body detected in the video; ensure the
    # upper body is clearly visible." Two people sharing the width leaves
    # neither of them big enough to track - the same rejection the 2.7M reel
    # hit on 31 Aug before it was cropped.
    #
    # So it is cropped to ONE of them, the dancer in the orange vest, which is
    # also the only sane choice for a pipeline that animates a single
    # character. The first three seconds go too: both men are walking in from
    # distance there and are small even after the crop.
    #
    # Headroom above the cap is deliberate. A crop that clipped the top of his
    # head is exactly what "complete upper body" is asking about.
    "court_orange_vest": {
        "look": "orange_vest_boy",
        "file": "driver_court_orange_10s.mp4",
        "source": "owner download 2026-09-07",
        "views": 0,
        "seconds": 10.4,
        "note": "dancer in an orange vest on a blue court at sunset; cropped "
                "out of a two-man clip, first 3s dropped",
    },
    "braai_kente": {
        "look": "kente_skirt_girl",
        "file": "driver_braai_kente_27s.mp4",
        "source": "https://www.facebook.com/reel/771054535872087",
        "views": 292_000,
        "seconds": 26.5,
        "note": "Mzansi tee and kente skirt at a backyard braai",
    },
}


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")


# A driver that has failed this many times stops being offered. Two is the
# number because two is what it took to prove school_tracksuit_car was bad on
# 7 Sep, and by then it had eaten both of the day's slots.
MAX_FAILURES = 2


def failures(key: str = "") -> dict | int:
    f = _load().get("failures", {})
    return f.get(key, 0) if key else f


def record_failed(key: str, why: str = "") -> None:
    """Count a render that the driver is to blame for.

    THE HOLE THIS FILLS. record_used fires only on a confirmed publish, which
    is right for rotation fairness and was catastrophic for reliability: a
    driver that fails never gets counted, so it stays the least-used one, so
    pick() hands it back on the very next slot. On 7 Sep that put
    school_tracksuit_car into the 07:00 run and then the 13:00 run, both
    rejected, and the profile posted nothing all day. Left alone it would have
    taken every slot from then on.

    Counting failures separately from uses keeps the rotation honest - a bad
    driver is not promoted to "used" - while still getting it out of the way.
    """
    st = _load()
    f = st.setdefault("failures", {})
    f[key] = f.get(key, 0) + 1
    if why:
        st.setdefault("failure_notes", {})[key] = why[:200]
    _save(st)
    n = f[key]
    if n >= MAX_FAILURES:
        print(f"[Drivers] {key} has failed {n}x - quarantined, "
              f"re-prepare it or drop it")
    else:
        print(f"[Drivers] {key} failed ({n}/{MAX_FAILURES})")


def available() -> list:
    """Drivers whose prepared file exists AND that have not been quarantined."""
    fails = failures()
    return [k for k, v in DRIVERS.items()
            if (DRIVER_DIR / v["file"]).exists()
            and fails.get(k, 0) < MAX_FAILURES]


def pick() -> str | None:
    """
    Least-used prepared driver that does not LOOK like the last one.

    Counting by key is not enough. zinhle_plaza and sandton_green are separate
    reels with separate view counts — and they are the same child in the same
    neon-green tracksuit dancing in the same mall. The ledger called that
    rotation; the owner called it "using the same reference video again", and
    he was right, because the audience sees the dancer, not the filename.

    So each driver carries a `look`, and a look is not repeated back to back.
    Views still break ties, but never at the cost of showing the same-looking
    reference twice in a row.
    """
    ready = available()
    if not ready:
        return None

    st = _load()
    counts = st.get("counts", {})
    last = st.get("last")
    last_look = DRIVERS.get(last, {}).get("look") if last else None

    fresh = [k for k in ready if DRIVERS[k].get("look") != last_look]
    pool = fresh or ready          # every look just used — allow the repeat
    if not fresh and last_look:
        print(f"[Drivers] only {last_look} clips remain; repeating that look")
    return min(pool, key=lambda k: counts.get(k, 0))


def path_for(key: str) -> Path:
    return DRIVER_DIR / DRIVERS[key]["file"]


def record_used(key: str) -> None:
    """Call only after the post using this driver is confirmed live."""
    st = _load()
    counts = st.setdefault("counts", {})
    counts[key] = counts.get(key, 0) + 1
    st["last"] = key
    _save(st)


def prepare(src: str | Path, key: str, crop: str, start: float = 0,
            duration: float | None = None) -> Path | None:
    """
    Turn a published reel into a usable driver.

    crop is an ffmpeg crop expression (w:h:x:y) around the dancer — there is no
    reliable way to find them automatically, and a wrong guess wastes a render,
    so the caller looks at the frames and says where they are.
    """
    out = DRIVER_DIR / DRIVERS[key]["file"]
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start:
        cmd += ["-ss", str(start)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-i", str(src),
            "-vf", f"crop={crop},scale=720:1280:flags=lanczos",
            "-c:v", "libx264", "-preset", "slow", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            str(out)]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"[Drivers] prepare failed for {key}: {str(e)[:160]}")
        return None
    print(f"[Drivers] {key} -> {out.name}")
    return out


if __name__ == "__main__":
    st = _load()
    print(f"{len(available())} of {len(DRIVERS)} drivers prepared")
    for k in DRIVERS:
        ready = "ready" if (DRIVER_DIR / DRIVERS[k]["file"]).exists() else "MISSING"
        print(f"  {k:<16} {ready:<8} used {st.get('counts', {}).get(k, 0)}x  "
              f"{DRIVERS[k]['views']:,} views  {DRIVERS[k]['seconds']}s")
    print(f"next: {pick()}")
