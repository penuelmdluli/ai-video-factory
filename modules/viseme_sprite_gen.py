"""
Viseme Sprite Library Generator — Pay once for D-ID, use forever.

Generates D-ID talking head clips with phoneme-rich scripts, then extracts
mouth region sprites classified by audio features. The resulting sprite
library lets the SpriteCompositor in local_avatar.py produce D-ID-quality
lip sync with zero ongoing API cost.

Usage:
    python -m modules.viseme_sprite_gen --generate          # Generate D-ID clips (~48 credits)
    python -m modules.viseme_sprite_gen --extract            # Extract sprites from clips
    python -m modules.viseme_sprite_gen --generate --extract  # Both
    python -m modules.viseme_sprite_gen --status             # Show library status
    python -m modules.viseme_sprite_gen --character sparky_ai_trading  # Single character
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
CHARACTERS_DIR = PROJECT_ROOT / "assets" / "podcast_characters" / "baby"
SPRITES_DIR = PROJECT_ROOT / "assets" / "viseme_sprites"
CLIPS_DIR = PROJECT_ROOT / "assets" / "viseme_did_clips"

# D-ID API
DID_BASE = "https://api.d-id.com"

# ── Phoneme-Rich Scripts ─────────────────────────────────────
# Designed to cover all major mouth shapes:
#   M/B/P, D/T/N, AH/AA, OH/OO, EE/IH, F/V, SH/CH, W, L/R, TH

VISEME_SCRIPT_NORMAL = (
    "Peter bought many big purple balloons from the busy market. "
    "She should choose the chocolate chip cheesecake today. "
    "The funny vivid fox jumped over the very fine wall. "
    "Look at the beautiful moon shining through the window tonight. "
    "We need to think about this thoroughly before making a decision. "
    "Oh wow, that is absolutely amazing, I cannot believe what happened. "
    "Really, truly, the world keeps changing faster than we think."
)

VISEME_SCRIPT_EXCITED = (
    "Oh my GOD! Are you SERIOUS right now? This is INSANE! "
    "BOOM! That just blew my mind, I am SHOCKED! "
    "Whoa whoa whoa, hold on, THIS changes EVERYTHING! "
    "No WAY! You have GOT to be KIDDING me! "
    "FIRE! That is absolutely FIRE, people need to HEAR this! "
    "Unbelievable! The numbers are through the ROOF! "
    "WOW, just WOW, I am completely blown away right now!"
)

VISEME_SCRIPT_WHISPER = (
    "Listen carefully, this is important, pay close attention now. "
    "Between you and me, something very strange is happening here. "
    "The numbers show a pattern nobody else has noticed yet. "
    "Keep this quiet, but the whole system is about to shift. "
    "Think about it, slowly, piece by piece, the truth becomes clear."
)

VISEME_SCRIPT_ANGRY = (
    "This is RIDICULOUS! How can anyone think this is acceptable? "
    "NO! Absolutely NOT! That is the WORST take I have ever heard! "
    "People are getting SCAMMED and nobody is doing ANYTHING about it! "
    "Wake UP! Stop pretending everything is fine when it clearly is NOT! "
    "I am DONE with these lazy excuses, we need ACTION right NOW!"
)

VISEME_SCRIPT_CALM = (
    "Now let us take a step back and think about this rationally. "
    "The data tells a very interesting and nuanced story here. "
    "When we look at the broader picture, things become much clearer. "
    "Patience is key, good things take time to develop properly. "
    "So in summary, the evidence points in a very promising direction."
)

VISEME_SCRIPT_FAST = (
    "Okay okay okay so check this out right, the numbers just dropped "
    "and everybody is losing their minds about it but here is the thing, "
    "if you actually look at what happened last time this pattern showed up, "
    "the market bounced back within forty eight hours, so basically "
    "what I am saying is do not panic, stay focused, trust the process!"
)

# Voice mapping: matches podcast_generator.py / voice_generator.py
EDGE_VOICES = {
    "sparky_ai_trading": "en-US-GuyNeural",
    "nova_ai_trading": "en-US-JennyNeural",
    "sparky_ai_money": "en-US-ChristopherNeural",
    "nova_ai_money": "en-US-AriaNeural",
    "sparky_tech_news": "en-GB-RyanNeural",
    "nova_tech_news": "en-GB-SoniaNeural",
    "sparky_motivation": "en-US-ChristopherNeural",
    "nova_motivation": "en-US-JennyNeural",
    "sparky_health_wellness": "en-US-GuyNeural",
    "nova_health_wellness": "en-US-AriaNeural",
    "sparky_blissful_moments": "en-US-ChristopherNeural",
    "nova_blissful_moments": "en-US-AriaNeural",
}

# ── Amplitude / Centroid Bin Edges ───────────────────────────
AMP_BINS = [0.05, 0.15, 0.30, 0.50, 0.75]   # 6 bins: silent, quiet, ..., loud
CENT_BINS = [0.33, 0.66]                       # 3 bins: low, mid, high

MAX_SPRITES_PER_BIN = 12


# ══════════════════════════════════════════════════════════════
# DISCOVERY
# ══════════════════════════════════════════════════════════════

def get_all_characters() -> list[dict]:
    """Scan character directory and return list of character info dicts."""
    characters = []
    if not CHARACTERS_DIR.exists():
        return characters
    for png in sorted(CHARACTERS_DIR.glob("*.png")):
        name = png.stem  # e.g. "sparky_ai_trading"
        voice = EDGE_VOICES.get(name)
        if voice:
            characters.append({
                "name": name,
                "image_path": str(png),
                "voice": voice,
            })
    return characters


def _bin_index(value: float, edges: list[float]) -> int:
    """Classify a value into bins defined by edges."""
    for i, edge in enumerate(edges):
        if value < edge:
            return i
    return len(edges)


# ══════════════════════════════════════════════════════════════
# GENERATION — Uses D-ID credits (~2 per clip)
# ══════════════════════════════════════════════════════════════

async def generate_viseme_audio(
    text: str, voice: str, output_path: Path
) -> bool:
    """Generate edge-tts audio for a phoneme script."""
    if output_path.exists() and output_path.stat().st_size > 1000:
        return True
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import edge_tts
        comm = edge_tts.Communicate(text, voice=voice)
        await comm.save(str(output_path))
        return output_path.exists()
    except Exception as e:
        print(f"  [Error] edge-tts failed: {e}")
        return False


async def generate_did_clip(
    image_path: str, audio_path: str, output_path: Path,
    api_key: str, max_wait: int = 300,
) -> bool:
    """Upload image+audio to D-ID Talks API and download the result MP4."""
    if output_path.exists() and output_path.stat().st_size > 50_000:
        print(f"  [Skip] Clip already exists: {output_path.name}")
        return True

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import httpx
    except ImportError:
        print("  [Error] httpx not installed. Run: pip install httpx")
        return False

    headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json",
    }
    upload_headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Upload image
        print(f"  Uploading image...")
        with open(image_path, "rb") as f:
            resp = await client.post(
                f"{DID_BASE}/images",
                headers=upload_headers,
                files={"image": (Path(image_path).name, f, "image/png")},
            )
        if resp.status_code not in (200, 201):
            print(f"  [Error] Image upload failed: {resp.status_code} {resp.text[:200]}")
            return False
        image_url = resp.json().get("url")

        # 2. Upload audio
        print(f"  Uploading audio...")
        with open(audio_path, "rb") as f:
            resp = await client.post(
                f"{DID_BASE}/audios",
                headers=upload_headers,
                files={"audio": (Path(audio_path).name, f, "audio/mpeg")},
            )
        if resp.status_code not in (200, 201):
            print(f"  [Error] Audio upload failed: {resp.status_code} {resp.text[:200]}")
            return False
        audio_url = resp.json().get("url")

        # 3. Create talk
        print(f"  Creating D-ID talk...")
        talk_body = {
            "script": {
                "type": "audio",
                "audio_url": audio_url,
                "subtitles": False,
            },
            "source_url": image_url,
            "config": {
                "result_format": "mp4",
                "stitch": True,
                "fluent": True,
                "pad_audio": 0.0,
                "auto_match": True,
            },
            "driver_url": "bank://lively/",
        }
        resp = await client.post(
            f"{DID_BASE}/talks", headers=headers, json=talk_body,
        )
        if resp.status_code not in (200, 201):
            print(f"  [Error] Talk create failed: {resp.status_code} {resp.text[:200]}")
            return False
        talk_id = resp.json()["id"]
        print(f"  Talk ID: {talk_id}")

        # 4. Poll for completion
        for poll in range(max_wait // 3):
            await asyncio.sleep(3)
            resp = await client.get(
                f"{DID_BASE}/talks/{talk_id}", headers=headers,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            status = data.get("status")
            if status == "done":
                result_url = data.get("result_url")
                if result_url:
                    video_resp = await client.get(result_url, timeout=120)
                    if video_resp.status_code == 200:
                        output_path.write_bytes(video_resp.content)
                        size_mb = len(video_resp.content) / (1024 * 1024)
                        print(f"  Done: {output_path.name} ({size_mb:.1f}MB)")
                        return True
                return False
            elif status in ("error", "rejected"):
                err = data.get("error", data.get("reject_reason", status))
                print(f"  [Error] D-ID talk failed: {err}")
                return False

        print(f"  [Error] D-ID timed out after {max_wait}s")
        return False


async def generate_all_clips(
    characters: list[dict] | None = None,
    api_key: str = "",
) -> dict:
    """Generate D-ID clips for all characters. Idempotent — skips existing clips."""
    if not api_key:
        from config import DID_API_KEY
        api_key = DID_API_KEY
    if not api_key:
        print("[VisemeGen] ERROR: DID_API_KEY not set. Cannot generate clips.")
        return {"generated": 0, "skipped": 0, "failed": 0}

    if characters is None:
        characters = get_all_characters()

    stats = {"generated": 0, "skipped": 0, "failed": 0}
    deliveries = [
        ("normal", VISEME_SCRIPT_NORMAL),
        ("excited", VISEME_SCRIPT_EXCITED),
        ("whisper", VISEME_SCRIPT_WHISPER),
        ("angry", VISEME_SCRIPT_ANGRY),
        ("calm", VISEME_SCRIPT_CALM),
        ("fast", VISEME_SCRIPT_FAST),
    ]

    for char in characters:
        name = char["name"]
        voice = char["voice"]
        image_path = char["image_path"]

        for delivery, script in deliveries:
            clip_path = CLIPS_DIR / f"{name}_{delivery}.mp4"
            audio_path = CLIPS_DIR / f"{name}_{delivery}.mp3"

            if clip_path.exists() and clip_path.stat().st_size > 50_000:
                stats["skipped"] += 1
                print(f"[VisemeGen] [{name}] {delivery}: already exists, skipping")
                continue

            print(f"\n[VisemeGen] [{name}] {delivery}: generating...")

            # Generate audio
            ok = await generate_viseme_audio(script, voice, audio_path)
            if not ok:
                print(f"[VisemeGen] [{name}] {delivery}: audio generation failed")
                stats["failed"] += 1
                continue

            # Generate D-ID clip
            ok = await generate_did_clip(
                image_path, str(audio_path), clip_path, api_key,
            )
            if ok:
                stats["generated"] += 1
            else:
                stats["failed"] += 1

    print(f"\n[VisemeGen] Generation complete: "
          f"{stats['generated']} new, {stats['skipped']} skipped, {stats['failed']} failed")
    return stats


# ══════════════════════════════════════════════════════════════
# EXTRACTION — Local only, no credits needed
# ══════════════════════════════════════════════════════════════

def _detect_mouth_region(frame: np.ndarray) -> tuple | None:
    """Detect mouth bounding box using face_alignment landmarks."""
    try:
        import face_alignment
        global _fa_model
        if "_fa_model" not in globals() or _fa_model is None:
            globals()["_fa_model"] = face_alignment.FaceAlignment(
                face_alignment.LandmarksType.TWO_D,
                device="cpu",
                flip_input=False,
            )
        fa = globals()["_fa_model"]
        preds = fa.get_landmarks(frame)
        if preds and len(preds) > 0:
            lm = preds[0]
            outer_lip = lm[48:60]
            cx = int(outer_lip[:, 0].mean())
            cy = int(outer_lip[:, 1].mean())
            half_w = int((outer_lip[:, 0].max() - outer_lip[:, 0].min()) / 2)
            half_h = int((outer_lip[:, 1].max() - outer_lip[:, 1].min()) / 2)
            # Add padding for surrounding skin context
            pad_w = int(half_w * 1.8)
            pad_h = int(half_h * 2.5)
            return (cx, cy, pad_w, pad_h)
    except Exception as e:
        print(f"  [Warn] Landmark detection failed: {e}")
    return None


def _crop_mouth_sprite(
    frame: np.ndarray, cx: int, cy: int, half_w: int, half_h: int,
) -> np.ndarray | None:
    """Crop mouth region with alpha mask (feathered edges)."""
    h, w = frame.shape[:2]
    x1 = max(0, cx - half_w)
    y1 = max(0, cy - half_h)
    x2 = min(w, cx + half_w)
    y2 = min(h, cy + half_h)

    if x2 - x1 < 10 or y2 - y1 < 10:
        return None

    crop = frame[y1:y2, x1:x2].copy()
    crop_h, crop_w = crop.shape[:2]

    # Create RGBA with feathered alpha mask
    rgba = np.zeros((crop_h, crop_w, 4), dtype=np.uint8)
    rgba[:, :, :3] = crop

    # Elliptical alpha mask
    mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
    cv2.ellipse(mask, (crop_w // 2, crop_h // 2),
                (crop_w // 2 - 2, crop_h // 2 - 2),
                0, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (11, 11), 4.0)
    rgba[:, :, 3] = mask

    return rgba


def _sprite_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compare two sprites by mean absolute difference (0=identical, 255=max diff)."""
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.mean(np.abs(a[:, :, :3].astype(float) - b[:, :, :3].astype(float))))


