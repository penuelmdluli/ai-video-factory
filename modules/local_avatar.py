"""
Local Avatar Generator — FREE talking head animation without cloud APIs.

Two tiers:
  Tier 1: Wav2Lip — ML-based lip sync (GPU preferred, CPU fallback)
  Tier 2: Audio-reactive compositing — draws mouth shapes over the original
          image with feathered blending, eye blinks, and head movement.
          Designed for cartoon characters where mesh warping looks unnatural.

Both produce standard MP4 files compatible with VideoFileClip in the
existing video_assembler pipeline.
"""
import asyncio
import math
import os
import random
import sys
import time
import numpy as np
from pathlib import Path

import cv2
import librosa
import soundfile as sf

# ── Configuration ─────────────────────────────────────────────
MODELS_DIR = Path(__file__).parent.parent / "assets" / "models"
WAV2LIP_DIR = MODELS_DIR / "Wav2Lip"
WAV2LIP_MODEL_PATH = MODELS_DIR / "wav2lip_gan.pth"
WAV2LIP_MODEL_URL = "https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/Eb3LEzbfuKlJiR600lQWRxgBIY27JZg80f7V9jtMfbNDaQ?e=TBFBVW"
GFPGAN_MODEL_PATH = MODELS_DIR / "GFPGANv1.4.pth"

ANIMATION_FPS = 30

# Module-level cache
_fa_model = None
_gfpgan_restorer = None


# ── Emotion → Landmark Offset Map ─────────────────────────────
# mouth_scale: multiplier for mouth width when open
# jaw_drop: multiplier for mouth opening height
# mouth_corners: (dx, dy) pixel offset for mouth center (smile/frown)

EMOTION_OFFSETS = {
    "SHOCKED": {
        "l_brow": (0, -3.0),
        "r_brow": (0, -3.0),
        "l_eye_top": (0, -1.5),
        "l_eye_bot": (0, 1.0),
        "r_eye_top": (0, -1.5),
        "r_eye_bot": (0, 1.0),
        "mouth_scale": 1.6,
        "jaw_drop": 1.4,
    },
    "ANGRY": {
        "l_brow_inner": (0, 1.5),
        "r_brow_inner": (0, 1.5),
        "l_brow_outer": (0, -0.5),
        "r_brow_outer": (0, -0.5),
        "l_eye_top": (0, 0.5),
        "r_eye_top": (0, 0.5),
        "mouth_scale": 0.8,
        "mouth_corners": (0, 0.5),
        "jaw_drop": 0.8,
    },
    "LAUGHS": {
        "l_brow": (0, -1.0),
        "r_brow": (0, -1.0),
        "l_eye_top": (0, 1.5),
        "l_eye_bot": (0, -1.0),
        "r_eye_top": (0, 1.5),
        "r_eye_bot": (0, -1.0),
        "mouth_scale": 1.4,
        "mouth_corners": (-1.5, -1.5),
        "jaw_drop": 1.3,
    },
    "EXCITED": {
        "l_brow": (0, -2.0),
        "r_brow": (0, -2.0),
        "l_eye_top": (0, -1.0),
        "r_eye_top": (0, -1.0),
        "mouth_scale": 1.3,
        "jaw_drop": 1.2,
    },
    "SARCASTIC": {
        "l_brow": (0, -2.0),
        "r_brow": (0, 0.5),
        "mouth_corners": (-1.0, -0.5),
        "mouth_scale": 0.9,
        "jaw_drop": 0.7,
    },
    "SMIRKING": {
        "l_brow": (0, -1.0),
        "mouth_corners": (-1.5, -1.0),
        "mouth_scale": 0.8,
        "jaw_drop": 0.6,
    },
    "WHISPERING": {
        "mouth_scale": 0.5,
        "jaw_drop": 0.4,
    },
    "DEAD SERIOUS": {
        "l_brow_inner": (0, 0.5),
        "r_brow_inner": (0, 0.5),
        "mouth_scale": 0.7,
        "jaw_drop": 0.6,
    },
    "DISBELIEF": {
        "l_brow": (0, -2.5),
        "r_brow": (0, -2.5),
        "l_eye_top": (0, -1.0),
        "r_eye_top": (0, -1.0),
        "mouth_scale": 1.1,
        "jaw_drop": 1.0,
    },
    "CONFUSED": {
        "l_brow": (0, -1.5),
        "r_brow": (0, 1.0),
        "mouth_corners": (0, 0.5),
        "mouth_scale": 0.9,
        "jaw_drop": 0.7,
    },
    "FIRED UP": {
        "l_brow": (0, -2.0),
        "r_brow": (0, -2.0),
        "mouth_scale": 1.5,
        "jaw_drop": 1.4,
    },
    "IMPRESSED": {
        "l_brow": (0, -2.0),
        "r_brow": (0, -2.0),
        "mouth_corners": (-1.0, -1.0),
        "mouth_scale": 1.1,
        "jaw_drop": 0.9,
    },
    "CALM": {
        "mouth_corners": (-0.5, -0.3),
        "mouth_scale": 0.8,
        "jaw_drop": 0.7,
    },
    "NERVOUS": {
        "l_brow_inner": (0, 1.0),
        "r_brow_inner": (0, 1.0),
        "mouth_scale": 0.7,
        "jaw_drop": 0.6,
    },
    "CUTS OFF": {
        "mouth_scale": 1.0,
        "jaw_drop": 1.0,
    },
}

DEFAULT_EMOTION = {
    "mouth_scale": 1.0,
    "jaw_drop": 1.0,
}


# ── Device Detection ──────────────────────────────────────────

def _get_device() -> str:
    """Detect best available compute device."""
    try:
        import torch
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            if vram_gb >= 4:
                return "cuda"
    except (ImportError, Exception):
        pass
    return "cpu"


# ── Face Landmark Detection ───────────────────────────────────

def _get_landmarks(image_path: str) -> np.ndarray | None:
    """
    Detect 68 face landmarks using face_alignment (cached model).
    Returns (68, 2) array or None.
    """
    global _fa_model
    img = cv2.imread(image_path)
    if img is None:
        return None

    try:
        import face_alignment
        if _fa_model is None:
            _fa_model = face_alignment.FaceAlignment(
                face_alignment.LandmarksType.TWO_D,
                device="cpu",
                flip_input=False,
            )
        preds = _fa_model.get_landmarks(img)
        if preds is not None and len(preds) > 0:
            return preds[0].astype(np.float32)  # (68, 2)
    except Exception as e:
        print(f"[LocalAvatar] face_alignment failed: {e}")

    # Heuristic 68-point landmarks for baby face (768x1024)
    h, w = img.shape[:2]
    return _heuristic_landmarks(w, h)


def _heuristic_landmarks(w: int, h: int) -> np.ndarray:
    """Generate approximate 68 landmarks for a centered baby face."""
    cx, cy = w * 0.5, h * 0.45  # face center
    fw, fh = w * 0.45, h * 0.40  # face half-width/height

    landmarks = np.zeros((68, 2), dtype=np.float32)

    # Jaw (0-16): oval from ear to ear
    for i in range(17):
        angle = math.pi * i / 16
        landmarks[i] = [cx - fw * math.cos(angle), cy + fh * math.sin(angle) * 0.8]

    # Left eyebrow (17-21)
    brow_y = cy - fh * 0.35
    for i, x_off in enumerate([-0.35, -0.28, -0.20, -0.12, -0.05]):
        landmarks[17 + i] = [cx + w * x_off, brow_y + abs(x_off) * h * 0.05]

    # Right eyebrow (22-26)
    for i, x_off in enumerate([0.05, 0.12, 0.20, 0.28, 0.35]):
        landmarks[22 + i] = [cx + w * x_off, brow_y + abs(x_off) * h * 0.05]

    # Nose (27-35)
    nose_top = cy - fh * 0.15
    nose_bot = cy + fh * 0.10
    for i in range(4):
        landmarks[27 + i] = [cx, nose_top + (nose_bot - nose_top) * i / 3]
    for i, x_off in enumerate([-0.06, -0.03, 0, 0.03, 0.06]):
        landmarks[31 + i] = [cx + w * x_off, nose_bot]

    # Left eye (36-41)
    eye_y = cy - fh * 0.18
    eye_lx = cx - w * 0.18
    for i, (dx, dy) in enumerate([(-0.04, 0), (-0.02, -0.015), (0.02, -0.015),
                                   (0.04, 0), (0.02, 0.015), (-0.02, 0.015)]):
        landmarks[36 + i] = [eye_lx + w * dx, eye_y + h * dy]

    # Right eye (42-47)
    eye_rx = cx + w * 0.18
    for i, (dx, dy) in enumerate([(-0.04, 0), (-0.02, -0.015), (0.02, -0.015),
                                   (0.04, 0), (0.02, 0.015), (-0.02, 0.015)]):
        landmarks[42 + i] = [eye_rx + w * dx, eye_y + h * dy]

    # Outer lip (48-59)
    mouth_cx, mouth_cy = cx, cy + fh * 0.35
    mouth_w, mouth_h = w * 0.10, h * 0.03
    for i in range(12):
        angle = 2 * math.pi * i / 12
        landmarks[48 + i] = [mouth_cx + mouth_w * math.cos(angle),
                              mouth_cy + mouth_h * math.sin(angle)]

    # Inner lip (60-67)
    inner_w, inner_h = mouth_w * 0.6, mouth_h * 0.5
    for i in range(8):
        angle = 2 * math.pi * i / 8
        landmarks[60 + i] = [mouth_cx + inner_w * math.cos(angle),
                              mouth_cy + inner_h * math.sin(angle)]

    return landmarks


