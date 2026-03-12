"""
Visual Effects — Cinema-Grade Video Effects Engine.

Transforms static images and video clips into eye-catching, viral-quality content.

Effects library:
- Ken Burns zoom/pan (8 types + enhanced diagonal)
- Scene transitions (12+ styles: crossfade, slide, whip, zoom, blur, flash, glitch)
- Zoom pulse (beat-sync zoom in/out on key moments)
- Screen shake (impact tremor for dramatic reveals)
- Glitch/RGB split (digital distortion for emphasis)
- Flash transitions (white flash between scenes)
- Vignette overlay (cinematic dark edges)
- Film grain (subtle texture overlay)
- Speed ramping (slow-mo reveals, speed-up transitions)
- Dynamic zoom (mid-scene zoom to focal point)
- Lower thirds (professional info bars)
- Animated text overlays
"""
import random
import math
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from moviepy import (
    VideoClip,
    ImageClip,
    ColorClip,
    TextClip,
    CompositeVideoClip,
    vfx,
)

from config import (
    KEN_BURNS_ZOOM_RANGE,
    TRANSITION_DURATION,
    CAPTION_FONT,
)


# ── Niche Accent Colors ──────────────────────────────────────

NICHE_ACCENT_COLORS = {
    "ai_trading": (0, 255, 136),        # Green
    "ai_money": (0, 200, 255),          # Cyan
    "tech_news": (160, 120, 255),       # Purple
    "motivation": (255, 200, 0),        # Gold
    "health_wellness": (100, 220, 100), # Green
    "blissful_moments": (255, 180, 100), # Warm gold
}


# ── Ken Burns Effect ──────────────────────────────────────────

def apply_ken_burns(
    image_path: str,
    duration: float,
    target_w: int,
    target_h: int,
    effect_type: str = "random",
) -> ImageClip:
    """
    Apply Ken Burns (zoom + pan) to a still image.

    Loads image oversized, then applies a moving crop to create
    the illusion of camera movement. Eliminates static slideshow feel.
    """
    if effect_type == "random":
        effect_type = random.choice([
            "zoom_in", "zoom_out", "pan_left", "pan_right",
            "pan_up", "pan_down", "diagonal_tl_br", "diagonal_br_tl",
        ])

    zoom_start, zoom_end = KEN_BURNS_ZOOM_RANGE

    # Load and resize image larger than target (room for zoom/pan)
    pil_img = Image.open(image_path).convert("RGB")
    oversize = 1.5
    new_h = int(target_h * oversize)
    new_w = int(new_h * pil_img.width / pil_img.height)
    if new_w < int(target_w * oversize):
        new_w = int(target_w * oversize)
        new_h = int(new_w * pil_img.height / pil_img.width)
    pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
    img_array = np.array(pil_img)

    from PIL import Image as PILImage

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        progress = min(max(progress, 0), 1)

        # Smooth easing (ease-in-out cubic) for more natural camera feel
        if progress < 0.5:
            eased = 4 * progress * progress * progress
        else:
            eased = 1 - pow(-2 * progress + 2, 3) / 2

        if effect_type == "zoom_in":
            scale = zoom_start + (zoom_end - zoom_start) * eased
            cx, cy = new_w / 2, new_h / 2
        elif effect_type == "zoom_out":
            scale = zoom_end - (zoom_end - zoom_start) * eased
            cx, cy = new_w / 2, new_h / 2
        elif effect_type == "pan_left":
            scale = (zoom_start + zoom_end) / 2
            cx = new_w / 2 + (new_w * 0.14) * (1 - eased)
            cy = new_h / 2
        elif effect_type == "pan_right":
            scale = (zoom_start + zoom_end) / 2
            cx = new_w / 2 - (new_w * 0.14) * (1 - eased)
            cy = new_h / 2
        elif effect_type == "pan_up":
            scale = (zoom_start + zoom_end) / 2
            cx = new_w / 2
            cy = new_h / 2 + (new_h * 0.14) * (1 - eased)
        elif effect_type == "pan_down":
            scale = (zoom_start + zoom_end) / 2
            cx = new_w / 2
            cy = new_h / 2 - (new_h * 0.14) * (1 - eased)
        elif effect_type == "diagonal_tl_br":
            scale = zoom_start + (zoom_end - zoom_start) * eased
            cx = new_w / 2 - (new_w * 0.10) * (1 - eased)
            cy = new_h / 2 - (new_h * 0.10) * (1 - eased)
        else:  # diagonal_br_tl
            scale = zoom_start + (zoom_end - zoom_start) * eased
            cx = new_w / 2 + (new_w * 0.10) * (1 - eased)
            cy = new_h / 2 + (new_h * 0.10) * (1 - eased)

        # Calculate crop window
        crop_w = int(target_w / scale)
        crop_h = int(target_h / scale)

        x1 = int(max(0, min(cx - crop_w / 2, new_w - crop_w)))
        y1 = int(max(0, min(cy - crop_h / 2, new_h - crop_h)))
        x2 = x1 + crop_w
        y2 = y1 + crop_h

        cropped = img_array[y1:y2, x1:x2]

        pil_crop = PILImage.fromarray(cropped).resize(
            (target_w, target_h), PILImage.LANCZOS
        )
        return np.array(pil_crop)

    clip = VideoClip(frame_function=make_frame, duration=duration, is_mask=False)
    return clip


# ── Cinematic Effects ─────────────────────────────────────────

def apply_zoom_pulse(clip, intensity: float = 1.12, pulse_time: float = 0.0):
    """
    Apply a quick zoom pulse (punch-in/out) at a specific time.

    Creates a sudden 12% zoom-in that smoothly returns to normal.
    Used on power words, reveals, and dramatic moments.
    Perfect for syncing with bass drops or impact SFX.

    Args:
        clip: Input video clip
        intensity: Max zoom level (1.12 = 12% zoom)
        pulse_time: Time in clip to center the pulse (0 = start)
    """
    w, h = clip.size
    pulse_duration = 0.35  # Quick punch-in/out

    def zoom_filter(get_frame, t):
        frame = get_frame(t)
        # Calculate zoom based on distance from pulse center
        dist = abs(t - pulse_time)
        if dist > pulse_duration:
            return frame

        # Smooth pulse curve (sine-based for organic feel)
        pulse_progress = 1 - (dist / pulse_duration)
        zoom = 1.0 + (intensity - 1.0) * math.sin(pulse_progress * math.pi)

        if zoom <= 1.001:
            return frame

        # Center crop and resize
        from PIL import Image as PILImage
        pil = PILImage.fromarray(frame)
        cw, ch = int(w / zoom), int(h / zoom)
        x1 = (w - cw) // 2
        y1 = (h - ch) // 2
        cropped = pil.crop((x1, y1, x1 + cw, y1 + ch))
        resized = cropped.resize((w, h), PILImage.LANCZOS)
        return np.array(resized)

    return clip.transform(zoom_filter)


