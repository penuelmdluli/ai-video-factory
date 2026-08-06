"""
Visual Fetcher — Gets visuals for video scenes.

Priority:
1. Pexels stock video (real footage — best quality, most natural)
2. AI-generated images (Gemini/Cloudflare FLUX/DALL-E fallback)
3. Pexels/Pixabay stock photos (fallback)
4. Solid color placeholder (last resort)
"""
import asyncio
import os
import random
import re
import requests
from pathlib import Path

from config import PEXELS_API_KEY
from modules.ai_images import generate_image

USE_STOCK_FOOTAGE = os.getenv("USE_STOCK_FOOTAGE", "true").lower() in ("true", "1", "yes")

# Visual strategy. STOCK-FIRST (default): real Pexels footage first — instant,
# clean, no 2.5hr AI render, no blur. AI images (→ SVD clips) are the fallback.
# The local AI video model (SVD-XT) is too soft on the 2080 Ti and the sharp
# models (LTX/Wan/CogVideoX) don't run on Turing — so stock is the pragmatic win.
# Set AI_VISUALS_FIRST=true to prefer AI images again.
AI_VISUALS_FIRST = os.getenv("AI_VISUALS_FIRST", "false").lower() in ("true", "1", "yes")

# Restore + upscale cloud i2v clips (GFPGAN face-restore + Real-ESRGAN x2) — the same
# enhancer the local SVD path uses. Default ON. By default only the HERO/hook clip
# (scene 1 — the money shot) is enhanced, which keeps builds fast; per-frame GFPGAN on
# every clip is far too slow on the 2080 Ti. Set ENHANCE_ALL_CLIPS=true to enhance all.
ENABLE_CLIP_ENHANCE = os.getenv("ENABLE_CLIP_ENHANCE", "true").lower() in ("true", "1", "yes")
ENHANCE_ALL_CLIPS = os.getenv("ENHANCE_ALL_CLIPS", "false").lower() in ("true", "1", "yes")

try:
    from config import (I2V_BACKEND, ENABLE_HERO_PREMIUM, HERO_PREMIUM_MODEL,
                        HERO_PREMIUM_RESOLUTION, HERO_PREMIUM_NICHES, HERO_PREMIUM_DAILY_MAX)
except Exception:
    I2V_BACKEND = os.getenv("I2V_BACKEND", "wavespeed").lower()
    ENABLE_HERO_PREMIUM = os.getenv("ENABLE_HERO_PREMIUM", "false").lower() in ("true", "1", "yes")
    HERO_PREMIUM_MODEL = os.getenv("HERO_PREMIUM_MODEL", "seedance")
    HERO_PREMIUM_RESOLUTION = os.getenv("HERO_PREMIUM_RESOLUTION", "720p")
    HERO_PREMIUM_NICHES = [n.strip() for n in os.getenv("HERO_PREMIUM_NICHES", "tech_news").split(",") if n.strip()]
    HERO_PREMIUM_DAILY_MAX = int(os.getenv("HERO_PREMIUM_DAILY_MAX", "6"))


# ── Premium hero-shot daily counter (hard cap so cost can't run away) ──
_HERO_PREMIUM_FILE = Path("output/hero_premium_count.json")


def _hero_premium_today(day: str) -> int:
    try:
        import json
        return int(json.loads(_HERO_PREMIUM_FILE.read_text()).get(day, 0))
    except Exception:
        return 0


def _hero_premium_record(day: str) -> None:
    import json
    try:
        data = json.loads(_HERO_PREMIUM_FILE.read_text()) if _HERO_PREMIUM_FILE.exists() else {}
    except Exception:
        data = {}
    data[day] = int(data.get(day, 0)) + 1
    _HERO_PREMIUM_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HERO_PREMIUM_FILE.write_text(json.dumps(data, indent=2))


