"""
AI Video Factory — Two-Phase Smart Scheduler

Two-phase scheduling: BUILD videos 3 hours before UPLOAD time.
This ensures videos are ready and uploaded exactly at optimal posting times.

Schedule (daily, all 6 niches):
    BUILD 6:00 AM  -> UPLOAD 8:00 AM   (shorts)
    BUILD 12:00 PM -> UPLOAD 2:00 PM   (shorts)
    BUILD 6:00 PM  -> UPLOAD 8:00 PM   (shorts)

Features:
- Build phase: Generate video content (script, voice, visuals, assembly)
- Upload phase: Upload pre-built videos to all platforms
- Per-niche failure retry with exponential backoff
- Day-of-week optimization (Thu-Sun weighted higher)
- Email alerts on failures (if configured)

Usage:
    python scheduler.py              # Start the scheduler daemon
    python scheduler.py --once       # Run one full build+upload cycle and exit
    python scheduler.py --build      # Run build phase only (all formats)
    python scheduler.py --upload     # Run upload phase only (pre-built videos)
    python scheduler.py --status     # Show schedule status
    python scheduler.py --optimize   # Show optimal posting times from data
"""
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — prevent tkinter crash in async pipeline

import asyncio
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    NICHES, SCHEDULE, ENABLE_NICHE_PRIORITIZATION,
    ENABLE_ENGAGEMENT_POSTS, ENABLE_BLOG_PROMO, ENGAGEMENT_HOURS, ENGAGEMENT_CONTENT_TYPES,
    ENABLE_GROWTH_ENGINE, COMMUNITY_CHECK_HOURS,
    INSIGHTS_COLLECTION_HOUR, CROSS_PROMO_HOUR, GROWTH_REPORT_HOUR,
)

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
SCHEDULE_LOG = LOG_DIR / "schedule_log.json"


# ── Schedule Configuration ────────────────────────────────
# QUALITY OVER QUANTITY — war-news short in the morning AND later the same day.
# Build a couple hours ahead, upload at prime times.

# The quality pipeline (SVD 15 steps + GFPGAN/ESRGAN enhance) takes ~2.5 hr/video,
# so build must start well before the upload slot or the clip won't be ready in time.
BUILD_LEAD_HOURS = 2

# 2 upload slots per day: early morning + evening prime time.
UPLOAD_HOURS = [7, 18]   # 7 AM (morning) and 6 PM (evening)

# Build 2 hours before each upload — plenty for the ~30 min Wan render
BUILD_HOURS = [h - BUILD_LEAD_HOURS for h in UPLOAD_HOURS]   # 5 AM, 4 PM

# Two daily slots (both short-form)
SLOT_FORMATS = {
    0: "short",   # 5 AM build -> 7 AM upload (morning)
    1: "short",   # 4 PM build -> 6 PM upload (evening prime time)
}

# Readable slot names for logging
SLOT_NAMES = {
    0: "Morning War Brief",
    1: "Evening War Brief",
}


# ── Platform-Specific Optimal Posting Times (reference) ──
# Kept for performance tracking and optimization data.
OPTIMAL_POST_HOURS = {
    "facebook": {
        "ai_money": [8, 12, 17],
        "tech_news": [9, 13, 18],
        "motivation": [6, 7, 8],
        "health_wellness": [7, 12, 18],
        "blissful_moments": [7, 19, 21],
        "daily_breakdown": [8, 13, 18],
        "shopmo_products": [9, 14, 19],
        "limitless_you": [7, 12, 19],
    },
    "tiktok": {
        "ai_money": [8, 13, 20],
        "tech_news": [9, 14, 20],
        "motivation": [6, 7, 20],
        "health_wellness": [7, 11, 19],
        "blissful_moments": [8, 19, 21],
        "daily_breakdown": [8, 14, 20],
        "shopmo_products": [9, 15, 20],
        "limitless_you": [7, 13, 20],
    },
    "youtube": {
        "ai_money": [9, 15, 19],
        "tech_news": [10, 15, 19],
        "motivation": [5, 6, 7],
        "health_wellness": [8, 12, 18],
        "blissful_moments": [9, 18, 20],
        "daily_breakdown": [9, 15, 19],
        "shopmo_products": [10, 15, 20],
        "limitless_you": [6, 12, 19],
    },
    "instagram": {
        "ai_money": [10, 14, 20],
        "tech_news": [11, 15, 19],
        "motivation": [7, 12, 18],
        "health_wellness": [8, 12, 19],
        "blissful_moments": [9, 18, 21],
        "daily_breakdown": [10, 14, 19],
        "shopmo_products": [11, 15, 20],
        "limitless_you": [7, 13, 19],
    },
}

# Day-of-week weights (higher = more content that day)
DAY_WEIGHTS = {
    "Monday": 0.8,
    "Tuesday": 0.8,
    "Wednesday": 0.9,
    "Thursday": 1.0,
    "Friday": 1.1,
    "Saturday": 1.2,
    "Sunday": 1.1,
}


