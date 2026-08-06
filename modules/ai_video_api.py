"""
AI Video API — Generate video clips with FREE-FIRST strategy.

Priority chain (COST-OPTIMIZED — free by default):
1. Clip Library (FREE — reuse existing clips)
2. FREE Local AI images (Gemini 500/day, Cloudflare FLUX 100K/day, SDXL)
   → Combined with Ken Burns animation in video_assembler for motion
3. Pexels stock footage (FREE)
4. [OPTIONAL] fal.ai Kling 3.0 — ONLY for hero shot (first scene) if ENABLE_HERO_SHOT=true

Money-saving strategy:
- ALL clips default to FREE local generation (AI images + Ken Burns)
- fal.ai is DISABLED by default (ENABLE_AI_VIDEO=false in config)
- Even when enabled, fal.ai only used for 1 hero shot per video
- Budget capped at $0.50/session (was $10)
- Clip library reuse for all generated content
"""
import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx

from config import ASSETS_DIR, OUTPUT_DIR

# ── Logging ───────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── API Keys & Config ─────────────────────────────────────────────
FAL_KEY = os.getenv("FAL_KEY", "")

# fal.ai model endpoints
KLING_MODEL = "fal-ai/kling-video/v3/standard/text-to-video"
KLING_IMG2VID_MODEL = "fal-ai/kling-video/v3/standard/image-to-video"
MINIMAX_MODEL = "fal-ai/minimax-video/video-01-live/text-to-video"

# Cost per second (USD) — fal.ai published rates
KLING_COST_PER_SEC = 0.17
MINIMAX_COST_PER_SEC = 0.08

# ── Budget (drastically reduced — FREE-first strategy) ───────────
SESSION_BUDGET = float(os.getenv("AI_VIDEO_BUDGET", "0.50"))  # Was $10, now $0.50
_session_spend = 0.0
_session_clips: list[dict] = []
_budget_limit = SESSION_BUDGET

# ── FREE-first config ────────────────────────────────────────────
ENABLE_AI_VIDEO = os.getenv("ENABLE_AI_VIDEO", "false").lower() in ("true", "1", "yes")
ENABLE_HERO_SHOT = os.getenv("ENABLE_HERO_SHOT", "false").lower() in ("true", "1", "yes")
HERO_SHOT_MAX_COST = float(os.getenv("HERO_SHOT_MAX_COST", "0.40"))

# ── fal.ai API base ──────────────────────────────────────────────
FAL_QUEUE_URL = "https://queue.fal.run"
FAL_REST_URL = "https://fal.run"

# ── Polling config ────────────────────────────────────────────────
POLL_INTERVAL_SEC = 3.0
POLL_TIMEOUT_SEC = 300.0  # 5 minutes max wait

# ── Retry config ──────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# ── Niche style hints for prompt enhancement ──────────────────────
NICHE_STYLE_HINTS: dict[str, str] = {
    "ai_money": "futuristic digital finance, glowing data streams, sleek modern aesthetics, blue and gold tones",
    "tech_news": "cutting-edge technology, holographic displays, neon accents, clean minimal design",
    "motivation": "epic cinematic landscapes, golden hour lighting, powerful imagery, warm inspiring tones",
    "health_wellness": "serene natural environments, soft organic light, lush greenery, calming earth tones",
    "blissful_moments": "dreamy soft-focus, warm golden light, gentle movement, pastel color palette",
    "daily_breakdown": "dynamic news-style graphics, bold contrasts, sharp clean footage, professional look",
    "shopmo_products": "bright product showcase lighting, clean white backgrounds, vibrant lifestyle scenes",
    "limitless_you": "expansive aerial vistas, dramatic lighting, powerful motion, deep saturated colors",
}

STYLE_PRESETS: dict[str, str] = {
    "cinematic": "cinematic 4K, shallow depth of field, anamorphic lens flare, smooth dolly movement, film grain",
    "documentary": "documentary style, handheld camera, natural lighting, authentic and raw, 4K clarity",
    "dramatic": "dramatic lighting, high contrast, slow motion, epic orchestral mood, deep shadows",
    "calm": "slow gentle camera drift, soft ambient lighting, serene atmosphere, minimal movement",
    "energetic": "fast dynamic camera, vibrant saturated colors, quick cuts feel, high energy motion",
    "surreal": "dreamlike surreal visuals, impossible geometry, ethereal glow, floating elements, vivid colors",
}


