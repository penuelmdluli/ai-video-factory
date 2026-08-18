"""
Mzansi Careers publisher — posts a VERIFIED job opportunity as BOTH a
static card (image post) and a voiced reel, to Facebook + YouTube, with a
follow-up comment carrying the official apply guidance.

House rules (non-negotiable):
  * Only official employer / government sources. Aggregator text is never
    copied — we link people to the employer's own portal.
  * Every post carries the closing date and "no fees, ever".
  * Photo credit + licence shown on the card and in the caption.

Usage:  python build_careers_post.py            (posts the queued job)
        python build_careers_post.py --card-only
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
# Claim the page lock: this page is Mzansi Careers, and only this script
# (plus the careers feed) may post to it.
import os  # noqa: E402
os.environ["PAGE_LOCK_OWNER"] = "build_careers_post.py"
sys.path.insert(0, str(Path(__file__).parent))

from modules.careers_kit import job_alert, make_job_card  # noqa: E402
from modules.thumb_engine import make_reel_cover, make_thumb  # noqa: E402
from modules.uploader_facebook import (  # noqa: E402
    post_comment, upload_photo, upload_to_facebook)

NICHE = "motivation"          # Elevate You page/channel → Mzansi Careers
OUT = Path("output")
STATE = Path("data/careers_posted.json")


def _posted() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _mark(key: str, payload: dict):
    st = _posted()
    st[key] = payload
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def build_caption(job: dict) -> str:
    lines = [
        f"🚨 JOB ALERT — {job['employer'].upper()}",
        "",
        job["programme"],
        "",
    ]
    for d in job["card_details"]:
        lines.append(f"✅ {d}")
    lines += [
        "",
        f"🗓️ CLOSING DATE: {job['closes_full']}",
        "",
        "HOW TO APPLY",
    ]
    for step in job["apply_steps"]:
        lines.append(f"• {step}")
    lines += [
        "",
        "⚠️ You never pay to apply. Anyone asking for money is a scam.",
        "",
        "We only post opportunities we verify on the employer's own site.",
        "Follow Mzansi Careers for verified SA jobs, learnerships and "
        "internships — every day.",
        "",
        job.get("photo_credit", ""),
        "",
        "#MzansiCareers #SAJobs #Learnership #Internship #YouthEmployment "
        f"#{job['employer'].replace(' ', '')}",
    ]
    return "\n".join(x for x in lines if x is not None)


def build_comment(job: dict) -> str:
    return (
        f"📌 APPLY HERE (official {job['employer']} portal only):\n"
        f"{job['apply_url']}\n\n"
        f"Closing {job['closes_full']}. Have your ID, CV and academic "
        "record ready as PDFs before you start — the portal times out.\n\n"
        "Tag someone who needs this 👇"
    )


JOB = {
    "key": "transnet-wil-2026",
    "employer": "TRANSNET",
    "programme": "Work Integrated Learning Programme",
    "card_details": [
        "18-month programme with a stipend",
        "TVET students & graduates (N4–N6)",
        "Cape Town · Saldanha · Durban · Ngqura · PE",
        "Engineering, logistics & procurement fields",
    ],
    "reel_details": ("18 months", "TVET N4-N6", "5 coastal cities"),
    "closes": "24 AUGUST",
    "closes_full": "24 August 2026",
    "closes_card": "CLOSES 24 AUGUST 2026",
    "days_left": 7,
    "apply_url": "https://www.transnet.net/Careers/",
    "apply_steps": [
        "Go to the official Transnet careers portal (link in the comments)",
        "Search 'Work Integrated Learning' and pick your city",
        "Upload your ID, CV and latest academic record",
        "Submit before the closing date — late applications are rejected",
    ],
    "source": "Verified on the official Transnet careers portal",
    "hook": "Transnet is hiring",
    "kicker": "TVET students & graduates",
    "focus": 0.62,
    "bg_photo": "assets/careers_transnet_bg.jpg",
    "photo_credit": "photo: Bob Adams (CC BY-SA 2.0, Wikimedia)",
    "yt_title": "TRANSNET Work Integrated Learning 2026 — TVET students & "
                "graduates | Closes 24 August",
    "yt_tags": ["transnet", "sa jobs", "learnership", "internship",
                "tvet", "mzansi careers", "south africa jobs", "wil"],
}


async def publish(job: dict, video_path: str | None, card_only=False):
    # HARD GATE. A dead link or an unverifiable claim stops the post — on a
    # page selling "verified", one wrong closing date costs more trust than
    # a week of good posts earns.
    from modules.link_check import gate
    verdict = gate(job)
    if not verdict["ok"]:
        print(f"[Careers] BLOCKED — {verdict['reason']}")
        return {"blocked": verdict}
    print(f"[Careers] verified: {verdict['link']['final']}")

    caption = build_caption(job)
    comment = build_comment(job)
    results = {}

    card = make_job_card(
        OUT / f"careers_{job['key']}_card.png",
        employer=job["employer"], programme=job["programme"],
        details=job["card_details"], closes=job["closes_card"],
        apply_line=f"Apply FREE on the official {job['employer'].title()} "
                   "careers portal",
        bg_photo=job.get("bg_photo"),
        photo_credit=job.get("photo_credit", ""))
    print(f"[Careers] card: {card}")

    r = await upload_photo(card, caption, NICHE)
    print(f"[Careers] FB card: {r}")
    results["fb_card"] = r
    pid = r.get("post_id") or r.get("id")
    if pid:
        await post_comment(pid, comment, NICHE)

    if card_only or not video_path:
        return results

    # Covers. Without these Facebook and YouTube each grab a random mid-video
    # frame — a letterboxed vertical clip that reads as nothing in a feed.
    hook = job.get("hook") or f"{job['employer'].title()} is hiring"
    # 9:16 — a reel cover that is not the video's aspect gets cropped by
    # Facebook and reads as the wrong size.
    fb_cover = make_reel_cover(OUT / f"careers_{job['key']}_cover.jpg",
                               hook=hook, kicker=job.get("kicker", ""),
                               chip=f"closes {job['closes'].title()}",
                               photo=job.get("bg_photo"), brand="careers",
                               focus=job.get("focus", 0.55))
    yt_thumb = make_thumb(OUT / f"careers_{job['key']}_thumb.jpg",
                          hook=hook, kicker=job.get("kicker", ""),
                          chip=f"{job['days_left']} days left",
                          photo=job.get("bg_photo"), brand="careers",
                          focus=job.get("focus", 0.66))
    print(f"[Careers] covers: {fb_cover} | {yt_thumb}")

    r2 = await upload_to_facebook(
        video_path=str(video_path),
        title=job["yt_title"][:90],
        description=caption,
        niche=NICHE, is_reel=True, thumbnail_path=fb_cover)
    print(f"[Careers] FB reel: {r2}")
    results["fb_reel"] = r2
    vid = r2.get("video_id") or r2.get("post_id")
    if vid:
        await post_comment(vid, comment, NICHE)

    try:
        from modules.uploader_youtube import upload_to_youtube
        r3 = await upload_to_youtube(
            video_path=str(video_path), title=job["yt_title"],
            description=caption, tags=job["yt_tags"], niche=NICHE,
            is_short=True, privacy="public", thumbnail_path=yt_thumb)
        print(f"[Careers] YouTube: {r3}")
        results["youtube"] = r3
        vid3 = r3.get("video_id")
        if vid3:
            try:
                from modules.uploader_youtube import _get_youtube_service
                yt = _get_youtube_service(NICHE)
                yt.commentThreads().insert(part="snippet", body={
                    "snippet": {"videoId": vid3, "topLevelComment": {
                        "snippet": {"textOriginal": comment}}}}).execute()
                print("[Careers] YouTube comment seeded")
            except Exception as e:
                print(f"[Careers] YT comment failed: {e}")
    except Exception as e:
        print(f"[Careers] YouTube failed: {e}")

    _mark(job["key"], {
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "results": {k: v.get("post_id") or v.get("video_id") or v.get("url")
                    for k, v in results.items() if isinstance(v, dict)},
    })
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card-only", action="store_true")
    ap.add_argument("--video", default="output/careers_transnet_voiced.mp4")
    a = ap.parse_args()
    v = Path(a.video)
    asyncio.run(publish(JOB, v if v.exists() else None,
                        card_only=a.card_only))


if __name__ == "__main__":
    main()
