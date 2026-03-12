"""
AI Video Factory — Two-Phase Smart Scheduler

Two-phase scheduling: BUILD videos 2 hours before UPLOAD time.
This ensures videos are ready and uploaded exactly at optimal posting times.

Schedule (daily, all 6 niches):
    BUILD 6:00 AM  -> UPLOAD 8:00 AM   (shorts)
    BUILD 12:00 PM -> UPLOAD 2:00 PM   (podcast)
    BUILD 6:00 PM  -> UPLOAD 8:00 PM   (long-form)

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
import asyncio
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, SCHEDULE

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
SCHEDULE_LOG = LOG_DIR / "schedule_log.json"


# ── Two-Phase Schedule Configuration ─────────────────────
# Videos are BUILT 2 hours before their UPLOAD time.
# Each slot handles one format type for ALL 6 niches.

BUILD_LEAD_HOURS = 2

# Upload slots: 3 per day (morning, afternoon, evening)
UPLOAD_HOURS = [8, 14, 20]

# Build slots: 2 hours before each upload
BUILD_HOURS = [h - BUILD_LEAD_HOURS for h in UPLOAD_HOURS]

# Map each slot index to a video format
SLOT_FORMATS = {
    0: "short",    # 6 AM build -> 8 AM upload (shorts = fast morning engagement)
    1: "podcast",  # 12 PM build -> 2 PM upload (podcast debates = afternoon)
    2: "long",     # 6 PM build -> 8 PM upload (long-form = evening deep content)
}

# Readable slot names for logging
SLOT_NAMES = {
    0: "Morning (Shorts)",
    1: "Afternoon (Podcast)",
    2: "Evening (Long-form)",
}


# ── Platform-Specific Optimal Posting Times (reference) ──
# Kept for performance tracking and optimization data.
OPTIMAL_POST_HOURS = {
    "facebook": {
        "ai_trading": [9, 13, 16],
        "ai_money": [8, 12, 17],
        "tech_news": [9, 13, 18],
        "motivation": [6, 7, 8],
        "health_wellness": [7, 12, 18],
        "blissful_moments": [7, 19, 21],
    },
    "tiktok": {
        "ai_trading": [7, 12, 19],
        "ai_money": [8, 13, 20],
        "tech_news": [9, 14, 20],
        "motivation": [6, 7, 20],
        "health_wellness": [7, 11, 19],
        "blissful_moments": [8, 19, 21],
    },
    "youtube": {
        "ai_trading": [8, 14, 18],
        "ai_money": [9, 15, 19],
        "tech_news": [10, 15, 19],
        "motivation": [5, 6, 7],
        "health_wellness": [8, 12, 18],
        "blissful_moments": [9, 18, 20],
    },
    "instagram": {
        "ai_trading": [11, 14, 19],
        "ai_money": [10, 14, 20],
        "tech_news": [11, 15, 19],
        "motivation": [7, 12, 18],
        "health_wellness": [8, 12, 19],
        "blissful_moments": [9, 18, 21],
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


# ── Build Phase ──────────────────────────────────────────

async def run_build_phase(slot: int | None = None):
    """
    BUILD phase: Generate videos for all niches (without uploading).
    Videos are saved with upload_manifest.json for later upload.

    Args:
        slot: Specific slot index (0, 1, 2) or None for all slots.
    """
    from main import create_video

    slots_to_build = [slot] if slot is not None else list(SLOT_FORMATS.keys())
    results = []

    for s in slots_to_build:
        fmt = SLOT_FORMATS[s]
        upload_hour = UPLOAD_HOURS[s]
        build_hour = BUILD_HOURS[s]

        print(f"\n{'#'*60}")
        print(f"# BUILD PHASE — {SLOT_NAMES[s]}")
        print(f"# Format: {fmt} | Build: {build_hour}:00 | Upload: {upload_hour}:00")
        print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}\n")

        for niche in NICHES:
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

    results = await upload_prebuilt_videos()

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

async def scheduler_loop():
    """
    Main scheduler daemon — two-phase scheduling.

    BUILD phase runs 2 hours before UPLOAD phase:
        6:00 AM  BUILD shorts      ->  8:00 AM  UPLOAD shorts
        12:00 PM BUILD podcasts    ->  2:00 PM  UPLOAD podcasts
        6:00 PM  BUILD long-form   ->  8:00 PM  UPLOAD long-form

    Checks every 15 minutes. Each phase runs once per slot per day.
    """
    print(f"\n{'#'*60}")
    print(f"# AI Video Factory — Two-Phase Smart Scheduler")
    print(f"# Niches: {len(NICHES)} ({', '.join(NICHES.keys())})")
    print(f"# Strategy: Build 2h before upload")
    print(f"# Press Ctrl+C to stop")
    print(f"{'#'*60}\n")

    print(f"  Daily Schedule:")
    for slot_idx in range(len(UPLOAD_HOURS)):
        fmt = SLOT_FORMATS[slot_idx]
        bh = BUILD_HOURS[slot_idx]
        uh = UPLOAD_HOURS[slot_idx]
        print(f"    Slot {slot_idx+1}: BUILD {bh:02d}:00 -> UPLOAD {uh:02d}:00  ({fmt})")
    print()

    completed_phases = set()  # Track (date, hour, phase) to avoid re-running

    while True:
        now = datetime.now()
        current_hour = now.hour
        today = now.strftime("%Y-%m-%d")

        # Check BUILD slots
        for slot_idx, build_hour in enumerate(BUILD_HOURS):
            phase_key = (today, build_hour, "build", slot_idx)
            if current_hour == build_hour and phase_key not in completed_phases:
                fmt = SLOT_FORMATS[slot_idx]
                print(f"\n[Scheduler] {now.strftime('%H:%M')} — BUILD phase for {fmt} (slot {slot_idx+1})")
                try:
                    await run_build_phase(slot_idx)
                except Exception as e:
                    print(f"[Scheduler] Build failed: {e}")
                    await _send_alert(f"Scheduler build failed: {e}")
                completed_phases.add(phase_key)

        # Check UPLOAD slots
        for slot_idx, upload_hour in enumerate(UPLOAD_HOURS):
            phase_key = (today, upload_hour, "upload", slot_idx)
            if current_hour == upload_hour and phase_key not in completed_phases:
                fmt = SLOT_FORMATS[slot_idx]
                print(f"\n[Scheduler] {now.strftime('%H:%M')} — UPLOAD phase for {fmt} (slot {slot_idx+1})")
                try:
                    await run_upload_phase()
                except Exception as e:
                    print(f"[Scheduler] Upload failed: {e}")
                    await _send_alert(f"Scheduler upload failed: {e}")
                completed_phases.add(phase_key)

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
    parser.add_argument("--slot", type=int, choices=[0, 1, 2], help="Specific slot to build (0=shorts, 1=podcast, 2=long)")
    parser.add_argument("--status", action="store_true", help="Show schedule status")
    parser.add_argument("--optimize", action="store_true", help="Show optimal posting times")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.optimize:
        show_optimization()
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
