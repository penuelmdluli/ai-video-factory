"""
Build one dance reel end to end, and optionally post it.

    python make_dance_reel.py                 # build only
    python make_dance_reel.py --post          # build and publish
    python make_dance_reel.py --dry           # show the choices, render nothing

The whole pipeline in one run:

    pick an unused character/template/setting  (dance_cast)
    pick the least-used driving clip           (dance_drivers)
    generate the character still on Cloudflare
    motion-transfer the driver onto the still  (WaveSpeed Kling)
    brand it, burn the hook on
    post it to the personal timeline           (Playwright)
    record the combination and the driver      (only on a confirmed publish)

WHY IT PICKS RATHER THAN TAKES ARGUMENTS
----------------------------------------
Three posts a day is the schedule, and the whole point of the ledgers is that
nobody has to remember what went out yesterday. Both ledgers are recorded ONLY
after the post is confirmed live, so a failed render or a refused composer
costs money but never silently burns a combination.

MODEL CHOICE
------------
kling-v2.6-std, measured 2026-08-31 at $0.070/sec against v3.0-std's $0.131,
for output that was indistinguishable on this material. Cost follows the
driver's length because the model ignores its own duration field — a 16s
driver is ~$1.12, a 25s one ~$1.75.
"""
import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
load_dotenv()

from modules import dance_cast, dance_drivers          # noqa: E402
from modules.brand import watermark_video               # noqa: E402
from modules.overlays import add_hook_text              # noqa: E402

WS_BASE = "https://api.wavespeed.ai/api/v3"
WS_MODEL = "kwaivgi/kling-v2.6-std/motion-control"
OUT_DIR = ROOT / "output" / "reels"
PENDING_DIR = ROOT / "output" / "pending"
LOG = ROOT / "output" / "reel_runs.jsonl"

# The hook that earns. Every reel this format is built on opens with it.
HOOK_TEXT = "Wait for it..."
HOOK_EMOJI = "\U0001F525\U0001F440"

# Caption openers, one per template, so a run does not read like the last one.
CAPTIONS = {
    "walk_in": ["{name} pulled up {where} — and the whole place stopped",
                "{name} walked out {where} like they owned it"],
    "stand_still": ["{name} stood dead still {where}... then this happened",
                    "Nobody expected {name} to do THIS {where}"],
    "crowd_reaction": ["{name} came out {where} and the crowd lost it",
                       "{where}, and {name} just took over"],
}
WHERE = {
    "sandton": "in Sandton City", "maponya": "at Maponya Mall",
    "stadium": "at FNB Stadium", "beachfront": "on the Durban beachfront",
    "vilakazi": "on Vilakazi Street", "waterfront": "at the V&A Waterfront",
    "rooftop": "at a Joburg rooftop party", "celebration": "at the celebration",
}




def _duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out)
    except Exception:
        return None


def log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def r2_upload(path: Path) -> str:
    """Put a local file on the CDN so WaveSpeed can fetch it."""
    import boto3  # imported late: only this step needs it
    env = os.environ
    s3 = boto3.client(
        "s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto")
    key = f"dance/{int(time.time())}-{path.name}"
    ctype = "video/mp4" if path.suffix == ".mp4" else "image/png"
    s3.upload_file(str(path), env["R2_BUCKET_NAME"], key, ExtraArgs={"ContentType": ctype})
    return f"{env['R2_PUBLIC_URL'].rstrip('/')}/{key}"