# ── Schedule Log Helpers ─────────────────────────────────

def load_schedule_log() -> dict:
    if SCHEDULE_LOG.exists():
        try:
            return json.loads(SCHEDULE_LOG.read_text())
        except Exception:
            pass
    return {}


def save_schedule_log(log: dict):
    SCHEDULE_LOG.write_text(json.dumps(log, indent=2))


def get_today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_phase_key(niche: str, slot: int, phase: str) -> str:
    """Generate a unique key for tracking build/upload per slot."""
    fmt = SLOT_FORMATS[slot]
    return f"{niche}_{phase}_{fmt}_slot{slot}"


def already_done_today(niche: str, slot: int, phase: str) -> bool:
    """Check if a niche/slot/phase already completed today."""
    log = load_schedule_log()
    today = get_today_key()
    key = get_phase_key(niche, slot, phase)
    entry = log.get(today, {}).get(key, {})
    return entry.get("status") in ("success", "built", "uploaded")


def mark_phase_done(niche: str, slot: int, phase: str, result: dict):
    """Mark a phase as done for today."""
    log = load_schedule_log()
    today = get_today_key()
    if today not in log:
        log[today] = {}
    key = get_phase_key(niche, slot, phase)
    log[today][key] = {
        "status": result.get("status", "unknown"),
        "title": result.get("title", ""),
        "completed_at": datetime.now().isoformat(),
        "retry_count": log.get(today, {}).get(key, {}).get("retry_count", 0),
    }
    save_schedule_log(log)


def should_retry(niche: str, slot: int, phase: str, max_retries: int = 3) -> bool:
    log = load_schedule_log()
    today = get_today_key()
    key = get_phase_key(niche, slot, phase)
    entry = log.get(today, {}).get(key, {})

    if entry.get("status") in ("success", "built", "uploaded"):
        return False
    if entry.get("status") == "error":
        return entry.get("retry_count", 0) < max_retries
    return True  # Never ran


def increment_retry(niche: str, slot: int, phase: str):
    log = load_schedule_log()
    today = get_today_key()
    key = get_phase_key(niche, slot, phase)
    if today not in log:
        log[today] = {}
    if key not in log[today]:
        log[today][key] = {}
    log[today][key]["retry_count"] = log[today][key].get("retry_count", 0) + 1
    save_schedule_log(log)


# ── Legacy helpers (kept for show_status compatibility) ──

def already_ran_today(niche: str, format_type: str) -> bool:
    log = load_schedule_log()
    today = get_today_key()
    key = f"{niche}_{format_type}"
    if today in log and key in log[today]:
        return log[today][key].get("status") == "success"
    return False


def get_optimal_hour_for_niche(niche: str) -> int:
    try:
        from modules.performance_tracker import get_best_posting_hours
        learned_hours = get_best_posting_hours(niche)
        if learned_hours:
            current_hour = datetime.now().hour
            future_hours = [h for h in learned_hours if h >= current_hour]
            if future_hours:
                return future_hours[0]
            return learned_hours[0]
    except Exception:
        pass

    defaults = OPTIMAL_POST_HOURS.get("facebook", {}).get(niche, [9, 14, 19])
    current_hour = datetime.now().hour
    future = [h for h in defaults if h >= current_hour]
    return future[0] if future else defaults[0]


# ── Engagement Phase ────────────────────────────────────

def already_posted_engagement(niche: str, slot_hour: int) -> bool:
    """Check if engagement was already posted for this niche/hour today."""
    log = load_schedule_log()
    today = get_today_key()
    key = f"{niche}_engagement_h{slot_hour}"
    entry = log.get(today, {}).get(key, {})
    return entry.get("status") == "posted"


def mark_engagement_done(niche: str, slot_hour: int, result: dict):
    """Mark an engagement post as done for today."""
    log = load_schedule_log()
    today = get_today_key()
    if today not in log:
        log[today] = {}
    key = f"{niche}_engagement_h{slot_hour}"
    log[today][key] = {
        "status": "posted" if result.get("success") else "failed",
        "type": result.get("content_type", ""),
        "completed_at": datetime.now().isoformat(),
    }
    save_schedule_log(log)