def extract_sprites(character_name: str) -> dict:
    """
    Extract mouth sprites from D-ID clips for one character.

    Opens each D-ID MP4, detects mouth on frame 0, crops mouth region
    from every frame, classifies by audio features into bins, deduplicates.
    """
    import librosa

    sprite_dir = SPRITES_DIR / character_name
    sprite_dir.mkdir(parents=True, exist_ok=True)

    clips = list(CLIPS_DIR.glob(f"{character_name}_*.mp4"))
    if not clips:
        print(f"  [Skip] No clips found for {character_name}")
        return {}

    all_sprites = {}  # bin_key -> list of (sprite_array, filename)

    for clip_path in sorted(clips):
        delivery = clip_path.stem.split("_")[-1]  # "normal" or "excited"
        audio_path = clip_path.with_suffix(".mp3")

        print(f"  Processing {clip_path.name}...")

        cap = cv2.VideoCapture(str(clip_path))
        if not cap.isOpened():
            print(f"  [Error] Cannot open {clip_path.name}")
            continue

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Detect mouth on first frame
        ret, first_frame = cap.read()
        if not ret:
            cap.release()
            continue

        mouth_region = _detect_mouth_region(first_frame)
        if mouth_region is None:
            print(f"  [Error] Cannot detect mouth in {clip_path.name}")
            cap.release()
            continue

        cx, cy, half_w, half_h = mouth_region
        print(f"  Mouth region: center=({cx},{cy}), size={half_w*2}x{half_h*2}")

        # Analyze audio for classification
        amp_data = np.zeros(total_frames)
        cent_data = np.zeros(total_frames)
        if audio_path.exists():
            try:
                y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
                hop = max(1, sr // int(fps))
                rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=hop * 2)[0]
                p95 = np.percentile(rms, 95) if rms.max() > 0 else 1.0
                if p95 > 0:
                    rms = np.clip(rms / p95, 0.0, 1.5)
                rms = np.clip(np.power(rms, 1.4), 0.0, 1.0)

                centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
                c95 = np.percentile(centroid, 95) if centroid.max() > 0 else 1.0
                if c95 > 0:
                    centroid = np.clip(centroid / c95, 0.0, 1.0)

                n = min(total_frames, len(rms))
                amp_data[:n] = rms[:n]
                cent_data[:n] = centroid[:n]
            except Exception as e:
                print(f"  [Warn] Audio analysis failed: {e}")

        # Extract sprites frame by frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        frame_idx = 0
        extracted = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            amp = float(amp_data[frame_idx]) if frame_idx < len(amp_data) else 0.0
            cent = float(cent_data[frame_idx]) if frame_idx < len(cent_data) else 0.5

            # Skip very low amplitude frames (closed mouth — use original image)
            if amp < 0.03:
                frame_idx += 1
                continue

            # Sample every 2nd frame to reduce redundancy
            if frame_idx % 2 != 0:
                frame_idx += 1
                continue

            sprite = _crop_mouth_sprite(frame, cx, cy, half_w, half_h)
            if sprite is None:
                frame_idx += 1
                continue

            a_bin = _bin_index(amp, AMP_BINS)
            c_bin = _bin_index(cent, CENT_BINS)
            bin_key = f"a{a_bin}_c{c_bin}"

            if bin_key not in all_sprites:
                all_sprites[bin_key] = []

            # Check duplicate before adding
            is_dup = False
            for existing_sprite, _ in all_sprites[bin_key]:
                if _sprite_similarity(sprite, existing_sprite) < 5.0:
                    is_dup = True
                    break

            if not is_dup and len(all_sprites[bin_key]) < MAX_SPRITES_PER_BIN:
                filename = f"{delivery}_f{frame_idx:04d}_a{a_bin}_c{c_bin}.png"
                all_sprites[bin_key].append((sprite, filename))
                extracted += 1

            frame_idx += 1

        cap.release()
        print(f"  Extracted {extracted} sprites from {clip_path.name}")

    # Save sprites and build manifest
    manifest = {"character": character_name, "bins": {}, "mouth_region": None}

    if clips:
        # Re-detect mouth region for manifest (from first clip)
        cap = cv2.VideoCapture(str(clips[0]))
        ret, frame = cap.read()
        if ret:
            region = _detect_mouth_region(frame)
            if region:
                manifest["mouth_region"] = {
                    "cx": region[0], "cy": region[1],
                    "half_w": region[2], "half_h": region[3],
                }
        cap.release()

    total_saved = 0
    for bin_key, sprites in all_sprites.items():
        manifest["bins"][bin_key] = []
        for sprite_arr, filename in sprites:
            out_path = sprite_dir / filename
            cv2.imwrite(str(out_path), sprite_arr)
            manifest["bins"][bin_key].append(filename)
            total_saved += 1

    # Write manifest
    manifest_path = sprite_dir / "sprites.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Saved {total_saved} sprites + manifest for {character_name}")
    return manifest