# ── Audio Analysis ────────────────────────────────────────────

def _analyze_audio(audio_path: str, fps: int = 30) -> dict:
    """
    Extract per-frame audio features with fast-attack / fast-decay envelope.

    Key improvements over v1:
    - Higher silence threshold (0.08) so mouth properly closes between words
    - Exponential decay (0.35/frame) so mouth snaps shut in ~3 frames (~100ms)
    - Power curve for better dynamic range
    - No temporal smoothing (prevents mouth staying open)
    """
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    hop = max(1, sr // fps)

    # RMS amplitude (loudness per frame)
    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=hop * 2)[0]
    # Normalize to 95th percentile (avoids outlier spikes dominating)
    p95 = np.percentile(rms, 95) if rms.max() > 0 else 1.0
    if p95 > 0:
        rms = np.clip(rms / p95, 0.0, 1.5)

    # Power curve: quiet parts quieter, loud parts proportionally louder
    rms = np.power(rms, 1.4)
    rms = np.clip(rms, 0.0, 1.0)

    # Spectral centroid (brightness → mouth width: low = round 'oo', high = spread 'ee')
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    c95 = np.percentile(centroid, 95) if centroid.max() > 0 else 1.0
    if c95 > 0:
        centroid = np.clip(centroid / c95, 0.0, 1.0)

    # ── Fast envelope follower ──
    # Instant attack: mouth opens immediately when speech starts
    # Exponential decay: mouth closes in ~3 frames when speech stops
    SILENCE_THRESH = 0.08
    DECAY = 0.35          # multiply by this each silent frame
    ATTACK_SMOOTH = 0.7   # slight smoothing on decrease during speech

    envelope = np.zeros_like(rms)
    for i in range(len(rms)):
        if i == 0:
            envelope[i] = rms[i] if rms[i] > SILENCE_THRESH else 0.0
        elif rms[i] > SILENCE_THRESH:
            # During speech: instant rise, slight smooth on dips
            if rms[i] >= envelope[i - 1]:
                envelope[i] = rms[i]  # instant attack
            else:
                envelope[i] = max(rms[i], envelope[i - 1] * ATTACK_SMOOTH)
        else:
            # Below threshold: fast exponential decay
            decayed = envelope[i - 1] * DECAY
            envelope[i] = decayed if decayed > SILENCE_THRESH * 0.5 else 0.0

    n_frames = len(envelope)
    return {
        "amplitude": envelope,
        "centroid": centroid[:n_frames],
        "n_frames": n_frames,
        "duration": n_frames / fps,
    }


# ── Blink Schedule ────────────────────────────────────────────

def _generate_blink_schedule(n_frames: int, fps: int = 30) -> np.ndarray:
    """
    Generate natural eye blink schedule.
    Returns per-frame blink intensity (0=open, 1=closed).
    Humans blink every 2-5 seconds. Each blink ~250-350ms (8-10 frames at 30fps).
    Eyes stay fully closed for 2-3 frames for a clearly visible blink.
    """
    blinks = np.zeros(n_frames, dtype=np.float32)
    t = 0
    while t < n_frames:
        gap = random.randint(fps * 2, fps * 5)  # 2-5s between blinks
        t += gap
        if t >= n_frames:
            break
        # Blink shape: quick close (3 frames), hold closed (2-3), slower open (3-4)
        # Curve: 0.4 → 0.8 → 1.0 → 1.0 → 0.85 → 0.5 → 0.2 → 0.0
        blink_curve = [0.40, 0.80, 1.0, 1.0, 0.85, 0.55, 0.25]
        # Occasionally do a quick double-blink (natural reflex)
        if random.random() < 0.2:
            # Double blink: normal blink + short gap + quick blink
            blink_curve = [0.40, 0.80, 1.0, 0.85, 0.4, 0.15, 0.50, 0.95, 1.0, 0.6, 0.2]
        for b, val in enumerate(blink_curve):
            idx = t + b
            if idx < n_frames:
                blinks[idx] = val
        t += len(blink_curve)
    return blinks


# ── Build Per-Frame Emotion Map ───────────────────────────────

def _build_emotion_timeline(
    line_timings: list[dict] | None,
    character: str,
    n_frames: int,
    fps: int = 30,
) -> list[dict]:
    """Build per-frame emotion config from line_timings."""
    if not line_timings:
        return [DEFAULT_EMOTION] * n_frames

    char_upper = character.upper()
    timeline = [DEFAULT_EMOTION.copy()] * n_frames

    for lt in line_timings:
        if lt.get("character", "").upper() != char_upper:
            continue
        emotion_name = lt.get("emotion", "").upper()
        start_frame = int(lt["start"] * fps)
        end_frame = int(lt["end"] * fps)

        emotion_config = EMOTION_OFFSETS.get(emotion_name, DEFAULT_EMOTION)

        # Apply with fade-in (first 5 frames)
        for f in range(max(0, start_frame), min(n_frames, end_frame)):
            fade = min(1.0, (f - start_frame + 1) / 5.0)
            blended = {}
            for key in emotion_config:
                val = emotion_config[key]
                def_val = DEFAULT_EMOTION.get(key, val)
                if isinstance(val, tuple):
                    def_t = (0, 0) if key not in DEFAULT_EMOTION else DEFAULT_EMOTION.get(key, (0, 0))
                    blended[key] = (
                        def_t[0] + (val[0] - def_t[0]) * fade,
                        def_t[1] + (val[1] - def_t[1]) * fade,
                    )
                elif isinstance(val, (int, float)):
                    blended[key] = def_val + (val - def_val) * fade
                else:
                    blended[key] = val
            # Always embed raw emotion name so animation effects can read it
            blended["_emotion_name"] = emotion_name
            timeline[f] = blended

    return timeline


# ══════════════════════════════════════════════════════════════
# MOUTH COMPOSITOR — Cartoon Mouth Overlay System
# ══════════════════════════════════════════════════════════════