def _run_blog_promo(slot_hour: int):
    """Post a ROTATING blog-article link to each Facebook page at the engagement
    slot — drives traffic to our owned blog (SEO + AdSense) instead of throwaway
    tip images. A different article each slot/day, so it never spams the same link."""
    import json, os, urllib.request, urllib.parse
    from pathlib import Path
    SITE_URL = os.getenv("BLOG_URL", "https://blog.genesisstudio.app").rstrip("/")
    GRAPH = "https://graph.facebook.com/v19.0"
    # blog niche -> FB page key  (mirror of blog/cross_post_fb.py FB_NICHE)
    FB_NICHE = {"kids": "blissful_moments", "news": "tech_news",
                "study": "limitless_you", "sleep": "limitless_you", "coding": "limitless_you",
                "wellness": "health_wellness", "sa": "sa_pulse"}
    BLURB = {"kids": "New on our blog for parents 👶", "news": "Fresh explainer on our blog 🌍",
             "study": "New focus & study tips on our blog 🎧", "sleep": "Sleep better — new guide 🌙",
             "coding": "For the coders — new post 💻", "wellness": "New organic-living tips 🌿",
             "sa": "New on Genesis News — South Africa, explained 🇿🇦"}
    state = Path("blog/state.json")
    if not state.exists():
        print("[BlogPromo] no blog/state.json — run the blog generator first"); return []
    posts = json.loads(state.read_text(encoding="utf-8")).get("posts", [])
    by_page = {}
    for p in posts:
        key = FB_NICHE.get(p.get("niche", ""))
        if key:
            by_page.setdefault(key, []).append(p)
    try:
        slot_idx = ENGAGEMENT_HOURS.index(slot_hour)
    except ValueError:
        slot_idx = 0
    yday = datetime.now().timetuple().tm_yday
    results = []
    for key, arts in by_page.items():
        pid = os.getenv(f"FB_PAGE_ID_{key}", ""); tok = os.getenv(f"FB_PAGE_TOKEN_{key}", "")
        if not pid or not tok:
            continue
        if already_posted_engagement(key, slot_hour):
            continue
        # Pick a rotating article that is actually LIVE (blog deploy can lag, and a
        # dead link would hurt the page). Use a browser UA — Cloudflare 403s bare
        # bot requests (Facebook's scraper is allowed, so live links post fine).
        _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120 Safari/537.36")
        art = None; url = None
        n = len(arts)
        for off in range(n):
            cand = arts[(yday * len(ENGAGEMENT_HOURS) + slot_idx + off) % n]
            cand_url = f"{SITE_URL}/posts/{cand['slug']}"
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(cand_url, headers={"User-Agent": _UA}), timeout=15) as hr:
                    if getattr(hr, "status", 200) == 200:
                        art, url = cand, cand_url; break
            except Exception:
                continue
        if not art:
            print(f"[BlogPromo] {key}: no live article yet — skip"); continue
        msg = f"{BLURB.get(art.get('niche', ''), 'New on our blog')}\n\n{art['title']}\n\n{url}"
        data = urllib.parse.urlencode({"message": msg, "link": url, "access_token": tok}).encode()
        try:
            req = urllib.request.Request(f"{GRAPH}/{pid}/feed", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode())
            print(f"[BlogPromo] {key}: {art['slug']} -> {res.get('id')}")
            mark_engagement_done(key, slot_hour, {"niche": key, "success": True, "blog": art["slug"]})
            results.append({"niche": key, "success": True})
        except Exception as e:
            print(f"[BlogPromo] {key} failed: {str(e)[:140]}")
            results.append({"niche": key, "success": False})
    print(f"[BlogPromo] slot {slot_hour}:00 — {sum(1 for r in results if r['success'])}/{len(results)} blog links posted")
    return results


async def run_engagement_phase(slot_hour: int | None = None):
    """
    Run engagement posts for all configured Facebook pages.

    Args:
        slot_hour: The engagement hour slot. None = auto-detect.
    """
    if slot_hour is None:
        slot_hour = datetime.now().hour

    # Post blog links first, then engagement posts for any pages the blog didn't cover.
    blog_results = []
    blog_covered_pages = set()
    if ENABLE_BLOG_PROMO:
        blog_results = _run_blog_promo(slot_hour)
        # Track which FB pages got a blog link
        FB_NICHE_MAP = {"kids": "blissful_moments", "news": "tech_news",
                        "study": "limitless_you", "sleep": "limitless_you", "coding": "limitless_you",
                        "wellness": "health_wellness", "sa": "sa_pulse"}
        blog_covered_pages = set(FB_NICHE_MAP.values())

    if not ENABLE_ENGAGEMENT_POSTS:
        if blog_results:
            return blog_results
        print("[Engagement] Disabled via ENABLE_ENGAGEMENT_POSTS=false")
        return []

    from modules.engagement_poster import run_engagement_round

    if slot_hour is None:
        slot_hour = datetime.now().hour

    # Determine content type based on slot index
    try:
        slot_idx = ENGAGEMENT_HOURS.index(slot_hour)
    except ValueError:
        slot_idx = slot_hour % len(ENGAGEMENT_CONTENT_TYPES)

    content_type = ENGAGEMENT_CONTENT_TYPES[slot_idx % len(ENGAGEMENT_CONTENT_TYPES)]

    # Post engagement to ALL pages that didn't get a blog link AND haven't been posted yet
    import os
    niches = [n for n in NICHES.keys()
              if os.getenv(f"FB_PAGE_ID_{n}", "")
              and n not in blog_covered_pages
              and not already_posted_engagement(n, slot_hour)]

    if not niches:
        if blog_results:
            print(f"[Engagement] Blog promo covered all pages for hour {slot_hour}")
            return blog_results
        print(f"[Engagement] All niches already posted for hour {slot_hour}")
        return []

    print(f"\n{'#'*60}")
    print(f"# ENGAGEMENT PHASE — {content_type.upper()} posts")
    print(f"# Hour: {slot_hour}:00 | Niches: {len(niches)} (uncovered by blog)")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")

    results = await run_engagement_round(niches=niches, content_type=content_type)

    for r in results:
        niche = r.get("niche", "")
        if niche:
            mark_engagement_done(niche, slot_hour, r)

    posted = sum(1 for r in results if r.get("success"))
    print(f"\n[Engagement] Phase complete: {posted}/{len(results)} engagement + {len(blog_results)} blog posted")
    return blog_results + results