# ── Budget Management ─────────────────────────────────────────────

def get_session_spend() -> float:
    """Return total API spend this session in USD."""
    return _session_spend


def set_budget_limit(max_dollars: float) -> None:
    """Set max spend per session."""
    global _budget_limit
    _budget_limit = max(0.0, max_dollars)
    logger.info(f"[AI-Video-API] Budget limit set to ${_budget_limit:.2f}")


def _budget_remaining() -> float:
    return max(0.0, _budget_limit - _session_spend)


def _record_spend(amount: float, model: str, prompt: str, duration: int) -> None:
    global _session_spend
    _session_spend += amount
    entry = {
        "timestamp": time.time(),
        "model": model,
        "cost_usd": round(amount, 4),
        "duration_sec": duration,
        "prompt_preview": prompt[:80],
        "session_total": round(_session_spend, 4),
    }
    _session_clips.append(entry)
    logger.info(
        f"[AI-Video-API] Spend: ${amount:.4f} ({model}, {duration}s) | "
        f"Session total: ${_session_spend:.4f} / ${_budget_limit:.2f}"
    )


def _can_afford(duration: int, cost_per_sec: float) -> bool:
    estimated = duration * cost_per_sec
    return estimated <= _budget_remaining()


# ── Prompt Engineering ────────────────────────────────────────────

def enhance_prompt(prompt: str, niche: str = "", style: str = "cinematic") -> str:
    """
    Enhance a basic visual description into a Kling-optimized prompt.

    Adds cinematic language, camera movements, lighting cues, and
    niche-specific style hints for best AI video output.
    """
    parts = []

    # Core visual description
    parts.append(prompt.strip().rstrip("."))

    # Style preset
    style_key = style.lower() if style.lower() in STYLE_PRESETS else "cinematic"
    parts.append(STYLE_PRESETS[style_key])

    # Niche-specific flavor
    niche_hint = NICHE_STYLE_HINTS.get(niche, "")
    if niche_hint:
        parts.append(niche_hint)

    # Quality boosters that help Kling produce better output
    parts.append("professional color grading, high production value")

    enhanced = ", ".join(parts)

    # Kling works best with prompts under 500 chars
    if len(enhanced) > 500:
        enhanced = enhanced[:497] + "..."

    return enhanced


# ── fal.ai helpers (using official fal_client) ───────────────────

def _fal_headers() -> dict[str, str]:
    return {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }


def _ensure_fal_auth():
    """Set FAL_KEY env var so fal_client picks it up automatically."""
    if FAL_KEY and not os.getenv("FAL_KEY_CREDENTIALS"):
        os.environ["FAL_KEY_CREDENTIALS"] = FAL_KEY


async def _fal_submit_and_wait(model: str, arguments: dict) -> Optional[dict]:
    """
    Submit a job to fal.ai and wait for completion using the official fal_client.
    Returns result dict or None on failure/timeout.
    """
    import fal_client
    _ensure_fal_auth()

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"[AI-Video-API] Submitting to {model} via fal_client (attempt {attempt+1})...")

            # fal_client.subscribe handles submit + poll internally
            result = await fal_client.subscribe_async(
                model,
                arguments=arguments,
                with_logs=False,
                client_timeout=POLL_TIMEOUT_SEC,
            )

            if result:
                logger.info(f"[AI-Video-API] Got result from {model}")
                return result

            logger.warning(f"[AI-Video-API] Empty result from {model}")
            return None

        except Exception as exc:
            exc_str = str(exc)
            logger.warning(f"[AI-Video-API] fal_client error (attempt {attempt+1}/{MAX_RETRIES}): {exc_str[:200]}")

            # Don't retry on auth errors or bad requests
            if any(code in exc_str for code in ("401", "403", "422")):
                logger.error(f"[AI-Video-API] Non-retryable error: {exc_str[:200]}")
                return None

            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF_BASE ** attempt
                await asyncio.sleep(wait)

    logger.error(f"[AI-Video-API] All {MAX_RETRIES} attempts failed for {model}")
    return None


