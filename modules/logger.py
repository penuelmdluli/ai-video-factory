"""
Logger — Tracks all generated videos, uploads, and errors.

Logs to:
1. Local JSON file (always)
2. Google Sheets (if configured)
3. Console output
"""
import json
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR

LOG_FILE = OUTPUT_DIR / "video_log.json"


def _load_log() -> list:
    """Load existing log entries."""
    if LOG_FILE.exists():
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return []


def _save_log(entries: list):
    """Save log entries to file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def log_video(
    niche: str,
    topic: str,
    format_type: str,
    script_title: str,
    video_path: str | None,
    uploads: list[dict],
    duration: float = 0,
    error: str | None = None,
) -> dict:
    """
    Log a video creation and upload event.

    Args:
        niche: Niche key
        topic: Original topic
        format_type: "long" or "short"
        script_title: Generated video title
        video_path: Path to the generated video
        uploads: List of upload results from each platform
        duration: Video duration in seconds
        error: Error message if pipeline failed

    Returns:
        The log entry dict
    """
    entry = {
        "id": f"{niche}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "niche": niche,
        "topic": topic,
        "format": format_type,
        "title": script_title,
        "video_path": video_path,
        "duration_seconds": duration,
        "uploads": uploads,
        "status": "error" if error else "success",
        "error": error,
    }

    # Save to local log
    entries = _load_log()
    entries.append(entry)
    _save_log(entries)

    # Console output
    status_icon = "ERROR" if error else "OK"
    platforms = [u["platform"] for u in uploads if u.get("status") == "uploaded"]
    safe_title = script_title.encode("ascii", errors="ignore").decode("ascii")
    print(f"[Log] [{status_icon}] {niche}/{format_type}: {safe_title[:50]}")
    if platforms:
        print(f"[Log]   Uploaded to: {', '.join(platforms)}")
    if error:
        print(f"[Log]   Error: {error}")

    return entry


def get_daily_summary() -> dict:
    """Get a summary of today's video activity."""
    entries = _load_log()
    today = datetime.now().strftime("%Y-%m-%d")

    today_entries = [e for e in entries if e["timestamp"].startswith(today)]

    return {
        "date": today,
        "total_videos": len(today_entries),
        "successful": sum(1 for e in today_entries if e["status"] == "success"),
        "failed": sum(1 for e in today_entries if e["status"] == "error"),
        "by_niche": {
            niche: sum(1 for e in today_entries if e["niche"] == niche)
            for niche in set(e["niche"] for e in today_entries)
        },
        "platforms_uploaded": sum(
            len([u for u in e.get("uploads", []) if u.get("status") == "uploaded"])
            for e in today_entries
        ),
    }


def get_total_stats() -> dict:
    """Get all-time statistics."""
    entries = _load_log()
    return {
        "total_videos": len(entries),
        "successful": sum(1 for e in entries if e["status"] == "success"),
        "failed": sum(1 for e in entries if e["status"] == "error"),
        "total_uploads": sum(
            len([u for u in e.get("uploads", []) if u.get("status") == "uploaded"])
            for e in entries
        ),
        "by_niche": {
            niche: sum(1 for e in entries if e["niche"] == niche)
            for niche in set(e["niche"] for e in entries)
        },
    }