# ── Build Phase ──────────────────────────────────────────

async def run_build_phase(slot: int | None = None):
    """
    BUILD phase: Generate videos for all niches (without uploading).
    Videos are saved with upload_manifest.json for later upload.

    When ENABLE_NICHE_PRIORITIZATION is on, niches are built in order
    of trend heat (hottest first), so the most important content is
    always produced even if time/resources run out.

    Args:
        slot: Specific slot index (0, 1, 2) or None for all slots.
    """
    from main import create_video

    slots_to_build = [slot] if slot is not None else list(SLOT_FORMATS.keys())
    results = []

    # Determine niche build order
    niche_order = list(NICHES.keys())
    heat_info = ""

    if ENABLE_NICHE_PRIORITIZATION:
        try:
            from modules.niche_prioritizer import rank_niches_by_heat, get_niche_order_for_slot
            rankings = await rank_niches_by_heat()
            if rankings:
                niche_order = get_niche_order_for_slot(rankings)
                top3 = [(r["niche"], r["heat_score"]) for r in rankings[:3]]
                heat_info = f"  Niche priority: {', '.join(f'{n} ({s:.0f})' for n, s in top3)}"

                # Log heat scores
                log = load_schedule_log()
                today = get_today_key()
                if today not in log:
                    log[today] = {}
                log[today]["_niche_heat"] = {
                    r["niche"]: {"heat_score": r["heat_score"], "top_trend": r.get("top_trend", "")}
                    for r in rankings
                }
                save_schedule_log(log)
        except Exception as e:
            print(f"[Scheduler] Niche prioritization failed (using default order): {e}")

    # Single-page mode: only build the active page(s) (default: Tech Pulse Africa).
    try:
        from config import BUILD_NICHES
        filtered = [n for n in niche_order if n in BUILD_NICHES]
        if filtered:
            niche_order = filtered
            print(f"[Scheduler] Single-page build: {', '.join(niche_order)}")
    except Exception:
        pass

    for s in slots_to_build:
        fmt = SLOT_FORMATS[s]
        upload_hour = UPLOAD_HOURS[s]
        build_hour = BUILD_HOURS[s]

        print(f"\n{'#'*60}")
        print(f"# BUILD PHASE — {SLOT_NAMES[s]}")
        print(f"# Format: {fmt} | Build: {build_hour}:00 | Upload: {upload_hour}:00")
        print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if heat_info:
            print(f"#{heat_info}")
        print(f"{'#'*60}\n")

        for niche in niche_order:
            if niche not in NICHES:
                continue
            if already_done_today(niche, s, "build"):
                print(f"[SKIP] {niche} {fmt} — already built today")
                continue
            if not should_retry(niche, s, "build"):
                print(f"[SKIP] {niche} {fmt} — max retries reached")
                continue

            print(f"\n[BUILD] {niche} | {fmt}")
            try:
                result = await create_video(niche, fmt, dry_run=False, build_only=True)
                results.append(result)

                if result["status"] == "built":
                    mark_phase_done(niche, s, "build", result)
                    print(f"[OK] {niche} {fmt}: built — {result.get('title', '')[:50]}")
                else:
                    print(f"[FAIL] {niche} {fmt}: {result.get('error', 'unknown')}")
                    mark_phase_done(niche, s, "build", {"status": "error", "error": result.get("error")})
                    increment_retry(niche, s, "build")
            except Exception as e:
                print(f"[ERROR] {niche} {fmt}: {e}")
                mark_phase_done(niche, s, "build", {"status": "error", "error": str(e)})
                increment_retry(niche, s, "build")

            await asyncio.sleep(10)

    built = sum(1 for r in results if r.get("status") == "built")
    failed = sum(1 for r in results if r.get("status") == "error")

    print(f"\n{'='*60}")
    print(f"BUILD PHASE COMPLETE — Built: {built} | Failed: {failed}")
    print(f"{'='*60}\n")

    if failed > 0:
        await _send_alert(f"AI Video Factory BUILD: {failed} failures")

    return results


# ── Upload Phase ─────────────────────────────────────────

