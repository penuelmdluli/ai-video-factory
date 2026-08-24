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
from pathlib import Path


async def publish(video_path, title: str, caption: str, cover_path=None,
                  niche: str = "sa_pulse", tags=None) -> dict:
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
    return out