# Legacy wrappers for backward compat with existing callers
async def _fal_submit(model: str, arguments: dict) -> Optional[str]:
    """Submit only (legacy). Prefer _fal_submit_and_wait instead."""
    import fal_client
    _ensure_fal_auth()
    try:
        handle = await fal_client.submit_async(model, arguments=arguments)
        request_id = handle.request_id
        logger.info(f"[AI-Video-API] Submitted to {model}, request_id={request_id}")
        return request_id
    except Exception as exc:
        logger.error(f"[AI-Video-API] Submit failed: {exc}")
        return None


async def _fal_poll(model: str, request_id: str) -> Optional[dict]:
    """Poll for result (legacy). Prefer _fal_submit_and_wait instead."""
    import fal_client
    _ensure_fal_auth()
    start = time.monotonic()

    while (time.monotonic() - start) < POLL_TIMEOUT_SEC:
        try:
            status = await fal_client.status_async(model, request_id, with_logs=False)

            if isinstance(status, fal_client.Completed):
                result = await fal_client.result_async(model, request_id)
                return result

            if hasattr(status, 'status') and status.status in ("FAILED", "CANCELLED"):
                logger.error(f"[AI-Video-API] Job {request_id} failed")
                return None

            elapsed = int(time.monotonic() - start)
            logger.debug(f"[AI-Video-API] Waiting... elapsed={elapsed}s")

        except Exception as exc:
            logger.warning(f"[AI-Video-API] Poll error: {exc}")

        await asyncio.sleep(POLL_INTERVAL_SEC)

    logger.error(f"[AI-Video-API] Timeout waiting for {request_id} after {POLL_TIMEOUT_SEC}s")
    return None