async def run_upload_phase():
    """
    UPLOAD phase: Upload all pre-built videos that haven't been uploaded yet.
    Reads upload_manifest.json files from output directories.
    """
    from main import upload_prebuilt_videos

    print(f"\n{'#'*60}")
    print(f"# UPLOAD PHASE — Uploading pre-built videos")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")

    # most_recent_only: post just the newest un-posted video per niche/format so an
    # upload run never fires multiple videos to the same page back-to-back.
    results = await upload_prebuilt_videos(most_recent_only=True)

    uploaded = sum(1 for r in results if r.get("status") == "uploaded")
    failed = sum(1 for r in results if r.get("status") == "failed")

    print(f"\n{'='*60}")
    print(f"UPLOAD PHASE COMPLETE — Uploaded: {uploaded} | Failed: {failed}")
    print(f"{'='*60}\n")

    if failed > 0:
        await _send_alert(f"AI Video Factory UPLOAD: {failed} failures")

    return results


# ── Combined Cycle (for --once) ──────────────────────────

async def run_full_cycle():
    """Run a complete build + upload cycle for all slots."""
    print(f"\n{'#'*60}")
    print(f"# AI Video Factory — Full Build + Upload Cycle")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# Day: {datetime.now().strftime('%A')} (weight: {DAY_WEIGHTS.get(datetime.now().strftime('%A'), 1.0)})")
    print(f"{'#'*60}\n")

    build_results = await run_build_phase()
    upload_results = await run_upload_phase()

    total_built = sum(1 for r in build_results if r.get("status") == "built")
    total_uploaded = sum(1 for r in upload_results if r.get("status") == "uploaded")

    print(f"\n{'='*60}")
    print(f"FULL CYCLE COMPLETE")
    print(f"  Built: {total_built} | Uploaded: {total_uploaded}")
    print(f"{'='*60}\n")


# ── Alert System ─────────────────────────────────────────

async def _send_alert(message: str):
    try:
        from config import ALERT_EMAIL
        import os
        if not ALERT_EMAIL:
            return

        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")

        if not all([smtp_host, smtp_user, smtp_pass]):
            print(f"[Alert] Would send: {message} (SMTP not configured)")
            return

        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(f"{message}\n\nTimestamp: {datetime.now().isoformat()}")
        msg["Subject"] = message
        msg["From"] = smtp_user
        msg["To"] = ALERT_EMAIL

        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[Alert] Email sent to {ALERT_EMAIL}")

    except Exception as e:
        print(f"[Alert] Failed to send alert: {e}")


# ── Two-Phase Scheduler Loop ────────────────────────────

async def _run_engagement_background(eng_hour: int):
    """Run engagement phase in the background so it doesn't block build/upload."""
    try:
        await run_engagement_phase(eng_hour)
    except Exception as e:
        print(f"[Scheduler] Engagement failed (hour {eng_hour}): {e}")


# ── Growth Engine Phase ────────────────────────────────────

async def _check_and_run_growth(completed_phases: set, today: str):
    """
    Check for growth engine phases that should run NOW.

    Growth phases:
    - Insights collection: 6 AM daily
    - Community management: every 2 hours (8-20)
    - Cross-promotion: 11 AM daily
    - Growth report: 10 PM daily
    """
    if not ENABLE_GROWTH_ENGINE:
        return

    current_hour = datetime.now().hour

    # Insights collection
    if current_hour == INSIGHTS_COLLECTION_HOUR:
        phase_key = (today, INSIGHTS_COLLECTION_HOUR, "growth_insights", 0)
        if phase_key not in completed_phases:
            print(f"\n[Growth] {datetime.now().strftime('%H:%M')} — Collecting page insights")
            try:
                from modules.growth_engine import run_growth_cycle
                await run_growth_cycle(["insights"])
            except Exception as e:
                print(f"[Growth] Insights collection failed: {e}")
            completed_phases.add(phase_key)

    # Community management (every 2 hours during active hours)
    if current_hour in COMMUNITY_CHECK_HOURS:
        phase_key = (today, current_hour, "growth_community", 0)
        if phase_key not in completed_phases:
            print(f"\n[Growth] {datetime.now().strftime('%H:%M')} — Community management round")
            try:
                from modules.growth_engine import run_growth_cycle
                await run_growth_cycle(["community"])
            except Exception as e:
                print(f"[Growth] Community management failed: {e}")
            completed_phases.add(phase_key)

    # Cross-promotion
    if current_hour == CROSS_PROMO_HOUR:
        phase_key = (today, CROSS_PROMO_HOUR, "growth_crosspromo", 0)
        if phase_key not in completed_phases:
            print(f"\n[Growth] {datetime.now().strftime('%H:%M')} — Cross-page promotion")
            try:
                from modules.growth_engine import run_growth_cycle
                await run_growth_cycle(["cross_promo"])
            except Exception as e:
                print(f"[Growth] Cross-promotion failed: {e}")
            completed_phases.add(phase_key)

    # Daily growth report
    if current_hour == GROWTH_REPORT_HOUR:
        phase_key = (today, GROWTH_REPORT_HOUR, "growth_report", 0)
        if phase_key not in completed_phases:
            print(f"\n[Growth] {datetime.now().strftime('%H:%M')} — Daily growth report")
            try:
                from modules.growth_engine import run_growth_cycle
                await run_growth_cycle(["optimize", "report"])
            except Exception as e:
                print(f"[Growth] Report generation failed: {e}")
            completed_phases.add(phase_key)