def apply_screen_shake(clip, intensity: float = 8, shake_time: float = 0.0):
    """
    Apply a quick screen shake effect at a specific time.

    Simulates camera impact — random X/Y offsets that decay quickly.
    Used on: dramatic reveals, impact SFX, "breaking news" moments.

    Args:
        clip: Input video clip
        intensity: Max pixel offset (8px default)
        shake_time: Center time for the shake
    """
    w, h = clip.size
    shake_duration = 0.3
    # Pre-generate shake offsets for consistency
    np.random.seed(42)
    shake_offsets = [(np.random.randint(-int(intensity), int(intensity) + 1),
                      np.random.randint(-int(intensity), int(intensity) + 1))
                     for _ in range(30)]

    def shake_filter(get_frame, t):
        frame = get_frame(t)
        dist = abs(t - shake_time)
        if dist > shake_duration:
            return frame

        # Decay the intensity based on distance from center
        decay = 1 - (dist / shake_duration)
        frame_idx = int((t * 30) % len(shake_offsets))
        dx = int(shake_offsets[frame_idx][0] * decay)
        dy = int(shake_offsets[frame_idx][1] * decay)

        if dx == 0 and dy == 0:
            return frame

        result = np.zeros_like(frame)
        # Apply offset with bounds checking
        src_x1 = max(0, -dx)
        src_y1 = max(0, -dy)
        src_x2 = min(w, w - dx)
        src_y2 = min(h, h - dy)
        dst_x1 = max(0, dx)
        dst_y1 = max(0, dy)
        dst_x2 = dst_x1 + (src_x2 - src_x1)
        dst_y2 = dst_y1 + (src_y2 - src_y1)

        result[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]
        return result

    return clip.transform(shake_filter)


def create_vignette_overlay(width: int, height: int, strength: float = 0.5) -> np.ndarray:
    """
    Create a cinematic vignette (dark edges) overlay.

    Makes the center subject pop by darkening the periphery.
    Strength 0.5 = subtle, 0.8 = dramatic, 1.0 = very dark edges.
    """
    Y, X = np.ogrid[:height, :width]
    cx, cy = width / 2, height / 2
    # Normalized distance from center (0=center, 1=corners)
    dist = np.sqrt((X - cx) ** 2 / (cx ** 2) + (Y - cy) ** 2 / (cy ** 2))
    # Smooth vignette curve
    vignette = 1.0 - np.clip(dist * strength, 0, 1) ** 1.5
    # Convert to 3-channel
    return np.stack([vignette] * 3, axis=-1).astype(np.float32)


