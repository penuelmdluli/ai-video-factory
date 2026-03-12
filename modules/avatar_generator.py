"""
Avatar Generator - AI talking head via D-ID Clips API (premium presenters).

Generates a full-duration avatar clip that appears as a PiP (picture-in-picture)
overlay in the corner of the video throughout its entire duration.

Uses D-ID's premium studio presenters for best quality.
"""
import asyncio
import httpx
from pathlib import Path

from config import DID_API_KEY, ENABLE_AVATAR, ASSETS_DIR


DID_BASE_URL = "https://api.d-id.com"

# Premium D-ID studio presenters — best quality, per-niche
# Voice gender MUST match presenter gender (male voice = male avatar, female voice = female avatar)
NICHE_PRESENTERS = {
    "ai_trading": "v2_public_Lily_NoHands_RedShirt_Office@JDOtgQlb_L",         # Female — matches JennyNeural
    "ai_money": "v2_public_Kayla_NoHands_BlackShirt_CoffeeShop@u1un3hTUDJ",     # Female — matches AriaNeural
    "tech_news": "v2_public_Fiona_NoHands_BlackJacket_ClassRoom@1BOeggEufb",    # Female — matches SoniaNeural
    "motivation": "v2_public_Rian_NoHands_RedJacket_Lobby@eEW_j8_sK6",         # Male — matches ChristopherNeural (deep male)
    "health_wellness": "v2_public_Fiona_NoHands_BlueShirt_Lab@5HRTMswT4U",     # Female — matches AriaNeural
    "blissful_moments": "v2_public_Kayla_NoHands_BlackShirt_CoffeeShop@u1un3hTUDJ", # Female — matches AriaNeural
}
DEFAULT_PRESENTER = "v2_public_Lily_NoHands_RedShirt_Office@JDOtgQlb_L"

# Fallback: custom source image (talks API)
DEFAULT_AVATAR_URL = "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg"


def _get_auth_header() -> dict:
    """Build D-ID auth headers."""
    return {
        "Authorization": f"Basic {DID_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _upload_audio_to_url(audio_path: str) -> str | None:
    """Upload audio to D-ID's asset endpoint to get a public URL."""
    if not DID_API_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{DID_BASE_URL}/audios",
                    headers={
                        "Authorization": f"Basic {DID_API_KEY}",
                        "Accept": "application/json",
                    },
                    files={"audio": (Path(audio_path).name, f, "audio/mpeg")},
                )

            if response.status_code in (200, 201):
                data = response.json()
                audio_url = data.get("url") or data.get("result_url")
                print(f"[Avatar] Audio uploaded: {audio_url[:60]}...")
                return audio_url
            else:
                print(f"[Avatar] Audio upload failed: {response.status_code} {response.text[:200]}")
                return None
    except Exception as e:
        print(f"[Avatar] Audio upload error: {e}")
        return None