def extract_all_sprites(characters: list[dict] | None = None) -> int:
    """Extract sprites from all characters' D-ID clips."""
    if characters is None:
        characters = get_all_characters()

    total = 0
    for char in characters:
        name = char["name"]
        print(f"\n[VisemeGen] Extracting sprites for {name}...")
        manifest = extract_sprites(name)
        count = sum(len(v) for v in manifest.get("bins", {}).values())
        total += count

    print(f"\n[VisemeGen] Extraction complete: {total} total sprites")
    return total


# ══════════════════════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════════════════════

def show_status():
    """Display sprite library status for all characters."""
    characters = get_all_characters()
    if not characters:
        print("[VisemeGen] No characters found in", CHARACTERS_DIR)
        return

    print(f"\n{'='*60}")
    print(f"  Viseme Sprite Library Status")
    print(f"  Characters dir: {CHARACTERS_DIR}")
    print(f"  Sprites dir:    {SPRITES_DIR}")
    print(f"  Clips dir:      {CLIPS_DIR}")
    print(f"{'='*60}\n")

    ready = 0
    for char in characters:
        name = char["name"]
        sprite_dir = SPRITES_DIR / name
        manifest_path = sprite_dir / "sprites.json"

        # Check clips
        delivery_names = ["normal", "excited", "whisper", "angry", "calm", "fast"]
        existing_clips = [d for d in delivery_names if (CLIPS_DIR / f"{name}_{d}.mp4").exists()]
        clips_ok = len(existing_clips) >= 2  # at least 2 clips exist

        # Check sprites
        sprites_ok = False
        sprite_count = 0
        bin_count = 0
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                for bin_key, files in manifest.get("bins", {}).items():
                    bin_count += 1
                    sprite_count += len(files)
                sprites_ok = sprite_count > 10
            except Exception:
                pass

        if sprites_ok:
            status = "[READY]"
            ready += 1
        elif clips_ok:
            status = "[CLIPS OK - needs extraction]"
        else:
            status = "[NOT STARTED]"

        clip_info = ""
        if existing_clips:
            total_clip_mb = sum(
                (CLIPS_DIR / f"{name}_{d}.mp4").stat().st_size / (1024 * 1024)
                for d in existing_clips
            )
            clip_info = f" clips: {len(existing_clips)}/6 ({total_clip_mb:.1f}MB)"

        sprite_info = ""
        if sprite_count > 0:
            sprite_info = f" sprites: {sprite_count} in {bin_count} bins"

        print(f"  {status:30s} {name}{clip_info}{sprite_info}")

    print(f"\n  Summary: {ready}/{len(characters)} characters ready")
    if ready == len(characters):
        print("  All characters have sprites! SpriteCompositor will be used automatically.")
    elif ready == 0:
        print("  Run: python -m modules.viseme_sprite_gen --generate --extract")
    else:
        print("  Some characters still need generation/extraction.")
    print()