def _looks_like_composite(image_path) -> bool:
    """Detect a FLUX 'stacked diptych' still — two scenes joined by a hard full-width
    horizontal seam — so we NEVER pay premium i2v to animate a broken image. Measures the
    strongest row-to-row discontinuity in the middle band. Calibrated conservatively
    (real single-scene stills peak ~26-41 / ratio ~3-4; a diptych peaks ~130 / ratio ~9),
    so it only flags an obvious composite. Returns False on any error (never blocks)."""
    try:
        from PIL import Image
        import numpy as np
        a = np.asarray(Image.open(image_path).convert("L").resize((96, 160)), dtype=float)
        d = np.abs(np.diff(a, axis=0)).mean(axis=1)          # per-row change across width
        n = len(d)
        band = d[int(n * 0.15):int(n * 0.85)]                # ignore top/bottom edges
        if band.size == 0:
            return False
        peak = float(band.max())
        ratio = peak / (float(np.median(d)) + 1e-6)
        return peak > 70.0 and ratio > 6.0
    except Exception:
        return False


PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PIXABAY_API_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Cache fetched videos to avoid re-downloading
_video_cache: dict[str, list] = {}


def search_pexels_videos(
    query: str,
    per_page: int = 10,
    orientation: str = "landscape",
    min_duration: int = 5,
    max_duration: int = 30,
) -> list[dict]:
    """
    Search Pexels for stock videos.

    Returns list of dicts: {url, width, height, duration, id}
    """
    if not PEXELS_API_KEY:
        return []

    # Check cache
    cache_key = f"{query}_{orientation}"
    if cache_key in _video_cache:
        return _video_cache[cache_key]

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
        }
        resp = requests.get(PEXELS_VIDEO_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for video in data.get("videos", []):
            duration = video.get("duration", 0)
            if duration < min_duration or duration > max_duration:
                continue

            # Get the best quality file (HD preferred)
            best_file = None
            for vf in video.get("video_files", []):
                if vf.get("quality") == "hd":
                    best_file = vf
                    break
            if not best_file and video.get("video_files"):
                best_file = video["video_files"][0]

            if best_file:
                results.append({
                    "url": best_file["link"],
                    "width": best_file.get("width", 1920),
                    "height": best_file.get("height", 1080),
                    "duration": duration,
                    "id": video["id"],
                    "type": "video",
                })

        _video_cache[cache_key] = results
        return results

    except Exception as e:
        print(f"[Visual] Pexels video search failed for '{query}': {e}")
        return []


def search_pexels_photos(
    query: str,
    per_page: int = 10,
    orientation: str = "landscape",
) -> list[dict]:
    """Search Pexels for stock photos."""
    if not PEXELS_API_KEY:
        return []

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
        }
        resp = requests.get(PEXELS_PHOTO_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        return [
            {
                "url": photo["src"]["large2x"],
                "width": photo["width"],
                "height": photo["height"],
                "id": photo["id"],
                "type": "photo",
            }
            for photo in data.get("photos", [])
        ]

    except Exception as e:
        print(f"[Visual] Pexels photo search failed for '{query}': {e}")
        return []


def search_pixabay_videos(
    query: str,
    per_page: int = 10,
    min_duration: int = 5,
    max_duration: int = 60,
) -> list[dict]:
    """
    Search Pixabay for free stock videos.
    More documentary/editorial content than Pexels.
    Free API key: 5000 requests/hour.
    """
    if not PIXABAY_API_KEY:
        return []

    cache_key = f"pixabay_v_{query}"
    if cache_key in _video_cache:
        return _video_cache[cache_key]

    try:
        params = {
            "key": PIXABAY_API_KEY,
            "q": query,
            "per_page": per_page,
            "safesearch": "true",
            "video_type": "film",  # Higher quality
        }
        resp = requests.get(PIXABAY_VIDEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for hit in data.get("hits", []):
            duration = hit.get("duration", 0)
            if duration < min_duration or duration > max_duration:
                continue

            # Get medium quality (good balance of quality/size)
            videos = hit.get("videos", {})
            medium = videos.get("medium", {})
            large = videos.get("large", {})
            best = large if large.get("url") else medium

            if best.get("url"):
                results.append({
                    "url": best["url"],
                    "width": best.get("width", 1920),
                    "height": best.get("height", 1080),
                    "duration": duration,
                    "id": hit.get("id"),
                    "type": "video",
                    "source": "pixabay",
                })

        _video_cache[cache_key] = results
        return results

    except Exception as e:
        print(f"[Visual] Pixabay video search failed for '{query}': {e}")
        return []


def search_pixabay_photos(
    query: str,
    per_page: int = 10,
    orientation: str = "horizontal",
) -> list[dict]:
    """
    Search Pixabay for free stock photos.
    Has strong editorial/documentary photography.
    """
    if not PIXABAY_API_KEY:
        return []

    try:
        params = {
            "key": PIXABAY_API_KEY,
            "q": query,
            "per_page": per_page,
            "image_type": "photo",
            "orientation": orientation,
            "safesearch": "true",
        }
        resp = requests.get(PIXABAY_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        return [
            {
                "url": hit["largeImageURL"],
                "width": hit.get("imageWidth", 1920),
                "height": hit.get("imageHeight", 1080),
                "id": hit.get("id"),
                "type": "photo",
                "source": "pixabay",
            }
            for hit in data.get("hits", [])
        ]

    except Exception as e:
        print(f"[Visual] Pixabay photo search failed for '{query}': {e}")
        return []


def download_asset(url: str, output_path: Path) -> bool:
    """Download a video or image from URL."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[Visual] Download failed: {e}")
        return False


def _extract_keywords(visual_description: str, narration: str = "") -> list[str]:
    """Extract searchable keywords from visual description + narration context."""
    stop_words = {
        "a", "an", "the", "of", "in", "on", "at", "to", "for", "with",
        "and", "or", "but", "is", "are", "was", "were", "showing",
        "displayed", "screen", "view", "shot", "image", "clip",
        "this", "that", "these", "those", "what", "how", "why", "when",
        "just", "now", "here", "there", "about", "into", "from",
        "been", "have", "had", "has", "would", "could", "should",
        "will", "can", "not", "don", "didn", "doesn", "won",
        "let", "get", "got", "going", "actually", "really", "very",
        "you", "your", "our", "they", "them", "their", "its",
    }
    # Filter out abstract/unsearchable words that return garbage stock footage
    abstract_words = {
        "abstract", "concept", "unknown", "symbols", "metaphor", "essence",
        "notion", "idea", "feeling", "sense", "impression", "split",
        "montage", "visualization", "representation", "illustration",
    }
    stop_words.update(abstract_words)

    # Prioritize visual description keywords, then supplement from narration
    vis_words = re.findall(r'\b\w+\b', visual_description.lower())
    vis_keywords = [w for w in vis_words if w not in stop_words and len(w) > 2]

    # Extract high-value keywords from narration (nouns, specific terms)
    narr_words = re.findall(r'\b\w+\b', narration.lower())
    narr_keywords = [w for w in narr_words if w not in stop_words and len(w) > 3]

    # Combine: visual keywords first, then unique narration keywords
    combined = vis_keywords[:3]
    for kw in narr_keywords:
        if kw not in combined and len(combined) < 5:
            combined.append(kw)

    return combined[:5]


async def fetch_visuals_for_scenes(
    scenes: list[dict],
    output_dir: Path,
    niche_queries: list[str] | None = None,
    orientation: str = "landscape",
    niche: str = "",
) -> list[dict]:
    """
    Fetch visuals for each scene in a script.

    Priority:
    1. Pexels stock video (real footage — best quality)
    2. AI-generated image (fallback if no stock video)
    3. Stock photos from Pexels/Pixabay
    4. Solid color placeholder (last resort)

    Args:
        scenes: List of {visual_description, duration, scene_number}
        output_dir: Directory to save downloaded files
        niche_queries: Fallback search terms from niche config
        orientation: "landscape" for 16:9, "portrait" for 9:16
        niche: Niche identifier for AI image style matching

    Returns:
        List of {scene_number, local_path, type, duration}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ai_dir = output_dir / "ai_images"
    ai_dir.mkdir(parents=True, exist_ok=True)
    ws_dir = output_dir / "wavespeed_clips"
    ws_dir.mkdir(parents=True, exist_ok=True)

    results = []
    used_ids = set()
    total_scenes = len(scenes)

    # ── VISUAL STRATEGY ────────────────────────────────────────────
    # AI_VISUALS_FIRST (default): AI images → SVD-XT motion clips come first,
    #   stock footage only as an emergency fallback. Matches the "AI over stock"
    #   preference and actually exercises the local video model.
    # AI_VISUALS_FIRST=false: legacy stock-first behaviour.

    async def _try_ai_image(scene_num, visual_desc, narration, duration):
        """Generate an AI image for this scene (later converted to an SVD-XT clip)."""
        ai_prompt = visual_desc or narration or "cinematic scene"
        ai_path = ai_dir / f"ai_scene_{scene_num:02d}.png"
        try:
            result_path = await generate_image(
                prompt=ai_prompt,
                output_path=ai_path,
                niche=niche,
                orientation=orientation,
            )
        except Exception as e:
            print(f"[Visual] Scene {scene_num}: AI generation error: {e}")
            return None
        if result_path:
            label = "primary" if AI_VISUALS_FIRST else "fallback"
            print(f"[Visual] Scene {scene_num}: AI image ({label}) -> {ai_path.name}")
            return {
                "scene_number": scene_num,
                "local_path": str(result_path),
                "type": "ai_image",
                "duration": duration,
            }
        return None

    def _try_stock_video(scene_num, query, duration):
        """Fetch a Pexels stock clip for this scene."""
        try:
            videos = search_pexels_videos(query, orientation=orientation)
            videos = [v for v in videos if v["id"] not in used_ids]
        except Exception as e:
            print(f"[Visual] Scene {scene_num}: Pexels search error: {e}")
            videos = []

        if not videos and niche_queries:
            fallback_query = random.choice(niche_queries)
            try:
                videos = search_pexels_videos(fallback_query, orientation=orientation)
                videos = [v for v in videos if v["id"] not in used_ids]
            except Exception:
                videos = []

        if videos:
            chosen = random.choice(videos[:5])
            local_path = output_dir / f"scene_{scene_num:02d}.mp4"
            if download_asset(chosen["url"], local_path):
                used_ids.add(chosen["id"])
                print(f"[Visual] Scene {scene_num}: stock video '{query}' -> {local_path.name}")
                return {
                    "scene_number": scene_num,
                    "local_path": str(local_path),
                    "type": "video",
                    "duration": duration,
                    "source_duration": chosen["duration"],
                }
        return None

    async def _try_wavespeed(scene_num, visual_desc, narration, duration):
        """FLUX war image -> sharp WaveSpeed cloud clip. None if it fails/over-budget."""
        import asyncio as _aio
        # 1) generate the AI still (reuse the AI-image path)
        ai = await _try_ai_image(scene_num, visual_desc, narration, duration)
        if not ai or not ai.get("local_path"):
            return None
        # 2) send it to WaveSpeed (runs on cloud GPU) — off-thread (blocking HTTP)
        try:
            from modules.wavespeed_video import generate as ws_generate
            from config import WAVESPEED_MODEL, WAVESPEED_RESOLUTION, WAVESPEED_DURATION
            clip_path = ws_dir / f"scene_{scene_num:02d}_ws.mp4"
            base = visual_desc or narration or "frontline war action, real combat"
            motion_prompt = (
                f"{base}. INTENSE MOTION — people running and moving fast, vehicles "
                f"driving, explosions and debris flying, thick smoke billowing and drifting, "
                f"sparks and dust in the air, fast dynamic handheld camera with strong push, "
                f"pan and shake, quick action. Everything alive and moving, high energy, "
                f"cinematic war footage. Avoid static shots and still frozen subjects."
            )
            result = await _aio.to_thread(
                ws_generate, ai["local_path"], str(clip_path),
                motion_prompt, WAVESPEED_MODEL, WAVESPEED_RESOLUTION, WAVESPEED_DURATION,
            )
        except Exception as e:
            print(f"[Visual] Scene {scene_num}: WaveSpeed error: {e}")
            result = None
        if result:
            print(f"[Visual] Scene {scene_num}: WaveSpeed clip -> {Path(result).name}")
            return {"scene_number": scene_num, "local_path": result,
                    "type": "ai_video", "duration": duration,
                    "source_image": ai["local_path"]}
        return None

    async def _try_runpod(scene_num, visual_desc, narration, duration):
        """FLUX/SDXL war image -> LTX image-to-video on RunPod (endpoint
        mp2awqavthuc2b, ~$0.02-0.05 vs WaveSpeed $0.15). Same rail Zuzu uses.
        None if it fails/times out."""
        import asyncio as _aio
        # 1) generate the AI still (same path WaveSpeed uses)
        ai = await _try_ai_image(scene_num, visual_desc, narration, duration)
        if not ai or not ai.get("local_path"):
            return None
        # 2) animate it on the LTX i2v endpoint (off-thread — blocking HTTP)
        try:
            from modules.runpod_ltx import generate as ltx_generate
            clip_path = ws_dir / f"scene_{scene_num:02d}_rp.mp4"
            base = visual_desc or narration or "frontline war action, real combat"
            motion_prompt = (
                f"{base}. INTENSE MOTION — people running and moving fast, vehicles "
                f"driving, explosions and debris flying, thick smoke billowing and drifting, "
                f"sparks and dust in the air, fast dynamic handheld camera with strong push, "
                f"pan and shake, quick action. Everything alive and moving, high energy, "
                f"cinematic war footage. Avoid static shots and still frozen subjects."
            )
            # LTX wants dims that are multiples of 32. Higher res = sharper war
            # footage (was 480 -> soft when upscaled to 1080). 640x1152 ≈ 9:16.
            w, h = (640, 1152) if orientation == "portrait" else (1152, 640)
            result = await _aio.to_thread(
                ltx_generate, ai["local_path"], str(clip_path), motion_prompt, w, h,
                97, 50,   # num_frames, steps (more steps = cleaner, less morphing)
            )
        except Exception as e:
            print(f"[Visual] Scene {scene_num}: RunPod error: {e}")
            result = None
        if result:
            print(f"[Visual] Scene {scene_num}: RunPod LTX clip -> {Path(result).name}")
            return {"scene_number": scene_num, "local_path": result,
                    "type": "ai_video", "duration": duration,
                    "source_image": ai["local_path"]}
        return None

    async def _try_wan(scene_num, visual_desc, narration, duration):
        """SDXL still -> Wan 2.2 image-to-video on our own RunPod serverless
        endpoint (worker-comfyui). Top open-model quality at GPU-only cost
        (~$0.05-0.12/clip). Returns None if the endpoint isn't provisioned yet
        or the render fails, so the router falls back to LTX."""
        import asyncio as _aio
        ai = await _try_ai_image(scene_num, visual_desc, narration, duration)
        if not ai or not ai.get("local_path"):
            return None
        try:
            from modules.runpod_wan import generate as wan_generate
            clip_path = ws_dir / f"scene_{scene_num:02d}_wan.mp4"
            base = visual_desc or narration or "cinematic scene"
            motion_prompt = (
                f"{base}. Dynamic, cinematic motion with energy and drama — bold camera "
                f"movement (a strong push-in and parallax), subjects clearly moving with "
                f"life, real momentum, crisp and sharp, realistic news-film footage. "
                f"No fog, no haze, no morphing, no warping."
            )
            w, h = (640, 1152) if orientation == "portrait" else (1152, 640)
            result = await _aio.to_thread(
                wan_generate, ai["local_path"], str(clip_path), motion_prompt, w, h,
                81, 10,   # num_frames, steps (Wan 2.2 std; template isn't 4-step Lightning by default)
            )
        except Exception as e:
            print(f"[Visual] Scene {scene_num}: Wan error: {e}")
            result = None
        if result:
            print(f"[Visual] Scene {scene_num}: RunPod Wan 2.2 clip -> {Path(result).name}")
            return {"scene_number": scene_num, "local_path": result,
                    "type": "ai_video", "duration": duration,
                    "source_image": ai["local_path"]}
        return None

    async def _try_hero_premium(scene_num, visual_desc, narration, duration):
        """PREMIUM hook shot: a free FLUX/SDXL still -> Seedance 2.0 (top-tier cloud
        i2v) for a cinematic, Hollywood-grade opening with clean human motion. Scene 1
        ONLY, and gated hard on cost: master switch + niche allow-list + daily cap +
        WaveSpeed monthly budget. Returns None (so the normal chain runs) whenever it's
        disabled, over any cap, or fails — the pipeline never breaks or overspends."""
        import asyncio as _aio
        from datetime import datetime
        if not ENABLE_HERO_PREMIUM:
            return None
        if HERO_PREMIUM_NICHES and niche not in HERO_PREMIUM_NICHES:
            return None
        day = datetime.now().strftime("%Y-%m-%d")
        if _hero_premium_today(day) >= HERO_PREMIUM_DAILY_MAX:
            print(f"[Visual] Scene {scene_num}: premium daily cap "
                  f"({HERO_PREMIUM_DAILY_MAX}) reached — standard tier")
            return None
        try:
            from modules import wavespeed_video as ws
            if not ws.can_afford(HERO_PREMIUM_MODEL, HERO_PREMIUM_RESOLUTION, datetime.now().isoformat()):
                print(f"[Visual] Scene {scene_num}: premium over monthly budget — standard tier")
                return None
        except Exception:
            return None
        # free still first — keeps composition/subject and costs nothing extra
        ai = await _try_ai_image(scene_num, visual_desc, narration, duration)
        if not ai or not ai.get("local_path"):
            return None
        # GUARD: never pay premium i2v to animate a broken 2-panel/collage still
        if _looks_like_composite(ai["local_path"]):
            print(f"[Visual] Scene {scene_num}: hero still looks like a split composite "
                  f"— skipping premium (saved ~$0.70), using standard tier")
            return None
        try:
            clip_path = ws_dir / f"scene_{scene_num:02d}_hero_premium.mp4"
            base = visual_desc or narration or "cinematic scene"
            motion_prompt = (
                f"{base}. Cinematic, Hollywood-grade motion: people moving and gesturing "
                f"naturally and clearly, a smooth dramatic camera push-in with parallax, "
                f"crisp realistic film-quality footage and lighting. No morphing, no warping."
            )
            result = await _aio.to_thread(
                ws.generate, ai["local_path"], str(clip_path), motion_prompt,
                HERO_PREMIUM_MODEL, HERO_PREMIUM_RESOLUTION, 5,
            )
        except Exception as e:
            print(f"[Visual] Scene {scene_num}: premium hero error: {e}")
            result = None
        if result:
            _hero_premium_record(datetime.now().strftime("%Y-%m-%d"))
            print(f"[Visual] Scene {scene_num}: *PREMIUM* hero "
                  f"({HERO_PREMIUM_MODEL} {HERO_PREMIUM_RESOLUTION}) -> {Path(result).name}")
            return {"scene_number": scene_num, "local_path": result,
                    "type": "ai_video", "duration": duration,
                    "source_image": ai["local_path"]}
        return None

    async def _process_scene(scene):
        scene_num = scene["scene_number"]
        visual_desc = scene.get("visual", scene.get("visual_description", ""))
        duration = scene.get("duration", scene.get("duration_seconds", 10))
        narration = scene.get("narration", "")
        keywords = _extract_keywords(visual_desc, narration)
        query = " ".join(keywords[:3]) if keywords else "cinematic"

        # ── PREMIUM hero shot: scene 1 (the hook) only, top-tier cloud model,
        #    cost-gated. Succeeds -> use it; else fall through to the normal chain. ──
        if scene_num == 1:
            hero = await _try_hero_premium(scene_num, visual_desc, narration, duration)
            if hero is not None:
                return hero

        # ── Strategy: cloud AI clip first (sharp), STOCK footage fallback ──
        if I2V_BACKEND == "wan":
            # Wan 2.2 on our RunPod endpoint -> LTX -> WaveSpeed -> stock
            chosen = await _try_wan(scene_num, visual_desc, narration, duration)
            if chosen is None:
                chosen = await _try_runpod(scene_num, visual_desc, narration, duration)
            if chosen is None:
                chosen = await _try_wavespeed(scene_num, visual_desc, narration, duration)
            if chosen is None and USE_STOCK_FOOTAGE:
                chosen = _try_stock_video(scene_num, query, duration)
        elif I2V_BACKEND == "runpod":
            chosen = await _try_runpod(scene_num, visual_desc, narration, duration)
            if chosen is None:   # safety: fall back to WaveSpeed so the pipeline never breaks
                chosen = await _try_wavespeed(scene_num, visual_desc, narration, duration)
            if chosen is None and USE_STOCK_FOOTAGE:
                chosen = _try_stock_video(scene_num, query, duration)
        elif I2V_BACKEND == "wavespeed":
            chosen = await _try_wavespeed(scene_num, visual_desc, narration, duration)
            if chosen is None and USE_STOCK_FOOTAGE:
                chosen = _try_stock_video(scene_num, query, duration)
        elif AI_VISUALS_FIRST:
            chosen = await _try_ai_image(scene_num, visual_desc, narration, duration)
            if chosen is None and USE_STOCK_FOOTAGE:
                chosen = _try_stock_video(scene_num, query, duration)
        else:
            chosen = _try_stock_video(scene_num, query, duration) if USE_STOCK_FOOTAGE else None
            if chosen is None:
                chosen = await _try_ai_image(scene_num, visual_desc, narration, duration)

        if chosen is not None:
            return chosen

        # ── 3. FALLBACK: Stock photos (Pexels + Pixabay) ──────────
        try:
            photos = search_pexels_photos(query, orientation=orientation)
            photos = [p for p in photos if p["id"] not in used_ids]
        except Exception:
            photos = []

        if not photos and niche_queries:
            fallback_query = random.choice(niche_queries)
            try:
                photos = search_pexels_photos(fallback_query, orientation=orientation)
            except Exception:
                photos = []

        if not photos:
            try:
                pix_orientation = "vertical" if orientation == "portrait" else "horizontal"
                photos = search_pixabay_photos(query, orientation=pix_orientation)
            except Exception:
                photos = []

        if photos:
            chosen = random.choice(photos[:5])
            local_path = output_dir / f"scene_{scene_num:02d}.jpg"
            if download_asset(chosen["url"], local_path):
                used_ids.add(chosen["id"])
                print(f"[Visual] Scene {scene_num}: stock photo '{query}' -> {local_path.name}")
                return {
                    "scene_number": scene_num,
                    "local_path": str(local_path),
                    "type": "photo",
                    "duration": duration,
                }

        # ── 4. Last resort: solid color placeholder ─────────────
        print(f"[Visual] Scene {scene_num}: no visuals available, using placeholder")
        return {
            "scene_number": scene_num,
            "local_path": None,  # Video assembler will create a solid color bg
            "type": "placeholder",
            "duration": duration,
        }

    # ── Generate all scenes CONCURRENTLY so the i2v clips render in PARALLEL ──
    # Was sequential (6 clips x ~7.5min = ~45min). Now the whole i2v stage takes
    # roughly one clip's time, bounded by MAX_I2V_CONCURRENCY (and by how many
    # workers the RunPod/WaveSpeed endpoint scales to). asyncio.gather preserves
    # scene order. A scene that errors degrades to a placeholder, never crashes.
    _maxc = max(1, int(os.getenv("MAX_I2V_CONCURRENCY", "6")))
    _sem = asyncio.Semaphore(_maxc)

    async def _bounded(sc):
        async with _sem:
            try:
                return await _process_scene(sc)
            except Exception as e:
                print(f"[Visual] Scene {sc.get('scene_number', '?')} failed ({e}) — placeholder")
                return {"scene_number": sc.get("scene_number"), "local_path": None,
                        "type": "placeholder", "duration": sc.get("duration", 10)}

    print(f"[Visual] Generating {len(scenes)} scenes concurrently (max {_maxc} at once)...")
    results = list(await asyncio.gather(*[_bounded(s) for s in scenes]))

    # ── 4. Image-to-Video conversion (SVD-XT) ────────────────
    # Convert AI images into video clips with natural motion
    ai_image_count = sum(1 for r in results if r.get("type") == "ai_image")
    if ai_image_count > 0:
        try:
            from modules.ai_video_generator import convert_images_to_videos
            vid_dir = output_dir / "ai_videos"
            results = await convert_images_to_videos(results, vid_dir, niche=niche)
        except ImportError:
            print("[Visual] Image-to-video module not available, using Ken Burns")
        except Exception as e:
            print(f"[Visual] Image-to-video conversion failed: {e}, using Ken Burns")

    # ── Enhance cloud i2v clips (Wan / LTX / WaveSpeed / Seedance hero) ────────
    # convert_images_to_videos above only runs (and enhances) when there are AI images
    # to convert. On the cloud i2v path scenes come back as finished "ai_video" clips, so
    # that branch is skipped and those clips would ship un-restored/un-upscaled. Run the
    # SAME GFPGAN + Real-ESRGAN pass here on any clip not yet enhanced. The local GPU is
    # free (the i2v ran in the cloud), and dims follow the target orientation.
    if ENABLE_CLIP_ENHANCE:
        pending = [r for r in results
                   if r.get("type") == "ai_video" and r.get("local_path")
                   and not r.get("enhanced") and Path(r["local_path"]).exists()]
        if not ENHANCE_ALL_CLIPS:
            # hero/hook only (scene 1 = the money shot) — keeps builds fast
            pending = [r for r in pending if r.get("scene_number") == 1]
        clip_paths = [r["local_path"] for r in pending]
        if clip_paths:
            tw, th = (1080, 1920) if orientation == "portrait" else (1920, 1080)
            try:
                import asyncio as _aio, time as _t
                from modules.clip_enhancer import enhance_clips
                _e0 = _t.time()
                print(f"[Visual] Enhancing {len(clip_paths)} cloud clip(s) "
                      f"(GFPGAN + Real-ESRGAN -> {tw}x{th})...")
                n = await _aio.to_thread(enhance_clips, clip_paths, tw, th)
                for r in pending:
                    r["enhanced"] = True
                print(f"[Visual] Enhanced {n}/{len(clip_paths)} clip(s) in {_t.time() - _e0:.0f}s")
            except Exception as e:
                print(f"[Visual] Clip enhancement skipped ({str(e)[:100]})")

    return results


async def fetch_visuals_for_viral_shorts(
    scenes: list[dict],
    output_dir: Path,
    niche: str = "",
    aspect_ratio: str = "9:16",
) -> list[dict]:
    """
    Fetch visuals for viral shorts — FREE-FIRST strategy.

    Default behavior ($0 cost):
    1. Clip library (FREE — reuse existing clips)
    2. FREE AI images (Gemini 500/day, Cloudflare FLUX 100K/day, SDXL)
       → video_assembler applies Ken Burns animation for motion
    3. Pexels stock footage (FREE)

    Optional (if ENABLE_HERO_SHOT=true):
    4. Scene 1 only → fal.ai Kling/MiniMax (max $0.40 per video)

    Cost: $0/video (default) or max $0.40/video (with hero shot)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Route through ai_video_api which now handles FREE-first logic
    try:
        from modules.ai_video_api import generate_scene_visuals, ENABLE_AI_VIDEO
        mode = "FREE-first"
        if ENABLE_AI_VIDEO:
            mode += " + hero shot enabled"
        print(f"[Visual] Visual pipeline: {mode} (saving money!)")
        results = await generate_scene_visuals(
            scenes=scenes,
            output_dir=output_dir,
            niche=niche,
            aspect_ratio=aspect_ratio,
        )
        if results:
            # Count sources for transparency
            free = sum(1 for r in results if r.get("source") not in ("kling_v3", "minimax_hailuo"))
            paid = sum(1 for r in results if r.get("source") in ("kling_v3", "minimax_hailuo"))
            print(f"[Visual] {len(results)} scenes: {free} FREE, {paid} PAID")
            return results
    except ImportError:
        print("[Visual] AI Video API not available, using standard FREE pipeline")
    except Exception as e:
        print(f"[Visual] AI Video API error: {e}, using standard FREE pipeline")

    # Fallback: standard AI image pipeline (100% FREE)
    print("[Visual] Using standard AI image pipeline (100% FREE)")
    return await fetch_visuals_for_scenes(
        scenes=scenes,
        output_dir=output_dir,
        orientation="portrait" if "9:16" in aspect_ratio else "landscape",
        niche=niche,
    )


# CLI test
if __name__ == "__main__":
    import asyncio

    async def test():
        scenes = [
            {"scene_number": 1, "visual": "stock market trading chart", "duration": 10},
            {"scene_number": 2, "visual": "person using laptop coding", "duration": 8},
            {"scene_number": 3, "visual": "money growth finance", "duration": 12},
        ]
        results = await fetch_visuals_for_scenes(
            scenes, OUTPUT_DIR / "test_visuals", orientation="landscape"
        )
        for r in results:
            print(f"  Scene {r['scene_number']}: {r['type']} -> {r.get('local_path', 'placeholder')}")

    asyncio.run(test())