async def _check_and_run_engagement(completed_phases: set, today: str):
    """
    Check for any engagement slots that should run NOW or were MISSED.

    Catches up on missed slots (e.g., if a long build/upload blocked the loop)
    by running any slot whose hour has passed but wasn't completed today.
    """
    if not ENABLE_ENGAGEMENT_POSTS:
        return

    current_hour = datetime.now().hour
    tasks = []

    for eng_hour in ENGAGEMENT_HOURS:
        phase_key = (today, eng_hour, "engagement", 0)
        if phase_key in completed_phases:
            continue

        # Run if we're at this hour OR if we've passed it (catch-up)
        if eng_hour <= current_hour:
            if eng_hour == current_hour:
                print(f"\n[Scheduler] {datetime.now().strftime('%H:%M')} — ENGAGEMENT phase (hour {eng_hour})")
            else:
                print(f"\n[Scheduler] {datetime.now().strftime('%H:%M')} — ENGAGEMENT catch-up (hour {eng_hour}, missed)")
            tasks.append((eng_hour, phase_key))

    # Run missed engagement slots sequentially (each is quick ~2-3 min)
    for eng_hour, phase_key in tasks:
        try:
            await run_engagement_phase(eng_hour)
        except Exception as e:
            print(f"[Scheduler] Engagement failed (hour {eng_hour}): {e}")
        completed_phases.add(phase_key)