async def _poll_for_result(
    client: httpx.AsyncClient,
    endpoint: str,
    max_wait: int = 300,
) -> dict | None:
    """Poll a D-ID endpoint until done, error, or timeout."""
    for _ in range(max_wait // 3):
        await asyncio.sleep(3)
        resp = await client.get(endpoint, headers=_get_auth_header())
        if resp.status_code != 200:
            continue
        data = resp.json()
        status = data.get("status")
        if status == "done":
            return data
        elif status in ("error", "rejected"):
            print(f"[Avatar] Failed: {data.get('error', data.get('reject_reason', status))}")
            return None
    print("[Avatar] Timed out waiting for D-ID")
    return None


async def generate_avatar_clip(
    audio_path: str,
    output_path: str | Path,
    niche: str = "ai_trading",
    max_wait_seconds: int = 300,
) -> str | None:
    """
    Generate a full-duration talking head clip using D-ID Clips API.

    Uses premium studio presenters for best quality.
    Falls back to Talks API with default avatar if clips fail.

    Returns: path to generated MP4, or None on failure.
    """
    if not ENABLE_AVATAR or not DID_API_KEY:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Upload audio
    audio_url = await _upload_audio_to_url(audio_path)
    if not audio_url:
        return None

    presenter_id = NICHE_PRESENTERS.get(niche, DEFAULT_PRESENTER)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Try Clips API first (premium presenters, best quality)
            response = await client.post(
                f"{DID_BASE_URL}/clips",
                headers=_get_auth_header(),
                json={
                    "presenter_id": presenter_id,
                    "script": {
                        "type": "audio",
                        "audio_url": audio_url,
                        "subtitles": False,
                    },
                    "config": {
                        "result_format": "mp4",
                        "fluent": True,
                        "pad_audio": 0.0,
                    },
                    "driver_url": "bank://lively/",
                },
            )

            if response.status_code in (200, 201):
                clip_id = response.json()["id"]
                presenter_name = presenter_id.split("@")[0].replace("v2_public_", "")
                print(f"[Avatar] Clip created (presenter: {presenter_name}): {clip_id}")

                result = await _poll_for_result(
                    client, f"{DID_BASE_URL}/clips/{clip_id}", max_wait_seconds,
                )
                if result:
                    result_url = result.get("result_url")
                    if result_url:
                        video_resp = await client.get(result_url, timeout=120)
                        if video_resp.status_code == 200:
                            output_path.write_bytes(video_resp.content)
                            size_kb = len(video_resp.content) / 1024
                            print(f"[Avatar] Generated (clips): {output_path.name} ({size_kb:.0f}KB)")
                            return str(output_path)

            # Fallback to Talks API with custom avatar
            print(f"[Avatar] Clips API didn't complete, trying Talks API fallback...")
            from config import DID_AVATAR_IMAGE_URL
            avatar_url = DID_AVATAR_IMAGE_URL or DEFAULT_AVATAR_URL

            response = await client.post(
                f"{DID_BASE_URL}/talks",
                headers=_get_auth_header(),
                json={
                    "script": {
                        "type": "audio",
                        "audio_url": audio_url,
                        "subtitles": False,
                    },
                    "source_url": avatar_url,
                    "config": {
                        "result_format": "mp4",
                        "stitch": True,
                        "fluent": True,
                        "pad_audio": 0.0,
                    },
                    "driver_url": "bank://lively/",
                },
            )

            if response.status_code not in (200, 201):
                print(f"[Avatar] Talks API also failed: {response.status_code} {response.text[:200]}")
                return None

            talk_id = response.json()["id"]
            print(f"[Avatar] Talk created (fallback): {talk_id}")

            result = await _poll_for_result(
                client, f"{DID_BASE_URL}/talks/{talk_id}", max_wait_seconds,
            )
            if result:
                result_url = result.get("result_url")
                if result_url:
                    video_resp = await client.get(result_url)
                    if video_resp.status_code == 200:
                        output_path.write_bytes(video_resp.content)
                        size_kb = len(video_resp.content) / 1024
                        print(f"[Avatar] Generated (fallback): {output_path.name} ({size_kb:.0f}KB)")
                        return str(output_path)

            return None

    except Exception as e:
        print(f"[Avatar] Generation failed: {e}")
        return None


async def generate_full_avatar(
    voice_result: dict,
    work_dir: Path,
    niche: str = "ai_trading",
) -> str | None:
    """
    Generate a full-duration avatar clip for the entire narration.

    This clip will be shown as a PiP overlay in the corner of the video.

    Returns: path to the avatar MP4, or None.
    """
    if not ENABLE_AVATAR:
        return None

    audio_path = voice_result["audio_path"]
    output_path = work_dir / "avatar_pip.mp4"

    print(f"[Avatar] Generating full-duration PiP avatar...")
    return await generate_avatar_clip(
        audio_path=audio_path,
        output_path=output_path,
        niche=niche,
    )


# Keep backward-compat alias
async def generate_intro_outro_clips(script, voice_result, work_dir, niche="ai_trading"):
    """Legacy wrapper — now generates full PiP avatar instead."""
    clip_path = await generate_full_avatar(voice_result, work_dir, niche)
    return {"intro_clip": None, "outro_clip": None, "pip_clip": clip_path}


# CLI test
if __name__ == "__main__":
    async def test():
        print("[Avatar] Module loaded successfully")
        print(f"[Avatar] D-ID enabled: {ENABLE_AVATAR}")
        print(f"[Avatar] API key set: {bool(DID_API_KEY)}")
        if DID_API_KEY:
            print(f"[Avatar] Key prefix: {DID_API_KEY[:8]}...")
        print(f"[Avatar] Presenters: {list(NICHE_PRESENTERS.keys())}")

    asyncio.run(test())