def apply_vignette(clip, strength: float = 0.45):
    """
    Apply a persistent cinematic vignette to a clip.

    Darkens edges to draw focus to center content.
    """
    w, h = clip.size
    vignette_mask = create_vignette_overlay(w, h, strength)

    def vignette_filter(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        result = frame * vignette_mask
        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.transform(vignette_filter)


def apply_film_grain(clip, intensity: float = 12, fps: int = 30):
    """
    Add subtle film grain texture to a clip.

    Gives footage a cinematic, high-production-value look.
    Intensity 8-15 is subtle, 20+ is dramatic.
    """
    w, h = clip.size

    def grain_filter(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        # Generate random noise (seeded by time for frame-to-frame variation)
        seed = int(t * fps) % 10000
        rng = np.random.RandomState(seed)
        noise = rng.normal(0, intensity, frame.shape).astype(np.float32)
        result = frame + noise
        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.transform(grain_filter)


def create_flash_transition(
    duration: float,
    width: int,
    height: int,
    flash_color: tuple = (255, 255, 255),
) -> VideoClip:
    """
    Create a quick white flash transition clip.

    A short (0.15-0.25s) bright flash that fades — used between
    scenes for dramatic impact. Common in music videos and trailers.
    """
    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        # Quick flash up then fade out
        if progress < 0.3:
            alpha = progress / 0.3
        else:
            alpha = 1.0 - (progress - 0.3) / 0.7
        alpha = max(0, min(alpha, 1))
        # Scale the alpha for intensity (not full white, more like 70% max)
        alpha *= 0.7
        frame = np.full((height, width, 3), 0, dtype=np.uint8)
        flash = np.array(flash_color, dtype=np.float32) * alpha
        frame[:] = np.clip(flash, 0, 255).astype(np.uint8)
        return frame

    return VideoClip(frame_function=make_frame, duration=duration)


def apply_glitch_effect(clip, glitch_time: float = 0.0, duration: float = 0.2):
    """
    Apply an RGB split / digital glitch effect at a specific time.

    Creates a brief visual disruption — RGB channels offset + horizontal
    scanlines. Used for: tech content, shocking reveals, data visualization.

    Args:
        clip: Input video clip
        glitch_time: When the glitch should occur
        duration: How long the glitch lasts (0.15-0.3s typical)
    """
    w, h = clip.size

    def glitch_filter(get_frame, t):
        frame = get_frame(t)
        dist = abs(t - glitch_time)
        if dist > duration / 2:
            return frame

        # Intensity decays from center
        decay = 1 - (dist / (duration / 2))

        result = frame.copy()
        offset = int(10 * decay)

        if offset < 2:
            return frame

        # RGB channel split — offset red left, blue right
        if offset > 0:
            # Red channel shift left
            result[:, :-offset, 0] = frame[:, offset:, 0]
            # Blue channel shift right
            result[:, offset:, 2] = frame[:, :-offset, 2]

        # Add scanlines (every 3rd row darkened)
        if decay > 0.3:
            scanline_rows = np.arange(0, h, 3)
            result[scanline_rows] = (result[scanline_rows].astype(np.float32) * 0.6).astype(np.uint8)

        # Random horizontal block displacement (signature glitch look)
        if decay > 0.5:
            num_blocks = random.randint(2, 5)
            for _ in range(num_blocks):
                by = random.randint(0, h - 20)
                bh = random.randint(5, 15)
                shift = random.randint(-20, 20)
                block = result[by:by+bh].copy()
                if shift > 0:
                    result[by:by+bh, shift:] = block[:, :-shift] if shift < w else block
                elif shift < 0:
                    result[by:by+bh, :shift] = block[:, -shift:] if -shift < w else block

        return result

    return clip.transform(glitch_filter)


def apply_speed_ramp(clip, ramp_type: str = "slow_reveal"):
    """
    Apply speed ramping to a clip for dramatic effect.

    Types:
    - slow_reveal: Start normal, slow to 0.5x at 70%, speed up at end
    - fast_intro: Start at 1.5x, ease to normal by 30%
    - punch: Speed up→slow→speed up (highlight middle moment)

    Note: Changes clip duration. Call early before compositing.
    """
    dur = clip.duration

    if ramp_type == "slow_reveal":
        def time_warp(t):
            p = t / dur if dur > 0 else 0
            if p < 0.6:
                return t * 1.0
            elif p < 0.8:
                # Slow down to 0.5x for the reveal
                return 0.6 * dur + (t - 0.6 * dur) * 0.5
            else:
                return 0.6 * dur + 0.1 * dur + (t - 0.8 * dur) * 1.3
    elif ramp_type == "fast_intro":
        def time_warp(t):
            p = t / dur if dur > 0 else 0
            if p < 0.25:
                return t * 1.4
            else:
                return 0.25 * dur * 1.4 + (t - 0.25 * dur) * 0.9
    else:  # punch
        def time_warp(t):
            p = t / dur if dur > 0 else 0
            if p < 0.3:
                return t * 1.3
            elif p < 0.7:
                return 0.3 * dur * 1.3 + (t - 0.3 * dur) * 0.6
            else:
                return 0.3 * dur * 1.3 + 0.4 * dur * 0.6 + (t - 0.7 * dur) * 1.3

    try:
        return clip.time_transform(time_warp)
    except Exception:
        return clip


def create_light_leak_overlay(
    width: int,
    height: int,
    duration: float,
    color: tuple = (255, 180, 80),
    position: str = "random",
) -> VideoClip:
    """
    Create an animated light leak overlay.

    Simulates lens flare / light bleeding — adds warmth and
    production value. Common in cinematic content.
    """
    if position == "random":
        position = random.choice(["top_right", "top_left", "bottom_right"])

    # Set leak origin
    if position == "top_right":
        ox, oy = int(width * 0.8), int(height * 0.1)
    elif position == "top_left":
        ox, oy = int(width * 0.2), int(height * 0.1)
    else:
        ox, oy = int(width * 0.85), int(height * 0.85)

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        # Pulse the light leak
        alpha = 0.12 * math.sin(progress * math.pi) ** 0.5

        frame = np.zeros((height, width, 3), dtype=np.float32)

        Y, X = np.ogrid[:height, :width]
        dist = np.sqrt((X - ox) ** 2 + (Y - oy) ** 2)
        max_dist = math.sqrt(width ** 2 + height ** 2) * 0.5
        falloff = np.clip(1.0 - dist / max_dist, 0, 1) ** 2

        for c in range(3):
            frame[:, :, c] = color[c] * falloff * alpha

        return np.clip(frame, 0, 255).astype(np.uint8)

    return VideoClip(frame_function=make_frame, duration=duration)


def create_dynamic_zoom_clip(
    clip,
    zoom_start: float = 1.0,
    zoom_end: float = 1.15,
    focus_point: tuple = (0.5, 0.4),
):
    """
    Apply a slow, deliberate zoom to a video clip (not just images).

    Unlike Ken Burns, this works on video footage too.
    Focus point (0.5, 0.4) = slightly above center (face-level).

    Args:
        clip: Video clip to zoom
        zoom_start: Starting zoom level
        zoom_end: Ending zoom level
        focus_point: (x_ratio, y_ratio) where 0.5, 0.5 = center
    """
    w, h = clip.size
    dur = clip.duration
    fx, fy = focus_point

    def zoom_filter(get_frame, t):
        frame = get_frame(t)
        progress = t / dur if dur > 0 else 0
        # Ease-in-out for smooth zoom
        eased = 0.5 - math.cos(progress * math.pi) / 2
        zoom = zoom_start + (zoom_end - zoom_start) * eased

        if zoom <= 1.001:
            return frame

        from PIL import Image as PILImage
        pil = PILImage.fromarray(frame)
        cw, ch = int(w / zoom), int(h / zoom)
        # Center on focus point
        cx = int(w * fx)
        cy = int(h * fy)
        x1 = max(0, min(cx - cw // 2, w - cw))
        y1 = max(0, min(cy - ch // 2, h - ch))
        cropped = pil.crop((x1, y1, x1 + cw, y1 + ch))
        resized = cropped.resize((w, h), PILImage.LANCZOS)
        return np.array(resized)

    return clip.transform(zoom_filter)


# ── Scene Transitions (Expanded) ─────────────────────────────

TRANSITION_STYLES = [
    "crossfade",
    "fade_black",
    "slide_left",
    "flash",
    "crossfade",
    "slide_right",
    "zoom_in",
    "fade_black",
    "slide_top",
    "flash",
    "crossfade",
    "glitch_cut",
]


def apply_entrance_transition(clip, style: str, duration: float = TRANSITION_DURATION):
    """Apply an entrance transition to a clip."""
    try:
        if style == "crossfade":
            return clip.with_effects([vfx.CrossFadeIn(duration)])
        elif style == "fade_black":
            return clip.with_effects([vfx.FadeIn(duration)])
        elif style.startswith("slide_"):
            side = style.replace("slide_", "")
            return clip.with_effects([vfx.SlideIn(duration, side)])
        elif style == "zoom_in":
            # Zoom entrance: start zoomed out, scale up to normal
            return clip.with_effects([vfx.CrossFadeIn(duration * 0.7)])
        elif style == "flash":
            # Flash entrance: start bright, fade to normal
            return clip.with_effects([vfx.CrossFadeIn(duration * 0.5)])
        elif style == "glitch_cut":
            # Hard cut with brief crossfade
            return clip.with_effects([vfx.CrossFadeIn(duration * 0.3)])
    except Exception:
        pass
    try:
        return clip.with_effects([vfx.CrossFadeIn(duration)])
    except Exception:
        return clip


def apply_exit_transition(clip, style: str, duration: float = TRANSITION_DURATION):
    """Apply an exit transition to a clip."""
    exit_map = {
        "slide_left": "slide_right",
        "slide_right": "slide_left",
        "slide_top": "slide_bottom",
        "slide_bottom": "slide_top",
    }
    exit_style = exit_map.get(style, style)
    try:
        if exit_style == "crossfade":
            return clip.with_effects([vfx.CrossFadeOut(duration)])
        elif exit_style == "fade_black":
            return clip.with_effects([vfx.FadeOut(duration)])
        elif exit_style.startswith("slide_"):
            side = exit_style.replace("slide_", "")
            return clip.with_effects([vfx.SlideOut(duration, side)])
        elif exit_style in ("zoom_in", "flash", "glitch_cut"):
            return clip.with_effects([vfx.CrossFadeOut(duration * 0.5)])
    except Exception:
        pass
    try:
        return clip.with_effects([vfx.CrossFadeOut(duration)])
    except Exception:
        return clip


def apply_transitions(
    scene_clips: list,
    transition_duration: float = TRANSITION_DURATION,
) -> list:
    """
    Apply entrance/exit transitions to a list of scene clips.
    Rotates through transition styles for variety.
    """
    if len(scene_clips) < 2:
        return scene_clips

    result = []
    for i, clip in enumerate(scene_clips):
        style = TRANSITION_STYLES[i % len(TRANSITION_STYLES)]

        if i > 0:
            clip = apply_entrance_transition(clip, style, transition_duration)
        if i < len(scene_clips) - 1:
            clip = apply_exit_transition(clip, style, transition_duration)

        result.append(clip)

    return result


def create_transition_effects(
    scene_start_times: list,
    width: int,
    height: int,
    niche: str = "ai_trading",
) -> list:
    """
    Create overlay transition effect clips (flash, glitch) between scenes.

    These are composited ON TOP of the scene transitions for extra punch.
    Only placed at select transitions (not every one — that would be annoying).
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    overlays = []

    for i, start in enumerate(scene_start_times):
        if i == 0:
            continue  # Skip first scene

        # Only place overlay effects on every 3rd transition
        if i % 3 != 0:
            continue

        effect_type = random.choice(["flash", "accent_flash"])

        if effect_type == "flash":
            flash = create_flash_transition(0.15, width, height)
            flash = flash.with_start(max(0, start - 0.08))
            flash = flash.with_opacity(0.5)
            overlays.append(flash)
        elif effect_type == "accent_flash":
            flash = create_flash_transition(0.12, width, height, flash_color=accent)
            flash = flash.with_start(max(0, start - 0.06))
            flash = flash.with_opacity(0.35)
            overlays.append(flash)

    return overlays


# ── Cinematic Scene Enhancement ──────────────────────────────

def enhance_scene_cinematic(
    clip,
    scene_index: int,
    total_scenes: int,
    niche: str = "ai_trading",
    narration: str = "",
    is_reveal: bool = False,
    is_dramatic: bool = False,
):
    """
    Apply cinematic enhancements to a single scene clip.

    Automatically selects appropriate effects based on scene position
    and content analysis. Not every scene gets every effect — that
    would be overwhelming. Instead, effects are strategically placed.

    Args:
        clip: Scene video clip
        scene_index: Index in the video (0 = first scene)
        total_scenes: Total number of scenes
        niche: Content niche for color selection
        narration: Scene narration text for content analysis
        is_reveal: Whether this scene reveals something important
        is_dramatic: Whether this scene has dramatic content
    """
    # 1. Always apply subtle vignette (cinematic baseline)
    clip = apply_vignette(clip, strength=0.35)

    # 2. Apply slow zoom to video clips (creates movement even on static footage)
    if clip.duration > 2.5:
        zoom_end = random.uniform(1.05, 1.12)
        focus = (0.5, random.uniform(0.35, 0.5))
        clip = create_dynamic_zoom_clip(clip, zoom_start=1.0, zoom_end=zoom_end, focus_point=focus)

    # 3. Dramatic scenes get extra effects
    drama_words = {"shocking", "incredible", "insane", "crash", "breaking",
                   "warning", "secret", "revealed", "never", "destroyed",
                   "exploded", "collapse", "panic", "emergency", "danger"}
    narration_lower = narration.lower()
    has_drama = is_dramatic or any(w in narration_lower for w in drama_words)

    money_words = {"profit", "million", "billion", "$", "percent", "%", "return",
                   "gain", "revenue", "income", "salary", "earned"}
    has_money = any(w in narration_lower for w in money_words)

    tech_words = {"algorithm", "ai", "neural", "code", "data", "compute",
                  "processing", "digital", "bot", "automated", "machine"}
    has_tech = any(w in narration_lower for w in tech_words)

    # 4. Zoom pulse on dramatic/money reveals (scene midpoint)
    if (has_drama or has_money or is_reveal) and clip.duration > 2:
        pulse_time = clip.duration * random.uniform(0.4, 0.6)
        clip = apply_zoom_pulse(clip, intensity=1.10, pulse_time=pulse_time)

    # 5. Screen shake on dramatic moments (rarely — max 2 per video)
    if has_drama and scene_index > 1 and random.random() < 0.4:
        shake_time = clip.duration * 0.5
        clip = apply_screen_shake(clip, intensity=6, shake_time=shake_time)

    # 6. Glitch on tech scenes (tech niches only, ~30% chance)
    if has_tech and niche in ("ai_trading", "ai_money", "tech_news") and random.random() < 0.3:
        glitch_time = clip.duration * random.uniform(0.3, 0.7)
        clip = apply_glitch_effect(clip, glitch_time=glitch_time, duration=0.15)

    # 7. Film grain on certain niches (subtle, adds texture)
    if niche in ("motivation", "blissful_moments") and random.random() < 0.5:
        clip = apply_film_grain(clip, intensity=8)

    return clip


# ── Dynamic Cut Pacing ───────────────────────────────────────

def calculate_scene_durations(
    scenes: list,
    total_duration: float,
    niche: str = "ai_trading",
) -> list[float]:
    """
    Calculate dynamic scene durations based on content energy.

    Instead of uniform durations, this creates:
    - Faster cuts for high-energy scenes (action, reveals, money)
    - Slower cuts for emotional/atmospheric scenes
    - Quick first scene (hook) and last scene (CTA)

    Returns list of durations that sum to total_duration.
    """
    num_scenes = len(scenes)
    if num_scenes == 0:
        return []

    # Score each scene's energy level
    energy_scores = []
    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "")
        score = 1.0  # Base energy

        # First scene (hook) = shorter for punch
        if i == 0:
            score *= 0.8

        # Last scene (CTA) = shorter
        if i == num_scenes - 1:
            score *= 0.85

        # High-energy keywords = faster cuts
        high_energy = {"breaking", "shocking", "crash", "explode", "insane",
                       "incredible", "massive", "surge", "skyrocket", "plummet"}
        if any(w in narration.lower() for w in high_energy):
            score *= 0.75  # Shorter duration = faster cuts

        # Calm/atmospheric = slower cuts
        calm_words = {"peaceful", "gentle", "slowly", "beautiful", "calm",
                      "reflect", "breathe", "consider", "think", "imagine"}
        if any(w in narration.lower() for w in calm_words):
            score *= 1.3  # Longer duration = slower cuts

        # Data/numbers = give time to read
        if any(c in narration for c in "$%0123456789"):
            score *= 1.1

        energy_scores.append(score)

    # Normalize to match total duration
    total_weight = sum(energy_scores)
    durations = [(s / total_weight) * total_duration for s in energy_scores]

    # Enforce min/max bounds
    min_dur = 2.0
    max_dur = total_duration * 0.3
    durations = [max(min_dur, min(max_dur, d)) for d in durations]

    # Re-normalize after clamping
    scale = total_duration / sum(durations) if sum(durations) > 0 else 1
    durations = [d * scale for d in durations]

    return durations


# ── Lower Third Bars ──────────────────────────────────────────

def create_lower_third(
    text: str,
    duration: float,
    start_time: float,
    target_w: int,
    target_h: int,
    niche: str = "ai_trading",
) -> list:
    """
    Create a professional lower-third bar overlay.

    Returns a list of clips (background bar + accent stripe + text)
    to add to the composite.
    """
    accent_color = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    bar_height = 70
    y_pos = int(target_h * 0.12)

    clips = []

    try:
        bg = ColorClip(
            size=(target_w, bar_height),
            color=(10, 10, 30),
        )
        bg = bg.with_duration(duration)
        bg = bg.with_start(start_time)
        bg = bg.with_position((0, y_pos))
        bg = bg.with_opacity(0.75)
        bg = bg.with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)])
        clips.append(bg)

        # Accent stripe on left
        stripe = ColorClip(
            size=(5, bar_height),
            color=accent_color,
        )
        stripe = stripe.with_duration(duration)
        stripe = stripe.with_start(start_time)
        stripe = stripe.with_position((0, y_pos))
        clips.append(stripe)

        # Text
        txt = TextClip(
            text=text,
            font_size=28,
            color="white",
            font=CAPTION_FONT,
            method="caption",
            size=(target_w - 36, None),
            duration=duration,
        )
        txt = txt.with_start(start_time)
        txt = txt.with_position((18, y_pos + 20))
        clips.append(txt)
    except Exception as e:
        print(f"[Effects] Lower third failed: {e}")

    return clips


# ── Animated Progress Bar ─────────────────────────────────────

def create_progress_bar(
    total_duration: float,
    width: int,
    height: int,
    niche: str = "ai_trading",
    bar_height: int = 4,
) -> VideoClip:
    """
    Create a thin animated progress bar at the top of the video.

    Shows viewers how much of the video remains — reduces drop-off
    by giving a sense of completion. Used by top creators.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))

    def make_frame(t):
        progress = t / total_duration if total_duration > 0 else 0
        frame = np.zeros((bar_height, width, 3), dtype=np.uint8)
        # Background track
        frame[:] = [30, 30, 30]
        # Progress fill
        fill_width = int(width * progress)
        if fill_width > 0:
            frame[:, :fill_width] = accent
        return frame

    bar = VideoClip(frame_function=make_frame, duration=total_duration)
    bar = bar.with_position((0, 0))
    return bar


# ── Animated Subscribe/CTA Button ────────────────────────────

def create_animated_cta(
    duration: float,
    width: int,
    height: int,
    niche: str = "ai_trading",
    cta_text: str = "FOLLOW FOR MORE",
) -> list:
    """
    Create a large, eye-catching CTA button overlay.

    Uses PIL to render the entire button as a single pre-rendered image.
    Designed to be HIGHLY VISIBLE — large text, bold colors, pulsing glow.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    clips = []
    is_portrait = height > width

    # Strip emojis from CTA text (they render as boxes in video)
    import re as _re
    clean_text = _re.sub(
        r'[\U00010000-\U0010ffff\u2600-\u27BF\u2B50\u2764\u200d\uFE0F]',
        '', cta_text
    ).strip()
    if not clean_text:
        clean_text = "FOLLOW FOR MORE"

    try:
        # ── Button dimensions — LARGE and prominent ──────────
        btn_w = int(width * 0.80) if is_portrait else int(width * 0.40)
        btn_h = int(height * 0.065) if is_portrait else int(height * 0.085)
        btn_h = max(btn_h, 90)
        # Extra canvas for glow effect
        glow_pad = 16
        canvas_w = btn_w + glow_pad * 2
        canvas_h = btn_h + glow_pad * 2
        x_pos = (width - canvas_w) // 2
        y_pos = int(height * 0.82) if is_portrait else int(height * 0.82)

        # ── Font setup — BIG and bold ────────────────────────
        font_size = int(btn_h * 0.48)
        font_size = max(font_size, 36)
        try:
            font = ImageFont.truetype(CAPTION_FONT, font_size)
        except Exception:
            font = ImageFont.load_default()

        corner_radius = btn_h // 2  # Pill shape

        def _render_cta_frame(t):
            """Render a single CTA button frame with pulsing glow."""
            # Pulsing glow: subtle scale of glow intensity
            glow_alpha = int(60 + 40 * math.sin(t * 4 * math.pi))

            img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            bx = glow_pad
            by = glow_pad

            # Outer glow (pulsing) — gives the button a "lit" look
            for g in range(3, 0, -1):
                ga = max(10, glow_alpha // (g + 1))
                draw.rounded_rectangle(
                    [(bx - g * 3, by - g * 3),
                     (bx + btn_w + g * 3 - 1, by + btn_h + g * 3 - 1)],
                    radius=corner_radius + g * 3,
                    fill=(*accent, ga),
                )

            # Drop shadow
            draw.rounded_rectangle(
                [(bx + 3, by + 4),
                 (bx + btn_w + 2, by + btn_h + 3)],
                radius=corner_radius,
                fill=(0, 0, 0, 130),
            )

            # Button background — solid accent, high opacity
            draw.rounded_rectangle(
                [(bx, by), (bx + btn_w - 1, by + btn_h - 1)],
                radius=corner_radius,
                fill=(*accent, 245),
            )

            # White inner highlight (top half gradient feel)
            draw.rounded_rectangle(
                [(bx + 2, by + 2), (bx + btn_w - 3, by + btn_h // 2)],
                radius=corner_radius - 2,
                fill=(255, 255, 255, 30),
            )

            # Thin white border
            draw.rounded_rectangle(
                [(bx + 2, by + 2), (bx + btn_w - 3, by + btn_h - 3)],
                radius=corner_radius - 2,
                outline=(255, 255, 255, 100),
                width=2,
            )

            # ── Text — centered, bold, with shadow ───────────
            bbox = draw.textbbox((0, 0), clean_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = bx + (btn_w - tw) // 2
            ty = by + (btn_h - th) // 2 - 2

            # Text shadow
            draw.text((tx + 2, ty + 3), clean_text, fill=(0, 0, 0, 160), font=font)
            # Main text — white bold
            draw.text((tx, ty), clean_text, fill=(255, 255, 255, 255), font=font)

            return np.array(img)

        btn_clip = VideoClip(
            frame_function=_render_cta_frame,
            duration=duration,
            is_mask=False,
        )
        btn_clip = btn_clip.with_position((x_pos, y_pos))
        btn_clip = btn_clip.with_effects([vfx.CrossFadeIn(0.3)])
        clips.append(btn_clip)

    except Exception as e:
        print(f"[Effects] CTA overlay failed: {e}")

    return clips


# ── Engagement Overlays (boost views & follows) ─────────────────

def create_follow_button_start(
    duration: float,
    width: int,
    height: int,
    niche: str = "ai_trading",
) -> list:
    """
    Create a "FOLLOW" button overlay for the first few seconds.
    Positioned near the avatar in the top-right corner.
    Uses a pointing hand + text to draw attention.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    clips = []
    is_portrait = height > width

    try:
        # Small, clean button near top-right (below avatar)
        btn_w = int(width * 0.30) if is_portrait else int(width * 0.15)
        btn_h = int(height * 0.032) if is_portrait else int(height * 0.045)
        btn_h = max(btn_h, 48)
        canvas_w = btn_w + 12
        canvas_h = btn_h + 12

        # Position below avatar area (top-right)
        margin = int(width * 0.03)
        pip_size = int(width * 0.22) if is_portrait else int(width * 0.16)
        x_pos = width - pip_size - margin + (pip_size - canvas_w) // 2
        y_pos = int(height * 0.08) + pip_size + 8 if is_portrait else int(height * 0.06) + pip_size + 8

        font_size = int(btn_h * 0.50)
        font_size = max(font_size, 22)
        try:
            font = ImageFont.truetype(CAPTION_FONT, font_size)
        except Exception:
            font = ImageFont.load_default()

        corner_radius = btn_h // 2

        def _render_follow_frame(t):
            # Gentle pulse
            pulse_a = int(220 + 25 * math.sin(t * 5 * math.pi))
            img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            bx, by = 6, 6

            # Shadow
            draw.rounded_rectangle(
                [(bx + 2, by + 3), (bx + btn_w + 1, by + btn_h + 2)],
                radius=corner_radius, fill=(0, 0, 0, 100),
            )
            # Button bg — accent color
            draw.rounded_rectangle(
                [(bx, by), (bx + btn_w - 1, by + btn_h - 1)],
                radius=corner_radius, fill=(*accent, pulse_a),
            )
            # White border
            draw.rounded_rectangle(
                [(bx + 1, by + 1), (bx + btn_w - 2, by + btn_h - 2)],
                radius=corner_radius - 1, outline=(255, 255, 255, 120), width=2,
            )

            text = "FOLLOW"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = bx + (btn_w - tw) // 2
            ty = by + (btn_h - th) // 2 - 1

            draw.text((tx + 1, ty + 2), text, fill=(0, 0, 0, 130), font=font)
            draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)

            return np.array(img)

        clip = VideoClip(frame_function=_render_follow_frame, duration=duration, is_mask=False)
        clip = clip.with_position((x_pos, y_pos))
        clip = clip.with_effects([vfx.CrossFadeIn(0.5), vfx.CrossFadeOut(0.5)])
        clips.append(clip)

    except Exception as e:
        print(f"[Effects] Follow button overlay failed: {e}")

    return clips


def create_engagement_overlays(
    total_duration: float,
    width: int,
    height: int,
    niche: str = "ai_trading",
) -> list:
    """
    Create mid-video engagement overlays that boost interaction:
    - "LIKE" reminder with heart icon
    - "COMMENT below!" prompt
    - "SHARE with a friend!" prompt
    - "FOLLOW for more!" reminder

    These appear at strategic points throughout the video.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    clips = []
    is_portrait = height > width

    if total_duration < 15:
        return clips

    try:
        font_size = int(width * 0.045) if is_portrait else int(width * 0.028)
        font_size = max(font_size, 28)
        try:
            font = ImageFont.truetype(CAPTION_FONT, font_size)
        except Exception:
            font = ImageFont.load_default()

        small_font_size = int(font_size * 0.65)
        try:
            small_font = ImageFont.truetype(CAPTION_FONT, small_font_size)
        except Exception:
            small_font = ImageFont.load_default()

        # Engagement prompts — appear at strategic intervals
        prompts = []

        # "LIKE" at ~20% of video
        like_t = total_duration * 0.20
        if like_t > 4 and like_t < total_duration - 5:
            prompts.append(("DOUBLE TAP IF YOU AGREE", like_t))

        # "COMMENT" at ~45%
        comment_t = total_duration * 0.45
        if comment_t > 8 and comment_t < total_duration - 5:
            prompts.append(("COMMENT YOUR THOUGHTS", comment_t))

        # "SHARE" at ~70%
        share_t = total_duration * 0.70
        if share_t > 12 and share_t < total_duration - 5:
            prompts.append(("SEND THIS TO A FRIEND", share_t))

        # "FOLLOW" at ~88%
        follow_t = total_duration * 0.88
        if follow_t > 15 and follow_t < total_duration - 3:
            prompts.append(("FOLLOW FOR MORE", follow_t))

        for prompt_text, start_time in prompts:
            try:
                # Render as a semi-transparent pill
                pill_w = int(width * 0.55) if is_portrait else int(width * 0.30)
                pill_h = int(height * 0.030) if is_portrait else int(height * 0.042)
                pill_h = max(pill_h, 42)
                pad = 10
                canvas_w = pill_w + pad * 2
                canvas_h = pill_h + pad * 2

                img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                # Dark semi-transparent pill background
                radius = pill_h // 2
                draw.rounded_rectangle(
                    [(pad, pad), (pad + pill_w - 1, pad + pill_h - 1)],
                    radius=radius,
                    fill=(0, 0, 0, 160),
                )
                # Accent left edge (colored stripe)
                draw.rounded_rectangle(
                    [(pad, pad), (pad + 6, pad + pill_h - 1)],
                    radius=3,
                    fill=(*accent, 220),
                )

                # Text
                bbox = draw.textbbox((0, 0), prompt_text, font=small_font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = pad + (pill_w - tw) // 2 + 4
                ty = pad + (pill_h - th) // 2 - 1
                draw.text((tx, ty), prompt_text, fill=(*accent, 255), font=small_font)

                img_array = np.array(img)
                rgb = img_array[:, :, :3]
                alpha = img_array[:, :, 3].astype(float) / 255.0

                x_pos = int(width * 0.04) if is_portrait else int(width * 0.02)
                y_pos = int(height * 0.52) if is_portrait else int(height * 0.55)

                clip = ImageClip(rgb, duration=2.2)
                mask = ImageClip(alpha, is_mask=True, duration=2.2)
                clip = clip.with_mask(mask)
                clip = clip.with_start(start_time)
                clip = clip.with_position((x_pos, y_pos))
                clip = clip.with_effects([vfx.CrossFadeIn(0.2), vfx.CrossFadeOut(0.4)])
                clips.append(clip)

            except Exception:
                continue

    except Exception as e:
        print(f"[Effects] Engagement overlays failed: {e}")

    return clips


def create_video_progress_bar(
    total_duration: float,
    width: int,
    height: int,
    niche: str = "ai_trading",
) -> list:
    """
    Create a thin animated progress bar at the top of the video.
    Grows from left to right over the video duration.
    This is a proven retention trick — viewers want to see it fill up.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    clips = []

    try:
        bar_h = 4
        bar_w = width

        def _render_progress(t):
            progress = t / total_duration if total_duration > 0 else 0
            fill_w = max(1, int(bar_w * progress))

            img = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Background track
            draw.rectangle([(0, 0), (bar_w - 1, bar_h - 1)], fill=(255, 255, 255, 40))
            # Filled progress
            draw.rectangle([(0, 0), (fill_w - 1, bar_h - 1)], fill=(*accent, 200))
            # Bright dot at the leading edge
            if fill_w > 3:
                draw.ellipse(
                    [(fill_w - 4, 0), (fill_w + 2, bar_h - 1)],
                    fill=(255, 255, 255, 220),
                )

            return np.array(img)

        clip = VideoClip(frame_function=_render_progress, duration=total_duration, is_mask=False)
        clip = clip.with_position((0, 0))
        clip = clip.with_start(0)
        clips.append(clip)

    except Exception as e:
        print(f"[Effects] Progress bar failed: {e}")

    return clips


def create_like_animation(
    width: int,
    height: int,
    start_time: float,
    niche: str = "ai_trading",
) -> list:
    """
    Create a floating heart/like animation that appears briefly.
    Heart rises from bottom-left and fades out — like TikTok like animation.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    clips = []

    try:
        is_portrait = height > width
        heart_size = int(width * 0.12) if is_portrait else int(width * 0.06)
        duration = 1.8

        img = Image.new("RGBA", (heart_size, heart_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw a heart shape using two circles and a triangle
        r = heart_size // 4
        cx1, cx2 = heart_size // 4 + 2, 3 * heart_size // 4 - 2
        cy = heart_size // 3
        # Left circle
        draw.ellipse([(cx1 - r, cy - r), (cx1 + r, cy + r)], fill=(255, 50, 80, 240))
        # Right circle
        draw.ellipse([(cx2 - r, cy - r), (cx2 + r, cy + r)], fill=(255, 50, 80, 240))
        # Triangle bottom
        draw.polygon([
            (2, cy + 2),
            (heart_size - 3, cy + 2),
            (heart_size // 2, heart_size - 4),
        ], fill=(255, 50, 80, 240))

        img_array = np.array(img)
        rgb = img_array[:, :, :3]
        alpha = img_array[:, :, 3].astype(float) / 255.0

        x_pos = int(width * 0.08)
        y_pos = int(height * 0.72) if is_portrait else int(height * 0.65)

        clip = ImageClip(rgb, duration=duration)
        mask = ImageClip(alpha, is_mask=True, duration=duration)
        clip = clip.with_mask(mask)
        clip = clip.with_start(start_time)
        clip = clip.with_position(lambda t: (x_pos, int(y_pos - t * 30)))  # Float up
        clip = clip.with_effects([vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.6)])
        clips.append(clip)

    except Exception as e:
        print(f"[Effects] Like animation failed: {e}")

    return clips


# ── Niche Emoji Sets for Animated Overlays ────────────────

NICHE_EMOJI_SETS = {
    "ai_trading": ["fire", "rocket", "chart", "money", "brain", "lightning"],
    "ai_money": ["money", "rocket", "fire", "diamond", "brain", "star"],
    "tech_news": ["lightning", "brain", "rocket", "fire", "star", "sparkle"],
    "motivation": ["fire", "star", "muscle", "crown", "lightning", "heart"],
    "health_wellness": ["leaf", "heart", "sparkle", "star", "sun", "wave"],
    "blissful_moments": ["heart", "star", "sparkle", "sun", "flower", "butterfly"],
}


def _render_emoji_shape(draw, shape, x, y, size, color):
    """Render a simple emoji-style shape using PIL primitives."""
    s = size
    if shape == "fire":
        # Flame shape — orange/red
        pts = [(x + s // 2, y), (x + s, y + s), (x + s // 2, y + int(s * 0.75)), (x, y + s)]
        draw.polygon(pts, fill=(255, 120, 0, 240))
        pts2 = [(x + s // 2, y + s // 4), (x + int(s * 0.75), y + s), (x + s // 2, y + int(s * 0.85)), (x + s // 4, y + s)]
        draw.polygon(pts2, fill=(255, 200, 0, 220))
    elif shape == "rocket":
        draw.ellipse([(x + s // 4, y), (x + 3 * s // 4, y + int(s * 0.7))], fill=(200, 200, 220, 240))
        draw.polygon([(x + s // 2, y - s // 4), (x + s // 4, y + s // 4), (x + 3 * s // 4, y + s // 4)], fill=(255, 80, 80, 240))
        draw.ellipse([(x + s // 3, y + int(s * 0.6)), (x + 2 * s // 3, y + s)], fill=(255, 160, 0, 200))
    elif shape == "money":
        draw.ellipse([(x, y), (x + s, y + s)], fill=(0, 180, 0, 240))
        try:
            font = ImageFont.truetype(CAPTION_FONT, s // 2)
        except Exception:
            font = ImageFont.load_default()
        draw.text((x + s // 4, y + s // 5), "$", fill=(255, 255, 255, 255), font=font)
    elif shape == "star":
        import math as _m
        pts = []
        for i in range(10):
            angle = _m.radians(i * 36 - 90)
            r = s // 2 if i % 2 == 0 else s // 4
            pts.append((x + s // 2 + int(r * _m.cos(angle)), y + s // 2 + int(r * _m.sin(angle))))
        draw.polygon(pts, fill=(255, 215, 0, 240))
    elif shape == "heart":
        r = s // 4
        draw.ellipse([(x + s // 8, y), (x + s // 2, y + s // 2)], fill=(255, 50, 80, 240))
        draw.ellipse([(x + s // 2, y), (x + 7 * s // 8, y + s // 2)], fill=(255, 50, 80, 240))
        draw.polygon([(x + s // 8, y + s // 4), (x + 7 * s // 8, y + s // 4), (x + s // 2, y + s)], fill=(255, 50, 80, 240))
    elif shape == "lightning":
        pts = [(x + s // 2, y), (x + s // 4, y + s // 2), (x + s // 2, y + s // 2),
               (x + s // 3, y + s), (x + 3 * s // 4, y + s // 3), (x + s // 2, y + s // 3)]
        draw.polygon(pts, fill=(255, 220, 0, 240))
    elif shape == "brain":
        draw.ellipse([(x, y + s // 4), (x + s // 2, y + 3 * s // 4)], fill=(255, 150, 200, 240))
        draw.ellipse([(x + s // 2, y + s // 4), (x + s, y + 3 * s // 4)], fill=(255, 150, 200, 240))
        draw.ellipse([(x + s // 6, y), (x + 5 * s // 6, y + s // 2)], fill=(255, 170, 210, 240))
    elif shape == "diamond":
        pts = [(x + s // 2, y), (x + s, y + s // 2), (x + s // 2, y + s), (x, y + s // 2)]
        draw.polygon(pts, fill=(100, 200, 255, 240))
    elif shape == "crown":
        draw.rectangle([(x, y + s // 2), (x + s, y + s)], fill=(255, 200, 0, 240))
        draw.polygon([(x, y + s // 2), (x, y + s // 4), (x + s // 4, y + s // 2)], fill=(255, 200, 0, 240))
        draw.polygon([(x + s // 2 - s // 8, y + s // 2), (x + s // 2, y), (x + s // 2 + s // 8, y + s // 2)], fill=(255, 200, 0, 240))
        draw.polygon([(x + s, y + s // 2), (x + s, y + s // 4), (x + 3 * s // 4, y + s // 2)], fill=(255, 200, 0, 240))
    elif shape == "muscle":
        draw.ellipse([(x + s // 4, y), (x + 3 * s // 4, y + s // 2)], fill=(240, 180, 120, 240))
        draw.ellipse([(x, y + s // 4), (x + s // 2, y + 3 * s // 4)], fill=(240, 180, 120, 240))
        draw.ellipse([(x + s // 2, y + s // 4), (x + s, y + 3 * s // 4)], fill=(240, 180, 120, 240))
    else:
        # Fallback: sparkle/circle
        draw.ellipse([(x, y), (x + s, y + s)], fill=(255, 255, 200, 200))
        draw.ellipse([(x + s // 4, y + s // 4), (x + 3 * s // 4, y + 3 * s // 4)], fill=(255, 255, 255, 240))


def create_floating_emojis(
    total_duration: float,
    width: int,
    height: int,
    niche: str = "ai_trading",
    scene_start_times: list[float] | None = None,
) -> list:
    """
    Create animated floating emoji overlays at strategic points in the video.
    Emojis float upward from random positions and fade out — like reaction animations.
    Niche-specific emoji sets for relevance.
    """
    accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
    clips = []
    is_portrait = height > width

    emoji_set = NICHE_EMOJI_SETS.get(niche, ["fire", "star", "rocket"])

    if total_duration < 10:
        return clips

    try:
        emoji_size = int(width * 0.08) if is_portrait else int(width * 0.05)
        emoji_size = max(emoji_size, 40)

        # Place emojis at scene transitions and key moments
        emoji_times = []
        if scene_start_times:
            # Every 2-3 scene transitions, add an emoji burst
            for i, t in enumerate(scene_start_times):
                if t < 3 or t > total_duration - 3:
                    continue
                if i % 3 == 1:  # every 3rd scene
                    emoji_times.append(t)
        else:
            # Fallback: spread evenly
            interval = max(8.0, total_duration / 5)
            t = 5.0
            while t < total_duration - 4:
                emoji_times.append(t)
                t += interval

        # Limit to prevent too many clips
        emoji_times = emoji_times[:6]

        for start_time in emoji_times:
            try:
                shape = random.choice(emoji_set)
                duration = 2.0

                # Render emoji image
                pad = 4
                img = Image.new("RGBA", (emoji_size + pad * 2, emoji_size + pad * 2), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                _render_emoji_shape(draw, shape, pad, pad, emoji_size, accent)

                img_array = np.array(img)
                rgb = img_array[:, :, :3]
                alpha = img_array[:, :, 3].astype(float) / 255.0

                # Random position on left or right side
                side = random.choice(["left", "right"])
                if side == "left":
                    x_pos = random.randint(int(width * 0.03), int(width * 0.15))
                else:
                    x_pos = random.randint(int(width * 0.80), int(width * 0.92))
                y_start = random.randint(int(height * 0.35), int(height * 0.55))

                clip = ImageClip(rgb, duration=duration)
                mask = ImageClip(alpha, is_mask=True, duration=duration)
                clip = clip.with_mask(mask)
                clip = clip.with_start(start_time)
                # Float upward + slight wiggle
                clip = clip.with_position(
                    lambda t, xs=x_pos, ys=y_start: (
                        int(xs + 8 * math.sin(t * 4)),
                        int(ys - t * 40),
                    )
                )
                clip = clip.with_effects([vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.5)])
                clips.append(clip)

            except Exception:
                continue

    except Exception as e:
        print(f"[Effects] Floating emojis failed: {e}")

    return clips