async def scheduler_loop():
    """
    Main scheduler daemon — two-phase scheduling.

    BUILD phase runs 2 hours before UPLOAD phase:
        6:00 AM  BUILD shorts  ->  8:00 AM  UPLOAD shorts
        12:00 PM BUILD shorts  ->  2:00 PM  UPLOAD shorts
        6:00 PM  BUILD shorts  ->  8:00 PM  UPLOAD shorts

    Engagement posts run at 9, 12, 15, 18, 21 and catch up on missed slots
    after build/upload phases complete.

    Checks every 15 minutes. Each phase runs once per slot per day.
    """
    print(f"\n{'#'*60}")
    print(f"# AI Video Factory — Two-Phase Smart Scheduler")
    print(f"# Niches: {len(NICHES)} ({', '.join(NICHES.keys())})")
    print(f"# Strategy: Build 3h before upload")
    print(f"# Press Ctrl+C to stop")
    print(f"{'#'*60}\n")

    print(f"  Daily Schedule:")
    for slot_idx in range(len(UPLOAD_HOURS)):
        fmt = SLOT_FORMATS[slot_idx]
        bh = BUILD_HOURS[slot_idx]
        uh = UPLOAD_HOURS[slot_idx]
        print(f"    Slot {slot_idx+1}: BUILD {bh:02d}:00 -> UPLOAD {uh:02d}:00  ({fmt})")
    if ENABLE_ENGAGEMENT_POSTS:
        eng_str = ", ".join(f"{h:02d}:00" for h in ENGAGEMENT_HOURS)
        print(f"    Engagement: {eng_str} (with catch-up)")
    if ENABLE_GROWTH_ENGINE:
        comm_str = ", ".join(f"{h:02d}:00" for h in COMMUNITY_CHECK_HOURS)
        print(f"    Growth Engine: ON")
        print(f"      Insights: {INSIGHTS_COLLECTION_HOUR:02d}:00 | Community: {comm_str}")
        print(f"      Cross-promo: {CROSS_PROMO_HOUR:02d}:00 | Report: {GROWTH_REPORT_HOUR:02d}:00")
    print()

    completed_phases = set()  # Track (date, hour, phase) to avoid re-running

    while True:
        now = datetime.now()
        current_hour = now.hour
        today = now.strftime("%Y-%m-%d")

        # ── ENGAGEMENT: check FIRST and catch up on missed slots ──
        # This runs before build/upload so engagement isn't blocked.
        await _check_and_run_engagement(completed_phases, today)

        # ── GROWTH ENGINE: insights, community, cross-promo, reports ──
        await _check_and_run_growth(completed_phases, today)

        # ── BUILD slots ──
        for slot_idx, build_hour in enumerate(BUILD_HOURS):
            phase_key = (today, build_hour, "build", slot_idx)
            if current_hour >= build_hour and phase_key not in completed_phases:
                fmt = SLOT_FORMATS[slot_idx]
                print(f"\n[Scheduler] {now.strftime('%H:%M')} — BUILD phase for {fmt} (slot {slot_idx+1})")
                try:
                    await run_build_phase(slot_idx)
                except Exception as e:
                    print(f"[Scheduler] Build failed: {e}")
                    await _send_alert(f"Scheduler build failed: {e}")
                completed_phases.add(phase_key)

                # After long build, catch up on any missed upload slots
                now_after_build = datetime.now()
                for ui, uh in enumerate(UPLOAD_HOURS):
                    up_key = (today, uh, "upload", ui)
                    if now_after_build.hour >= uh and up_key not in completed_phases:
                        print(f"\n[Scheduler] {now_after_build.strftime('%H:%M')} — CATCH-UP UPLOAD for slot {ui+1} (build overran past {uh:02d}:00)")
                        try:
                            await run_upload_phase()
                        except Exception as e:
                            print(f"[Scheduler] Catch-up upload failed: {e}")
                            await _send_alert(f"Scheduler catch-up upload failed: {e}")
                        completed_phases.add(up_key)

                # After long build, catch up on any missed engagement slots
                await _check_and_run_engagement(completed_phases, today)

        # ── UPLOAD slots ──
        for slot_idx, upload_hour in enumerate(UPLOAD_HOURS):
            phase_key = (today, upload_hour, "upload", slot_idx)
            if current_hour >= upload_hour and phase_key not in completed_phases:
                fmt = SLOT_FORMATS[slot_idx]
                print(f"\n[Scheduler] {now.strftime('%H:%M')} — UPLOAD phase for {fmt} (slot {slot_idx+1})")
                try:
                    await run_upload_phase()
                except Exception as e:
                    print(f"[Scheduler] Upload failed: {e}")
                    await _send_alert(f"Scheduler upload failed: {e}")
                completed_phases.add(phase_key)

                # After long upload, catch up on any missed engagement slots
                await _check_and_run_engagement(completed_phases, today)

        # ── MUSIC VIDEO (once daily at noon — AlphaZone Sounds channel) ──
        music_key = (today, 12, "music", 0)
        if current_hour >= 12 and music_key not in completed_phases:
            print(f"\n[Scheduler] {now.strftime('%H:%M')} — MUSIC VIDEO build (AlphaZone Sounds)")
            try:
                import subprocess as _sp
                result = _sp.run(
                    [sys.executable, "make_music.py", "--type", "rotate", "--clips", "4"],
                    cwd=str(Path(__file__).parent),
                    capture_output=True, text=True, timeout=7200,
                )
                if result.returncode == 0:
                    print(f"[Scheduler] Music video built + posted successfully")
                else:
                    print(f"[Scheduler] Music video failed: {result.stderr[-300:]}")
                    await _send_alert(f"Music video build failed: {result.stderr[-200:]}")
            except Exception as e:
                print(f"[Scheduler] Music video error: {e}")
                await _send_alert(f"Music video error: {e}")
            completed_phases.add(music_key)

        # Reset tracking at midnight
        if current_hour == 0:
            tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            completed_phases = {p for p in completed_phases if p[0] == tomorrow}

        await asyncio.sleep(900)  # Check every 15 minutes


# ── Status Display ───────────────────────────────────────

def show_status():
    """Show current two-phase schedule status."""
    log = load_schedule_log()
    today = get_today_key()
    today_log = log.get(today, {})

    print(f"\n{'='*60}")
    print(f"  Two-Phase Schedule Status — {today} ({datetime.now().strftime('%A')})")
    print(f"{'='*60}")

    for slot_idx in range(len(UPLOAD_HOURS)):
        fmt = SLOT_FORMATS[slot_idx]
        bh = BUILD_HOURS[slot_idx]
        uh = UPLOAD_HOURS[slot_idx]
        print(f"\n  --- Slot {slot_idx+1}: {SLOT_NAMES[slot_idx]} ---")
        print(f"  Format: {fmt} | Build: {bh:02d}:00 | Upload: {uh:02d}:00")

        for niche in NICHES:
            niche_name = NICHES[niche]["name"]
            build_key = get_phase_key(niche, slot_idx, "build")
            upload_key = get_phase_key(niche, slot_idx, "upload")

            build_entry = today_log.get(build_key, {})
            upload_entry = today_log.get(upload_key, {})

            build_status = build_entry.get("status", "pending")
            upload_status = upload_entry.get("status", "pending")

            # Color-code status
            b_icon = "[OK]" if build_status in ("built", "success") else "[--]" if build_status == "pending" else "[!!]"
            u_icon = "[OK]" if upload_status in ("uploaded", "success") else "[--]" if upload_status == "pending" else "[!!]"

            print(f"    {niche_name[:24]:<26} Build: {b_icon} {build_status:<10}  Upload: {u_icon} {upload_status}")

    # Summary counts
    total = len(today_log)
    built = sum(1 for v in today_log.values() if v.get("status") in ("built", "success"))
    uploaded = sum(1 for v in today_log.values() if v.get("status") == "uploaded")
    errors = sum(1 for v in today_log.values() if v.get("status") == "error")

    print(f"\n  Today: {built} built / {uploaded} uploaded / {errors} errors / {total} total entries")
    print(f"{'='*60}\n")