class MouthCompositor:
    """
    Draws and composites cartoon mouth shapes onto character frames.

    Approach (optimized for cartoon characters):
    1. Covers original mouth with sampled skin color
    2. Draws sized mouth opening (dark interior + teeth + lip outline)
    3. Feather-blends the mouth region onto the original image

    No inpainting needed — the skin-color cover + new mouth drawing
    replaces the original mouth cleanly within the blend zone.
    """

    def __init__(self, base_image: np.ndarray, landmarks: np.ndarray):
        self.h, self.w = base_image.shape[:2]
        self.base_image = base_image.copy()

        # Mouth geometry from outer lip landmarks (48-59)
        outer_lip = landmarks[48:60]
        self.mouth_cx = int(outer_lip[:, 0].mean())
        self.mouth_cy = int(outer_lip[:, 1].mean())

        lip_left = outer_lip[:, 0].min()
        lip_right = outer_lip[:, 0].max()
        lip_top = outer_lip[:, 1].min()
        lip_bottom = outer_lip[:, 1].max()

        self.base_mouth_w = max(15, int((lip_right - lip_left) / 2))
        self.base_mouth_h = max(8, int((lip_bottom - lip_top) / 2))

        # Sample face colors
        self.skin_color = self._sample_color(base_image, landmarks, "skin")
        self.lip_color = self._sample_color(base_image, landmarks, "lip")
        self.lip_outline_color = tuple(max(0, c - 40) for c in self.lip_color)

        print(f"[LocalAvatar] Mouth compositor: center=({self.mouth_cx},{self.mouth_cy}), "
              f"size={self.base_mouth_w * 2}x{self.base_mouth_h * 2}, "
              f"skin={self.skin_color}, lip={self.lip_color}")

    def _sample_color(self, img: np.ndarray, landmarks: np.ndarray, region: str) -> tuple:
        """Sample average color from face region."""
        if region == "skin":
            # Sample from face INTERIOR: cheek centers between eyes and nose.
            nose_bottom = landmarks[33]
            l_eye_inner = landmarks[39]
            r_eye_inner = landmarks[42]

            l_cheek = (l_eye_inner + nose_bottom) / 2
            l_cheek[0] -= 10

            r_cheek = (r_eye_inner + nose_bottom) / 2
            r_cheek[0] += 10

            under_nose = landmarks[33].copy()
            under_nose[1] += 10

            points = np.array([l_cheek, r_cheek, under_nose])
        else:
            points = landmarks[48:60]

        colors = []
        for px, py in points:
            px = int(np.clip(px, 3, self.w - 4))
            py = int(np.clip(py, 3, self.h - 4))
            patch = img[py - 3:py + 4, px - 3:px + 4]
            if patch.size > 0:
                colors.append(patch.mean(axis=(0, 1)))

        if colors:
            avg = np.mean(colors, axis=0).astype(int)
            return (int(avg[0]), int(avg[1]), int(avg[2]))
        return (200, 180, 160) if region == "skin" else (160, 120, 130)

    def render(self, amplitude: float, centroid: float, emotion: dict) -> np.ndarray:
        """
        Render frame with phoneme-aware, emotion-driven mouth animation.

        Improvements over v1:
        - Filled upper/lower lip shapes for 3D depth
        - Phoneme-aware width: oo/uh (narrow) → ee/ah (wide)
        - Detailed teeth with subtle gap lines
        - Lower teeth visible for wide-open emotions (LAUGHS, SHOCKED, FIRED UP)
        - Tongue with centre ridge for realism
        - Smile/frown corner shift per emotion
        - Mouth-corner depth shadows
        - Blend zone sized to encompass full lip area
        """
        if amplitude < 0.02:
            return self.base_image.copy()

        mouth_canvas = self.base_image.copy()

        jaw_drop     = emotion.get("jaw_drop",    1.0)
        mouth_scale  = emotion.get("mouth_scale", 1.0)
        emotion_name = emotion.get("_emotion_name", "")

        # ── Mouth opening dimensions ──
        open_h = int(self.base_mouth_h * amplitude * 0.9 * jaw_drop)
        open_h = max(2, min(open_h, int(self.base_mouth_h * 1.4)))

        # Phoneme-aware width: low centroid = round (oo/uh), high = wide (ee/ah)
        width_factor = 0.28 + 0.52 * centroid      # range 0.28 – 0.80
        open_w = int(self.base_mouth_w * width_factor * mouth_scale)
        open_w = max(4, min(open_w, int(self.base_mouth_w * 0.92)))

        # Lip thickness proportional to face size
        lip_t = max(2, int(self.base_mouth_h * 0.28))

        # Mouth centre (shifts down slightly as mouth opens)
        cx = self.mouth_cx
        cy = self.mouth_cy + open_h // 6
        if "mouth_corners" in emotion:
            mc = emotion["mouth_corners"]
            cx += int(mc[0])
            cy += int(mc[1])

        # Smile / frown corner vertical shift
        smile_v = 0
        if emotion_name in ("LAUGHS", "EXCITED", "IMPRESSED", "SMIRKING"):
            smile_v = -max(1, int(open_h * 0.12))   # corners up
        elif emotion_name in ("ANGRY", "DEAD SERIOUS", "NERVOUS"):
            smile_v = max(1, int(open_h * 0.08))    # corners down (frown)

        # ── 1. Dark mouth cavity (two-layer depth) ──
        dark_inner = (18, 12, 28)
        dark_mid   = (32, 22, 42)
        cv2.ellipse(mouth_canvas, (cx, cy + smile_v), (open_w, open_h),
                    0, 0, 360, dark_mid, -1)
        cv2.ellipse(mouth_canvas, (cx, cy + smile_v),
                    (max(2, int(open_w * 0.65)), max(1, int(open_h * 0.55))),
                    0, 0, 360, dark_inner, -1)

        # ── 2. Upper teeth ──
        if amplitude > 0.10 and open_h > 3:
            teeth_h = max(2, int(open_h * 0.35))
            teeth_w = int(open_w * 0.72)
            teeth_y = cy + smile_v - open_h // 2 + teeth_h // 2 + 1
            cv2.ellipse(mouth_canvas, (cx, teeth_y), (teeth_w, teeth_h),
                        0, 0, 180, (222, 222, 230), -1)
            # Subtle tooth gap lines
            if teeth_w > 10 and open_h > 5:
                n_gaps = 3
                for gi in range(1, n_gaps + 1):
                    gx = cx - teeth_w + (2 * teeth_w * gi) // (n_gaps + 1)
                    cv2.line(mouth_canvas,
                             (gx, teeth_y - teeth_h // 2 + 1),
                             (gx, teeth_y + teeth_h // 2 - 1),
                             (178, 176, 185), 1)
            # Lower teeth for wide-open emotions
            if emotion_name in ("LAUGHS", "SHOCKED", "FIRED UP", "EXCITED") and open_h > 7:
                lt_y = cy + smile_v + open_h // 2 - max(1, teeth_h // 2) - 1
                lt_w = int(teeth_w * 0.80)
                lt_h = max(1, int(teeth_h * 0.65))
                cv2.ellipse(mouth_canvas, (cx, lt_y), (lt_w, lt_h),
                            0, 180, 360, (205, 205, 212), -1)

        # ── 3. Tongue ──
        if amplitude > 0.42 and open_h > 5:
            tong_y = cy + smile_v + int(open_h * 0.20)
            tong_w = int(open_w * 0.36)
            tong_h = max(2, int(open_h * 0.26))
            cv2.ellipse(mouth_canvas, (cx, tong_y), (tong_w, tong_h),
                        0, 180, 360, (88, 68, 150), -1)
            if tong_h > 3:
                cv2.line(mouth_canvas,
                         (cx, tong_y - tong_h // 2 + 1),
                         (cx, tong_y + tong_h // 2 - 1),
                         (68, 52, 128), 1)

        # ── 4. Lower lip (fuller, with highlight strip) ──
        if open_h >= 2:
            ll_cy = cy + smile_v + open_h + lip_t // 2 - 1
            ll_w  = int(open_w * 0.92)
            ll_h  = max(1, int(lip_t * 1.15))
            cv2.ellipse(mouth_canvas, (cx, ll_cy), (ll_w, ll_h),
                        0, 0, 180, self.lip_color, -1)
            # Centre highlight — lighter strip for 3-D roundness
            hl = tuple(min(255, c + 22) for c in self.lip_color)
            cv2.ellipse(mouth_canvas, (cx, ll_cy),
                        (max(1, ll_w // 2), max(1, ll_h // 2)),
                        0, 0, 180, hl, -1)

        # ── 5. Upper lip (thinner, cupid's-bow shape) ──
        if open_h >= 2:
            ul_cy = cy + smile_v - open_h - lip_t // 2 + 1
            ul_w  = int(open_w * 0.85)
            ul_h  = max(1, lip_t)
            cv2.ellipse(mouth_canvas, (cx, ul_cy), (ul_w, ul_h),
                        0, 180, 360, self.lip_color, -1)

        # ── 6. Lip outline (definition border) ──
        border = max(1, int(min(open_w, open_h) * 0.09))
        cv2.ellipse(mouth_canvas, (cx, cy + smile_v),
                    (open_w + 1, open_h + lip_t),
                    0, 0, 360, self.lip_outline_color, border)

        # ── 7. Corner depth shadows ──
        shadow_r = max(2, int(open_w * 0.12))
        for corner_x in [cx - open_w + 2, cx + open_w - 2]:
            cv2.circle(mouth_canvas, (corner_x, cy + smile_v),
                       shadow_r, self.lip_outline_color, -1)

        # ── Feathered blend mask (covers full lip area) ──
        mask = np.zeros((self.h, self.w), dtype=np.float32)
        blend_w = open_w + lip_t + 4
        blend_h = open_h + lip_t * 2 + 4
        cv2.ellipse(mask, (cx, cy + smile_v), (blend_w, blend_h), 0, 0, 360, 1.0, -1)
        ksize = max(3, (min(blend_w, blend_h) // 2) * 2 + 1)
        mask = cv2.GaussianBlur(mask, (ksize, ksize), max(1.5, min(blend_w, blend_h) * 0.3))

        # Smooth blend ramp: 0 at amp=0.02 → 1.0 at amp=0.12
        t = min(1.0, max(0.0, (amplitude - 0.02) / 0.10))
        blend_strength = t * t * (3.0 - 2.0 * t)  # smoothstep
        mask *= blend_strength

        mask_3 = mask[:, :, np.newaxis]
        result = (self.base_image.astype(np.float32) * (1.0 - mask_3) +
                  mouth_canvas.astype(np.float32) * mask_3).astype(np.uint8)

        return result


# ══════════════════════════════════════════════════════════════
# SPRITE COMPOSITOR — D-ID Quality Lip Sync (zero ongoing cost)
# ══════════════════════════════════════════════════════════════

class SpriteCompositor:
    """
    Composites pre-extracted D-ID mouth sprites onto character frames.

    Same render(amplitude, centroid, emotion) interface as MouthCompositor,
    but uses real D-ID mouth crops instead of drawn ellipses.
    """

    def __init__(self, base_image: np.ndarray, sprite_dir: Path):
        import json
        self.h, self.w = base_image.shape[:2]
        self.base_image = base_image.copy()
        self.sprite_dir = sprite_dir

        manifest_path = sprite_dir / "sprites.json"
        with open(manifest_path) as f:
            self.manifest = json.load(f)

        self.mouth_region = self.manifest.get("mouth_region", {})
        self.cx = self.mouth_region.get("cx", self.w // 2)
        self.cy = self.mouth_region.get("cy", int(self.h * 0.65))
        self.half_w = self.mouth_region.get("half_w", 40)
        self.half_h = self.mouth_region.get("half_h", 25)

        # Resolve sprite file base directory (supports cross-character references)
        source_dir_rel = self.manifest.get("source_dir")
        if source_dir_rel:
            file_base = (sprite_dir / source_dir_rel).resolve()
        else:
            file_base = sprite_dir

        # Pre-load all sprites into memory
        self.sprites = {}  # bin_key -> list of RGBA arrays
        total = 0
        for bin_key, filenames in self.manifest.get("bins", {}).items():
            self.sprites[bin_key] = []
            for fname in filenames:
                path = file_base / fname
                if path.exists():
                    sprite = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                    if sprite is not None and sprite.shape[2] == 4:
                        self.sprites[bin_key].append(sprite)
                        total += 1
        self._sprite_idx = {}  # bin_key -> current index for variety
        self._prev_composite = None  # previous frame's composited ROI for temporal smoothing
        self._prev_bin = None  # previous bin key to reduce flickering
        self._frame_hold = 0  # frames held on current sprite
        print(f"[LocalAvatar] SpriteCompositor loaded: {total} sprites in {len(self.sprites)} bins")

    def render(self, amplitude: float, centroid: float, emotion: dict) -> np.ndarray:
        """Render frame with D-ID mouth sprite, with temporal smoothing."""
        frame = self.base_image.copy()

        if amplitude < 0.02:
            self._prev_composite = None
            self._prev_bin = None
            return frame

        # Classify into bins
        amp_bins = [0.05, 0.15, 0.30, 0.50, 0.75]
        cent_bins = [0.33, 0.66]

        a_bin = 0
        for i, edge in enumerate(amp_bins):
            if amplitude >= edge:
                a_bin = i + 1
        c_bin = 0
        for i, edge in enumerate(cent_bins):
            if centroid >= edge:
                c_bin = i + 1

        bin_key = f"a{a_bin}_c{c_bin}"

        # Hold each sprite for 2-3 frames to reduce flickering
        if bin_key == self._prev_bin and self._frame_hold < 2:
            self._frame_hold += 1
        else:
            self._frame_hold = 0
            self._prev_bin = bin_key

        # Find sprite: exact bin, then nearest fallback
        if self._frame_hold > 0 and self._prev_composite is not None:
            sprite = None  # reuse previous composite
        else:
            sprite = self._pick_sprite(bin_key, a_bin, c_bin)

        if sprite is None and self._prev_composite is None:
            return frame

        # Compute composited ROI
        if sprite is not None:
            sprite_h, sprite_w = sprite.shape[:2]

            # Position centered on mouth
            x1 = self.cx - sprite_w // 2
            y1 = self.cy - sprite_h // 2
            x2 = x1 + sprite_w
            y2 = y1 + sprite_h

            # Clamp to image bounds
            sx1 = max(0, -x1)
            sy1 = max(0, -y1)
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(self.w, x2)
            y2 = min(self.h, y2)
            sx2 = sx1 + (x2 - x1)
            sy2 = sy1 + (y2 - y1)

            if x2 <= x1 or y2 <= y1:
                return frame

            # Alpha blend with smoother ramp (cubic ease)
            rgb = sprite[sy1:sy2, sx1:sx2, :3]
            alpha = sprite[sy1:sy2, sx1:sx2, 3:4].astype(np.float32) / 255.0

            # Soften alpha edges with gaussian blur
            alpha_2d = alpha[:, :, 0]
            alpha_2d = cv2.GaussianBlur(alpha_2d, (5, 5), 1.5)
            alpha = alpha_2d[:, :, np.newaxis]

            # Smooth cubic ramp: 0 at amp=0.02 → 1.0 at amp=0.15
            t = min(1.0, max(0.0, (amplitude - 0.02) / 0.13))
            blend_strength = t * t * (3.0 - 2.0 * t)  # smoothstep
            alpha = alpha * blend_strength

            roi = frame[y1:y2, x1:x2].astype(np.float32)
            current_composite = roi * (1.0 - alpha) + rgb.astype(np.float32) * alpha

            # Temporal smoothing: blend 60% current + 40% previous to reduce flicker
            if self._prev_composite is not None and self._prev_composite.shape == current_composite.shape:
                current_composite = current_composite * 0.6 + self._prev_composite * 0.4

            self._prev_composite = current_composite.copy()
            frame[y1:y2, x1:x2] = current_composite.astype(np.uint8)
        elif self._prev_composite is not None:
            # Reuse previous composite (held sprite)
            sprite_h, sprite_w = self._prev_composite.shape[:2]
            x1 = self.cx - sprite_w // 2
            y1 = self.cy - sprite_h // 2
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(self.w, x1 + sprite_w)
            y2 = min(self.h, y1 + sprite_h)
            ph = y2 - y1
            pw = x2 - x1
            if ph > 0 and pw > 0:
                frame[y1:y2, x1:x2] = self._prev_composite[:ph, :pw].astype(np.uint8)

        return frame

    def _pick_sprite(self, bin_key: str, a_bin: int, c_bin: int) -> np.ndarray | None:
        """Pick a sprite from the bin with variety, fallback to nearest bin."""
        # Try exact bin
        if bin_key in self.sprites and self.sprites[bin_key]:
            idx = self._sprite_idx.get(bin_key, 0)
            sprite = self.sprites[bin_key][idx % len(self.sprites[bin_key])]
            self._sprite_idx[bin_key] = idx + 1
            return sprite

        # Nearest bin fallback: try same amplitude, different centroid
        for dc in range(3):
            for c_try in [c_bin + dc, c_bin - dc]:
                if 0 <= c_try <= 2:
                    key = f"a{a_bin}_c{c_try}"
                    if key in self.sprites and self.sprites[key]:
                        return self.sprites[key][0]

        # Try any bin with closest amplitude
        for da in range(1, 6):
            for a_try in [a_bin + da, a_bin - da]:
                if 0 <= a_try <= 5:
                    for c_try in range(3):
                        key = f"a{a_try}_c{c_try}"
                        if key in self.sprites and self.sprites[key]:
                            return self.sprites[key][0]

        return None


def _check_sprites_available(image_path: str) -> Path | None:
    """Check if sprite library exists for the character in the image path."""
    try:
        from config import VISEME_SPRITES_DIR, VISEME_SPRITES_ENABLED
    except ImportError:
        return None
    if not VISEME_SPRITES_ENABLED:
        return None

    # Extract character name from image filename
    name = Path(image_path).stem  # e.g. "sparky_ai_trading"
    sprite_dir = VISEME_SPRITES_DIR / name
    manifest = sprite_dir / "sprites.json"

    if manifest.exists():
        try:
            import json
            with open(manifest) as f:
                data = json.load(f)
            sprite_count = sum(len(v) for v in data.get("bins", {}).values())
            if sprite_count > 10:
                return sprite_dir
        except Exception:
            pass
    return None


# ── Eye Animation (Blinks + Gaze Drift + Emotion Squint) ──────


def _create_closed_eyes_image(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """
    Pre-compute a 'closed eyes' version of the character image using cv2.inpaint.

    OpenCV inpainting fills the masked eye regions using surrounding skin texture,
    lighting, and color gradients — producing a photorealistic 'eyelids closed'
    result without any flat colors or blur artifacts.

    Called once at init, then blink frames just cross-fade to this image.
    """
    h, w = image.shape[:2]

    # Build inpaint mask covering both eyes (slightly expanded for full coverage)
    inpaint_mask = np.zeros((h, w), dtype=np.uint8)

    for eye_pts in [landmarks[36:42], landmarks[42:48]]:
        ecx = int(eye_pts[:, 0].mean())
        ecy = int(eye_pts[:, 1].mean())
        ew = max(4, int((eye_pts[:, 0].max() - eye_pts[:, 0].min()) / 2) + 5)
        eh = max(2, int((eye_pts[:, 1].max() - eye_pts[:, 1].min()) / 2) + 4)

        # Elliptical mask over each eye — 1.3x expanded to cover full visible eye
        cv2.ellipse(inpaint_mask, (ecx, ecy), (int(ew * 1.3), int(eh * 1.2)),
                    0, 0, 360, 255, -1)

    # Inpaint: TELEA algorithm fills eyes with surrounding skin context
    closed = cv2.inpaint(image, inpaint_mask, inpaintRadius=12, flags=cv2.INPAINT_TELEA)

    # Draw subtle eyelid crease lines on the inpainted result
    # Sample skin color near the eye for the crease color
    sample_y = max(0, int(landmarks[36:42][:, 1].min()) - 8)
    sample_x = int(landmarks[36:42][:, 0].mean())
    if 0 <= sample_y < h and 0 <= sample_x < w:
        sc = tuple(int(c) for c in closed[sample_y, sample_x])
    else:
        sc = (140, 120, 100)
    crease_dark = tuple(max(0, c - 50) for c in sc)

    for eye_pts in [landmarks[36:42], landmarks[42:48]]:
        ecx = int(eye_pts[:, 0].mean())
        ecy = int(eye_pts[:, 1].mean())
        ew = max(4, int((eye_pts[:, 0].max() - eye_pts[:, 0].min()) / 2) + 3)

        # Upper eyelid crease (curved line)
        cv2.ellipse(closed, (ecx, ecy), (int(ew * 1.1), 2),
                    0, 0, 180, crease_dark, 1)
        # Thin lash line at center
        cv2.line(closed, (ecx - ew + 2, ecy), (ecx + ew - 2, ecy),
                 crease_dark, 1)

    return closed


def _apply_eye_animation(
    frame: np.ndarray,
    frame_idx: int,
    blink_value: float,
    landmarks: np.ndarray,
    skin_color: tuple,
    emotion_config: dict | None = None,
    fps: int = 30,
    closed_eyes_img: np.ndarray | None = None,
) -> np.ndarray:
    """
    Full eye animation system:
      1. Blink    — cross-fade to pre-computed inpainted 'closed eyes' image
      2. Squint   — emotion-driven top/bottom lid narrowing (ANGRY, LAUGHS, SHOCKED)
      3. Catchlight drift — small bright highlight oscillates inside the iris,
                            giving the illusion of live, moving eyes every frame
    """
    t = frame_idx / fps
    emotion_name = (emotion_config or {}).get("_emotion_name", "") if emotion_config else ""

    frame = frame.copy()

    # Per-eye: (landmark slice, phase offset for async gaze movement)
    eye_defs = [
        (landmarks[36:42], 0.00),   # left eye
        (landmarks[42:48], 0.40),   # right eye — slight phase offset
    ]

    for eye_pts, phase in eye_defs:
        ecx = int(eye_pts[:, 0].mean())
        ecy = int(eye_pts[:, 1].mean())
        ew  = max(4, int((eye_pts[:, 0].max() - eye_pts[:, 0].min()) / 2) + 3)
        eh  = max(2, int((eye_pts[:, 1].max() - eye_pts[:, 1].min()) / 2) + 3)

        # ── 1. Blink (inpaint cross-fade) ──
        # Cross-fade between current frame and the pre-inpainted "closed eyes"
        # image in the eye ROI. Inpainting fills eyes with real surrounding skin
        # texture — no flat colors, no blur artifacts, fully photorealistic.
        if blink_value >= 0.15 and closed_eyes_img is not None:
            close = min(1.0, blink_value)

            # ROI around the eye (expanded + padding for feathered blend)
            blink_ew = int(ew * 1.35)
            blink_eh = int(eh * 1.25)
            pad = 6
            ry1 = max(0, ecy - blink_eh - pad)
            ry2 = min(frame.shape[0], ecy + blink_eh + pad)
            rx1 = max(0, ecx - blink_ew - pad)
            rx2 = min(frame.shape[1], ecx + blink_ew + pad)
            roi_h = ry2 - ry1
            roi_w = rx2 - rx1

            if roi_h > 2 and roi_w > 2:
                # Extract ROIs from both images
                open_roi = frame[ry1:ry2, rx1:rx2].astype(np.float32)
                shut_roi = closed_eyes_img[ry1:ry2, rx1:rx2].astype(np.float32)

                # Feathered elliptical mask — soft edges prevent hard boundaries
                mask = np.zeros((roi_h, roi_w), dtype=np.float32)
                mc_x = ecx - rx1
                mc_y = ecy - ry1
                cv2.ellipse(mask, (mc_x, mc_y), (blink_ew, blink_eh),
                            0, 0, 360, 1.0, -1)
                mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=4.0, sigmaY=3.0)

                # Alpha = blink intensity (partial close → translucent)
                alpha = close * 0.95
                m3 = (mask * alpha)[:, :, np.newaxis]

                # Cross-fade: open eyes → closed eyes
                frame[ry1:ry2, rx1:rx2] = (
                    open_roi * (1.0 - m3) + shut_roi * m3
                ).astype(np.uint8)

            continue   # skip gaze + squint while blinking

        # ── 2. Emotion squint (modifies lid height without blinking) ──
        if emotion_name in ("ANGRY", "DEAD SERIOUS", "NERVOUS"):
            # Upper lid drops slightly — authoritative squint
            squint_h = max(1, int(eh * 0.28))
            squint_col = tuple(max(0, c - 45) for c in skin_color)
            sq_cy = ecy - eh + squint_h // 2
            cv2.ellipse(frame, (ecx, sq_cy), (ew, squint_h), 0, 0, 180, skin_color, -1)
            cv2.ellipse(frame, (ecx, sq_cy), (ew, 1), 0, 0, 180, squint_col, 2)

        elif emotion_name == "LAUGHS":
            # Both top & bottom close in — laugh squint
            squint_h = max(1, int(eh * 0.22))
            squint_col = tuple(max(0, c - 35) for c in skin_color)
            cv2.ellipse(frame, (ecx, ecy - eh + squint_h // 2), (ew, squint_h),
                        0, 0, 180, skin_color, -1)
            cv2.ellipse(frame, (ecx, ecy + eh - squint_h // 2), (ew, squint_h),
                        0, 180, 360, skin_color, -1)

        elif emotion_name == "SHOCKED":
            # Upper lid pulls UP — wide eyes: draw a thin bright strip above eye
            wide_col = tuple(min(255, c + 18) for c in skin_color)
            wide_h = max(1, int(eh * 0.18))
            cv2.ellipse(frame, (ecx, ecy - eh - wide_h // 2), (ew, wide_h),
                        0, 0, 180, wide_col, -1)

        # ── 3. Iris / pupil drift + catchlight ──────────────────────────────
        # Two overlapping sine waves → natural-looking saccadic drift
        # Amplitude ~6px so movement is clearly visible on typical avatar sizes
        drift_x = int(
            math.sin(2 * math.pi * 0.28 * t + phase * math.pi) * 4.5 +
            math.sin(2 * math.pi * 1.10 * t + phase * 0.7)      * 1.5
        )
        drift_y = int(
            math.sin(2 * math.pi * 0.11 * t) * 2.5 +
            math.sin(2 * math.pi * 0.47 * t) * 1.0
        )

        # Emotion gaze bias
        if emotion_name == "SHOCKED":
            drift_y -= 4          # eyes dart upward
        elif emotion_name in ("DEAD SERIOUS", "ANGRY"):
            drift_y += 2          # focused downward stare
        elif emotion_name == "DISBELIEF":
            drift_x += int(math.sin(2 * math.pi * 0.4 * t) * 4)
        elif emotion_name in ("LAUGHS", "EXCITED"):
            drift_y -= 2          # bright upward gaze

        # Iris shadow: dark semi-transparent oval that shifts with the gaze
        # This is the main visible eye-movement indicator
        iris_x = ecx + drift_x
        iris_y = ecy + drift_y
        iris_rx = max(2, int(ew * 0.42))     # iris width (~42% of eye width)
        iris_ry = max(1, int(eh * 0.55))     # iris height (~55% of eye height)

        # Clamp iris centre inside eye bounds
        iris_x = max(ecx - ew + iris_rx + 1, min(ecx + ew - iris_rx - 1, iris_x))
        iris_y = max(ecy - eh + iris_ry + 1, min(ecy + eh - iris_ry - 1, iris_y))

        # 3a. Dark iris shadow (semi-transparent, shows the pupil/iris drifting)
        overlay = frame.copy()
        # Outer iris ring — coloured (sample from existing eye area: usually dark)
        iris_color = (35, 32, 30)            # near-black pupil
        cv2.ellipse(overlay, (iris_x, iris_y), (iris_rx, iris_ry),
                    0, 0, 360, iris_color, -1)
        cv2.addWeighted(overlay, 0.30, frame, 0.70, 0, frame)   # 30% blend — subtle but visible

        # 3b. Catchlight — small bright dot upper-inner of iris
        shine_x = iris_x - max(1, int(iris_rx * 0.30))
        shine_y = iris_y - max(1, int(iris_ry * 0.35))
        shine_r = max(1, int(iris_rx * 0.28))

        shine_x = max(ecx - ew + shine_r + 1, min(ecx + ew - shine_r - 1, shine_x))
        shine_y = max(ecy - eh + shine_r + 1, min(ecy + eh - shine_r - 1, shine_y))

        overlay2 = frame.copy()
        cv2.circle(overlay2, (shine_x, shine_y), shine_r, (248, 248, 252), -1)
        cv2.addWeighted(overlay2, 0.65, frame, 0.35, 0, frame)

    return frame


# Keep old name as alias so any external callers still work
def _apply_blinks(frame, blink_value, landmarks, skin_color):
    return _apply_eye_animation(frame, 0, blink_value, landmarks, skin_color)


# ── Head Movement ─────────────────────────────────────────────

def _apply_head_movement(
    frame: np.ndarray,
    frame_idx: int,
    amplitude: float,
    fps: int,
    emotion_config: dict | None = None,
) -> np.ndarray:
    """Apply dynamic emotion-driven head movement via affine transform."""
    t = frame_idx / fps
    emotion_name = (emotion_config or {}).get("_emotion_name", "")

    # Natural breathing oscillation (3× more visible than before)
    breath_dy = math.sin(2 * math.pi * 0.25 * t) * 2.5
    # Gentle side sway (3× more visible)
    sway_dx = math.sin(2 * math.pi * 0.15 * t + math.pi / 4) * 2.5
    # Speaking nod — downward push when loud
    nod_dy = amplitude * 4.0
    # Rapid talking bob during active speech
    talk_bob = math.sin(2 * math.pi * 3.5 * t) * amplitude * 2.5 if amplitude > 0.15 else 0.0

    # Emotion-driven movement overrides
    emotion_dx = 0.0
    emotion_dy = 0.0
    emotion_rot = 0.0  # degrees

    if emotion_name == "SHOCKED":
        emotion_dy = -4.0                                          # head snaps back
        emotion_rot = math.sin(2 * math.pi * 0.8 * t) * 0.8      # slight wobble
    elif emotion_name in ("ANGRY", "FIRED UP"):
        emotion_dy = 4.0                                           # aggressive forward lean
        emotion_dx = math.sin(2 * math.pi * 0.6 * t) * 1.5       # side-to-side intensity
        emotion_rot = -0.8                                         # forward tilt
    elif emotion_name == "LAUGHS":
        emotion_dy = math.sin(2 * math.pi * 4.0 * t) * 5.0       # laugh bounce
        emotion_rot = math.sin(2 * math.pi * 2.0 * t) * 2.0      # head rocks with laughter
    elif emotion_name == "EXCITED":
        emotion_dy = math.sin(2 * math.pi * 2.5 * t) * 3.5       # bouncy excitement
        emotion_dx = math.sin(2 * math.pi * 1.8 * t) * 1.5       # energetic side movement
    elif emotion_name == "WHISPERING":
        emotion_dy = 3.5                                           # lean in conspiratorially
        breath_dy *= 0.4; sway_dx *= 0.4; nod_dy *= 0.3          # reduce background motion
        talk_bob = 0.0
    elif emotion_name == "DEAD SERIOUS":
        # Lock down — almost no movement, very authoritative
        breath_dy *= 0.2; sway_dx *= 0.2; nod_dy *= 0.2
        talk_bob = 0.0
    elif emotion_name == "NERVOUS":
        emotion_dx = math.sin(2 * math.pi * 5.0 * t) * 1.5       # fidgety side tremor
        emotion_dy = math.sin(2 * math.pi * 5.5 * t) * 0.8       # slight up-down tremor
    elif emotion_name == "DISBELIEF":
        emotion_rot = math.sin(2 * math.pi * 0.4 * t) * 1.5      # slow incredulous head shake

    dx = sway_dx + emotion_dx
    dy = breath_dy + nod_dy + talk_bob + emotion_dy
    h, w = frame.shape[:2]

    if abs(emotion_rot) > 0.05:
        cx, cy = w / 2, h / 2
        M = cv2.getRotationMatrix2D((cx, cy), emotion_rot, 1.0)
        M[0, 2] += dx
        M[1, 2] += dy
        return cv2.warpAffine(frame, M, (w, h),
                              flags=cv2.INTER_LANCZOS4,
                              borderMode=cv2.BORDER_REFLECT_101)

    if abs(dx) < 0.05 and abs(dy) < 0.05:
        return frame
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(frame, M, (w, h),
                          flags=cv2.INTER_LANCZOS4,
                          borderMode=cv2.BORDER_REFLECT_101)


# ── Emotion Color Tint ─────────────────────────────────────────
# Subtle screen-blend tints reinforce each emotion visually.
# Values are normalised BGR additive offsets (0.0–1.0 scale).

_EMOTION_TINTS: dict[str, tuple[float, float, float]] = {
    "EXCITED":      (0.00, 0.03, 0.09),   # warm golden-orange
    "FIRED UP":     (0.00, 0.00, 0.14),   # hot red energy
    "ANGRY":        (0.00, 0.00, 0.10),   # red aggression
    "SHOCKED":      (0.06, 0.02, 0.00),   # icy blue surprise
    "LAUGHS":       (0.00, 0.05, 0.10),   # warm happiness
    "DEAD SERIOUS": (0.06, 0.01, 0.00),   # cold authority
    "WHISPERING":   (0.02, 0.01, 0.03),   # dim soft warmth
    "NERVOUS":      (0.03, 0.00, 0.04),   # cool anxious purple
    "DISBELIEF":    (0.04, 0.01, 0.00),   # cool blue doubt
    "IMPRESSED":    (0.00, 0.04, 0.07),   # warm admiration
}


def _apply_emotion_tint(frame: np.ndarray, emotion_name: str) -> np.ndarray:
    """Screen-blend a subtle colour tint to reinforce the current emotion."""
    tint = _EMOTION_TINTS.get(emotion_name)
    if not tint or max(tint) < 0.005:
        return frame
    b_add, g_add, r_add = tint
    result = frame.astype(np.float32) / 255.0
    result[:, :, 0] = np.clip(result[:, :, 0] + b_add, 0.0, 1.0)
    result[:, :, 1] = np.clip(result[:, :, 1] + g_add, 0.0, 1.0)
    result[:, :, 2] = np.clip(result[:, :, 2] + r_add, 0.0, 1.0)
    return (result * 255.0).astype(np.uint8)


# ── Zoom Pulse ─────────────────────────────────────────────────

def _apply_zoom_pulse(frame: np.ndarray, amplitude: float, emotion_name: str = "") -> np.ndarray:
    """Dynamic push-in zoom on loud / energetic moments — cinematic feel."""
    zoom = 1.0 + amplitude * 0.03           # 0–3 % on speech amplitude
    if emotion_name in ("EXCITED", "FIRED UP", "SHOCKED", "LAUGHS"):
        zoom = min(zoom + 0.015, 1.055)     # extra kick for hype emotions (max ~5.5 %)
    if zoom <= 1.004:
        return frame
    h, w = frame.shape[:2]
    new_h = max(1, int(h / zoom))
    new_w = max(1, int(w / zoom))
    y1 = (h - new_h) // 2
    x1 = (w - new_w) // 2
    return cv2.resize(frame[y1:y1 + new_h, x1:x1 + new_w], (w, h),
                      interpolation=cv2.INTER_LANCZOS4)


# ══════════════════════════════════════════════════════════════
# TIER 1: Wav2Lip — ML-Based Lip Sync
# ══════════════════════════════════════════════════════════════

def _check_wav2lip_available() -> bool:
    """Check if Wav2Lip inference code and model weights exist."""
    if not WAV2LIP_MODEL_PATH.exists():
        return False
    if WAV2LIP_MODEL_PATH.stat().st_size < 400_000_000:
        return False
    inference_script = WAV2LIP_DIR / "inference.py"
    return inference_script.exists()


async def _ensure_wav2lip_setup() -> bool:
    """Clone Wav2Lip repo and download model weights on first run."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not (WAV2LIP_DIR / "inference.py").exists():
        print("[LocalAvatar] Cloning Wav2Lip repository...")
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "https://github.com/Rudrabha/Wav2Lip.git",
                str(WAV2LIP_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            if proc.returncode != 0:
                print("[LocalAvatar] Git clone failed")
                return False
        except FileNotFoundError:
            print("[LocalAvatar] Git not found")
            return False

    if not WAV2LIP_MODEL_PATH.exists() or WAV2LIP_MODEL_PATH.stat().st_size < 400_000_000:
        print("[LocalAvatar] Downloading Wav2Lip model (436MB)...")
        try:
            import gdown
            gdown.download(WAV2LIP_MODEL_URL, str(WAV2LIP_MODEL_PATH), quiet=False, fuzzy=True)
        except (ImportError, Exception) as e:
            print(f"[LocalAvatar] Model download failed: {e}")
            return False
        if not WAV2LIP_MODEL_PATH.exists():
            return False

    return True


def _get_gfpgan_restorer():
    """Lazy-load GFPGAN face restorer (cached after first call)."""
    global _gfpgan_restorer
    if _gfpgan_restorer is not None:
        return _gfpgan_restorer
    if not GFPGAN_MODEL_PATH.exists():
        print("[LocalAvatar] GFPGAN model not found, skipping face restoration")
        return None
    try:
        from gfpgan import GFPGANer
        _gfpgan_restorer = GFPGANer(
            model_path=str(GFPGAN_MODEL_PATH),
            upscale=1,
            arch='clean',
            channel_multiplier=2,
            bg_upsampler=None,
        )
        print("[LocalAvatar] GFPGAN face restorer loaded")
        return _gfpgan_restorer
    except Exception as e:
        print(f"[LocalAvatar] GFPGAN init failed: {e}")
        return None


def _enhance_wav2lip_video(input_path: Path, output_path: Path, character: str = "",
                            original_image: str | None = None,
                            line_timings: list | None = None):
    """Enhance Wav2Lip output via mouth-mask blending with original sharp image.

    Strategy: Wav2Lip only modifies the mouth area but blurs the entire face.
    We keep the original sharp image for everything except the mouth region,
    blending only the lip-synced mouth from Wav2Lip output.
    Additionally applies eye animation (blinks + iris drift) to the final frames
    so Wav2Lip output has the same eye movement as the audio-reactive compositor.
    Result: sharp face + lip-synced mouth + live eye movement in ~10-20s.
    """
    if original_image is None:
        return str(input_path)

    original = cv2.imread(original_image)
    if original is None:
        return str(input_path)

    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = ANIMATION_FPS
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if original.shape[:2] != (h, w):
        original = cv2.resize(original, (w, h))

    # ── Pre-compute face/mouth mask ───────────────────────────
    face_box = None
    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        return str(input_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    try:
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(50, 50))
        if len(faces) > 0:
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            face_box = (fx, fy, fx + fw, fy + fh)
            print(f"[LocalAvatar] {character}: Face detected for mask blend: {face_box}")
    except Exception as e:
        print(f"[LocalAvatar] {character}: Face detection failed: {e}")

    mask = np.zeros((h, w), dtype=np.float32)
    if face_box:
        fx1, fy1, fx2, fy2 = face_box
        face_h = fy2 - fy1
        mouth_y1 = fy1 + int(face_h * 0.4)
        mouth_y2 = min(h, fy2 + int(face_h * 0.1))
        mask[mouth_y1:mouth_y2, fx1:fx2] = 1.0
    else:
        mask[int(h * 0.6):, :] = 1.0

    mask = cv2.GaussianBlur(mask, (51, 51), 12)
    mask_u8 = (mask * 255).astype(np.uint8)
    inv_mask_u8 = (255 - mask_u8)
    mask_3ch_u8 = np.stack([mask_u8] * 3, axis=-1)
    inv_mask_3ch_u8 = np.stack([inv_mask_u8] * 3, axis=-1)
    orig_weighted = (original.astype(np.uint16) * inv_mask_3ch_u8.astype(np.uint16)) // 255

    # ── Pre-compute eye animation data (runs on every frame) ─────
    landmarks = _get_landmarks(original_image)
    blinks = _generate_blink_schedule(total, int(fps))
    mc = MouthCompositor(original, landmarks) if landmarks is not None else None
    skin_color = mc.skin_color if mc is not None else (200, 180, 160)
    del mc

    # Pre-compute inpainted "closed eyes" image (one-time cost, ~50ms)
    closed_eyes_img = None
    if landmarks is not None:
        closed_eyes_img = _create_closed_eyes_image(original, landmarks)
        print(f"[LocalAvatar] {character}: Closed-eyes image pre-computed (inpaint)")

    emotion_tl = _build_emotion_timeline(line_timings, character, total, int(fps))

    # ── Frame loop ────────────────────────────────────────────
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

    start = time.time()
    for frame_idx in range(total):
        ret, frame = cap.read()
        if not ret:
            break

        # 1. Mouth-mask blend: restore sharp face, keep Wav2Lip mouth
        result = (orig_weighted +
                  (frame.astype(np.uint16) * mask_3ch_u8.astype(np.uint16)) // 255
                  ).astype(np.uint8)

        # 2. Sharpen the blended result (counters Wav2Lip's inherent softness)
        sharp_kernel = np.array([[0, -0.5, 0],
                                  [-0.5, 3.0, -0.5],
                                  [0, -0.5, 0]], dtype=np.float32)
        result = cv2.filter2D(result, -1, sharp_kernel)

        # 3. Eye animation on top of every frame
        if landmarks is not None:
            emo = emotion_tl[frame_idx] if frame_idx < len(emotion_tl) else {}
            blk = float(blinks[frame_idx]) if frame_idx < len(blinks) else 0.0
            result = _apply_eye_animation(result, frame_idx, blk, landmarks,
                                          skin_color, emo, int(fps),
                                          closed_eyes_img=closed_eyes_img)

        writer.write(result)

    cap.release()
    writer.release()
    elapsed = time.time() - start
    print(f"[LocalAvatar] {character}: Enhanced (mouth-mask + eye anim) "
          f"{total} frames in {elapsed:.1f}s")
    return str(output_path)


async def _generate_wav2lip(
    image_path: str, audio_path: str, output_path: Path,
    character: str = "SPARKY", use_gpu: bool = True,
    line_timings: list | None = None,
) -> str | None:
    """Generate lip-synced video using Wav2Lip subprocess."""
    if not _check_wav2lip_available():
        if not await _ensure_wav2lip_setup():
            return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create static video from image
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = len(y) / sr
    temp_video = output_path.parent / f"_temp_static_{character.lower()}.mp4"
    img = cv2.imread(image_path)
    if img is None:
        return None
    h, w = img.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(temp_video), fourcc, ANIMATION_FPS, (w, h))
    for _ in range(int(duration * ANIMATION_FPS) + 1):
        writer.write(img)
    writer.release()

    # Convert audio to WAV
    temp_wav = output_path.parent / f"_temp_audio_{character.lower()}.wav"
    y_audio, sr_audio = librosa.load(audio_path, sr=16000, mono=True)
    sf.write(str(temp_wav), y_audio, 16000)

    temp_w2l = output_path.parent / f"_temp_w2l_{character.lower()}.mp4"
    # All paths must be absolute since Wav2Lip runs from its own cwd
    cmd = [
        sys.executable, str(WAV2LIP_DIR.resolve() / "inference.py"),
        "--checkpoint_path", str(WAV2LIP_MODEL_PATH.resolve()),
        "--face", str(temp_video.resolve()), "--audio", str(temp_wav.resolve()),
        "--outfile", str(temp_w2l.resolve()),
        "--static", "True", "--fps", str(ANIMATION_FPS),
        "--nosmooth", "--resize_factor", "1",
        "--face_det_batch_size", "4", "--wav2lip_batch_size", "32",
    ]

    start = time.time()
    print(f"[LocalAvatar] {character}: Running Wav2Lip ({_get_device()})...")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(WAV2LIP_DIR),
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        if proc.returncode != 0:
            print(f"[LocalAvatar] {character}: Wav2Lip failed: {stderr.decode(errors='replace')[:200]}")
            for f in [temp_video, temp_wav]:
                f.unlink(missing_ok=True)
            return None
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[LocalAvatar] {character}: Wav2Lip error: {e}")
        for f in [temp_video, temp_wav]:
            f.unlink(missing_ok=True)
        return None

    if temp_w2l.exists():
        # Mouth-mask blend + sharpening + eye animation to fix Wav2Lip blurriness
        temp_enhanced = output_path.parent / f"_temp_enhanced_{character.lower()}.mp4"
        _enhance_wav2lip_video(temp_w2l, temp_enhanced, character,
                               original_image=image_path, line_timings=line_timings)
        source_video = temp_enhanced if temp_enhanced.exists() else temp_w2l

        try:
            from moviepy import VideoFileClip, AudioFileClip
            video = VideoFileClip(str(source_video))
            audio = AudioFileClip(audio_path)
            if video.duration > audio.duration:
                video = video.subclipped(0, audio.duration)
            video.with_audio(audio).write_videofile(str(output_path), codec="libx264",
                                                     audio_codec="aac", logger=None)
            video.close()
            audio.close()
        except Exception:
            import shutil
            shutil.move(str(source_video), str(output_path))
    else:
        for f in [temp_video, temp_wav]:
            f.unlink(missing_ok=True)
        return None

    for f in [temp_video, temp_wav, temp_w2l, temp_enhanced]:
        f.unlink(missing_ok=True)

    elapsed = time.time() - start
    print(f"[LocalAvatar] {character}: Wav2Lip done in {elapsed:.1f}s -> {output_path.name}")
    return str(output_path)


# ══════════════════════════════════════════════════════════════
# TIER 2: Audio-Reactive Compositing (Cartoon Optimized)
# ══════════════════════════════════════════════════════════════

def _generate_composite_sync(
    image_path: str,
    audio_path: str,
    output_path: Path,
    character: str = "SPARKY",
    fps: int = 30,
    line_timings: list[dict] | None = None,
) -> str | None:
    """
    Generate talking head with composited mouth overlay.

    Instead of warping the full face mesh (which stretches pixels
    unnaturally on cartoon characters), this draws shaped mouth
    openings over an inpainted face base and feather-blends them.

    Much faster and better looking than mesh warping for cartoons.
    """
    start = time.time()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[LocalAvatar] {character}: Audio-reactive compositing starting...")

    # 1. Load image and detect landmarks
    src_img = cv2.imread(image_path)
    if src_img is None:
        print(f"[LocalAvatar] {character}: Cannot read image")
        return None
    h, w = src_img.shape[:2]

    landmarks = _get_landmarks(image_path)
    if landmarks is None:
        print(f"[LocalAvatar] {character}: Cannot detect face landmarks")
        return None

    # Log mouth detection
    outer_lip = landmarks[48:60]
    lip_l, lip_t = int(outer_lip[:, 0].min()), int(outer_lip[:, 1].min())
    lip_r, lip_b = int(outer_lip[:, 0].max()), int(outer_lip[:, 1].max())
    print(f"[LocalAvatar] Mouth detected via landmarks: ({lip_l},{lip_t})-({lip_r},{lip_b})")

    # 2. Analyze audio
    audio_data = _analyze_audio(audio_path, fps)
    n_frames = audio_data["n_frames"]
    amplitude = audio_data["amplitude"]
    centroid = audio_data["centroid"]
    print(f"[LocalAvatar] {character}: Audio: {audio_data['duration']:.1f}s, {n_frames} frames @ {fps}fps")

    # 3. Build emotion timeline and blink schedule
    emotion_timeline = _build_emotion_timeline(line_timings, character, n_frames, fps)
    blinks = _generate_blink_schedule(n_frames, fps)

    # 4. Initialize mouth compositor (prefer D-ID sprites when available)
    sprite_dir = _check_sprites_available(image_path)
    if sprite_dir:
        print(f"[LocalAvatar] {character}: Using D-ID sprite compositor (FREE, D-ID quality)")
        compositor = SpriteCompositor(src_img, sprite_dir)
        # Sample skin color from landmarks for blinks
        temp_mc = MouthCompositor(src_img, landmarks)
        skin_color = temp_mc.skin_color
        del temp_mc
    else:
        compositor = MouthCompositor(src_img, landmarks)
        skin_color = compositor.skin_color

    # Pre-compute inpainted "closed eyes" image for natural blinks
    closed_eyes_img = _create_closed_eyes_image(src_img, landmarks)
    print(f"[LocalAvatar] {character}: Closed-eyes image pre-computed (inpaint)")

    # 5. Render frames
    temp_video = output_path.parent / f"_temp_comp_{character.lower()}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (w, h))

    print(f"[LocalAvatar] {character}: Rendering {n_frames} frames...")
    for i in range(n_frames):
        amp = float(amplitude[i]) if i < len(amplitude) else 0.0
        cent = float(centroid[i]) if i < len(centroid) else 0.5
        emo = emotion_timeline[i]
        blk = float(blinks[i])
        emo_name = emo.get("_emotion_name", "") if isinstance(emo, dict) else ""

        # a. Mouth overlay (main lip sync)
        frame = compositor.render(amp, cent, emo)

        # b. Eye animation (blinks + gaze drift + emotion squint)
        frame = _apply_eye_animation(frame, i, blk, landmarks, skin_color, emo, fps,
                                     closed_eyes_img=closed_eyes_img)

        # c. Emotion colour tint (subtle screen blend)
        if emo_name:
            frame = _apply_emotion_tint(frame, emo_name)

        # d. Zoom pulse (push-in on loud/exciting moments)
        frame = _apply_zoom_pulse(frame, amp, emo_name)

        # e. Head movement (emotion-driven — breathing, sway, nod, tilt, rotation)
        frame = _apply_head_movement(frame, i, amp, fps, emo)

        writer.write(frame)

        if (i + 1) % (fps * 10) == 0:
            pct = int((i + 1) / n_frames * 100)
            print(f"[LocalAvatar] {character}: {pct}%")

    writer.release()
    print(f"[LocalAvatar] {character}: Frames written ({n_frames} frames)")

    # 6. Mux audio
    try:
        from moviepy import VideoFileClip, AudioFileClip
        video = VideoFileClip(str(temp_video))
        audio = AudioFileClip(audio_path)
        min_dur = min(video.duration, audio.duration)
        video = video.subclipped(0, min_dur)
        audio = audio.subclipped(0, min_dur)
        final = video.with_audio(audio)
        final.write_videofile(str(output_path), codec="libx264",
                              audio_codec="aac", fps=fps, logger=None)
        video.close()
        audio.close()
        final.close()
    except Exception as e:
        print(f"[LocalAvatar] {character}: Audio mux failed: {e}")
        import shutil
        shutil.move(str(temp_video), str(output_path))

    temp_video.unlink(missing_ok=True)

    if not output_path.exists():
        return None

    elapsed = time.time() - start
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[LocalAvatar] {character}: Audio-reactive completed in {elapsed:.1f}s -> {output_path.name} ({size_mb:.1f}MB)")
    return str(output_path)


async def _generate_composite(
    image_path: str,
    audio_path: str,
    output_path: Path,
    character: str = "SPARKY",
    fps: int = 30,
    line_timings: list[dict] | None = None,
) -> str | None:
    """Async wrapper for compositing animation."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _generate_composite_sync,
        image_path, audio_path, output_path, character, fps, line_timings,
    )


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

async def generate_local_avatar(
    image_path: str,
    audio_path: str,
    output_path: str | Path,
    character: str = "SPARKY",
    fps: int = 30,
    prefer_gpu: bool = True,
    line_timings: list[dict] | None = None,
) -> str | None:
    """
    Generate animated talking head video using local methods (FREE).

    Priority: Wav2Lip -> Sprite Compositor (D-ID quality, FREE) -> Ellipse Compositor.

    Args:
        image_path: Path to character PNG
        audio_path: Path to character MP3 audio
        output_path: Where to write the output MP4
        character: "SPARKY" or "NOVA" (for logging)
        fps: Output video frame rate
        prefer_gpu: Try GPU acceleration if CUDA available
        line_timings: Per-line timing data with emotions for expression animation

    Returns:
        Path to output MP4, or None on failure.
    """
    output_path = Path(output_path)

    if not Path(image_path).exists():
        print(f"[LocalAvatar] {character}: Image not found: {image_path}")
        return None
    if not Path(audio_path).exists():
        print(f"[LocalAvatar] {character}: Audio not found: {audio_path}")
        return None

    # Tier 1: Try Wav2Lip
    if _check_wav2lip_available():
        print(f"[LocalAvatar] {character}: Trying Wav2Lip...")
        result = await _generate_wav2lip(
            image_path, audio_path, output_path,
            character=character, use_gpu=prefer_gpu,
            line_timings=line_timings,
        )
        if result:
            return result
        print(f"[LocalAvatar] {character}: Wav2Lip failed, using compositing")

    # Tier 2: Audio-reactive compositing (cartoon optimized)
    print(f"[LocalAvatar] {character}: Using audio-reactive compositing")
    result = await _generate_composite(
        image_path, audio_path, output_path,
        character=character, fps=fps, line_timings=line_timings,
    )
    return result


# ── CLI Test ──────────────────────────────────────────────────

if __name__ == "__main__":

    async def test():
        print("[LocalAvatar] Testing audio-reactive compositing...")

        char_dir = Path(__file__).parent.parent / "assets" / "podcast_characters" / "baby"
        test_images = list(char_dir.glob("sparky_*.png"))
        if not test_images:
            print("[LocalAvatar] No cached character images found")
            return

        test_image = str(test_images[0])
        print(f"[LocalAvatar] Image: {test_image}")

        # Generate test audio
        test_audio = Path(__file__).parent.parent / "output" / "test_local_audio.mp3"
        test_audio.parent.mkdir(parents=True, exist_ok=True)
        try:
            import edge_tts
            comm = edge_tts.Communicate(
                "Oh my god, are you serious right now? That is absolutely insane! "
                "I cannot believe what I'm hearing. This changes everything we know!",
                voice="en-US-GuyNeural",
            )
            await comm.save(str(test_audio))
        except Exception as e:
            print(f"[LocalAvatar] Cannot generate test audio: {e}")
            return

        # Test with emotions
        test_timings = [
            {"character": "SPARKY", "emotion": "SHOCKED", "text": "Oh my god",
             "start": 0.0, "end": 2.0, "section": "HOOK"},
            {"character": "SPARKY", "emotion": "EXCITED", "text": "are you serious",
             "start": 2.0, "end": 4.0, "section": "ROUND 1"},
            {"character": "SPARKY", "emotion": "DISBELIEF", "text": "absolutely insane",
             "start": 4.0, "end": 6.0, "section": "ROUND 1"},
            {"character": "SPARKY", "emotion": "FIRED UP", "text": "changes everything",
             "start": 6.0, "end": 9.0, "section": "ROUND 2"},
        ]

        output = Path(__file__).parent.parent / "output" / "test_local_avatar.mp4"
        result = await generate_local_avatar(
            image_path=test_image,
            audio_path=str(test_audio),
            output_path=output,
            character="SPARKY",
            line_timings=test_timings,
        )

        if result:
            size_mb = Path(result).stat().st_size / (1024 * 1024)
            print(f"[LocalAvatar] SUCCESS: {result} ({size_mb:.1f}MB)")
        else:
            print("[LocalAvatar] FAILED")

        test_audio.unlink(missing_ok=True)

    asyncio.run(test())
