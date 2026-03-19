"""
AI Video Factory Dashboard — FastAPI Backend

Serves the React frontend + REST API + WebSocket live logs.
Imports existing pipeline modules directly for zero data duplication.
"""
import sys
import json
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, deque

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Add parent dir to path so we can import pipeline modules ──
ROOT_DIR = Path(__file__).parent.parent
DASHBOARD_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(DASHBOARD_DIR))

from auth import DASHBOARD_PASSWORD, create_token, require_auth
from monetization_api import router as monetization_router

# ── Import pipeline modules ──
from modules.logger import _load_log, _save_log, get_daily_summary, get_total_stats
from config import (
    NICHES, SCHEDULE, OUTPUT_DIR, VIDEO_SETTINGS,
    GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY,
    ELEVENLABS_API_KEY, PEXELS_API_KEY, DID_API_KEY,
    YOUTUBE_CLIENT_ID, TWITTER_API_KEY,
    VOICE_YOUTUBE_LONG, VOICE_SHORTS, DEFAULT_EDGE_VOICE,
    ELEVENLABS_VOICE_ID, ENABLE_KEN_BURNS, ENABLE_TRANSITIONS,
    ENABLE_LOWER_THIRDS, ENABLE_SFX, ENABLE_AVATAR,
    CAPTION_FONT_SIZE, CAPTION_MAX_WORDS,
)

# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="AI Video Factory", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Monetization API ──────────────────────────────────────────
app.include_router(monetization_router)

# Serve video/thumbnail files from output directory
app.mount("/media", StaticFiles(directory=str(OUTPUT_DIR)), name="media")

# ── Pipeline State ────────────────────────────────────────────
pipeline_state = {
    "running": False,
    "current_niche": None,
    "current_format": None,
    "started_at": None,
    "last_result": None,
}

# ── WebSocket Log Broadcasting ────────────────────────────────
log_buffer: deque = deque(maxlen=500)
ws_clients: set = set()


class LogBroadcaster:
    """Captures stdout and broadcasts to WebSocket clients."""

    def __init__(self, original):
        self.original = original

    def write(self, text):
        if self.original:
            self.original.write(text)
        if text and text.strip():
            entry = {"timestamp": datetime.now().isoformat(), "message": text.strip()}
            log_buffer.append(entry)
            for ws in list(ws_clients):
                try:
                    asyncio.get_event_loop().create_task(ws.send_json(entry))
                except Exception:
                    ws_clients.discard(ws)

    def flush(self):
        if self.original:
            self.original.flush()


# Install stdout broadcaster on startup
_original_stdout = sys.stdout
sys.stdout = LogBroadcaster(_original_stdout)


# ── Helpers ───────────────────────────────────────────────────
def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


def _enrich_video_entry(entry: dict) -> dict:
    """Add media URLs to a video log entry."""
    entry = dict(entry)
    vp = entry.get("video_path")
    if vp:
        vp_path = Path(vp)
        # Get relative path from output dir
        try:
            if vp_path.is_absolute():
                rel = vp_path.relative_to(OUTPUT_DIR)
            else:
                rel = Path(vp).relative_to("output") if "output" in str(vp) else Path(vp)
            entry["video_url"] = f"/media/{rel.as_posix()}"
            # Thumbnail
            thumb = vp_path.parent / "thumbnail.jpg"
            if not thumb.exists() and not vp_path.is_absolute():
                thumb = OUTPUT_DIR / rel.parent / "thumbnail.jpg"
            if thumb.exists():
                thumb_rel = thumb.relative_to(OUTPUT_DIR)
                entry["thumbnail_url"] = f"/media/{thumb_rel.as_posix()}"
            else:
                entry["thumbnail_url"] = None
        except (ValueError, TypeError):
            entry["video_url"] = None
            entry["thumbnail_url"] = None
    else:
        entry["video_url"] = None
        entry["thumbnail_url"] = None
    return entry


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    password: str


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    if body.password != DASHBOARD_PASSWORD:
        raise HTTPException(401, "Invalid password")
    return {"token": create_token()}


# ══════════════════════════════════════════════════════════════
#  VIDEOS
# ══════════════════════════════════════════════════════════════