def show_optimization():
    """Show learned optimal posting times from performance data."""
    try:
        from modules.performance_tracker import get_performance_summary
        summary = get_performance_summary()
        posting_data = summary.get("posting_time_scores", {})

        print(f"\n{'='*60}")
        print(f"  Posting Time Optimization (from performance data)")
        print(f"{'='*60}")

        for niche in NICHES:
            niche_data = posting_data.get(niche, {})
            hours = niche_data.get("hours", {})
            weekdays = niche_data.get("weekdays", {})

            if hours:
                best_hours = sorted(hours.items(), key=lambda x: x[1].get("avg", 0), reverse=True)[:3]
                hour_str = ", ".join(f"{h}:00 (score: {d['avg']})" for h, d in best_hours)
            else:
                hour_str = "Not enough data yet"

            if weekdays:
                best_days = sorted(weekdays.items(), key=lambda x: x[1].get("avg", 0), reverse=True)[:2]
                day_str = ", ".join(f"{d} ({info['avg']})" for d, info in best_days)
            else:
                day_str = "Not enough data yet"

            print(f"\n  {NICHES[niche]['name']}:")
            print(f"    Best hours: {hour_str}")
            print(f"    Best days: {day_str}")

        print(f"\n{'='*60}\n")
    except Exception as e:
        print(f"Error loading optimization data: {e}")


# ── CLI Entry Point ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Video Factory Two-Phase Smart Scheduler")
    parser.add_argument("--once", action="store_true", help="Run one full build+upload cycle and exit")
    parser.add_argument("--build", action="store_true", help="Run build phase only (generate videos, no upload)")
    parser.add_argument("--upload", action="store_true", help="Run upload phase only (upload pre-built videos)")
    parser.add_argument("--slot", type=int, choices=[0, 1, 2], help="Specific slot to build (0=morning, 1=afternoon, 2=evening)")
    parser.add_argument("--status", action="store_true", help="Show schedule status")
    parser.add_argument("--optimize", action="store_true", help="Show optimal posting times")
    parser.add_argument("--engagement", action="store_true", help="Run one round of engagement posts to all FB pages")
    parser.add_argument("--niche-heat", action="store_true", help="Show current niche trend heat rankings")
    parser.add_argument("--growth", action="store_true", help="Run one full growth engine cycle")
    parser.add_argument("--community", action="store_true", help="Run community management (reply to comments)")
    parser.add_argument("--insights", action="store_true", help="Collect Facebook page insights")
    parser.add_argument("--cross-promo", action="store_true", help="Run cross-page promotion")
    parser.add_argument("--growth-report", action="store_true", help="Generate daily growth report")
    parser.add_argument("--growth-goals", action="store_true", help="Show daily growth goal progress")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.niche_heat:
        from modules.niche_prioritizer import show_niche_heat
        asyncio.run(show_niche_heat())
        return

    if args.optimize:
        show_optimization()
        return

    if args.engagement:
        asyncio.run(run_engagement_phase())
        return

    if args.growth:
        from modules.growth_engine import run_growth_cycle
        asyncio.run(run_growth_cycle())
        return

    if args.community:
        from modules.growth_engine import run_growth_cycle
        asyncio.run(run_growth_cycle(["community"]))
        return

    if args.insights:
        from modules.growth_engine import run_growth_cycle
        asyncio.run(run_growth_cycle(["insights"]))
        return

    if args.cross_promo:
        from modules.growth_engine import run_growth_cycle
        asyncio.run(run_growth_cycle(["cross_promo"]))
        return

    if args.growth_report:
        from modules.growth_engine import run_growth_cycle
        asyncio.run(run_growth_cycle(["optimize", "report"]))
        return

    if args.growth_goals:
        from modules.growth_engine import check_goal_progress, ACTIVE_NICHES, NICHE_PAGE_NAMES
        print("\n" + "=" * 60)
        print("  DAILY GOAL PROGRESS")
        print("=" * 60)
        for niche in ACTIVE_NICHES:
            progress = check_goal_progress(niche)
            status = "DONE" if progress["overall_complete"] else "IN PROGRESS"
            print(f"\n  {progress['page_name']} [{progress['tier']}] - {status}")
            for key, p in progress["progress"].items():
                check = "x" if p["complete"] else " "
                print(f"    [{check}] {key}: {p['actual']}/{p['target']}")
        print("=" * 60)
        return

    if args.build:
        asyncio.run(run_build_phase(args.slot))
        return

    if args.upload:
        asyncio.run(run_upload_phase())
        return

    if args.once:
        asyncio.run(run_full_cycle())
        return

    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        print("\n[Scheduler] Stopped by user.")


if __name__ == "__main__":
    main()