async def _download_video(url: str, output_path: Path) -> bool:
    """Download a video file from URL to local path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                output_path.write_bytes(resp.content)
                size_mb = len(resp.content) / (1024 * 1024)
                logger.info(f"[AI-Video-API] Downloaded {size_mb:.1f}MB -> {output_path}")
                return True
            logger.error(f"[AI-Video-API] Download failed: {resp.status_code}")
    except Exception as exc:
        logger.error(f"[AI-Video-API] Download error: {exc}")
    return False


# ── Clip Library Integration ─────────────────────────────────────

def _try_clip_library(prompt: str, niche: str, aspect_ratio: str) -> Optional[dict]:
    """
    Check clip library for a matching cached clip.
    Returns {path, source, duration, clip_id} or None.
    """
    try:
        from modules.clip_library import get_best_match, record_usage
        match = get_best_match(prompt, niche, aspect_ratio)
        if match and match.get("path") and Path(match["path"]).exists():
            record_usage(match.get("clip_id", ""))
            logger.info(f"[AI-Video-API] Clip library hit: {match['path']}")
            return {
                "path": match["path"],
                "source": "clip_library",
                "duration": match.get("duration", 5),
                "clip_id": match.get("clip_id", ""),
            }
    except ImportError:
        logger.debug("[AI-Video-API] clip_library module not available")
    except Exception as exc:
        logger.warning(f"[AI-Video-API] Clip library check failed: {exc}")
    return None


def _save_to_clip_library(
    path: str, prompt: str, niche: str, aspect_ratio: str, duration: int, source: str
) -> str:
    """Save a generated clip to the library for future reuse. Returns clip_id."""
    clip_id = hashlib.md5(f"{prompt}:{niche}:{aspect_ratio}:{time.time()}".encode()).hexdigest()[:12]
    try:
        from modules.clip_library import add_clip, extract_keywords
        keywords = extract_keywords(prompt)
        add_clip(
            file_path=path,
            source=source,
            niche=niche,
            keywords=keywords,
            duration=duration,
        )
        logger.info(f"[AI-Video-API] Saved to clip library: {clip_id}")
    except ImportError:
        logger.debug("[AI-Video-API] clip_library module not available, skipping save")
    except Exception as exc:
        logger.warning(f"[AI-Video-API] Failed to save to clip library: {exc}")
    return clip_id


# ── Core Generation Functions ─────────────────────────────────────

async def generate_clip_kling(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    output_path: Optional[Path] = None,
) -> Optional[str]:
    """
    Generate a video clip via Kling 3.0 on fal.ai.

    Args:
        prompt: Visual description for the video.
        duration: 5 or 10 seconds.
        aspect_ratio: "9:16" (portrait/shorts) or "16:9" (landscape).
        output_path: Where to save the file. Auto-generated if None.

    Returns:
        Path to the downloaded video file, or None on failure.
    """
    if not FAL_KEY:
        logger.warning("[AI-Video-API] FAL_KEY not set, skipping Kling")
        return None

    if not _can_afford(duration, KLING_COST_PER_SEC):
        logger.warning(
            f"[AI-Video-API] Budget insufficient for Kling {duration}s "
            f"(need ${duration * KLING_COST_PER_SEC:.2f}, have ${_budget_remaining():.2f})"
        )
        return None

    # Normalize duration to string as fal.ai expects
    dur_str = str(min(max(duration, 5), 10))

    arguments = {
        "prompt": prompt,
        "duration": dur_str,
        "aspect_ratio": aspect_ratio,
    }

    logger.info(f"[AI-Video-API] Kling 3.0: {dur_str}s {aspect_ratio} — {prompt[:60]}...")

    # Submit and wait for completion via fal_client
    result = await _fal_submit_and_wait(KLING_MODEL, arguments)
    if not result:
        return None

    # Extract video URL from result
    video_url = None
    if isinstance(result.get("video"), dict):
        video_url = result["video"].get("url")
    elif isinstance(result.get("video"), str):
        video_url = result["video"]

    if not video_url:
        logger.error(f"[AI-Video-API] No video URL in Kling result: {json.dumps(result)[:200]}")
        return None

    # Download
    if output_path is None:
        output_path = OUTPUT_DIR / "ai_clips" / f"kling_{uuid.uuid4().hex[:8]}.mp4"
    output_path = Path(output_path)

    if await _download_video(video_url, output_path):
        cost = duration * KLING_COST_PER_SEC
        _record_spend(cost, "kling_v3", prompt, duration)
        return str(output_path)

    return None


async def generate_clip_minimax(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    output_path: Optional[Path] = None,
) -> Optional[str]:
    """
    Generate a video clip via MiniMax/Hailuo on fal.ai (cheaper fallback).

    Args:
        prompt: Visual description for the video.
        duration: 5 or 10 seconds.
        aspect_ratio: "9:16" or "16:9".
        output_path: Where to save the file.

    Returns:
        Path to the downloaded video file, or None on failure.
    """
    if not FAL_KEY:
        logger.warning("[AI-Video-API] FAL_KEY not set, skipping MiniMax")
        return None

    if not _can_afford(duration, MINIMAX_COST_PER_SEC):
        logger.warning(
            f"[AI-Video-API] Budget insufficient for MiniMax {duration}s "
            f"(need ${duration * MINIMAX_COST_PER_SEC:.2f}, have ${_budget_remaining():.2f})"
        )
        return None

    dur_str = str(min(max(duration, 5), 10))

    arguments = {
        "prompt": prompt,
        "duration": dur_str,
        "aspect_ratio": aspect_ratio,
    }

    logger.info(f"[AI-Video-API] MiniMax: {dur_str}s {aspect_ratio} — {prompt[:60]}...")

    # Submit and wait for completion via fal_client
    result = await _fal_submit_and_wait(MINIMAX_MODEL, arguments)
    if not result:
        return None

    # Extract video URL
    video_url = None
    if isinstance(result.get("video"), dict):
        video_url = result["video"].get("url")
    elif isinstance(result.get("video"), str):
        video_url = result["video"]

    if not video_url:
        logger.error(f"[AI-Video-API] No video URL in MiniMax result: {json.dumps(result)[:200]}")
        return None

    if output_path is None:
        output_path = OUTPUT_DIR / "ai_clips" / f"minimax_{uuid.uuid4().hex[:8]}.mp4"
    output_path = Path(output_path)

    if await _download_video(video_url, output_path):
        cost = duration * MINIMAX_COST_PER_SEC
        _record_spend(cost, "minimax_hailuo", prompt, duration)
        return str(output_path)

    return None


async def _generate_clip_local(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    niche: str = "",
    output_path: Optional[Path] = None,
) -> Optional[str]:
    """
    Local fallback: generate an AI image then convert to video clip
    using the existing ai_images + ai_video_generator pipeline.

    Free but lower quality than Kling/MiniMax.
    """
    try:
        from modules.ai_images import generate_image

        # Determine resolution from aspect ratio
        if aspect_ratio == "16:9":
            width, height = 1280, 720
        else:
            width, height = 720, 1280

        # Generate AI image first
        if output_path is None:
            output_path = OUTPUT_DIR / "ai_clips" / f"local_{uuid.uuid4().hex[:8]}.mp4"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        img_path = output_path.with_suffix(".png")

        logger.info(f"[AI-Video-API] FREE image generation: '{prompt[:50]}...'")
        image_result = await generate_image(
            prompt=prompt,
            output_path=str(img_path),
            niche=niche,
            orientation="landscape" if aspect_ratio == "16:9" else "portrait",
        )

        if not image_result or not Path(str(image_result)).exists():
            logger.warning("[AI-Video-API] Local image generation failed")
            return None

        # Return the image path — video_assembler applies Ken Burns for motion
        logger.info(f"[AI-Video-API] FREE image ready (Ken Burns will animate): {image_result}")
        return str(image_result)

    except ImportError as exc:
        logger.warning(f"[AI-Video-API] Local generation unavailable: {exc}")
    except Exception as exc:
        logger.error(f"[AI-Video-API] Local generation error: {exc}")
    return None


async def _fetch_pexels_fallback(
    prompt: str,
    aspect_ratio: str = "9:16",
    niche: str = "",
) -> Optional[str]:
    """
    Last resort: fetch a stock clip from Pexels matching the prompt.
    """
    try:
        from modules.visual_fetcher import search_pexels_videos, download_pexels_video

        orientation = "portrait" if aspect_ratio == "9:16" else "landscape"

        # Extract key search terms from prompt (first 3-4 meaningful words)
        search_query = " ".join(prompt.split()[:5])

        videos = search_pexels_videos(
            query=search_query,
            per_page=5,
            orientation=orientation,
            min_duration=3,
            max_duration=15,
        )

        if videos:
            video = videos[0]
            out_dir = OUTPUT_DIR / "ai_clips"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"pexels_{uuid.uuid4().hex[:8]}.mp4"

            path = download_pexels_video(video, str(out_path))
            if path and Path(path).exists():
                logger.info(f"[AI-Video-API] Pexels fallback: {path}")
                return str(path)
    except ImportError:
        logger.debug("[AI-Video-API] visual_fetcher not available for Pexels fallback")
    except Exception as exc:
        logger.warning(f"[AI-Video-API] Pexels fallback failed: {exc}")
    return None


# ── Main Entry Point ──────────────────────────────────────────────

async def generate_video_clip(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    niche: str = "",
    style: str = "cinematic",
    output_dir: Optional[str] = None,
    is_hero_shot: bool = False,
) -> Optional[dict]:
    """
    Generate a video clip using FREE-FIRST strategy.

    Priority chain (cost-optimized):
    1. Clip Library (cached/reused clips — FREE)
    2. FREE Local AI image (Gemini/FLUX/SDXL) — video_assembler adds Ken Burns
    3. Pexels stock footage (FREE)
    4. [ONLY if is_hero_shot=True AND ENABLE_HERO_SHOT=True] fal.ai Kling 3.0

    Args:
        prompt: Scene description / visual prompt.
        duration: Target duration in seconds (5 or 10).
        aspect_ratio: "9:16" for shorts or "16:9" for landscape.
        niche: Content niche for style matching.
        style: Visual style preset.
        output_dir: Optional output directory override.
        is_hero_shot: If True AND fal.ai is enabled, allows ONE paid API call.

    Returns:
        Dict with {path, source, duration, clip_id} or None if all methods fail.
    """
    if output_dir:
        out_base = Path(output_dir)
    else:
        out_base = OUTPUT_DIR / "ai_clips"
    out_base.mkdir(parents=True, exist_ok=True)

    # ── 1. Check clip library (FREE) ──
    cached = _try_clip_library(prompt, niche, aspect_ratio)
    if cached:
        return cached

    clip_id = ""

    # ── 2. FREE Local AI image generation (PRIMARY — $0 cost) ──
    out_path = out_base / f"local_{uuid.uuid4().hex[:8]}.mp4"
    path = await _generate_clip_local(prompt, duration, aspect_ratio, niche, out_path)
    if path:
        source = "local_svd" if path.endswith(".mp4") else "local_image"
        clip_id = _save_to_clip_library(path, prompt, niche, aspect_ratio, duration, source)
        logger.info(f"[AI-Video-API] FREE local generation success: {source}")
        return {"path": path, "source": source, "duration": duration, "clip_id": clip_id}

    # ── 3. Pexels stock footage (FREE) ──
    path = await _fetch_pexels_fallback(prompt, aspect_ratio, niche)
    if path:
        clip_id = _save_to_clip_library(path, prompt, niche, aspect_ratio, duration, "pexels")
        logger.info("[AI-Video-API] FREE Pexels fallback success")
        return {"path": path, "source": "pexels", "duration": duration, "clip_id": clip_id}

    # ── 4. PAID fal.ai — ONLY for hero shot if explicitly enabled ──
    if is_hero_shot and ENABLE_AI_VIDEO and ENABLE_HERO_SHOT:
        enhanced = enhance_prompt(prompt, niche, style)

        # Try MiniMax first (cheaper: $0.08/sec vs Kling $0.17/sec)
        if _can_afford(duration, MINIMAX_COST_PER_SEC):
            out_path = out_base / f"minimax_{uuid.uuid4().hex[:8]}.mp4"
            path = await generate_clip_minimax(enhanced, duration, aspect_ratio, out_path)
            if path:
                clip_id = _save_to_clip_library(path, prompt, niche, aspect_ratio, duration, "minimax_hailuo")
                return {"path": path, "source": "minimax_hailuo", "duration": duration, "clip_id": clip_id}

        # Kling as last resort (most expensive)
        if _can_afford(duration, KLING_COST_PER_SEC):
            out_path = out_base / f"kling_{uuid.uuid4().hex[:8]}.mp4"
            path = await generate_clip_kling(enhanced, duration, aspect_ratio, out_path)
            if path:
                clip_id = _save_to_clip_library(path, prompt, niche, aspect_ratio, duration, "kling_v3")
                return {"path": path, "source": "kling_v3", "duration": duration, "clip_id": clip_id}

        logger.warning("[AI-Video-API] Hero shot fal.ai failed or over budget")
    elif is_hero_shot:
        logger.info("[AI-Video-API] Hero shot requested but fal.ai DISABLED (saving money)")

    logger.error(f"[AI-Video-API] All FREE generation methods failed for: {prompt[:60]}")
    return None


async def generate_scene_visuals(
    scenes: list[dict],
    output_dir: str,
    niche: str = "",
    aspect_ratio: str = "9:16",
    style: str = "cinematic",
    max_concurrent: int = 3,
) -> list[dict]:
    """
    Generate visuals for all scenes using FREE-FIRST strategy.

    - Scene 1 (the hook) = hero shot candidate → may use fal.ai IF enabled
    - ALL other scenes = 100% FREE (local AI images + Ken Burns, or Pexels)
    - Total cost per video: $0 (default) or max ~$0.40 (if hero shot enabled)

    Args:
        scenes: List of scene dicts with "visual" or "description" key.
        output_dir: Directory to save generated clips.
        niche: Content niche for style matching.
        aspect_ratio: "9:16" or "16:9".
        style: Visual style preset.
        max_concurrent: Max parallel generations.

    Returns:
        List of dicts: {scene_number, local_path, type, duration, source}
    """
    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_scene(index: int, scene: dict) -> dict:
        async with semaphore:
            prompt = (
                scene.get("visual")
                or scene.get("visual_description")
                or scene.get("description")
                or scene.get("text", "")[:100]
            )
            if not prompt:
                logger.warning(f"[AI-Video-API] Scene {index+1}: no visual prompt, skipping")
                return {
                    "scene_number": index + 1,
                    "local_path": None,
                    "type": "none",
                    "duration": 0,
                    "source": "none",
                }

            scene_duration = scene.get("duration", 5)
            scene_duration = 5 if scene_duration <= 7 else 10

            # ONLY scene 1 (index 0) is eligible for paid hero shot
            is_hero = (index == 0)

            result = await generate_video_clip(
                prompt=prompt,
                duration=scene_duration,
                aspect_ratio=aspect_ratio,
                niche=niche,
                style=style,
                output_dir=str(out_base),
                is_hero_shot=is_hero,
            )

            if result:
                file_type = "video" if result["path"].endswith(".mp4") else "ai_image"
                return {
                    "scene_number": index + 1,
                    "local_path": result["path"],
                    "type": file_type,
                    "duration": result["duration"],
                    "source": result["source"],
                }

            return {
                "scene_number": index + 1,
                "local_path": None,
                "type": "none",
                "duration": 0,
                "source": "failed",
            }

    tasks = [_process_scene(i, scene) for i, scene in enumerate(scenes)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final: list[dict] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error(f"[AI-Video-API] Scene {i+1} exception: {r}")
            final.append({
                "scene_number": i + 1,
                "local_path": None,
                "type": "none",
                "duration": 0,
                "source": "error",
            })
        else:
            final.append(r)

    # Summary
    sources = {}
    free_count = 0
    paid_count = 0
    for f in final:
        src = f["source"]
        sources[src] = sources.get(src, 0) + 1
        if src in ("kling_v3", "minimax_hailuo", "kling_v3_img2vid"):
            paid_count += 1
        else:
            free_count += 1

    logger.info(
        f"[AI-Video-API] Scene generation complete: {len(final)} scenes | "
        f"FREE: {free_count} | PAID: {paid_count} | "
        f"Sources: {sources} | Session spend: ${_session_spend:.4f}"
    )

    return final


# ── Image-to-Video (Kling) ────────────────────────────────────────

async def generate_clip_from_image(
    image_path: str,
    prompt: str = "",
    duration: int = 5,
    aspect_ratio: str = "9:16",
    output_path: Optional[Path] = None,
) -> Optional[str]:
    """
    Generate video from an existing image via Kling 3.0 image-to-video.

    Args:
        image_path: Path to source image.
        prompt: Optional motion/style guidance prompt.
        duration: 5 or 10 seconds.
        aspect_ratio: "9:16" or "16:9".
        output_path: Where to save output.

    Returns:
        Path to generated video or None.
    """
    if not FAL_KEY:
        logger.warning("[AI-Video-API] FAL_KEY not set, skipping image-to-video")
        return None

    if not _can_afford(duration, KLING_COST_PER_SEC):
        logger.warning("[AI-Video-API] Budget insufficient for Kling image-to-video")
        return None

    img = Path(image_path)
    if not img.exists():
        logger.error(f"[AI-Video-API] Image not found: {image_path}")
        return None

    # fal.ai expects image as a data URI or URL; upload via base64 data URI
    import base64
    suffix = img.suffix.lower().lstrip(".")
    mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    mime = mime_map.get(suffix, "image/png")
    b64 = base64.b64encode(img.read_bytes()).decode()
    image_data_uri = f"data:{mime};base64,{b64}"

    dur_str = str(min(max(duration, 5), 10))

    arguments = {
        "prompt": prompt or "smooth cinematic camera movement, natural motion",
        "image_url": image_data_uri,
        "duration": dur_str,
        "aspect_ratio": aspect_ratio,
    }

    logger.info(f"[AI-Video-API] Kling img2vid: {dur_str}s from {img.name}")

    # Submit and wait for completion via fal_client
    result = await _fal_submit_and_wait(KLING_IMG2VID_MODEL, arguments)
    if not result:
        return None

    video_url = None
    if isinstance(result.get("video"), dict):
        video_url = result["video"].get("url")
    elif isinstance(result.get("video"), str):
        video_url = result["video"]

    if not video_url:
        logger.error(f"[AI-Video-API] No video URL in img2vid result")
        return None

    if output_path is None:
        output_path = OUTPUT_DIR / "ai_clips" / f"kling_i2v_{uuid.uuid4().hex[:8]}.mp4"
    output_path = Path(output_path)

    if await _download_video(video_url, output_path):
        cost = duration * KLING_COST_PER_SEC
        _record_spend(cost, "kling_v3_img2vid", prompt or "image-to-video", duration)
        return str(output_path)

    return None


# ── Utility ───────────────────────────────────────────────────────

def get_session_report() -> dict:
    """Get a summary of this session's API usage and spend."""
    return {
        "total_spend_usd": round(_session_spend, 4),
        "budget_limit_usd": _budget_limit,
        "budget_remaining_usd": round(_budget_remaining(), 4),
        "clips_generated": len(_session_clips),
        "clips": _session_clips.copy(),
    }


def reset_session() -> None:
    """Reset session tracking (for testing or new batch runs)."""
    global _session_spend, _session_clips
    _session_spend = 0.0
    _session_clips.clear()
    logger.info("[AI-Video-API] Session reset")