def transfer(image_url: str, video_url: str, timeout: int = 1500) -> str | None:
    """Submit the motion transfer and wait. Returns the output URL."""
    key = os.getenv("WAVESPEED_API_KEY", "").strip()
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = requests.post(f"{WS_BASE}/{WS_MODEL}", headers=h, timeout=60, json={
        "image": image_url, "video": video_url,
        "character_orientation": "video", "keep_original_sound": True})
    if r.status_code != 200:
        print(f"[Reel] submit failed {r.status_code}: {r.text[:200]}")
        return None
    job = r.json()["data"]["id"]
    print(f"[Reel] transfer job {job}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(20)
        d = requests.get(f"{WS_BASE}/predictions/{job}/result", headers=h, timeout=60).json()["data"]
        if d["status"] == "completed":
            return d["outputs"][0]
        if d["status"] == "failed":
            # Almost always the input, not the model: a subject too small in
            # frame, or more than one clear figure. Both are prompt/crop bugs.
            print(f"[Reel] transfer failed: {d.get('error')}")
            return None
    print("[Reel] transfer timed out")
    return None


def finish(raw: Path, stem: str) -> Path:
    """Compress, brand, hook. The order matters: hook goes on last so it sits
    above the watermark and survives the final encode untouched."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    small = OUT_DIR / f"{stem}_small.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(small)], check=True)
    branded = watermark_video(str(small), str(OUT_DIR / f"{stem}_branded.mp4"))
    final = add_hook_text(branded, str(OUT_DIR / f"{stem}.mp4"),
                          text=HOOK_TEXT, emoji=HOOK_EMOJI)
    for tmp in (small, Path(branded)):
        tmp.unlink(missing_ok=True)
    return Path(final)


def caption_for(character: str, template: str, setting: str) -> str:
    name = dance_cast.CAST[character]["name"]
    line = random.choice(CAPTIONS.get(template, CAPTIONS["walk_in"]))
    body = line.format(name=name, where=WHERE.get(setting, ""))
    return f"{HOOK_TEXT} {HOOK_EMOJI} {body} \U0001F62D\U0001F64C"


def _pending_manifests() -> list:
    if not PENDING_DIR.exists():
        return []
    out = []
    for f in PENDING_DIR.glob("*.json"):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


def pending_characters() -> set:
    """
    Characters already rendered and waiting in the queue.

    Neither ledger knows about them — both record only on a confirmed publish —
    so without this the picker chooses a character already sitting in the queue
    and the same dancer goes out twice in a row. The CHARACTER, not the whole
    combination: the same dancer in a different setting still reads as a repeat
    to anyone scrolling, because the character is the half they recognise.
    """
    return {m["combo"].split("|")[0] for m in _pending_manifests() if m.get("combo")}


def pending_drivers() -> set:
    """
    Driving clips already claimed by a queued reel.

    Same hole as the characters, found the same way: building two reels back to
    back without posting either gave both the same driver, because
    dance_drivers.record_used only fires on a publish. Different dancers hid it,
    but the dance itself was repeating.
    """
    return {m["driver"] for m in _pending_manifests() if m.get("driver")}


def pick_unqueued() -> tuple:
    """Next combination whose character is neither posted nor already queued."""
    queued = pending_characters()
    for _ in range(40):
        c, t, s = dance_cast.pick(motion_only=True)
        if c not in queued:
            return c, t, s
        # Temporarily treat it as spent so the next call moves past it.
        dance_cast.record_posted(c, t, s)
        _rollback.append((c, t, s))
    return dance_cast.pick(motion_only=True)


def pick_driver_unqueued() -> str | None:
    """
    Least-used driver that no queued reel has already claimed.

    Falls back to the plain least-used pick when every driver is spoken for —
    a repeat is better than refusing to build.
    """
    ready = dance_drivers.available()
    if not ready:
        return None
    claimed = pending_drivers()
    free = [d for d in ready if d not in claimed]
    if not free:
        print("[Reel] every driver is already queued; allowing a repeat")
        return dance_drivers.pick()
    counts = dance_drivers._load().get("counts", {})
    return min(free, key=lambda k: counts.get(k, 0))


_rollback: list = []


def undo_rollback() -> None:
    """Un-record the combinations pick_unqueued marked to step over them."""
    if not _rollback:
        return
    st = dance_cast._load()
    used = st.get("used", [])
    counts = st.get("counts", {})
    for c, t, s in _rollback:
        key = dance_cast._key(c, t, s)
        if key in used:
            used.remove(key)
        for token in (c, t, s, key):
            if counts.get(token):
                counts[token] -= 1
    st["used"], st["counts"] = used, counts
    dance_cast._save(st)
    _rollback.clear()


def take_pending() -> dict | None:
    """
    A reel rendered earlier and waiting to go out.

    Renders cost money, so a video built ahead of schedule — or one whose post
    slot was moved — should be posted rather than rebuilt. A scheduled run
    drains this queue first and only renders when it is empty. Each entry is a
    .json next to its .mp4, holding the caption and the ledger keys the post
    must record.
    """
    if not PENDING_DIR.exists():
        return None
    entries = sorted(PENDING_DIR.glob("*.json"))
    if not entries:
        return None
    meta = json.loads(entries[0].read_text(encoding="utf-8"))
    meta["_manifest"] = entries[0]
    if not Path(meta["video"]).exists():
        print(f"[Reel] pending manifest {entries[0].name} points at a missing video, skipping")
        entries[0].unlink(missing_ok=True)
        return None
    return meta


async def seed_first_comment(caption: str, headless: bool = True) -> dict:
    """
    Leave the first comment on the reel we just published.

    Runs only after a confirmed publish, and finds the post by matching the
    distinctive half of its caption — the composer gives back no url, and the
    reels grid is not ordered newest-first, so "the newest one" would be a
    guess. A failure here is logged and swallowed: the post is already live and
    is the thing that matters, and retrying browser sessions against this
    account is the risk we are managing.
    """
    from modules.profile_finder import find_recent_post, distinctive, seed_comment
    from modules.profile_commenter import comment_on_post

    # FACEBOOK DOES NOT INDEX A REEL THE INSTANT IT IS POSTED.
    #
    # The composer closes, the post is live on the timeline, and the reels grid
    # still does not list it — so looking immediately finds nothing and the
    # comment is silently skipped. That is what happened on 2026-08-31: the
    # post went out fine and the seed comment did not, and it only worked when
    # retried by hand a minute later. Wait it out instead.
    found = None
    for attempt in range(6):
        found = await find_recent_post(distinctive(caption), headless=headless)
        if found.get("status") == "ok":
            break
        if attempt < 5:
            print(f"[Reel] new post not indexed yet, waiting 30s "
                  f"(attempt {attempt + 1}/6)")
            await asyncio.sleep(30)

    if found.get("status") != "ok":
        print(f"[Reel] could not locate the new post to comment on: {found.get('error')}")
        return found

    text = seed_comment()
    print(f"[Reel] seeding first comment on {found['url']}: {text}")
    result = await comment_on_post(found["url"], text, post=True, headless=headless)
    result["url"] = found["url"]
    result["text"] = text
    if result.get("status") != "ok":
        print(f"[Reel] comment failed: {result.get('error')}")
    return result


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", action="store_true", help="publish when the render succeeds")
    ap.add_argument("--dry", action="store_true", help="show the choices and stop")
    ap.add_argument("--show", action="store_true", help="visible browser when posting")
    ap.add_argument("--no-comment", action="store_true",
                    help="skip the first comment after posting")
    ap.add_argument("--queue", action="store_true",
                    help="render a fresh reel and add it to the pending queue "
                         "instead of posting; ignores anything already queued")
    args = ap.parse_args()

    pending = None if args.queue else take_pending()
    if pending:
        print(f"[Reel] posting a pending reel instead of rendering: {Path(pending['video']).name}")
        c, t, s = pending["combo"].split("|")
        driver = pending["driver"]
        caption = pending["caption"]
        final = Path(pending["video"])
        print(f"character : {c} / {t} / {s}")
        print(f"driver    : {driver}")
        print(f"caption   : {caption}")
        if args.dry:
            return 0
        if not args.post:
            print("[Reel] built already; pass --post to publish it")
            return 0
        from modules.uploader_fb_profile import post_to_profile
        result = await post_to_profile(message=caption, media_path=str(final),
                                       post=True, headless=not args.show, timeout=840)
        print(json.dumps(result, indent=2))
        ok = result.get("status") in ("ok", "uploaded")
        if ok:
            dance_cast.record_posted(c, t, s)
            dance_drivers.record_used(driver)
            pending["_manifest"].unlink(missing_ok=True)
            print(f"[Reel] recorded {c}|{t}|{s} + driver {driver}")
            if not args.no_comment:
                await seed_first_comment(caption, headless=not args.show)
        else:
            # Leave the manifest in place: the reel is paid for and unposted,
            # so the next run should try it again rather than render another.
            print("[Reel] post failed — pending reel kept for the next run")
        log({"at": datetime.now().isoformat(timespec="seconds"),
             "combo": pending["combo"], "driver": driver, "video": str(final),
             "caption": caption, "posted": ok, "from_pending": True,
             "result": result})
        return 0 if ok else 1

    c, t, s = pick_unqueued()
    undo_rollback()
    driver = pick_driver_unqueued()
    if driver is None:
        print("No prepared drivers. See modules/dance_drivers.prepare().")
        return 1

    meta = dance_drivers.DRIVERS[driver]
    caption = caption_for(c, t, s)
    stem = f"{c}_{t}_{s}_{int(time.time())}"

    print(f"character : {c} / {t} / {s}")
    print(f"driver    : {driver}  ({meta['seconds']}s, {meta['views']:,} views)")
    print(f"est. cost : ${meta['seconds'] * 0.070:.2f}")
    print(f"caption   : {caption}")
    if args.dry:
        return 0

    still = dance_cast.generate(c, t, s)
    if not still:
        print("character image failed")
        return 1

    out_url = transfer(r2_upload(Path(still)), r2_upload(dance_drivers.path_for(driver)))
    if not out_url:
        # The driver is the usual suspect - subject too small, more than one
        # figure, overlays on the dancer. Count it so the next slot does not
        # pick the same clip and fail the same way.
        dance_drivers.record_failed(driver, "transfer rejected or timed out")
        return 1

    raw = OUT_DIR / f"{stem}_raw.mp4"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(requests.get(out_url, timeout=300).content)

    # LENGTH IS THE TELL THAT THE TRANSFER ACTUALLY FOLLOWED THE DRIVER.
    #
    # The model has no duration control — output length comes from the driving
    # clip — so a good transfer lands within a fraction of a second of its
    # source. When whodis_hall came back 6.25s short of its 25.2s driver on
    # 2026-09-01, the character was barely moving: the pose track had failed
    # and the render was noise, but nothing downstream noticed and it went
    # out. Anything more than 10% adrift is not a transfer, so refuse it
    # rather than brand it and queue it.
    got = _duration(raw)
    want = meta["seconds"]
    if got and want and abs(got - want) > want * 0.10:
        print(f"[Reel] REJECTED: output {got:.1f}s vs driver {want:.1f}s "
              f"({got - want:+.1f}s). The transfer did not follow the driver — "
              f"check {driver} for overlays or smearing over the dancer.")
        raw.unlink(missing_ok=True)
        dance_drivers.record_failed(
            driver, f"output {got:.1f}s vs driver {want:.1f}s")
        return 1
    if got:
        print(f"[Reel] length check ok: {got:.1f}s vs driver {want:.1f}s")

    final = finish(raw, stem)
    raw.unlink(missing_ok=True)
    print(f"[Reel] ready: {final}")

    entry = {"at": datetime.now().isoformat(timespec="seconds"),
             "combo": f"{c}|{t}|{s}", "driver": driver,
             "video": str(final), "caption": caption, "posted": False}

    if args.queue:
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        n = len(list(PENDING_DIR.glob("*.json"))) + 1
        manifest = PENDING_DIR / f"{n:03d}-{c}-{t}-{s}.json"
        manifest.write_text(json.dumps(
            {"video": str(final), "caption": caption,
             "combo": f"{c}|{t}|{s}", "driver": driver,
             "note": f"queued {datetime.now():%Y-%m-%d %H:%M}"},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Reel] queued as {manifest.name}")
        entry["queued"] = str(manifest)
        log(entry)
        return 0

    if args.post:
        from modules.uploader_fb_profile import post_to_profile
        result = await post_to_profile(message=caption, media_path=str(final),
                                       post=True, headless=not args.show, timeout=840)
        print(json.dumps(result, indent=2))
        entry["result"] = result
        if result.get("status") in ("ok", "uploaded"):
            # Both ledgers move together, and only now.
            dance_cast.record_posted(c, t, s)
            dance_drivers.record_used(driver)
            entry["posted"] = True
            print(f"[Reel] recorded {c}|{t}|{s} + driver {driver}")
            if not args.no_comment:
                entry["comment"] = await seed_first_comment(caption, headless=not args.show)
        else:
            print("[Reel] post failed — ledgers untouched, nothing burned")

    log(entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