@app.get("/api/videos", dependencies=[Depends(require_auth)])
async def list_videos(
    niche: str | None = None,
    format: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    entries = _load_log()
    if niche:
        entries = [e for e in entries if e.get("niche") == niche]
    if format:
        entries = [e for e in entries if e.get("format") == format]
    if status:
        entries = [e for e in entries if e.get("status") == status]

    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    total = len(entries)
    start = (page - 1) * per_page
    items = [_enrich_video_entry(e) for e in entries[start:start + per_page]]

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@app.get("/api/videos/{video_id}", dependencies=[Depends(require_auth)])
async def get_video(video_id: str):
    entries = _load_log()
    entry = next((e for e in entries if e.get("id") == video_id), None)
    if not entry:
        raise HTTPException(404, "Video not found")
    return _enrich_video_entry(entry)


@app.delete("/api/videos/{video_id}", dependencies=[Depends(require_auth)])
async def delete_video(video_id: str):
    entries = _load_log()
    entry = next((e for e in entries if e.get("id") == video_id), None)
    if not entry:
        raise HTTPException(404, "Video not found")

    # Delete files
    vp = entry.get("video_path")
    if vp:
        video_dir = Path(vp).parent
        if video_dir.exists():
            shutil.rmtree(video_dir, ignore_errors=True)

    # Remove from log
    entries = [e for e in entries if e.get("id") != video_id]
    _save_log(entries)
    return {"status": "deleted", "id": video_id}


# ══════════════════════════════════════════════════════════════
#  STATISTICS
# ══════════════════════════════════════════════════════════════

@app.get("/api/stats/daily", dependencies=[Depends(require_auth)])
async def stats_daily():
    return get_daily_summary()


@app.get("/api/stats/total", dependencies=[Depends(require_auth)])
async def stats_total():
    return get_total_stats()


@app.get("/api/stats/timeline", dependencies=[Depends(require_auth)])
async def stats_timeline(days: int = Query(30, ge=1, le=365)):
    entries = _load_log()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    recent = [e for e in entries if e.get("timestamp", "") >= cutoff]

    by_date = Counter()
    by_niche_date: dict[str, dict[str, int]] = {}

    for e in recent:
        date = e.get("timestamp", "")[:10]
        by_date[date] += 1
        niche = e.get("niche", "unknown")
        if date not in by_niche_date:
            by_niche_date[date] = {}
        by_niche_date[date][niche] = by_niche_date[date].get(niche, 0) + 1

    # Build ordered list of dates
    dates = sorted(by_date.keys())
    timeline = []
    for d in dates:
        point = {"date": d, "total": by_date[d]}
        point.update(by_niche_date.get(d, {}))
        timeline.append(point)

    return {"timeline": timeline, "days": days}


# ══════════════════════════════════════════════════════════════
#  PIPELINE CONTROL
# ══════════════════════════════════════════════════════════════

class TriggerRequest(BaseModel):
    niche: str = "ai_trading"
    format: str = "short"
    dry_run: bool = True


@app.post("/api/pipeline/trigger", dependencies=[Depends(require_auth)])
async def trigger_pipeline(body: TriggerRequest):
    if pipeline_state["running"]:
        raise HTTPException(409, "Pipeline already running")
    if body.niche not in NICHES:
        raise HTTPException(400, f"Unknown niche: {body.niche}")
    if body.format not in ("long", "short"):
        raise HTTPException(400, f"Unknown format: {body.format}")

    pipeline_state["running"] = True
    pipeline_state["current_niche"] = body.niche
    pipeline_state["current_format"] = body.format
    pipeline_state["started_at"] = datetime.now().isoformat()
    pipeline_state["last_result"] = None

    async def run():
        try:
            from main import create_video
            result = await create_video(body.niche, body.format, body.dry_run)
            pipeline_state["last_result"] = result
        except Exception as e:
            pipeline_state["last_result"] = {"status": "error", "error": str(e)}
            print(f"[Dashboard] Pipeline error: {e}")
        finally:
            pipeline_state["running"] = False

    asyncio.create_task(run())
    return {
        "status": "triggered",
        "niche": body.niche,
        "format": body.format,
        "dry_run": body.dry_run,
    }


@app.get("/api/pipeline/status", dependencies=[Depends(require_auth)])
async def pipeline_status():
    return pipeline_state


# ══════════════════════════════════════════════════════════════
#  SCHEDULE
# ══════════════════════════════════════════════════════════════

SCHEDULE_OVERRIDE_FILE = ROOT_DIR / "schedule_override.json"


@app.get("/api/schedule", dependencies=[Depends(require_auth)])
async def get_schedule():
    schedule = {k: dict(v) for k, v in SCHEDULE.items()}
    if SCHEDULE_OVERRIDE_FILE.exists():
        try:
            overrides = json.loads(SCHEDULE_OVERRIDE_FILE.read_text())
            for niche, values in overrides.items():
                if niche in schedule:
                    schedule[niche].update(values)
        except Exception:
            pass

    result = {}
    for niche_key, counts in schedule.items():
        niche_info = NICHES.get(niche_key, {})
        result[niche_key] = {
            "name": niche_info.get("name", niche_key),
            "long_form": counts.get("long_form", 0),
            "shorts": counts.get("shorts", 0),
        }
    return result


class ScheduleUpdate(BaseModel):
    schedule: dict


@app.put("/api/schedule", dependencies=[Depends(require_auth)])
async def update_schedule(body: ScheduleUpdate):
    SCHEDULE_OVERRIDE_FILE.write_text(json.dumps(body.schedule, indent=2))
    return {"status": "updated"}


# ══════════════════════════════════════════════════════════════
#  HEALTH
# ══════════════════════════════════════════════════════════════

@app.get("/api/health", dependencies=[Depends(require_auth)])
async def health_check():
    from modules.retry import PipelineHealthCheck
    checker = PipelineHealthCheck()
    return await checker.run_all()


# ══════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════

@app.get("/api/settings", dependencies=[Depends(require_auth)])
async def get_settings():
    return {
        "api_keys": {
            "gemini": {"set": bool(GEMINI_API_KEY), "masked": _mask_key(GEMINI_API_KEY)},
            "openai": {"set": bool(OPENAI_API_KEY), "masked": _mask_key(OPENAI_API_KEY)},
            "anthropic": {"set": bool(ANTHROPIC_API_KEY), "masked": _mask_key(ANTHROPIC_API_KEY)},
            "elevenlabs": {"set": bool(ELEVENLABS_API_KEY), "masked": _mask_key(ELEVENLABS_API_KEY)},
            "pexels": {"set": bool(PEXELS_API_KEY), "masked": _mask_key(PEXELS_API_KEY)},
            "did": {"set": bool(DID_API_KEY), "masked": _mask_key(DID_API_KEY)},
            "youtube": {"set": bool(YOUTUBE_CLIENT_ID), "masked": _mask_key(YOUTUBE_CLIENT_ID)},
            "twitter": {"set": bool(TWITTER_API_KEY), "masked": _mask_key(TWITTER_API_KEY)},
        },
        "voice": {
            "youtube_long": VOICE_YOUTUBE_LONG,
            "shorts": VOICE_SHORTS,
            "edge_default": DEFAULT_EDGE_VOICE,
            "elevenlabs_voice_id": ELEVENLABS_VOICE_ID,
        },
        "features": {
            "ken_burns": ENABLE_KEN_BURNS,
            "transitions": ENABLE_TRANSITIONS,
            "lower_thirds": ENABLE_LOWER_THIRDS,
            "sfx": ENABLE_SFX,
            "avatar": ENABLE_AVATAR,
        },
        "captions": {
            "font_size": CAPTION_FONT_SIZE,
            "max_words": CAPTION_MAX_WORDS,
        },
        "video_settings": VIDEO_SETTINGS,
    }


@app.get("/api/settings/niches", dependencies=[Depends(require_auth)])
async def get_niches():
    result = {}
    for key, niche in NICHES.items():
        result[key] = {
            "name": niche["name"],
            "cpm_estimate": niche.get("cpm_estimate", 0),
            "topics_count": len(niche.get("topics_bank", [])),
            "hashtags": niche.get("hashtags", []),
            "generate_charts": niche.get("generate_charts", False),
            "edge_voice": niche.get("edge_voice", DEFAULT_EDGE_VOICE),
        }
    return result


# ══════════════════════════════════════════════════════════════
#  UPLOADS
# ══════════════════════════════════════════════════════════════

@app.get("/api/uploads", dependencies=[Depends(require_auth)])
async def list_uploads(
    platform: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    entries = _load_log()
    uploads = []
    for e in entries:
        for u in e.get("uploads", []):
            upload = {
                "video_id": e.get("id"),
                "video_title": e.get("title", "Unknown"),
                "niche": e.get("niche"),
                "format": e.get("format"),
                "timestamp": e.get("timestamp"),
                **u,
            }
            if platform and u.get("platform") != platform:
                continue
            if status and u.get("status") != status:
                continue
            uploads.append(upload)

    uploads.sort(key=lambda u: u.get("timestamp", ""), reverse=True)
    total = len(uploads)
    start = (page - 1) * per_page
    items = uploads[start:start + per_page]

    # Summary counts
    all_uploads = []
    for e in entries:
        all_uploads.extend(e.get("uploads", []))

    summary = {
        "total": len(all_uploads),
        "by_platform": dict(Counter(u.get("platform") for u in all_uploads)),
        "by_status": dict(Counter(u.get("status") for u in all_uploads)),
    }

    return {"items": items, "total": total, "page": page, "per_page": per_page, "summary": summary}


@app.post("/api/uploads/{video_id}/retry/{platform_name}", dependencies=[Depends(require_auth)])
async def retry_upload(video_id: str, platform_name: str):
    entries = _load_log()
    entry = next((e for e in entries if e.get("id") == video_id), None)
    if not entry:
        raise HTTPException(404, "Video not found")

    vp = entry.get("video_path")
    if not vp or not Path(vp).exists():
        raise HTTPException(400, "Video file not found on disk")

    result = {"platform": platform_name, "status": "failed", "error": "Unknown platform"}

    try:
        if platform_name == "youtube":
            from modules.uploader_youtube import upload_to_youtube
            result = await upload_to_youtube(
                video_path=vp,
                title=entry.get("title", "AI Video"),
                description="",
                tags=[],
                niche=entry.get("niche", "ai_trading"),
                is_short=entry.get("format") == "short",
            )
        elif platform_name == "tiktok":
            from modules.uploader_tiktok import upload_to_tiktok
            niche_config = NICHES.get(entry.get("niche", "ai_trading"), {})
            result = await upload_to_tiktok(
                video_path=vp,
                description=entry.get("title", ""),
                hashtags=niche_config.get("hashtags", []),
            )
        elif platform_name == "twitter":
            from modules.uploader_twitter import upload_to_twitter
            niche_config = NICHES.get(entry.get("niche", "ai_trading"), {})
            result = await upload_to_twitter(
                video_path=vp,
                text=entry.get("title", "")[:200],
                hashtags=niche_config.get("hashtags", [])[:5],
            )
        else:
            raise HTTPException(400, f"Unknown platform: {platform_name}")
    except HTTPException:
        raise
    except Exception as e:
        result = {"platform": platform_name, "status": "failed", "error": str(e)}

    # Update log entry
    for e in entries:
        if e.get("id") == video_id:
            e.setdefault("uploads", []).append(result)
    _save_log(entries)

    return result


# ══════════════════════════════════════════════════════════════
#  TOPICS
# ══════════════════════════════════════════════════════════════

@app.get("/api/topics", dependencies=[Depends(require_auth)])
async def get_topics():
    history_file = OUTPUT_DIR / "topic_history.json"
    if history_file.exists():
        return json.loads(history_file.read_text())
    return {}


@app.get("/api/topics/suggest", dependencies=[Depends(require_auth)])
async def suggest_topic(niche: str = "ai_trading"):
    if niche not in NICHES:
        raise HTTPException(400, f"Unknown niche: {niche}")
    from modules.topic_generator import pick_topic
    result = await pick_topic(niche)
    return result


# ══════════════════════════════════════════════════════════════
#  WEBSOCKET — LIVE LOGS
# ══════════════════════════════════════════════════════════════

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    # Send recent history
    for entry in log_buffer:
        try:
            await websocket.send_json(entry)
        except Exception:
            break
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(websocket)


# ══════════════════════════════════════════════════════════════
#  SPA FALLBACK — Serve React frontend
# ══════════════════════════════════════════════════════════════

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve React SPA — catch-all route (must be last)."""
    if FRONTEND_DIST.exists():
        # Try to serve exact file first
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Fallback to index.html for SPA routing
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return JSONResponse(
        {"message": "Frontend not built. Run: cd dashboard/frontend && npm run build"},
        status_code=200,
    )