# ══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Viseme Sprite Library — D-ID quality lip sync, zero ongoing cost",
    )
    parser.add_argument("--generate", action="store_true",
                        help="Generate D-ID clips (~48 credits for all characters)")
    parser.add_argument("--extract", action="store_true",
                        help="Extract sprites from D-ID clips (local, no credits)")
    parser.add_argument("--status", action="store_true",
                        help="Show sprite library status")
    parser.add_argument("--character", type=str, default=None,
                        help="Process single character (e.g. sparky_ai_trading)")

    args = parser.parse_args()

    if not args.generate and not args.extract and not args.status:
        args.status = True

    # Filter to single character if specified
    characters = None
    if args.character:
        all_chars = get_all_characters()
        characters = [c for c in all_chars if c["name"] == args.character]
        if not characters:
            print(f"[VisemeGen] Character '{args.character}' not found.")
            print(f"  Available: {', '.join(c['name'] for c in all_chars)}")
            sys.exit(1)

    if args.status:
        show_status()
        return

    if args.generate:
        print("\n[VisemeGen] Starting D-ID clip generation...")
        n_chars = len(characters or get_all_characters())
        print(f"  {n_chars} characters x 6 deliveries = {n_chars * 6} clips (~{n_chars * 6 * 2} credits)")
        asyncio.run(generate_all_clips(characters))

    if args.extract:
        print("\n[VisemeGen] Starting sprite extraction (local, no credits)...")
        extract_all_sprites(characters)

    # Always show status after operations
    show_status()


if __name__ == "__main__":
    main()
