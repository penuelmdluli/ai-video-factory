"""
One reel, every audience — shared publisher for the non-news formats.

build_psl_news has always fanned out to Facebook, YouTube and TikTok. The
line-up and selection-debate formats added on 2026-08-24 went to Facebook only,
which quietly threw away two thirds of their reach: the owner asked "do we also
post to YouTube?" and the answer was no. Rather than copy the fan-out into each
new builder, it lives here once.

Every channel is best-effort and independent. A dead TikTok session or a
missing YouTube token must never cost the Facebook post — that is the whole
reason each upload sits in its own try block and the result is reported per
channel instead of as one pass/fail.

    from modules.publish_reel import publish
    await publish(video, title, caption, cover, niche="sa_pulse",
                  tags=["PSL", "KaizerChiefs"])
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent

# THE SAME WORDS TWICE, 27 Aug 2026. An identical fancall caption went out to
# the page twice inside a minute — two renders, two posts, one question. It
# costs twice to make and post, and it splits the format's engagement across
# two rows, so format_intel reads the fancall as half as good as it was.
#
# _claim_manifest below stops the sweeper re-posting a BUILD. This stops the
# same MESSAGE going out twice no matter which builder wrote it: a fingerprint
# of page + format + words, kept for the lookback window and checked before
# anything is uploaded. Thirty minutes is well short of the gap between our own
# slots, so a genuine repeat of a format later in the day still posts.
DEDUPE_LOG = ROOT / "data" / "publish_dedupe.json"
DEDUPE_WINDOW_MIN = 30

# First comment on every reel. The news builder has always seeded one; the
# line-up, debate and versus formats added on 2026-08-24 did not, so the three
# best-performing posts on the page — 16k and 9.5k views, fifty fan comments
# between them — carried no follow prompt and no channel link at all.
# It is PINNED so it stays at the top as the fan replies stack up underneath.
FOLLOW_COMMENT = (
    "📲 Follow GENESIS NEWS for the team sheets before kickoff, full-time "
    "results and every big Amakhosi call." + chr(10) +
    "▶️ More on YouTube: https://www.youtube.com/@GenesisNewsPSL")


def _content_type(caption: str) -> str:
    """The format this caption belongs to, by format_intel's own signatures —
    the same labels the metrics table is keyed on ("fancall", "rollcall", ...).
    Best-effort: an unclassifiable caption still dedupes on page + words."""
    try:
        from modules.format_intel import classify
        return classify(caption)
    except Exception:
        return "other"


def _dupe_key(niche: str, content_type: str, message: str) -> str:
    """One post's fingerprint. Whitespace is collapsed so a caption rebuilt
    with a different line wrap is still recognised as the same message."""
    raw = f"{niche}|{content_type}|{' '.join((message or '').split())}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def _recent_keys() -> dict:
    """Fingerprints published inside the lookback window. Anything older is
    dropped on read, so the file never grows past half an hour of posts."""
    try:
        posted = json.loads(DEDUPE_LOG.read_text(encoding="utf-8")).get("posted", {})
        entries = list(posted.items())          # a mangled file reads as empty
    except Exception:
        return {}
    cutoff = datetime.now() - timedelta(minutes=DEDUPE_WINDOW_MIN)
    fresh = {}
    for key, ts in entries:
        try:
            if datetime.fromisoformat(ts) > cutoff:
                fresh[key] = ts
        except (TypeError, ValueError):
            continue
    return fresh


def _record_published(key: str) -> None:
    """Remember a post that actually went live. Recorded AFTER the upload, not
    before, so a failed post can be retried straight away — only something the
    page really carries can block the next attempt. Best-effort by design:
    failing to write this must never take down a post that is already live."""
    try:
        fresh = _recent_keys()
        fresh[key] = datetime.now().isoformat()
        DEDUPE_LOG.parent.mkdir(parents=True, exist_ok=True)
        DEDUPE_LOG.write_text(json.dumps({"posted": fresh}, indent=2),
                              encoding="utf-8")
    except Exception as e:
        print(f"[Publish] dedupe log not updated: {str(e)[:100]}")


async def _seed_and_pin(video_id: str, niche: str, message: str) -> str:
    """Post the first comment as the page and pin it. Returns the comment id.

    Must be the VIDEO id, not the post id — commenting on a reel's post id
    returns "(#12) singular statuses API is deprecated".
    """
    try:
        import requests
        from modules.uploader_facebook import post_comment
        res = await post_comment(video_id, message, niche)
        cid = (res or {}).get("comment_id") or (res or {}).get("id", "")
        if not cid:
            print(f"[Publish] first comment failed: {(res or {}).get('error', '')[:100]}")
            return ""
        tok = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
        r = requests.post(f"https://graph.facebook.com/v21.0/{cid}",
                          data={"is_pinned": "true", "access_token": tok},
                          timeout=30)
        pinned = r.status_code == 200 and (r.json() or {}).get("success") is True
        print(f"[Publish] first comment {'pinned' if pinned else 'posted (pin failed)'}")
        return cid
    except Exception as e:
        print(f"[Publish] first comment skipped: {str(e)[:110]}")
        return ""


async def publish(video_path, title: str, caption: str, cover_path=None,
                  niche: str = "sa_pulse", tags=None,
                  first_comment: str = "") -> dict:
    """Post one vertical reel to Facebook, YouTube and TikTok. Returns a
    per-channel result; callers should log it rather than assume success."""
    tags = tags or []
    video_path, cover_path = str(video_path), (str(cover_path) if cover_path else None)
    out = {}

    # Same page, same format, same words in the last half hour — refuse before
    # a single channel is touched, so nothing is half-posted.
    content_type = _content_type(caption)
    dupe_key = _dupe_key(niche, content_type, caption)
    if dupe_key in _recent_keys():
        print(f"[Publish] DUPLICATE — this {content_type} caption already went "
              f"out on {niche} within {DEDUPE_WINDOW_MIN} min, not posting again")
        return {ch: {"status": "skipped", "error": "duplicate"}
                for ch in ("facebook", "youtube", "tiktok")}

    # ── Facebook ────────────────────────────────────────────────────────
    try:
        from modules.uploader_facebook import upload_to_facebook
        fb = await upload_to_facebook(video_path, title, caption, niche,
                                      is_reel=True, thumbnail_path=cover_path)
        out["facebook"] = fb
        print(f"[Publish] Facebook: {(fb or {}).get('status')} "
              f"{(fb or {}).get('post_id', '')}")
        vid = (fb or {}).get("video_id", "")
        if vid:
            await _seed_and_pin(vid, niche, first_comment or FOLLOW_COMMENT)
    except Exception as e:
        out["facebook"] = {"status": "failed", "error": str(e)[:120]}
        print(f"[Publish] Facebook failed: {str(e)[:120]}")

    # ── YouTube ─────────────────────────────────────────────────────────
    token = Path("tokens") / f"youtube_token_{niche}.json"
    if token.exists():
        try:
            from modules.uploader_youtube import upload_to_youtube
            yt = await upload_to_youtube(
                video_path=video_path, title=title[:95], description=caption,
                tags=tags, niche=niche, thumbnail_path=cover_path,
                is_short=True)
            out["youtube"] = yt
            vid = (yt or {}).get("video_id", "")
            print(f"[Publish] YouTube: {(yt or {}).get('status')} {vid}")
            if vid:
                try:
                    from modules.playlists import add_youtube
                    add_youtube(vid, shorts=True)
                except Exception as e:
                    print(f"[Publish] playlist skipped: {str(e)[:80]}")
        except Exception as e:
            out["youtube"] = {"status": "failed", "error": str(e)[:120]}
            print(f"[Publish] YouTube failed: {str(e)[:120]}")
    else:
        out["youtube"] = {"status": "skipped", "error": "no channel token"}
        print(f"[Publish] YouTube skipped — no token at {token}")

    # ── TikTok ──────────────────────────────────────────────────────────
    try:
        from modules.uploader_tiktok import upload_to_tiktok
        tt = await upload_to_tiktok(video_path=video_path,
                                    description=caption[:150],
                                    hashtags=tags[:5], niche=niche)
        out["tiktok"] = tt
        print(f"[Publish] TikTok: {(tt or {}).get('status')}")
    except Exception as e:
        out["tiktok"] = {"status": "failed", "error": str(e)[:120]}
        print(f"[Publish] TikTok skipped: {str(e)[:120]}")

    live = [k for k, v in out.items() if (v or {}).get("status") == "uploaded"]
    print(f"[Publish] live on: {', '.join(live) if live else 'NOTHING'}")
    if live:
        _record_published(dupe_key)
        _claim_manifest(video_path)
    return out


def _claim_manifest(video_path) -> None:
    """Mark this build's manifest as already posted.

    THE DUPLICATE-POST BUG, 6 Sep 2026. Every Genesis builder writes an
    upload_manifest.json next to its video BEFORE posting, and none of them
    ever came back to update it. main.py sweeps output/*/upload_manifest.json
    and uploads anything built today whose `uploaded` flag is falsy - so the
    MATCHDAY reel went out at 06:36 from build_matchday_hype and AGAIN at
    07:11 from the sweeper, because as far as the manifest was concerned it
    had never been posted.

    The second copy was also the one with the broken emoji, since the sweeper
    read the manifest with the wrong codec (fixed separately in main.py). So
    the page got the same reel twice, and the duplicate was the ugly one.

    Claiming the manifest here rather than in each builder means every caller
    of publish() is covered by one change, including the ones written next.
    Best-effort by design: failing to write this flag must never take down a
    post that has already gone live.
    """
    try:
        import json
        from pathlib import Path
        mp = Path(video_path).parent / "upload_manifest.json"
        if not mp.exists():
            return
        m = json.loads(mp.read_text(encoding="utf-8"))
        m["uploaded"] = True
        m["uploaded_by"] = "publish_reel"
        mp.write_text(json.dumps(m, indent=2, ensure_ascii=False),
                      encoding="utf-8")
        print(f"[Publish] manifest claimed - the sweeper will skip {mp.parent.name}")
    except Exception as e:
        print(f"[Publish] could not claim manifest: {str(e)[:100]}")
