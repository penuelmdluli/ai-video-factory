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
import os
from pathlib import Path

# First comment on every reel. The news builder has always seeded one; the
# line-up, debate and versus formats added on 2026-08-24 did not, so the three
# best-performing posts on the page — 16k and 9.5k views, fifty fan comments
# between them — carried no follow prompt and no channel link at all.
# It is PINNED so it stays at the top as the fan replies stack up underneath.
FOLLOW_COMMENT = (
    "📲 Follow GENESIS NEWS for the team sheets before kickoff, full-time "
    "results and every big Amakhosi call." + chr(10) +
    "▶️ More on YouTube: https://www.youtube.com/@GenesisNewsPSL")


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
