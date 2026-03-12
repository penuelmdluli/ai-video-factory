"""
Visual Fetcher — Gets stock footage and images for video scenes.

Sources:
- Pexels API (free, no attribution required, 200 req/hr)
- Falls back to solid color backgrounds if API fails
"""
import random
import re
import requests
from pathlib import Path

from config import PEXELS_API_KEY


PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"

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
) -> list[dict]:
    """
    Fetch visuals for each scene in a script.

    Args:
        scenes: List of {visual_description, duration, scene_number}
        output_dir: Directory to save downloaded files
        niche_queries: Fallback search terms from niche config
        orientation: "landscape" for 16:9, "portrait" for 9:16

    Returns:
        List of {scene_number, local_path, type, duration}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    used_ids = set()

    for scene in scenes:
        scene_num = scene["scene_number"]
        visual_desc = scene.get("visual", scene.get("visual_description", ""))
        duration = scene.get("duration", scene.get("duration_seconds", 10))

        # Try searching with visual description + narration context
        narration = scene.get("narration", "")
        keywords = _extract_keywords(visual_desc, narration)
        query = " ".join(keywords[:3]) if keywords else "technology"

        # Search for videos first
        videos = search_pexels_videos(query, orientation=orientation)
        # Filter out already-used videos
        videos = [v for v in videos if v["id"] not in used_ids]

        if videos:
            chosen = random.choice(videos[:5])  # Pick from top 5
            ext = ".mp4"
            local_path = output_dir / f"scene_{scene_num:02d}{ext}"
            if download_asset(chosen["url"], local_path):
                used_ids.add(chosen["id"])
                results.append({
                    "scene_number": scene_num,
                    "local_path": str(local_path),
                    "type": "video",
                    "duration": duration,
                    "source_duration": chosen["duration"],
                })
                print(f"[Visual] Scene {scene_num}: video '{query}' -> {local_path.name}")
                continue

        # Fallback: try photos
        photos = search_pexels_photos(query, orientation=orientation)
        photos = [p for p in photos if p["id"] not in used_ids]

        if not photos and niche_queries:
            # Try niche-specific fallback queries
            fallback_query = random.choice(niche_queries)
            photos = search_pexels_photos(fallback_query, orientation=orientation)

        if photos:
            chosen = random.choice(photos[:5])
            local_path = output_dir / f"scene_{scene_num:02d}.jpg"
            if download_asset(chosen["url"], local_path):
                used_ids.add(chosen["id"])
                results.append({
                    "scene_number": scene_num,
                    "local_path": str(local_path),
                    "type": "photo",
                    "duration": duration,
                })
                print(f"[Visual] Scene {scene_num}: photo '{query}' -> {local_path.name}")
                continue

        # Last resort: solid color placeholder
        print(f"[Visual] Scene {scene_num}: no results for '{query}', using placeholder")
        results.append({
            "scene_number": scene_num,
            "local_path": None,  # Video assembler will create a solid color bg
            "type": "placeholder",
            "duration": duration,
        })

    return results


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
