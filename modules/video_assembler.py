"""
Video Assembler — Cinema-Grade Video Composition Engine.

Combines footage, voiceover, captions, and effects into viral-quality video.

Uses MoviePy v2 API. Features:
- 16:9 landscape (YouTube long-form), 9:16 vertical (Shorts/TikTok/Reels)
- Ken Burns zoom/pan on still images with eased motion
- 12 transition styles (crossfade, slide, flash, glitch cut, zoom)
- Cinematic per-scene effects (vignette, zoom pulse, screen shake, glitch, film grain)
- Dynamic cut pacing (energy-based scene durations)
- Flash transitions between key scenes
- Light leak overlays for cinematic warmth
- Progress bar (retention tool)
- Karaoke-style captions with power words + animated entrance
- Hook overlay engineering (first 3 seconds)
- Pattern interrupts for retention
- Avatar PiP with circular mask (FULL VIDEO duration)
- Niche-specific color grading
- Background music + SFX mixing
"""
import os
import random
import math
from pathlib import Path

from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    ColorClip,
    CompositeAudioClip,
    concatenate_videoclips,
    vfx,
)

import re
import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont

from config import (
    VIDEO_SETTINGS,
    CAPTION_FONT_SIZE,
    CAPTION_FONT_COLOR,
    CAPTION_STROKE_COLOR,
    CAPTION_STROKE_WIDTH,
    CAPTION_FONT,
    CAPTION_BG_OPACITY,
    MUSIC_DIR,
    ASSETS_DIR,
    ENABLE_KEN_BURNS,
    ENABLE_TRANSITIONS,
    ENABLE_LOWER_THIRDS,
    TRANSITION_DURATION,
)

from modules.visual_effects import (
    apply_ken_burns,
    apply_transitions,
    create_lower_third,
    # Cinematic effects
    enhance_scene_cinematic,
    create_transition_effects,
    create_light_leak_overlay,
    create_progress_bar,
    create_animated_cta,
    calculate_scene_durations,
    NICHE_ACCENT_COLORS,
    # Engagement overlays (boost views)
    create_follow_button_start,
    create_engagement_overlays,
    create_video_progress_bar,
    create_like_animation,
    create_floating_emojis,
)


# ── Niche Color Grading ──────────────────────────────────────

NICHE_COLOR_GRADE = {
    # (r_shift, g_shift, b_shift, brightness) — subtle tint per niche
    "ai_trading": (0, 8, -5, 1.02),        # Slightly green/warm
    "ai_money": (-3, 5, 10, 1.02),         # Cool blue tint
    "tech_news": (5, -3, 12, 1.00),        # Purple/blue tech feel
    "motivation": (10, 5, -8, 1.05),       # Warm amber/golden
    "health_wellness": (-5, 10, -3, 1.03), # Green/natural tint
    "blissful_moments": (8, 4, -5, 1.04),  # Warm golden glow
}


def _apply_color_grade(clip, niche: str):
    """Apply subtle niche-specific color grading to a video/image clip."""
    grade = NICHE_COLOR_GRADE.get(niche)
    if not grade:
        return clip

    r_shift, g_shift, b_shift, brightness = grade

    def color_filter(frame):
        f = frame.astype(np.float32)
        f[:, :, 0] = f[:, :, 0] * brightness + r_shift
        f[:, :, 1] = f[:, :, 1] * brightness + g_shift
        f[:, :, 2] = f[:, :, 2] * brightness + b_shift
        return np.clip(f, 0, 255).astype(np.uint8)

    return clip.image_transform(color_filter)


def _get_music_track() -> str | None:
    """Pick a random background music track from the music directory."""
    if not MUSIC_DIR.exists():
        return None
    tracks = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))
    return str(random.choice(tracks)) if tracks else None


def _create_scene_clip(
    visual: dict,
    target_w: int,
    target_h: int,
    duration: float,
):
    """
    Create a clip for a single scene from visual data.
    Handles: video clips, photos (with Ken Burns), and placeholders.
    """
    local_path = visual.get("local_path")
    visual_type = visual.get("type", "placeholder")

    if visual_type == "video" and local_path and Path(local_path).exists():
        try:
            clip = VideoFileClip(local_path)
            if clip.duration > duration:
                clip = clip.subclipped(0, duration)
            elif clip.duration < duration:
                loops = int(duration / clip.duration) + 1
                clip = clip.with_effects([vfx.Loop(n=loops)])
                clip = clip.subclipped(0, duration)
            src_aspect = clip.w / clip.h
            target_aspect = target_w / target_h
            if src_aspect > target_aspect:
                clip = clip.resized(height=target_h)
            else:
                clip = clip.resized(width=target_w)
            clip = clip.cropped(
                x_center=clip.w / 2, y_center=clip.h / 2,
                width=target_w, height=target_h,
            )
            return clip
        except Exception as e:
            print(f"[Assembler] Video clip failed: {e}")

    if visual_type in ("photo", "ai_image") and local_path and Path(local_path).exists():
        try:
            if ENABLE_KEN_BURNS:
                return apply_ken_burns(local_path, duration, target_w, target_h)
            img = ImageClip(local_path, duration=duration)
            src_aspect = img.w / img.h
            target_aspect = target_w / target_h
            if src_aspect > target_aspect:
                img = img.resized(height=target_h)
            else:
                img = img.resized(width=target_w)
            img = img.cropped(
                x_center=img.w / 2, y_center=img.h / 2,
                width=target_w, height=target_h,
            )
            return img
        except Exception as e:
            print(f"[Assembler] Image clip failed: {e}")

    return ColorClip(
        size=(target_w, target_h),
        color=(10, 10, 30),
        duration=duration,
    )


# ── Power Word / Emoji Detection for Captions ───────────────

POWER_WORD_PATTERNS = [
    r'\$[\d,]+',
    r'\d+%',
    r'\d+x',
    r'\d+k\b',
]

POWER_WORDS = {
    "secret", "secrets", "shocking", "incredible", "insane", "powerful",
    "proven", "guaranteed", "free", "million", "billions", "thousands",
    "hack", "hacks", "trick", "tricks", "mistake", "mistakes",
    "never", "always", "nobody", "everyone", "actually", "revealed",
    "warning", "danger", "urgent", "breaking", "discovered", "truth",
}

EMOJI_KEYWORDS = {
    "money": "💰", "dollar": "💰", "profit": "💰", "income": "💰",
    "cash": "💰", "earn": "💰", "paid": "💰", "revenue": "💰",
    "growth": "🚀", "explode": "🚀", "skyrocket": "🚀", "launch": "🚀",
    "rocket": "🚀", "soar": "🚀", "boom": "🚀",
    "fire": "🔥", "hot": "🔥", "viral": "🔥", "trending": "🔥",
    "insane": "🔥", "incredible": "🔥", "amazing": "🔥",
    "brain": "🧠", "smart": "🧠", "think": "🧠", "mind": "🧠",
    "intelligence": "🧠", "genius": "🧠",
    "warning": "⚠️", "danger": "⚠️", "careful": "⚠️", "risk": "⚠️",
    "secret": "🤫", "hidden": "🤫", "nobody": "🤫",
    "shock": "😱", "shocking": "😱", "terrifying": "😱", "crazy": "😱",
    "health": "💪", "strong": "💪", "fitness": "💪", "exercise": "💪",
    "love": "❤️", "heart": "❤️", "peace": "✨", "beautiful": "✨",
    "grateful": "✨", "blessed": "✨", "bliss": "✨", "calm": "🧘",
    "sleep": "😴", "morning": "🌅", "sunrise": "🌅",
    "food": "🍃", "herb": "🍃", "natural": "🍃", "organic": "🍃",
}

NICHE_CAPTION_COLORS = {
    "ai_trading": (0, 255, 136),
    "ai_money": (0, 200, 255),
    "tech_news": (160, 120, 255),
    "motivation": (255, 200, 0),
    "health_wellness": (100, 220, 100),
    "blissful_moments": (255, 180, 100),
}


def _is_power_word(word: str) -> bool:
    """Check if a word should be highlighted in accent color."""
    clean = word.strip(".,!?:;'\"").lower()
    if clean in POWER_WORDS:
        return True
    for pattern in POWER_WORD_PATTERNS:
        if re.search(pattern, word, re.IGNORECASE):
            return True
    return False


def _get_emoji_for_text(text: str) -> str:
    """Get a relevant emoji for caption text based on keywords."""
    text_lower = text.lower()
    for keyword, emoji in EMOJI_KEYWORDS.items():
        if keyword in text_lower:
            return emoji
    return ""


def _render_caption_image(
    text: str,
    font_path: str,
    font_size: int,
    text_w: int,
    accent_color: tuple,
    stroke_width: int = 4,
) -> np.ndarray:
    """
    Render a caption with colored power words using PIL.
    Returns an RGBA numpy array.
    """
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    words = text.upper().split()

    emoji = _get_emoji_for_text(text)

    dummy_img = PILImage.new("RGBA", (text_w + 40, font_size * 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy_img)
    space_w = draw.textlength(" ", font=font)

    word_widths = []
    for w in words:
        w_width = draw.textlength(w, font=font)
        word_widths.append(w_width)

    lines = []
    current_line = []
    current_width = 0
    for i, w in enumerate(words):
        test_width = current_width + word_widths[i] + (space_w if current_line else 0)
        if test_width > text_w and current_line:
            lines.append(current_line)
            current_line = [(w, word_widths[i], _is_power_word(w))]
            current_width = word_widths[i]
        else:
            current_line.append((w, word_widths[i], _is_power_word(w)))
            current_width = test_width
    if current_line:
        lines.append(current_line)

    line_height = int(font_size * 1.3)
    total_height = line_height * len(lines) + stroke_width * 2 + 20
    padding = stroke_width + 10
    img = PILImage.new("RGBA", (text_w + padding * 2, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = padding
    for line in lines:
        line_w = sum(w for _, w, _ in line) + space_w * (len(line) - 1)
        x = (text_w + padding * 2 - line_w) / 2

        for word, w_width, is_power in line:
            color = accent_color if is_power else (255, 255, 255)

            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx * dx + dy * dy <= stroke_width * stroke_width:
                        draw.text((x + dx, y + dy), word, font=font, fill=(0, 0, 0, 255))

            draw.text((x, y), word, font=font, fill=color + (255,))
            x += w_width + space_w

        y += line_height

    return np.array(img)


def _create_caption_clips(
    captions: list[dict],
    target_w: int,
    target_h: int,
    font_size: int = CAPTION_FONT_SIZE,
    niche: str = "ai_trading",
) -> list:
    """
    Create karaoke-style caption clips with animated entrances.

    Each caption pops in with a scale-up effect and colored power words.
    """
    caption_clips = []
    is_portrait = target_h > target_w
    text_w = int(target_w * 0.85)
    stroke_w = max(CAPTION_STROKE_WIDTH, 4)
    accent_color = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))

    if is_portrait:
        cap_y = int(target_h * 0.62)
    else:
        cap_y = int(target_h * 0.70)

    for idx, cap in enumerate(captions):
        try:
            duration = cap["end"] - cap["start"]
            if duration <= 0.1:
                continue

            # PIL-rendered colored captions with scale-up entrance
            try:
                img_array = _render_caption_image(
                    text=cap["text"],
                    font_path=CAPTION_FONT,
                    font_size=font_size,
                    text_w=text_w,
                    accent_color=accent_color,
                    stroke_width=stroke_w,
                )
                rgb = img_array[:, :, :3]
                alpha = img_array[:, :, 3].astype(float) / 255.0

                clip = ImageClip(rgb, duration=duration)
                mask = ImageClip(alpha, is_mask=True, duration=duration)
                clip = clip.with_mask(mask)
                clip = clip.with_start(cap["start"])
                clip = clip.with_position(("center", cap_y))

                # Animated entrance: quick scale-up pop effect
                # Every 3rd caption gets a slightly bouncier entrance
                if idx % 3 == 0 and duration > 0.5:
                    clip = clip.with_effects([vfx.CrossFadeIn(0.08)])
                else:
                    clip = clip.with_effects([vfx.CrossFadeIn(0.05)])

                caption_clips.append(clip)
                continue
            except Exception:
                pass

            # Fallback: plain white TextClip
            pad = stroke_w + 6
            txt = TextClip(
                text=cap["text"].upper(),
                font_size=font_size,
                color=CAPTION_FONT_COLOR,
                stroke_color=CAPTION_STROKE_COLOR,
                stroke_width=stroke_w,
                font=CAPTION_FONT,
                method="caption",
                size=(text_w, None),
                text_align="center",
                duration=duration,
                margin=(pad, pad),
            )
            txt = txt.with_start(cap["start"])
            txt = txt.with_position(("center", cap_y))
            txt = txt.with_effects([vfx.CrossFadeIn(0.05)])
            caption_clips.append(txt)
        except Exception:
            continue

    return caption_clips


# ── Hook Engineering (First 3 Seconds) ──────────────────

def _create_hook_overlay(
    title: str,
    target_w: int,
    target_h: int,
    duration: float = 3.0,
    niche: str = "ai_trading",
) -> list:
    """
    Create an eye-catching visual hook overlay for the first 3 seconds.

    Uses: bold text slam + accent bar + dark overlay backdrop for readability.
    """
    hook_clips = []
    accent_color = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))
    is_portrait = target_h > target_w

    try:
        # Semi-transparent dark backdrop for first 3 seconds (makes text POP)
        backdrop = ColorClip(
            size=(target_w, target_h),
            color=(0, 0, 0),
            duration=duration,
        )
        backdrop = backdrop.with_start(0)
        backdrop = backdrop.with_opacity(0.3)
        backdrop = backdrop.with_effects([vfx.CrossFadeIn(0.1), vfx.CrossFadeOut(0.5)])
        hook_clips.append(backdrop)

        # Extract the first compelling phrase (max 6 words)
        words = title.split()
        hook_text = " ".join(words[:6]).upper()
        if len(words) > 6:
            hook_text += "..."

        font_size = int(target_w * 0.08) if is_portrait else int(target_w * 0.045)

        img_array = _render_caption_image(
            text=hook_text,
            font_path=CAPTION_FONT,
            font_size=font_size,
            text_w=int(target_w * 0.85),
            accent_color=accent_color,
            stroke_width=6,
        )

        rgb = img_array[:, :, :3]
        alpha = img_array[:, :, 3].astype(float) / 255.0
        hook_img_h = img_array.shape[0]  # actual rendered height (multi-line aware)

        hook_clip = ImageClip(rgb, duration=duration)
        mask = ImageClip(alpha, is_mask=True, duration=duration)
        hook_clip = hook_clip.with_mask(mask)
        hook_y = int(target_h * 0.22) if is_portrait else int(target_h * 0.30)
        hook_clip = hook_clip.with_position(("center", hook_y))
        hook_clip = hook_clip.with_start(0)
        hook_clip = hook_clip.with_effects([
            vfx.CrossFadeIn(0.1),
            vfx.CrossFadeOut(0.4),
        ])
        hook_clips.append(hook_clip)

        # Position bar + micro text BELOW the actual rendered hook image
        bar_top = hook_y + hook_img_h + 8
        # Safety cap: never go below 48% of frame (well above captions at 62%)
        max_bar_y = int(target_h * 0.48)
        bar_top = min(bar_top, max_bar_y)

        # Accent bar underneath hook text (animated width expansion)
        bar_w = int(target_w * 0.45)
        bar_h = 6
        bar = ColorClip(size=(bar_w, bar_h), color=accent_color, duration=duration - 0.3)
        bar = bar.with_start(0.15)
        bar = bar.with_position(("center", bar_top))
        bar = bar.with_effects([vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.3)])
        hook_clips.append(bar)

        # "WATCH TILL THE END" micro-text below the bar (retention trick)
        try:
            micro_size = int(font_size * 0.35)
            micro_img = _render_caption_image(
                text="WATCH TILL THE END",
                font_path=CAPTION_FONT,
                font_size=micro_size,
                text_w=int(target_w * 0.6),
                accent_color=accent_color,
                stroke_width=2,
            )
            micro_rgb = micro_img[:, :, :3]
            micro_alpha = micro_img[:, :, 3].astype(float) / 255.0
            micro_clip = ImageClip(micro_rgb, duration=duration - 0.8)
            micro_mask = ImageClip(micro_alpha, is_mask=True, duration=duration - 0.8)
            micro_clip = micro_clip.with_mask(micro_mask)
            micro_clip = micro_clip.with_start(0.5)
            micro_clip = micro_clip.with_position(("center", bar_top + 15))
            micro_clip = micro_clip.with_effects([vfx.CrossFadeIn(0.2), vfx.CrossFadeOut(0.3)])
            hook_clips.append(micro_clip)
        except Exception:
            pass

    except Exception as e:
        print(f"[Assembler] Hook overlay failed: {e}")

    return hook_clips


def _create_pattern_interrupts(
    scene_start_times: list[float],
    total_duration: float,
    target_w: int,
    target_h: int,
    niche: str = "ai_trading",
) -> list:
    """
    Create pattern interrupt overlays at strategic points.
    Reduces viewer drop-off by re-capturing attention with text pop-ins.
    """
    interrupt_clips = []
    accent_color = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))
    is_portrait = target_h > target_w

    interrupt_texts = [
        "WAIT FOR THIS",
        "HERE'S THE KEY",
        "WATCH THIS",
        "PAY ATTENTION",
        "THIS IS IMPORTANT",
        "DON'T SKIP",
        "THE SECRET IS...",
        "YOU WON'T BELIEVE THIS",
        "THIS CHANGES EVERYTHING",
    ]

    interrupt_interval = 16.0
    next_interrupt = interrupt_interval

    for i, start_time in enumerate(scene_start_times):
        if start_time < next_interrupt or start_time < 5.0:
            continue
        if start_time > total_duration - 5.0:
            break

        if random.random() > 0.55:
            continue

        try:
            text = random.choice(interrupt_texts)
            font_size = int(target_w * 0.055) if is_portrait else int(target_w * 0.032)

            img_array = _render_caption_image(
                text=text,
                font_path=CAPTION_FONT,
                font_size=font_size,
                text_w=int(target_w * 0.7),
                accent_color=accent_color,
                stroke_width=4,
            )

            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3].astype(float) / 255.0

            txt_clip = ImageClip(rgb, duration=0.9)
            mask = ImageClip(alpha, is_mask=True, duration=0.9)
            txt_clip = txt_clip.with_mask(mask)
            txt_y = int(target_h * 0.43) if is_portrait else int(target_h * 0.48)
            txt_clip = txt_clip.with_position(("center", txt_y))
            txt_clip = txt_clip.with_start(start_time)
            txt_clip = txt_clip.with_effects([
                vfx.CrossFadeIn(0.08),
                vfx.CrossFadeOut(0.15),
            ])
            interrupt_clips.append(txt_clip)

            # Quick flash behind the interrupt for extra punch
            try:
                from modules.visual_effects import create_flash_transition
                flash = create_flash_transition(0.1, target_w, target_h, flash_color=accent_color)
                flash = flash.with_start(max(0, start_time - 0.05))
                flash = flash.with_opacity(0.25)
                interrupt_clips.append(flash)
            except Exception:
                pass

            next_interrupt = start_time + interrupt_interval

        except Exception:
            continue

    return interrupt_clips


# ── Cinematic Overlay Creator ────────────────────────────────

def _create_cinematic_overlays(
    total_duration: float,
    target_w: int,
    target_h: int,
    niche: str = "ai_trading",
    scene_start_times: list = None,
) -> list:
    """
    Create cinematic overlay layers that run throughout the video.

    Includes:
    - Progress bar (top of screen — retention tool)
    - Light leaks (intermittent warmth)
    - Flash transitions at scene boundaries
    """
    overlays = []

    # 1. Progress bar at top (thin, niche-colored)
    try:
        progress = create_progress_bar(
            total_duration=total_duration,
            width=target_w,
            height=target_h,
            niche=niche,
            bar_height=3,
        )
        progress = progress.with_position((0, 0))
        overlays.append(progress)
    except Exception as e:
        print(f"[Assembler] Progress bar failed: {e}")

    # 2. Light leak overlays (2-3 scattered through video for cinematic warmth)
    try:
        accent = NICHE_ACCENT_COLORS.get(niche, (0, 255, 136))
        # Warm light leaks — place 2-3 throughout the video
        num_leaks = min(3, max(1, int(total_duration / 20)))
        for i in range(num_leaks):
            leak_start = (total_duration / (num_leaks + 1)) * (i + 1)
            leak_dur = min(3.0, total_duration - leak_start)
            if leak_dur < 1.0:
                continue

            # Alternate between warm amber and niche accent color
            leak_color = (255, 180, 80) if i % 2 == 0 else accent

            leak = create_light_leak_overlay(
                width=target_w,
                height=target_h,
                duration=leak_dur,
                color=leak_color,
                position="random",
            )
            leak = leak.with_start(leak_start)
            leak = leak.with_opacity(0.6)
            overlays.append(leak)
    except Exception as e:
        print(f"[Assembler] Light leaks failed: {e}")

    # 3. Flash transitions at select scene boundaries
    if scene_start_times:
        try:
            flash_overlays = create_transition_effects(
                scene_start_times=scene_start_times,
                width=target_w,
                height=target_h,
                niche=niche,
            )
            overlays.extend(flash_overlays)
        except Exception as e:
            print(f"[Assembler] Flash transitions failed: {e}")

    return overlays


async def assemble_video(
    scenes: list[dict],
    audio_path: str,
    captions: list[dict],
    output_path: str | Path,
    format_type: str = "youtube_long",
    music_volume: float = 0.08,
    sfx_placements: list[dict] | None = None,
    avatar_pip_path: str | None = None,
    niche: str = "ai_trading",
    title: str = "",
) -> dict:
    """
    Assemble a complete cinema-grade video from components.

    Layer stack (bottom to top):
    1. Background canvas
    2. Scene clips (with per-scene cinematic effects)
    3. Cinematic overlays (progress bar, light leaks, flash transitions)
    4. Lower thirds
    5. Avatar PiP
    6. Pattern interrupts
    7. Hook overlay
    8. CTA overlay
    9. Captions (topmost)

    Audio stack:
    1. Voiceover (1.0x volume)
    2. Background music (0.08x volume)
    3. Sound effects (0.25-0.3x volume)
    """
    settings = VIDEO_SETTINGS[format_type]
    target_w = settings["width"]
    target_h = settings["height"]
    fps = settings["fps"]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[Assembler] Building {format_type} video ({target_w}x{target_h})...")

    # Load voiceover audio
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration

    # Enforce max duration for short-form formats
    is_short_format = format_type != "youtube_long"
    max_duration = settings.get("duration_target")
    if is_short_format and max_duration and total_duration > max_duration + 2:
        print(f"[Assembler] Trimming audio from {total_duration:.1f}s to {max_duration}s (format limit)")
        audio = audio.subclipped(0, max_duration)
        total_duration = max_duration

    # Background canvas
    bg = ColorClip(size=(target_w, target_h), color=(10, 10, 30), duration=total_duration)

    # ── Dynamic Scene Pacing ──────────────────────────────
    # Calculate energy-based scene durations instead of uniform
    raw_total = sum(s.get("duration", 10) for s in scenes)
    try:
        dynamic_durations = calculate_scene_durations(scenes, total_duration, niche)
        if dynamic_durations and len(dynamic_durations) == len(scenes):
            for i, dur in enumerate(dynamic_durations):
                scenes[i]["duration"] = dur
            print(f"[Assembler] Dynamic pacing: {len(scenes)} scenes, energy-based durations")
    except Exception:
        # Fallback: proportional redistribution
        if raw_total > 0 and abs(raw_total - total_duration) > 1.0:
            scale_factor = total_duration / raw_total
            for s in scenes:
                s["duration"] = s.get("duration", 10) * scale_factor
            print(f"[Assembler] Rescaled {len(scenes)} scene durations ({raw_total:.0f}s -> {total_duration:.0f}s)")

    # ── Create Scene Clips with Cinematic Effects ──────────
    scene_clips = []
    scene_start_times = []
    current_time = 0
    scene_index = 0
    total_scenes = len(scenes)

    while current_time < total_duration - 0.1:
        scene = scenes[scene_index % len(scenes)]
        duration = scene.get("duration", 10)
        remaining = total_duration - current_time
        if remaining <= 0.1:
            break
        actual_duration = min(duration, remaining)

        clip = _create_scene_clip(scene, target_w, target_h, actual_duration)

        # Apply niche color grading
        try:
            clip = _apply_color_grade(clip, niche)
        except Exception:
            pass

        # Apply per-scene cinematic effects (vignette, zoom pulse, shake, glitch, grain)
        try:
            narration = scene.get("narration", "")
            is_reveal = scene_index in (1, total_scenes - 2)  # 2nd scene + penultimate
            has_drama_hint = "dramatic" in scene.get("sfx_hint", "").lower()

            clip = enhance_scene_cinematic(
                clip=clip,
                scene_index=scene_index,
                total_scenes=total_scenes,
                niche=niche,
                narration=narration,
                is_reveal=is_reveal,
                is_dramatic=has_drama_hint,
            )
        except Exception as e:
            print(f"[Assembler] Scene {scene_index} cinematic effects failed: {e}")

        scene_clips.append(clip)
        scene_start_times.append(current_time)
        current_time += actual_duration
        scene_index += 1

    # Apply transitions between scenes (12 styles)
    if ENABLE_TRANSITIONS and len(scene_clips) > 1:
        scene_clips = apply_transitions(scene_clips, TRANSITION_DURATION)

    for i, clip in enumerate(scene_clips):
        scene_clips[i] = clip.with_start(scene_start_times[i])

    # ── Cinematic Overlays ───────────────────────────────
    cinematic_overlays = _create_cinematic_overlays(
        total_duration=total_duration,
        target_w=target_w,
        target_h=target_h,
        niche=niche,
        scene_start_times=scene_start_times,
    )
    if cinematic_overlays:
        print(f"[Assembler] Cinematic overlays: {len(cinematic_overlays)} (progress bar, light leaks, flash)")

    # ── Lower Thirds ─────────────────────────────────────
    lower_third_clips = []
    if ENABLE_LOWER_THIRDS:
        for i, scene in enumerate(scenes):
            lt_text = scene.get("lower_third_text") or scene.get("narration", "")[:60]
            if lt_text and i < len(scene_start_times) and i % 2 == 0:
                lt_clips = create_lower_third(
                    text=lt_text,
                    duration=min(4.0, scene.get("duration", 10) - 0.5),
                    start_time=scene_start_times[i] + 0.3,
                    target_w=target_w,
                    target_h=target_h,
                    niche=niche,
                )
                lower_third_clips.extend(lt_clips)

    # ── Caption Clips ────────────────────────────────────
    caption_clips = _create_caption_clips(captions, target_w, target_h, niche=niche)

    # ── Avatar PiP (FULL VIDEO — more views with avatar throughout) ───
    avatar_pip_clips = []
    if avatar_pip_path and Path(avatar_pip_path).exists():
        try:
            pip_clip = VideoFileClip(avatar_pip_path)

            orig_w, orig_h = pip_clip.w, pip_clip.h
            if orig_w != orig_h:
                sq = min(orig_w, orig_h)
                x1 = (orig_w - sq) // 2
                y1 = max(0, (orig_h - sq) // 4)
                pip_clip = pip_clip.cropped(x1=x1, y1=y1, x2=x1 + sq, y2=y1 + sq)

            is_portrait = target_h > target_w
            pip_size = int(target_w * 0.22) if is_portrait else int(target_w * 0.16)
            pip_clip = pip_clip.resized((pip_size, pip_size))

            Y, X = np.ogrid[:pip_size, :pip_size]
            center = pip_size // 2
            radius = pip_size // 2 - 2
            circle = ((X - center) ** 2 + (Y - center) ** 2 <= radius ** 2).astype(float)

            margin = int(target_w * 0.03)
            pip_x = target_w - pip_size - margin
            pip_y = int(target_h * 0.08) if is_portrait else int(target_h * 0.06)

            border_px = 4
            border_total = pip_size + border_px * 2
            bY, bX = np.ogrid[:border_total, :border_total]
            bc = border_total // 2
            br = border_total // 2
            border_mask = ((bX - bc) ** 2 + (bY - bc) ** 2 <= br ** 2).astype(float)

            # Use niche accent color for avatar border
            accent = NICHE_ACCENT_COLORS.get(niche, (255, 255, 255))

            # Avatar runs for ENTIRE video — loop if avatar clip is shorter
            avatar_dur = min(total_duration, pip_clip.duration)
            if pip_clip.duration < total_duration:
                # Loop the avatar clip to cover full video
                loops_needed = int(total_duration / pip_clip.duration) + 1
                from moviepy import concatenate_videoclips as _concat_v
                pip_clips_loop = [pip_clip] + [
                    VideoFileClip(avatar_pip_path).resized((pip_size, pip_size))
                    for _ in range(loops_needed - 1)
                ]
                # Re-crop non-square clips in the loop
                for li in range(1, len(pip_clips_loop)):
                    lc = pip_clips_loop[li]
                    lw, lh = lc.w, lc.h
                    if lw != lh:
                        lsq = min(lw, lh)
                        lx1 = (lw - lsq) // 2
                        ly1 = max(0, (lh - lsq) // 4)
                        pip_clips_loop[li] = lc.cropped(x1=lx1, y1=ly1, x2=lx1 + lsq, y2=ly1 + lsq).resized((pip_size, pip_size))
                pip_clip = _concat_v(pip_clips_loop)
                pip_clip = pip_clip.subclipped(0, total_duration)
                avatar_dur = total_duration

            seg = pip_clip.subclipped(0, avatar_dur)
            mask = ImageClip(circle, is_mask=True, duration=avatar_dur)
            seg = seg.with_mask(mask)
            seg = seg.with_start(0)
            seg = seg.with_position((pip_x, pip_y))
            seg = seg.with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)])

            # Accent-colored border for full duration
            border = ColorClip(size=(border_total, border_total), color=accent, duration=avatar_dur)
            b_mask = ImageClip(border_mask, is_mask=True, duration=avatar_dur)
            border = border.with_mask(b_mask)
            border = border.with_start(0)
            border = border.with_position((pip_x - border_px, pip_y - border_px))
            border = border.with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)])

            avatar_pip_clips.extend([border, seg])

            print(f"[Assembler] Avatar PiP: {pip_size}x{pip_size} FULL VIDEO ({avatar_dur:.0f}s)")
        except Exception as e:
            print(f"[Assembler] Avatar PiP failed: {e}")

    # ── Hook Overlay ─────────────────────────────────────
    hook_clips = []
    if is_short_format and title:
        hook_clips = _create_hook_overlay(
            title=title,
            target_w=target_w,
            target_h=target_h,
            duration=3.0,
            niche=niche,
        )
        if hook_clips:
            print(f"[Assembler] Hook overlay: {len(hook_clips)} elements for first 3s")

    # ── Pattern Interrupts ───────────────────────────────
    pattern_interrupt_clips = _create_pattern_interrupts(
        scene_start_times=scene_start_times,
        total_duration=total_duration,
        target_w=target_w,
        target_h=target_h,
        niche=niche,
    )
    if pattern_interrupt_clips:
        print(f"[Assembler] Pattern interrupts: {len(pattern_interrupt_clips)} placed")

    # ── CTA Overlay (BOTH start AND end) ─────────────────
    cta_clips = []
    if is_short_format and total_duration > 10:
        try:
            # END CTA — "FOLLOW FOR MORE" (last 5 seconds)
            cta_dur = min(5.0, total_duration * 0.15)
            cta_start = total_duration - cta_dur
            end_cta = create_animated_cta(
                duration=cta_dur,
                width=target_w,
                height=target_h,
                niche=niche,
                cta_text="FOLLOW FOR MORE",
            )
            end_cta = [c.with_start(cta_start) for c in end_cta]
            cta_clips.extend(end_cta)

            # START CTA — small "FOLLOW" button below avatar (first 4s)
            start_follow = create_follow_button_start(
                duration=4.0,
                width=target_w,
                height=target_h,
                niche=niche,
            )
            start_follow = [c.with_start(0.5) for c in start_follow]
            cta_clips.extend(start_follow)

            if cta_clips:
                print(f"[Assembler] CTA: start FOLLOW + end FOLLOW FOR MORE ({len(cta_clips)} clips)")
        except Exception as e:
            print(f"[Assembler] CTA overlay failed: {e}")

    # ── Engagement Overlays (mid-video prompts) ───────────
    engagement_clips = []
    if is_short_format and total_duration > 15:
        try:
            # Mid-video engagement prompts (like, comment, share, follow)
            engagement_clips = create_engagement_overlays(
                total_duration=total_duration,
                width=target_w,
                height=target_h,
                niche=niche,
            )

            # Floating heart animation at ~20% mark
            like_t = total_duration * 0.20
            if like_t > 4:
                heart_clips = create_like_animation(
                    width=target_w,
                    height=target_h,
                    start_time=like_t,
                    niche=niche,
                )
                engagement_clips.extend(heart_clips)

            # Floating emoji overlays at scene transitions
            emoji_clips = create_floating_emojis(
                total_duration=total_duration,
                width=target_w,
                height=target_h,
                niche=niche,
                scene_start_times=scene_start_times,
            )
            engagement_clips.extend(emoji_clips)

            if engagement_clips:
                print(f"[Assembler] Engagement overlays: {len(engagement_clips)} prompts + emojis")
        except Exception as e:
            print(f"[Assembler] Engagement overlays failed: {e}")

    # ── Progress Bar (retention) ──────────────────────────
    progress_bar_clips = []
    if is_short_format and total_duration > 10:
        try:
            progress_bar_clips = create_video_progress_bar(
                total_duration=total_duration,
                width=target_w,
                height=target_h,
                niche=niche,
            )
            if progress_bar_clips:
                print(f"[Assembler] Progress bar: animated top bar for retention")
        except Exception as e:
            print(f"[Assembler] Progress bar failed: {e}")

    # ── Compose All Layers ───────────────────────────────
    # Order: bottom → top. Captions always on top.
    all_clips = (
        [bg]
        + scene_clips
        + cinematic_overlays
        + lower_third_clips
        + progress_bar_clips
        + avatar_pip_clips
        + engagement_clips
        + pattern_interrupt_clips
        + hook_clips
        + cta_clips
        + caption_clips  # Captions always on top
    )

    video = CompositeVideoClip(all_clips, size=(target_w, target_h))

    # ── Audio Mixing ─────────────────────────────────────
    audio_tracks = [audio]
    music_path = _get_music_track()
    if music_path:
        try:
            music = AudioFileClip(music_path)
            if music.duration < total_duration:
                loops_needed = int(total_duration / music.duration) + 1
                music_clips = [music] + [
                    AudioFileClip(music_path) for _ in range(loops_needed - 1)
                ]
                from moviepy import concatenate_audioclips
                music = concatenate_audioclips(music_clips)
                music = music.subclipped(0, total_duration)
            else:
                music = music.subclipped(0, total_duration)
            music = music.with_volume_scaled(music_volume)
            audio_tracks.append(music)
        except Exception as e:
            print(f"[Assembler] Music mixing failed: {e}")

    if sfx_placements:
        for sfx in sfx_placements:
            try:
                sfx_clip = AudioFileClip(sfx["sfx_path"])
                sfx_clip = sfx_clip.with_start(max(0, sfx["start_time"]))
                sfx_clip = sfx_clip.with_volume_scaled(sfx.get("volume", 0.3))
                audio_tracks.append(sfx_clip)
            except Exception:
                pass
        print(f"[Assembler] Mixed {len(sfx_placements)} sound effects")

    final_audio = CompositeAudioClip(audio_tracks) if len(audio_tracks) > 1 else audio
    video = video.with_audio(final_audio)
    video = video.with_duration(total_duration)

    # ── Export (High Quality) ────────────────────────────
    print(f"[Assembler] Rendering {output_path.name} ({total_duration:.0f}s)...")
    # temp_audiofile_path must be a DIRECTORY in MoviePy v2
    import tempfile, time as _time, shutil
    temp_audio_dir = Path(tempfile.gettempdir()) / f"mpy_audio_{int(_time.time())}"
    temp_audio_dir.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        bitrate="8000k",
        preset="medium",
        threads=4,
        logger=None,
        temp_audiofile_path=str(temp_audio_dir),
    )

    # Cleanup — close all clips, then remove temp audio
    video.close()
    audio.close()
    for clip in scene_clips:
        try:
            clip.close()
        except Exception:
            pass
    # Remove temp audio dir (Windows may need a brief delay)
    try:
        _time.sleep(0.5)
        if temp_audio_dir.exists():
            shutil.rmtree(str(temp_audio_dir), ignore_errors=True)
    except Exception:
        pass  # Non-critical, OS will clean temp dir

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[Assembler] Done: {output_path.name} ({total_duration:.0f}s, {file_size_mb:.1f}MB)")

    return {
        "output_path": str(output_path),
        "duration": total_duration,
        "format_type": format_type,
        "file_size_mb": file_size_mb,
        "resolution": f"{target_w}x{target_h}",
    }


# ══════════════════════════════════════════════════════════════
# ██  PODCAST SPLIT-SCREEN ASSEMBLER  ██
# ══════════════════════════════════════════════════════════════

# ── Podcast Studio Background Generator ──────────────────────
# Creates premium podcast studio backgrounds via PIL — dark moody lighting,
# gradient backdrop, subtle desk/mic silhouettes, ambient LED strip glow.

STUDIO_THEMES = {
    "ai_trading": {
        "bg_gradient": [(10, 5, 20), (20, 10, 35)],    # Deep purple-black
        "accent_led": (0, 255, 136),                      # Neon green
        "wall_tint": (15, 8, 25),
        "desk_color": (30, 20, 40),
        "rim_light": (80, 60, 140),
    },
    "ai_money": {
        "bg_gradient": [(8, 12, 5), (18, 25, 12)],      # Deep green-black
        "accent_led": (0, 230, 118),                      # Money green
        "wall_tint": (10, 15, 8),
        "desk_color": (25, 32, 20),
        "rim_light": (60, 140, 80),
    },
    "tech_news": {
        "bg_gradient": [(5, 10, 20), (12, 20, 38)],     # Tech blue-black
        "accent_led": (0, 180, 255),                      # Electric blue
        "wall_tint": (8, 12, 22),
        "desk_color": (18, 25, 40),
        "rim_light": (60, 100, 180),
    },
    "motivation": {
        "bg_gradient": [(15, 8, 5), (30, 15, 10)],      # Warm amber-black
        "accent_led": (255, 180, 50),                     # Gold
        "wall_tint": (18, 10, 6),
        "desk_color": (35, 22, 15),
        "rim_light": (160, 120, 60),
    },
    "health_wellness": {
        "bg_gradient": [(5, 12, 10), (12, 25, 20)],     # Forest green-black
        "accent_led": (100, 220, 150),                    # Organic green
        "wall_tint": (8, 15, 12),
        "desk_color": (20, 30, 25),
        "rim_light": (80, 160, 120),
    },
    "blissful_moments": {
        "bg_gradient": [(12, 8, 18), (22, 15, 32)],     # Soft purple
        "accent_led": (200, 150, 255),                    # Lavender
        "wall_tint": (15, 10, 20),
        "desk_color": (28, 20, 35),
        "rim_light": (140, 100, 180),
    },
}


def _create_studio_background(
    width: int, height: int, character: str, niche: str = "ai_trading",
) -> np.ndarray:
    """
    Create a premium podcast studio background using PIL.

    Features:
    - Dark moody vertical gradient backdrop
    - Subtle acoustic wall panel texture
    - LED accent strip along edges (niche colored)
    - Desk/table silhouette at bottom
    - Soft rim lighting on sides
    - Microphone silhouette
    - Character-specific color tint (red side vs blue side)
    """
    from PIL import Image as _PILImage, ImageDraw as _PILDraw, ImageFilter as _PILFilter

    theme = STUDIO_THEMES.get(niche, STUDIO_THEMES["ai_trading"])
    img = _PILImage.new("RGB", (width, height), theme["wall_tint"])
    draw = _PILDraw.Draw(img)

    # Character side tint (SPARKY = warm red tint, NOVA = cool blue tint)
    char_tint = (25, 8, 8) if character == "SPARKY" else (8, 12, 28)

    # ── 1. Dark gradient backdrop ──────────────────────────
    top_color = theme["bg_gradient"][0]
    bot_color = theme["bg_gradient"][1]
    for y in range(height):
        ratio = y / height
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * ratio + char_tint[0] * 0.6)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * ratio + char_tint[1] * 0.6)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * ratio + char_tint[2] * 0.6)
        draw.line([(0, y), (width, y)], fill=(min(r, 255), min(g, 255), min(b, 255)))

    # ── 2. Acoustic panel texture (subtle grid) ────────────
    panel_color = tuple(min(c + 8, 255) for c in theme["wall_tint"])
    panel_spacing = max(40, width // 12)
    for x in range(0, width, panel_spacing):
        for y in range(0, int(height * 0.72), panel_spacing):
            margin = 3
            draw.rectangle(
                [x + margin, y + margin, x + panel_spacing - margin, y + panel_spacing - margin],
                outline=panel_color, width=1,
            )

    # ── 3. LED accent strip (top edge) ─────────────────────
    led = theme["accent_led"]
    strip_h = max(3, height // 120)
    for i in range(strip_h):
        alpha_ratio = 1.0 - (i / strip_h) * 0.7
        led_c = tuple(int(c * alpha_ratio * 0.6) for c in led)
        draw.line([(0, i), (width, i)], fill=led_c)

    # LED glow below strip (diffused)
    for i in range(strip_h, strip_h + max(15, height // 40)):
        falloff = 1.0 - ((i - strip_h) / max(15, height // 40))
        glow_c = tuple(int(c * falloff * 0.15) for c in led)
        draw.line([(0, i), (width, i)], fill=glow_c)

    # ── 4. Side LED strips (vertical) ─────────────────────
    side_w = max(2, width // 180)
    for i in range(side_w):
        alpha = 0.5 * (1.0 - i / side_w)
        sc = tuple(int(c * alpha) for c in led)
        draw.line([(i, 0), (i, height)], fill=sc)
        draw.line([(width - 1 - i, 0), (width - 1 - i, height)], fill=sc)

    # ── 5. Desk / table surface at bottom ──────────────────
    desk_top_y = int(height * 0.75)
    desk_color = theme["desk_color"]
    # Desk edge highlight
    edge_c = tuple(min(c + 25, 255) for c in desk_color)
    draw.line([(0, desk_top_y), (width, desk_top_y)], fill=edge_c, width=2)
    # Desk surface
    for y in range(desk_top_y + 2, height):
        darken = 1.0 - ((y - desk_top_y) / (height - desk_top_y)) * 0.3
        dc = tuple(int(c * darken) for c in desk_color)
        draw.line([(0, y), (width, y)], fill=dc)

    # ── 6. Microphone silhouette ───────────────────────────
    mic_x = int(width * 0.15) if character == "SPARKY" else int(width * 0.85)
    mic_top = int(height * 0.48)
    mic_w = max(8, width // 35)
    mic_h = max(20, height // 12)
    mic_color = tuple(min(c + 15, 255) for c in desk_color)

    # Mic arm (angled line from desk to mic head)
    arm_bottom = (mic_x + mic_w * 2, desk_top_y)
    arm_top = (mic_x, mic_top + mic_h)
    draw.line([arm_bottom, arm_top], fill=mic_color, width=max(2, mic_w // 4))

    # Mic head (rounded rectangle)
    draw.rounded_rectangle(
        [mic_x - mic_w // 2, mic_top, mic_x + mic_w // 2, mic_top + mic_h],
        radius=mic_w // 2, fill=mic_color,
        outline=tuple(min(c + 30, 255) for c in mic_color), width=1,
    )
    # Mic grille lines
    for gy in range(mic_top + 3, mic_top + mic_h - 3, 3):
        draw.line(
            [mic_x - mic_w // 3, gy, mic_x + mic_w // 3, gy],
            fill=tuple(min(c + 10, 255) for c in mic_color), width=1,
        )

    # ── 7. Rim lighting (soft glow on edges) ──────────────
    rim = theme["rim_light"]
    rim_w = max(20, width // 15)
    for i in range(rim_w):
        falloff = (1.0 - i / rim_w) ** 2 * 0.12
        rc = tuple(int(c * falloff) for c in rim)
        # Left rim
        draw.line([(i, 0), (i, int(height * 0.72))], fill=rc)
        # Right rim
        draw.line([(width - 1 - i, 0), (width - 1 - i, int(height * 0.72))], fill=rc)

    # ── 8. Subtle vignette (darken corners) ────────────────
    vignette = _PILImage.new("L", (width, height), 255)
    v_draw = _PILDraw.Draw(vignette)
    cx, cy = width // 2, height // 2
    max_dist = ((cx ** 2 + cy ** 2) ** 0.5)
    for r in range(int(max_dist), int(max_dist * 0.55), -3):
        brightness = int(255 * (r / max_dist) ** 0.5 * 0.25)
        v_draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=max(0, 255 - brightness),
        )
    vignette = vignette.filter(_PILFilter.GaussianBlur(30))
    # Apply vignette by compositing
    dark = _PILImage.new("RGB", (width, height), (0, 0, 0))
    img = _PILImage.composite(img, dark, vignette)

    return np.array(img)


# Character color schemes
PODCAST_COLORS = {
    "SPARKY": {
        "primary": (239, 68, 68),     # Red
        "glow": (255, 100, 100),
        "border": (200, 50, 50),
        "label_bg": (239, 68, 68),
        "emoji": "🔴",
    },
    "NOVA": {
        "primary": (59, 130, 246),    # Blue
        "glow": (100, 150, 255),
        "border": (50, 100, 200),
        "label_bg": (59, 130, 246),
        "emoji": "🔵",
    },
}


def _create_name_badge(name: str, accent_color: tuple, badge_w: int, badge_h: int) -> np.ndarray:
    """
    Render a premium pill-shaped name badge using PIL.

    Returns an RGBA numpy array with:
    - Rounded rectangle dark semi-transparent background
    - Colored accent border (2px)
    - Colored live-indicator dot before the name
    - Bold white name text
    """
    # Create RGBA image
    img = PILImage.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Outer glow layer (subtle colored halo) ──
    glow_radius = 14
    glow_rect = [
        glow_radius // 2, glow_radius // 2,
        badge_w - glow_radius // 2 - 1, badge_h - glow_radius // 2 - 1,
    ]
    glow_color = accent_color + (30,)  # Very subtle glow
    draw.rounded_rectangle(glow_rect, radius=badge_h // 2, fill=glow_color)

    # ── Main pill background (dark, semi-transparent) ──
    border_width = 2
    inset = 4  # Inset from glow edge
    pill_rect = [
        inset + border_width, inset + border_width,
        badge_w - inset - border_width - 1, badge_h - inset - border_width - 1,
    ]
    pill_radius = (badge_h - 2 * inset - 2 * border_width) // 2

    # Draw colored border first (slightly larger pill)
    border_rect = [inset, inset, badge_w - inset - 1, badge_h - inset - 1]
    border_radius = (badge_h - 2 * inset) // 2
    draw.rounded_rectangle(border_rect, radius=border_radius, fill=accent_color + (180,))

    # Draw dark interior pill on top
    bg_color = (15, 15, 25, 210)  # Dark semi-transparent
    draw.rounded_rectangle(pill_rect, radius=pill_radius, fill=bg_color)

    # ── Subtle gradient highlight at top of pill ──
    highlight_rect = [
        pill_rect[0] + 4, pill_rect[1] + 1,
        pill_rect[2] - 4, pill_rect[1] + max(4, badge_h // 6),
    ]
    highlight_color = (255, 255, 255, 18)
    draw.rounded_rectangle(highlight_rect, radius=pill_radius // 2, fill=highlight_color)

    # ── Load font ──
    name_text = name.upper()
    font_size = max(14, int(badge_h * 0.42))
    try:
        font = ImageFont.truetype(CAPTION_FONT, font_size)
    except Exception:
        font = ImageFont.load_default()

    # Measure text
    text_bbox = draw.textbbox((0, 0), name_text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    # ── Live indicator dot ──
    dot_radius = max(4, int(badge_h * 0.09))
    dot_gap = max(6, int(badge_h * 0.12))
    total_content_w = dot_radius * 2 + dot_gap + text_w
    content_x_start = (badge_w - total_content_w) // 2

    dot_cx = content_x_start + dot_radius
    dot_cy = badge_h // 2
    # Dot outer glow
    draw.ellipse(
        [dot_cx - dot_radius - 2, dot_cy - dot_radius - 2,
         dot_cx + dot_radius + 2, dot_cy + dot_radius + 2],
        fill=accent_color + (60,),
    )
    # Dot solid
    draw.ellipse(
        [dot_cx - dot_radius, dot_cy - dot_radius,
         dot_cx + dot_radius, dot_cy + dot_radius],
        fill=accent_color + (255,),
    )
    # Dot highlight
    hl_r = max(1, dot_radius // 2)
    draw.ellipse(
        [dot_cx - hl_r + 1, dot_cy - hl_r,
         dot_cx + hl_r - 1, dot_cy],
        fill=(255, 255, 255, 100),
    )

    # ── Name text with shadow ──
    text_x = content_x_start + dot_radius * 2 + dot_gap
    text_y = (badge_h - text_h) // 2 - 1

    # Text shadow
    shadow_offset = max(1, font_size // 16)
    draw.text(
        (text_x + shadow_offset, text_y + shadow_offset),
        name_text, font=font, fill=(0, 0, 0, 160),
    )

    # Main text (white bold)
    draw.text((text_x, text_y), name_text, font=font, fill=(255, 255, 255, 255))

    return np.array(img)


# ── Emotion Badge Styles ──────────────────────────────────────
EMOTION_BADGE_STYLES = {
    "SHOCKED":      {"color": (255, 220, 50),  "scale": 1.15},
    "ANGRY":        {"color": (255, 80, 80),   "scale": 1.1},
    "LAUGHS":       {"color": (80, 255, 120),  "scale": 1.05},
    "WHISPERING":   {"color": (180, 130, 255), "scale": 0.9},
    "SARCASTIC":    {"color": (120, 200, 200), "scale": 1.0},
    "DISBELIEF":    {"color": (230, 100, 200), "scale": 1.1},
    "EXCITED":      {"color": (255, 165, 0),   "scale": 1.15},
    "DEAD SERIOUS": {"color": (100, 160, 255), "scale": 1.0},
    "SMIRKING":     {"color": (255, 140, 50),  "scale": 1.0},
    "CUTS OFF":     {"color": (255, 50, 50),   "scale": 1.1},
    "CONFUSED":     {"color": (200, 200, 100), "scale": 1.0},
    "FIRED UP":     {"color": (220, 80, 20),   "scale": 1.15},
    "CALM":         {"color": (100, 180, 220), "scale": 0.9},
    "NERVOUS":      {"color": (180, 100, 200), "scale": 1.0},
    "IMPRESSED":    {"color": (255, 180, 50),  "scale": 1.05},
}


def _create_emotion_badge(emotion: str, badge_w: int = None) -> np.ndarray:
    """
    Render a styled emotion pill badge using PIL.

    Returns an RGBA numpy array with:
    - Rounded pill-shaped dark semi-transparent background
    - Emotion-specific colored text and thin accent border
    - Clean typography without brackets
    """
    style = EMOTION_BADGE_STYLES.get(emotion, {"color": (200, 200, 200), "scale": 1.0})
    accent = style["color"]
    scale = style.get("scale", 1.0)
    label = emotion.upper()

    # ── Measure text to determine badge size (scaled by emotion intensity) ──
    font_size = int(22 * scale)
    try:
        font = ImageFont.truetype(CAPTION_FONT, font_size)
    except Exception:
        font = ImageFont.load_default()

    temp_img = PILImage.new("RGBA", (400, 60), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    text_bbox = temp_draw.textbbox((0, 0), label, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    padding_x = max(20, int(text_w * 0.35))
    padding_y = max(10, int(text_h * 0.5))
    final_w = badge_w if badge_w else text_w + padding_x * 2
    final_h = text_h + padding_y * 2

    img = PILImage.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Outer glow ──
    glow_rect = [2, 2, final_w - 3, final_h - 3]
    glow_color = accent + (25,)
    draw.rounded_rectangle(glow_rect, radius=final_h // 2, fill=glow_color)

    # ── Accent border pill ──
    border_rect = [4, 4, final_w - 5, final_h - 5]
    border_radius = (final_h - 8) // 2
    draw.rounded_rectangle(border_rect, radius=border_radius, fill=accent + (70,))

    # ── Dark interior pill ──
    inner_rect = [6, 6, final_w - 7, final_h - 7]
    inner_radius = (final_h - 12) // 2
    draw.rounded_rectangle(inner_rect, radius=inner_radius, fill=(10, 10, 20, 200))

    # ── Top highlight ──
    hl_rect = [inner_rect[0] + 4, inner_rect[1] + 1, inner_rect[2] - 4, inner_rect[1] + max(3, final_h // 8)]
    draw.rounded_rectangle(hl_rect, radius=inner_radius // 2, fill=(255, 255, 255, 15))

    # ── Colored accent line at left edge ──
    line_y_start = inner_rect[1] + 4
    line_y_end = inner_rect[3] - 4
    line_x = inner_rect[0] + 8
    draw.line([(line_x, line_y_start), (line_x, line_y_end)], fill=accent + (200,), width=3)

    # ── Emotion text ──
    tx = (final_w - text_w) // 2 + 4  # Slight right offset for accent line
    ty = (final_h - text_h) // 2 - 1

    # Text shadow
    draw.text((tx + 1, ty + 1), label, font=font, fill=(0, 0, 0, 140))
    # Main text in accent color
    draw.text((tx, ty), label, font=font, fill=accent + (255,))

    return np.array(img)


def _create_character_panel(
    image_path: str,
    panel_w: int,
    panel_h: int,
    character: str,
    duration: float,
    is_active: bool = False,
    niche: str = "ai_trading",
    animated_video: str = None,
) -> list:
    """
    Create a single character panel for split-screen layout.

    Supports both:
    - Static images (fallback) — ImageClip with circular mask
    - Animated D-ID video clips (premium) — VideoFileClip fills the panel

    Returns list of clips for this panel (background, character, label).
    """
    clips = []
    colors = PODCAST_COLORS.get(character, PODCAST_COLORS["SPARKY"])

    # ── Panel background — Professional podcast studio ──────
    try:
        studio_arr = _create_studio_background(panel_w, panel_h, character, niche)
        panel_bg = ImageClip(studio_arr, duration=duration)
    except Exception as e:
        print(f"[Podcast] Studio bg fallback for {character}: {e}")
        bg_color = (20, 8, 8) if character == "SPARKY" else (8, 12, 25)
        panel_bg = ColorClip(size=(panel_w, panel_h), color=bg_color, duration=duration)
    clips.append(panel_bg)

    # ── Character visual (animated video or static image) ───
    if animated_video and Path(animated_video).exists():
        # PREMIUM: D-ID animated talking head video
        try:
            char_vid = VideoFileClip(animated_video)

            # Scale to fill panel nicely (center the avatar in frame)
            vid_w, vid_h = char_vid.w, char_vid.h
            # Fill panel width, crop height if needed
            scale = panel_w / vid_w
            new_w = panel_w
            new_h = int(vid_h * scale)
            char_vid = char_vid.resized((new_w, new_h))

            # Center vertically in panel, slightly above center (sitting at desk)
            vid_y = max(0, (panel_h - new_h) // 2 - int(panel_h * 0.05))
            if new_h > panel_h:
                # Crop to fit panel
                crop_y = (new_h - panel_h) // 2
                char_vid = char_vid.cropped(x1=0, y1=crop_y, x2=new_w, y2=crop_y + panel_h)
                vid_y = 0

            # Loop if video is shorter than needed
            if char_vid.duration < duration:
                from moviepy import concatenate_videoclips as _concat
                loops = int(duration / char_vid.duration) + 1
                vid_list = [char_vid] + [
                    VideoFileClip(animated_video).resized((new_w, new_h))
                    for _ in range(loops - 1)
                ]
                char_vid = _concat(vid_list)
            char_vid = char_vid.subclipped(0, duration)
            char_vid = char_vid.with_position((0, vid_y))
            # Remove audio from the avatar clip (we mix our own audio)
            char_vid = char_vid.without_audio()
            clips.append(char_vid)
            print(f"[Podcast] {character}: Using D-ID animated avatar ({new_w}x{new_h})")
        except Exception as e:
            print(f"[Podcast] Animated avatar failed for {character}: {e} — falling back to static")
            animated_video = None  # Fall through to static image

    if not animated_video and image_path and Path(image_path).exists():
        # FALLBACK: Static character image with circular mask
        try:
            char_img = ImageClip(image_path, duration=duration)
            img_size = int(min(panel_w, panel_h) * 0.58)
            char_img = char_img.resized(width=img_size)

            img_x = (panel_w - char_img.w) // 2
            img_y = int(panel_h * 0.18)  # Positioned behind desk
            char_img = char_img.with_position((img_x, img_y))

            # Circular mask
            h, w = char_img.h, char_img.w
            mask_sz = min(h, w)
            Y, X = np.ogrid[:h, :w]
            cx, cy = w // 2, h // 2
            radius = mask_sz // 2 - 4
            circle = ((X - cx) ** 2 + (Y - cy) ** 2 <= radius ** 2).astype(float)
            mask = ImageClip(circle, is_mask=True, duration=duration)
            char_img = char_img.with_mask(mask)
            clips.append(char_img)

            # Colored ring around character
            ring_size = mask_sz + 8
            rY, rX = np.ogrid[:ring_size, :ring_size]
            rcx, rcy = ring_size // 2, ring_size // 2
            outer = (rX - rcx) ** 2 + (rY - rcy) ** 2
            ring_mask_arr = ((outer <= (ring_size // 2) ** 2) & (outer > (ring_size // 2 - 5) ** 2)).astype(float)
            ring = ColorClip(size=(ring_size, ring_size), color=colors["primary"], duration=duration)
            ring_mask_clip = ImageClip(ring_mask_arr, is_mask=True, duration=duration)
            ring = ring.with_mask(ring_mask_clip)
            ring_x = img_x + (char_img.w - ring_size) // 2
            ring_y = img_y + (char_img.h - ring_size) // 2
            ring = ring.with_position((ring_x, ring_y))
            clips.append(ring)
        except Exception as e:
            print(f"[Podcast] Character image failed for {character}: {e}")

    # ── Character name badge (premium pill-shaped floating badge) ──
    try:
        from modules.podcast_generator import NICHE_CHARACTER_NAMES
        display_names = NICHE_CHARACTER_NAMES.get(niche, {})
        display_name = display_names.get(character.lower(), character)

        badge_h = max(44, int(panel_h * 0.065))
        badge_w = max(180, int(panel_w * 0.55))
        accent = colors["primary"]

        badge_arr = _create_name_badge(display_name, accent, badge_w, badge_h)
        badge_clip = ImageClip(badge_arr, duration=duration)
        badge_x = (panel_w - badge_w) // 2
        badge_y = int(panel_h * 0.83)
        badge_clip = badge_clip.with_position((badge_x, badge_y))
        clips.append(badge_clip)
    except Exception as e:
        print(f"[Podcast] Name badge failed for {character}: {e}")
        pass

    return clips


def _create_active_speaker_glow(
    line_timings: list,
    panel_w: int,
    panel_h: int,
    target_w: int,
    target_h: int,
    is_portrait: bool,
) -> list:
    """Create glow overlays for active speaker during their lines."""
    glow_clips = []
    for timing in line_timings:
        character = timing["character"]
        start = timing["start"]
        duration = timing["end"] - start
        if duration < 0.1:
            continue
        colors = PODCAST_COLORS.get(character, PODCAST_COLORS["SPARKY"])

        # Top edge glow bar
        if is_portrait:
            glow_x, glow_y = 0, (0 if character == "SPARKY" else panel_h + 4)
            glow_w, glow_h = target_w, 5
        else:
            glow_x = 0 if character == "SPARKY" else panel_w + int(target_w * 0.04)
            glow_y, glow_w, glow_h = 0, panel_w, 4

        glow = ColorClip(size=(glow_w, glow_h), color=colors["glow"], duration=duration)
        glow = glow.with_start(start).with_position((glow_x, glow_y)).with_opacity(0.8)
        glow = glow.with_effects([vfx.CrossFadeIn(0.08), vfx.CrossFadeOut(0.08)])
        glow_clips.append(glow)

        # Subtle full-panel tint for active speaker
        if is_portrait:
            panel_pos = (0, 0 if character == "SPARKY" else panel_h + 4)
        else:
            panel_pos = (0 if character == "SPARKY" else panel_w + int(target_w * 0.04), 0)
        panel_glow = ColorClip(size=(panel_w, panel_h), color=colors["primary"], duration=duration)
        panel_glow = panel_glow.with_start(start).with_position(panel_pos).with_opacity(0.06)
        panel_glow = panel_glow.with_effects([vfx.CrossFadeIn(0.1), vfx.CrossFadeOut(0.1)])
        glow_clips.append(panel_glow)

    return glow_clips


# Emotion → caption style modifiers (font scale, opacity, stroke, fade speed)
EMOTION_CAPTION_STYLES = {
    "SHOCKED":      {"font_scale": 1.2,  "opacity": 1.0, "stroke": 5, "fade_in": 0.03},
    "ANGRY":        {"font_scale": 1.15, "opacity": 1.0, "stroke": 5, "fade_in": 0.03},
    "EXCITED":      {"font_scale": 1.2,  "opacity": 1.0, "stroke": 5, "fade_in": 0.03},
    "FIRED UP":     {"font_scale": 1.15, "opacity": 1.0, "stroke": 5, "fade_in": 0.03},
    "DISBELIEF":    {"font_scale": 1.1,  "opacity": 1.0, "stroke": 5, "fade_in": 0.04},
    "CUTS OFF":     {"font_scale": 1.1,  "opacity": 1.0, "stroke": 4, "fade_in": 0.02},
    "WHISPERING":   {"font_scale": 0.85, "opacity": 0.75, "stroke": 3, "fade_in": 0.1},
    "CALM":         {"font_scale": 0.9,  "opacity": 0.85, "stroke": 3, "fade_in": 0.08},
    "NERVOUS":      {"font_scale": 0.95, "opacity": 0.9,  "stroke": 4, "fade_in": 0.06},
    "LAUGHS":       {"font_scale": 1.05, "opacity": 1.0, "stroke": 4, "fade_in": 0.05},
    "SARCASTIC":    {"font_scale": 1.0,  "opacity": 0.95, "stroke": 4, "fade_in": 0.05},
    "SMIRKING":     {"font_scale": 1.0,  "opacity": 0.95, "stroke": 4, "fade_in": 0.05},
    "CONFUSED":     {"font_scale": 1.0,  "opacity": 0.9,  "stroke": 4, "fade_in": 0.06},
    "IMPRESSED":    {"font_scale": 1.05, "opacity": 1.0, "stroke": 4, "fade_in": 0.05},
    "DEAD SERIOUS": {"font_scale": 1.1,  "opacity": 1.0, "stroke": 5, "fade_in": 0.04},
}


def _create_podcast_captions(
    line_timings: list,
    target_w: int,
    target_h: int,
    niche: str = "ai_trading",
) -> list:
    """Create podcast captions with character color coding, display names, and emotion-aware styling."""
    from modules.podcast_generator import NICHE_CHARACTER_NAMES

    caption_clips = []
    is_portrait = target_h > target_w
    text_w = int(target_w * 0.88)
    base_font_size = int(target_w * 0.045) if is_portrait else int(target_w * 0.032)
    name_font_size = int(base_font_size * 0.65)
    cap_y = int(target_h * 0.78) if is_portrait else int(target_h * 0.80)
    name_y = cap_y - name_font_size - 8  # Name label sits above caption

    display_names = NICHE_CHARACTER_NAMES.get(niche, {})

    for timing in line_timings:
        text = timing.get("text", "")
        start = timing["start"]
        end = timing["end"]
        duration = end - start
        emotion = timing.get("emotion", "")
        if duration < 0.1 or not text:
            continue

        char_key = timing["character"].lower()
        accent = (255, 120, 120) if timing["character"] == "SPARKY" else (120, 170, 255)
        display_name = display_names.get(char_key, timing["character"])

        # ── Emotion-aware styling ──
        em_style = EMOTION_CAPTION_STYLES.get(emotion, {"font_scale": 1.0, "opacity": 1.0, "stroke": 4, "fade_in": 0.05})
        font_size = int(base_font_size * em_style["font_scale"])
        stroke_width = em_style["stroke"]
        fade_in = em_style["fade_in"]
        cap_opacity = em_style["opacity"]

        try:
            # ── Name label above captions ──
            name_img = _render_caption_image(
                text=display_name, font_path=CAPTION_FONT, font_size=name_font_size,
                text_w=text_w, accent_color=accent, stroke_width=3,
            )
            n_rgb = name_img[:, :, :3]
            n_alpha = name_img[:, :, 3].astype(float) / 255.0
            name_clip = ImageClip(n_rgb, duration=min(duration, 1.5))
            n_mask = ImageClip(n_alpha, is_mask=True, duration=min(duration, 1.5))
            name_clip = name_clip.with_mask(n_mask).with_start(start).with_position(("center", name_y))
            name_clip = name_clip.with_effects([vfx.CrossFadeIn(0.05), vfx.CrossFadeOut(0.2)])
            caption_clips.append(name_clip)

            # ── Phrase captions (emotion-styled) ──
            words = text.upper().split()
            # Fewer words per phrase for intense emotions (punchy), more for calm
            if em_style["font_scale"] >= 1.1:
                max_pw = 4  # Punchy short phrases for high-intensity
            elif em_style["font_scale"] <= 0.9:
                max_pw = 8  # Longer phrases for calm/whisper
            else:
                max_pw = 6
            phrases = [" ".join(words[j:j + max_pw]) for j in range(0, len(words), max_pw)]
            if not phrases:
                continue
            phrase_dur = duration / len(phrases)

            for p_idx, phrase in enumerate(phrases):
                p_start = start + p_idx * phrase_dur
                img_array = _render_caption_image(
                    text=phrase, font_path=CAPTION_FONT, font_size=font_size,
                    text_w=text_w, accent_color=accent, stroke_width=stroke_width,
                )
                rgb = img_array[:, :, :3]
                alpha = img_array[:, :, 3].astype(float) / 255.0
                clip = ImageClip(rgb, duration=phrase_dur)
                mask = ImageClip(alpha, is_mask=True, duration=phrase_dur)
                clip = clip.with_mask(mask).with_start(p_start).with_position(("center", cap_y))
                effects = [vfx.CrossFadeIn(fade_in)]
                if cap_opacity < 1.0:
                    clip = clip.with_opacity(cap_opacity)
                clip = clip.with_effects(effects)
                caption_clips.append(clip)
        except Exception:
            continue

    return caption_clips


def _create_section_title_overlay(
    section_name: str, start_time: float,
    target_w: int, target_h: int, niche: str = "ai_trading",
) -> list:
    """Create section title overlays (e.g. 'THE TWIST', 'ROUND 1')."""
    clips = []
    accent = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))
    duration = 1.8
    is_portrait = target_h > target_w

    try:
        backdrop = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=duration)
        backdrop = backdrop.with_start(start_time).with_opacity(0.4)
        backdrop = backdrop.with_effects([vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.4)])
        clips.append(backdrop)

        font_size = int(target_w * 0.07) if is_portrait else int(target_w * 0.04)
        display_name = section_name.upper()
        if "TWIST" in display_name:
            display_name = f"🔄 {display_name}"
        elif "HOOK" in display_name:
            display_name = f"🎯 {display_name}"
        elif "CLIFFHANGER" in display_name:
            display_name = "💥 CLIFFHANGER"
        elif display_name.startswith("ROUND"):
            display_name = f"⚡ {display_name}"

        img_array = _render_caption_image(
            text=display_name, font_path=CAPTION_FONT, font_size=font_size,
            text_w=int(target_w * 0.8), accent_color=accent, stroke_width=5,
        )
        rgb = img_array[:, :, :3]
        alpha = img_array[:, :, 3].astype(float) / 255.0
        title_clip = ImageClip(rgb, duration=duration)
        mask = ImageClip(alpha, is_mask=True, duration=duration)
        title_clip = title_clip.with_mask(mask)
        y_pos = int(target_h * 0.40) if is_portrait else int(target_h * 0.42)
        title_clip = title_clip.with_start(start_time).with_position(("center", y_pos))
        title_clip = title_clip.with_effects([vfx.CrossFadeIn(0.1), vfx.CrossFadeOut(0.3)])
        clips.append(title_clip)

        bar_w = int(target_w * 0.3)
        bar = ColorClip(size=(bar_w, 4), color=accent, duration=duration - 0.3)
        bar = bar.with_start(start_time + 0.15).with_position(("center", y_pos + font_size + 15))
        bar = bar.with_effects([vfx.CrossFadeIn(0.1), vfx.CrossFadeOut(0.2)])
        clips.append(bar)
    except Exception:
        pass
    return clips


# ── Camera Angle Cuts — Dynamic "shot" effects for podcast videos ────────

# Emotions that trigger snap zoom effect
_SNAP_ZOOM_EMOTIONS = {"SHOCKED", "ANGRY", "LAUGHS", "EXCITED"}

# Sections that trigger wide-shot effect
_WIDE_SHOT_SECTIONS = {"THE TWIST", "ROUND 1", "ROUND 2", "ROUND 3", "CLIFFHANGER", "THE HOOK"}


def _create_camera_angle_cuts(
    line_timings: list,
    panel_positions: dict,
    panel_sizes: dict,
    target_w: int,
    target_h: int,
    total_duration: float,
    niche: str = "ai_trading",
) -> list:
    """
    Create dynamic camera angle cut overlays for podcast videos.

    Simulates professional podcast multi-camera editing by layering
    vignette/letterbox overlays that draw focus to the active speaker,
    widen out during section transitions, and snap-zoom on high-emotion
    moments.

    Shot types:
    1. CLOSE-UP — During each character's dialogue: subtle vignette darkens
       the inactive speaker's panel, simulating a camera push-in on the
       active speaker. Uses a gentle 0.06 opacity darken overlay.
    2. WIDE SHOT — During section transitions (THE TWIST, ROUNDs): brief
       letterbox bars (top/bottom) give a cinematic wide-angle feel.
    3. SNAP ZOOM — On high-emotion lines (SHOCKED, ANGRY, LAUGHS, EXCITED):
       a quick bright flash + tighter vignette for a punch-in effect.

    Args:
        line_timings: List of dicts with character, emotion, start, end,
                      text, section fields.
        panel_positions: Dict mapping character name to (x, y) position.
                         e.g. {"SPARKY": (0, 0), "NOVA": (540, 0)}
        panel_sizes: Dict with "panel_w" and "panel_h" integers.
        target_w: Final video width.
        target_h: Final video height.
        total_duration: Total video duration in seconds.
        niche: Niche identifier for accent color.

    Returns:
        List of MoviePy clips (overlays) to add to the composition.
    """
    clips = []
    is_portrait = target_h > target_w
    panel_w = panel_sizes["panel_w"]
    panel_h = panel_sizes["panel_h"]
    accent = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))

    # Track which sections we've already shown wide-shot for (avoid duplicates)
    seen_wide_sections = set()
    # Track last snap-zoom time to avoid overlapping snaps
    last_snap_time = -999.0

    for timing in line_timings:
        character = timing.get("character", "SPARKY")
        emotion = timing.get("emotion", "")
        section = timing.get("section", "")
        start = timing["start"]
        end = timing["end"]
        line_duration = end - start

        if line_duration < 0.15:
            continue

        # ── 1. CLOSE-UP: Darken inactive speaker panel ──────────
        # Creates the effect of "cutting" to the active speaker by
        # subtly dimming the other panel
        try:
            inactive_char = "NOVA" if character == "SPARKY" else "SPARKY"
            inactive_pos = panel_positions.get(inactive_char, (0, 0))

            # Dark overlay on inactive panel (subtle dim = camera not on them)
            dim_overlay = ColorClip(
                size=(panel_w, panel_h),
                color=(0, 0, 0),
                duration=line_duration,
            )
            dim_overlay = (
                dim_overlay
                .with_start(start)
                .with_position(inactive_pos)
                .with_opacity(0.06)
                .with_effects([
                    vfx.CrossFadeIn(0.25),
                    vfx.CrossFadeOut(0.2),
                ])
            )
            clips.append(dim_overlay)

            # Subtle edge vignette on the active speaker panel to simulate
            # a camera lens push-in (darker corners = tighter framing feel)
            active_pos = panel_positions.get(character, (0, 0))
            if line_duration > 1.0:
                vignette_clips = _create_panel_vignette(
                    panel_w, panel_h, active_pos,
                    line_duration, start,
                    opacity=0.10, border_fraction=0.15,
                )
                clips.extend(vignette_clips)
        except Exception:
            pass

        # ── 2. WIDE SHOT: Section transitions ───────────────────
        # Brief letterbox + full-frame vignette lift when entering a
        # new section (THE TWIST, ROUND 1, etc.) — cinematic feel
        if section and section.upper() in _WIDE_SHOT_SECTIONS:
            section_key = section.upper()
            if section_key not in seen_wide_sections:
                seen_wide_sections.add(section_key)
                try:
                    wide_dur = min(1.6, line_duration)
                    wide_start = max(0.0, start - 0.3)

                    # Letterbox bars (top and bottom) — cinematic wide-shot
                    bar_h = int(target_h * 0.04) if is_portrait else int(target_h * 0.05)

                    top_bar = ColorClip(
                        size=(target_w, bar_h), color=(0, 0, 0),
                        duration=wide_dur,
                    )
                    top_bar = (
                        top_bar
                        .with_start(wide_start)
                        .with_position((0, 0))
                        .with_opacity(0.7)
                        .with_effects([
                            vfx.CrossFadeIn(0.15),
                            vfx.CrossFadeOut(0.4),
                        ])
                    )
                    clips.append(top_bar)

                    bottom_bar = ColorClip(
                        size=(target_w, bar_h), color=(0, 0, 0),
                        duration=wide_dur,
                    )
                    bottom_bar = (
                        bottom_bar
                        .with_start(wide_start)
                        .with_position((0, target_h - bar_h))
                        .with_opacity(0.7)
                        .with_effects([
                            vfx.CrossFadeIn(0.15),
                            vfx.CrossFadeOut(0.4),
                        ])
                    )
                    clips.append(bottom_bar)

                    # Accent color thin line at letterbox inner edges
                    line_h = 2
                    top_accent = ColorClip(
                        size=(target_w, line_h), color=accent,
                        duration=wide_dur - 0.3,
                    )
                    top_accent = (
                        top_accent
                        .with_start(wide_start + 0.1)
                        .with_position((0, bar_h))
                        .with_opacity(0.4)
                        .with_effects([
                            vfx.CrossFadeIn(0.1),
                            vfx.CrossFadeOut(0.3),
                        ])
                    )
                    clips.append(top_accent)

                    bottom_accent = ColorClip(
                        size=(target_w, line_h), color=accent,
                        duration=wide_dur - 0.3,
                    )
                    bottom_accent = (
                        bottom_accent
                        .with_start(wide_start + 0.1)
                        .with_position((0, target_h - bar_h - line_h))
                        .with_opacity(0.4)
                        .with_effects([
                            vfx.CrossFadeIn(0.1),
                            vfx.CrossFadeOut(0.3),
                        ])
                    )
                    clips.append(bottom_accent)

                    # Lighten both panels slightly (wide shot = both visible)
                    both_lift = ColorClip(
                        size=(target_w, target_h), color=(255, 255, 255),
                        duration=wide_dur,
                    )
                    both_lift = (
                        both_lift
                        .with_start(wide_start)
                        .with_position((0, 0))
                        .with_opacity(0.02)
                        .with_effects([
                            vfx.CrossFadeIn(0.1),
                            vfx.CrossFadeOut(0.35),
                        ])
                    )
                    clips.append(both_lift)
                except Exception:
                    pass

        # ── 3. SNAP ZOOM: High-emotion moments ─────────────────
        # Quick flash + tighter vignette on the speaker for punch-in
        if emotion in _SNAP_ZOOM_EMOTIONS and (start - last_snap_time) > 2.0:
            last_snap_time = start
            try:
                snap_dur = min(0.6, line_duration * 0.5)
                active_pos = panel_positions.get(character, (0, 0))

                # Brief bright flash (white overlay that fades fast)
                flash = ColorClip(
                    size=(panel_w, panel_h), color=(255, 255, 255),
                    duration=snap_dur,
                )
                flash = (
                    flash
                    .with_start(start)
                    .with_position(active_pos)
                    .with_opacity(0.12)
                    .with_effects([
                        vfx.CrossFadeIn(0.03),
                        vfx.CrossFadeOut(snap_dur * 0.7),
                    ])
                )
                clips.append(flash)

                # Heavier darken on inactive panel during snap zoom
                inactive_char = "NOVA" if character == "SPARKY" else "SPARKY"
                inactive_pos = panel_positions.get(inactive_char, (0, 0))
                snap_dim = ColorClip(
                    size=(panel_w, panel_h), color=(0, 0, 0),
                    duration=snap_dur + 0.3,
                )
                snap_dim = (
                    snap_dim
                    .with_start(start)
                    .with_position(inactive_pos)
                    .with_opacity(0.15)
                    .with_effects([
                        vfx.CrossFadeIn(0.05),
                        vfx.CrossFadeOut(0.25),
                    ])
                )
                clips.append(snap_dim)

                # Tight vignette on active panel for snap zoom
                snap_vignette = _create_panel_vignette(
                    panel_w, panel_h, active_pos,
                    snap_dur + 0.2, start,
                    opacity=0.18, border_fraction=0.22,
                )
                clips.extend(snap_vignette)

                # Accent color border flash on active panel
                border_w = 3
                border_clips = _create_panel_border_flash(
                    panel_w, panel_h, active_pos, accent,
                    snap_dur, start, border_w=border_w,
                )
                clips.extend(border_clips)
            except Exception:
                pass

    print(f"[Podcast] Camera angle cuts: {len(clips)} overlay clips")
    return clips


def _create_panel_vignette(
    panel_w: int, panel_h: int, position: tuple,
    duration: float, start: float,
    opacity: float = 0.10, border_fraction: float = 0.15,
) -> list:
    """
    Create edge-darkening vignette overlays around a panel.

    Simulates the natural lens vignette of a close-up camera shot by
    placing semi-transparent dark strips along the four edges of the panel.

    Args:
        panel_w: Panel width in pixels.
        panel_h: Panel height in pixels.
        position: (x, y) top-left position of the panel on the canvas.
        duration: Duration of the vignette in seconds.
        start: Start time in seconds.
        opacity: Maximum opacity of the vignette edges (0.0–1.0).
        border_fraction: How much of each edge is darkened (fraction of
                         panel dimension, e.g. 0.15 = 15%).

    Returns:
        List of ColorClip overlays (top, bottom, left, right edges).
    """
    clips = []
    px, py = position

    edge_w = max(6, int(panel_w * border_fraction))
    edge_h = max(6, int(panel_h * border_fraction))

    fade_effects = [vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.15)]

    # Top edge
    top = ColorClip(size=(panel_w, edge_h), color=(0, 0, 0), duration=duration)
    top = (
        top.with_start(start)
        .with_position((px, py))
        .with_opacity(opacity)
        .with_effects(fade_effects)
    )
    clips.append(top)

    # Bottom edge
    bot = ColorClip(size=(panel_w, edge_h), color=(0, 0, 0), duration=duration)
    bot = (
        bot.with_start(start)
        .with_position((px, py + panel_h - edge_h))
        .with_opacity(opacity)
        .with_effects(fade_effects)
    )
    clips.append(bot)

    # Left edge
    left = ColorClip(size=(edge_w, panel_h), color=(0, 0, 0), duration=duration)
    left = (
        left.with_start(start)
        .with_position((px, py))
        .with_opacity(opacity * 0.7)
        .with_effects(fade_effects)
    )
    clips.append(left)

    # Right edge
    right = ColorClip(size=(edge_w, panel_h), color=(0, 0, 0), duration=duration)
    right = (
        right.with_start(start)
        .with_position((px + panel_w - edge_w, py))
        .with_opacity(opacity * 0.7)
        .with_effects(fade_effects)
    )
    clips.append(right)

    return clips


def _create_panel_border_flash(
    panel_w: int, panel_h: int, position: tuple,
    color: tuple, duration: float, start: float,
    border_w: int = 3,
) -> list:
    """
    Create a brief colored border flash around a panel.

    Used during snap-zoom moments to draw the eye with a thin accent-colored
    border that appears and fades quickly.

    Args:
        panel_w: Panel width in pixels.
        panel_h: Panel height in pixels.
        position: (x, y) top-left position of the panel on the canvas.
        color: RGB tuple for the border color.
        duration: Duration of the flash in seconds.
        start: Start time in seconds.
        border_w: Border thickness in pixels.

    Returns:
        List of ColorClip overlays forming the border.
    """
    clips = []
    px, py = position
    fade_effects = [vfx.CrossFadeIn(0.03), vfx.CrossFadeOut(duration * 0.6)]

    # Top border
    top = ColorClip(size=(panel_w, border_w), color=color, duration=duration)
    top = top.with_start(start).with_position((px, py)).with_opacity(0.5)
    top = top.with_effects(fade_effects)
    clips.append(top)

    # Bottom border
    bot = ColorClip(size=(panel_w, border_w), color=color, duration=duration)
    bot = bot.with_start(start).with_position((px, py + panel_h - border_w)).with_opacity(0.5)
    bot = bot.with_effects(fade_effects)
    clips.append(bot)

    # Left border
    left = ColorClip(size=(border_w, panel_h), color=color, duration=duration)
    left = left.with_start(start).with_position((px, py)).with_opacity(0.5)
    left = left.with_effects(fade_effects)
    clips.append(left)

    # Right border
    right = ColorClip(size=(border_w, panel_h), color=color, duration=duration)
    right = right.with_start(start).with_position((px + panel_w - border_w, py)).with_opacity(0.5)
    right = right.with_effects(fade_effects)
    clips.append(right)

    return clips


def _create_lower_third_bar(
    target_w: int, target_h: int, total_duration: float,
    niche: str = "ai_trading", title: str = "",
) -> list:
    """
    Create a professional lower-third gradient bar for podcast videos.

    Features:
    - Sleek dark gradient bar across the bottom 12% of the screen
    - Thin accent-colored top border line (2px)
    - Left-to-right gradient sweep (static)
    - Podcast title text in small font at the very bottom

    Returns a list of clips to add to the composition.
    """
    clips = []
    accent = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))
    bar_h = int(target_h * 0.12)
    bar_y = target_h - bar_h

    try:
        # ── 1. Dark gradient bar (PIL rendered) ──────────────
        bar_img = PILImage.new("RGBA", (target_w, bar_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bar_img)

        # Vertical gradient: transparent at top -> dark at bottom
        for y in range(bar_h):
            ratio = y / bar_h
            # Ease-in: starts very transparent, gets opaque toward bottom
            alpha = int(220 * (ratio ** 0.6))
            # Subtle left-to-right gradient sweep using accent color
            for x in range(target_w):
                x_ratio = x / target_w
                # Subtle accent tint that sweeps left to right
                sweep = 0.04 * math.sin(x_ratio * math.pi)
                r = int(min(255, 8 + accent[0] * sweep))
                g = int(min(255, 8 + accent[1] * sweep))
                b = int(min(255, 12 + accent[2] * sweep))
                bar_img.putpixel((x, y), (r, g, b, alpha))

        # ── 2. Accent top border line (2px) ──────────────────
        border_h = 2
        for y in range(border_h):
            for x in range(target_w):
                # Fade border from center outward for elegance
                center_dist = abs(x - target_w / 2) / (target_w / 2)
                fade = 1.0 - center_dist * 0.3
                r = int(accent[0] * fade)
                g = int(accent[1] * fade)
                b = int(accent[2] * fade)
                bar_img.putpixel((x, y), (r, g, b, 180))

        # ── 3. Title text at bottom ──────────────────────────
        if title:
            display_title = title.upper()
            if len(display_title) > 50:
                display_title = display_title[:47] + "..."

            title_fs = max(14, int(target_w * 0.022))
            try:
                title_font = ImageFont.truetype(CAPTION_FONT, title_fs)
            except Exception:
                title_font = ImageFont.load_default()

            # Measure text
            bbox = draw.textbbox((0, 0), display_title, font=title_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # Center horizontally, place near bottom of bar
            tx = (target_w - tw) // 2
            ty = bar_h - th - int(bar_h * 0.15)

            # Text shadow
            draw.text((tx + 1, ty + 1), display_title, font=title_font,
                       fill=(0, 0, 0, 200))
            # Title text in muted white
            draw.text((tx, ty), display_title, font=title_font,
                       fill=(200, 200, 210, 180))

        # ── 4. Thin separator dots (decorative) ──────────────
        dot_y = int(bar_h * 0.25)
        dot_spacing = max(30, target_w // 25)
        dot_r = 1
        for dx in range(int(target_w * 0.15), int(target_w * 0.85), dot_spacing):
            draw.ellipse(
                [dx - dot_r, dot_y - dot_r, dx + dot_r, dot_y + dot_r],
                fill=(accent[0], accent[1], accent[2], 50),
            )

        # Convert to clip
        bar_arr = np.array(bar_img)
        rgb = bar_arr[:, :, :3]
        alpha = bar_arr[:, :, 3].astype(float) / 255.0

        bar_clip = ImageClip(rgb, duration=total_duration)
        bar_mask = ImageClip(alpha, is_mask=True, duration=total_duration)
        bar_clip = bar_clip.with_mask(bar_mask)
        bar_clip = bar_clip.with_position((0, bar_y))
        bar_clip = bar_clip.with_effects([vfx.CrossFadeIn(1.0)])
        clips.append(bar_clip)

        print(f"[Podcast] Lower third bar: {target_w}x{bar_h} at y={bar_y}")

    except Exception as e:
        print(f"[Podcast] Lower third bar failed: {e}")

    return clips


def _create_top_live_bar(
    target_w: int, target_h: int, total_duration: float,
    niche: str = "ai_trading",
) -> list:
    """
    Create a top overlay bar with 'LIVE' badge and niche name.

    Features:
    - Thin gradient overlay at the very top (top 5% of screen)
    - 'LIVE' text with a red dot badge (rounded rect)
    - Niche name displayed next to the LIVE badge
    - Professional broadcast/stream aesthetic

    Returns a list of clips to add to the composition.
    """
    clips = []
    accent = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))
    bar_h = int(target_h * 0.05)

    # Format niche name for display
    niche_display = niche.replace("_", " ").upper()

    try:
        # ── 1. Top gradient overlay ──────────────────────────
        bar_img = PILImage.new("RGBA", (target_w, bar_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bar_img)

        # Gradient: dark at top -> transparent at bottom
        for y in range(bar_h):
            ratio = y / bar_h
            alpha = int(160 * (1.0 - ratio ** 0.5))
            draw.line([(0, y), (target_w, y)], fill=(5, 5, 15, alpha))

        # ── 2. LIVE badge (red rounded rectangle) ────────────
        badge_fs = max(12, int(target_w * 0.02))
        try:
            badge_font = ImageFont.truetype(CAPTION_FONT, badge_fs)
        except Exception:
            badge_font = ImageFont.load_default()

        live_text = "LIVE"
        bbox = draw.textbbox((0, 0), live_text, font=badge_font)
        lt_w = bbox[2] - bbox[0]
        lt_h = bbox[3] - bbox[1]

        # Badge dimensions
        badge_pad_x = int(lt_w * 0.5)
        badge_pad_y = int(lt_h * 0.3)
        badge_w = lt_w + badge_pad_x * 2
        badge_h = lt_h + badge_pad_y * 2
        badge_x = int(target_w * 0.04)
        badge_y = (bar_h - badge_h) // 2

        # Red rounded rectangle background
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=max(4, badge_h // 3),
            fill=(220, 30, 30, 220),
        )

        # Red dot (pulsing indicator circle) — left of text
        dot_r = max(3, badge_fs // 5)
        dot_cx = badge_x + badge_pad_x + dot_r
        dot_cy = badge_y + badge_h // 2
        draw.ellipse(
            [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
            fill=(255, 80, 80, 255),
        )
        # Bright center for glow effect
        inner_r = max(1, dot_r - 1)
        draw.ellipse(
            [dot_cx - inner_r, dot_cy - inner_r, dot_cx + inner_r, dot_cy + inner_r],
            fill=(255, 200, 200, 255),
        )

        # LIVE text (white, bold) — after dot
        text_x = dot_cx + dot_r + int(dot_r * 1.5)
        text_y = badge_y + badge_pad_y
        draw.text((text_x, text_y), live_text, font=badge_font, fill=(255, 255, 255, 255))

        # ── 3. Niche name next to badge ──────────────────────
        niche_fs = max(10, int(target_w * 0.018))
        try:
            niche_font = ImageFont.truetype(CAPTION_FONT, niche_fs)
        except Exception:
            niche_font = ImageFont.load_default()

        niche_x = badge_x + badge_w + int(target_w * 0.025)
        niche_y = (bar_h - niche_fs) // 2

        # Accent colored niche name
        draw.text((niche_x + 1, niche_y + 1), niche_display, font=niche_font,
                   fill=(0, 0, 0, 150))
        draw.text((niche_x, niche_y), niche_display, font=niche_font,
                   fill=(accent[0], accent[1], accent[2], 220))

        # ── 4. Thin accent line at bottom edge ───────────────
        line_y = bar_h - 1
        for x in range(target_w):
            # Fade from edges
            edge_dist = min(x, target_w - x) / (target_w * 0.3)
            fade = min(1.0, edge_dist)
            r = int(accent[0] * fade * 0.4)
            g = int(accent[1] * fade * 0.4)
            b = int(accent[2] * fade * 0.4)
            bar_img.putpixel((x, line_y), (r, g, b, int(120 * fade)))

        # Convert to clip
        bar_arr = np.array(bar_img)
        rgb = bar_arr[:, :, :3]
        alpha_ch = bar_arr[:, :, 3].astype(float) / 255.0

        top_clip = ImageClip(rgb, duration=total_duration)
        top_mask = ImageClip(alpha_ch, is_mask=True, duration=total_duration)
        top_clip = top_clip.with_mask(top_mask)
        top_clip = top_clip.with_position((0, 0))
        top_clip = top_clip.with_effects([vfx.CrossFadeIn(0.5)])
        clips.append(top_clip)

        print(f"[Podcast] Top LIVE bar: {target_w}x{bar_h} ({niche_display})")

    except Exception as e:
        print(f"[Podcast] Top LIVE bar failed: {e}")

    return clips


async def assemble_podcast_video(
    line_timings: list,
    audio_path: str,
    character_images: dict,
    output_path: str | Path,
    format_type: str = "youtube_shorts",
    music_volume: float = 0.06,
    niche: str = "ai_trading",
    title: str = "",
    script: dict = None,
    animated_avatars: dict = None,
) -> dict:
    """
    Assemble a split-screen podcast debate video.

    Layer stack (bottom to top):
    1. Split background (dark, color-tinted per character)
    2. Character panels (images + name labels + colored rings)
    3. Center divider line (niche accent color)
    4. Active speaker glow (red/blue per character)
    5. Section title overlays (THE TWIST, ROUND 1, etc.)
    6. Emotion tag indicators (floating [SHOCKED] etc.)
    7. Caption bar at bottom (red for SPARKY, blue for NOVA)
    8. Lower third bar (dark gradient + title)
    9. Top LIVE bar (broadcast aesthetic)
    10. Progress bar
    11. Hook overlay (first 3s)
    """
    settings = VIDEO_SETTINGS[format_type]
    target_w = settings["width"]
    target_h = settings["height"]
    fps = settings["fps"]
    is_portrait = target_h > target_w

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[Podcast] Assembling split-screen video ({target_w}x{target_h})...")

    # Load audio
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    max_dur = settings.get("duration_target")
    if max_dur and total_duration > max_dur + 5:
        audio = audio.subclipped(0, max_dur)
        total_duration = max_dur

    # ── Layout Calculation ────────────────────────────────
    # Detect if we have animated D-ID avatars
    sparky_animated = None
    nova_animated = None
    has_animated = False
    if animated_avatars:
        sparky_animated = animated_avatars.get("sparky")
        nova_animated = animated_avatars.get("nova")
        has_animated = bool(sparky_animated or nova_animated)
        if has_animated:
            print(f"[Podcast] Using D-ID animated avatars: SPARKY={'YES' if sparky_animated else 'NO'} NOVA={'YES' if nova_animated else 'NO'}")

    if is_portrait:
        # 9:16 vertical — top/bottom split
        panel_w = target_w
        panel_h = int(target_h * 0.42)
        gap = 4 if not has_animated else 2  # Thinner gap for animated
        sparky_pos = (0, 0)
        nova_pos = (0, panel_h + gap)
    else:
        # 16:9 landscape — side by side (same room feel)
        panel_w = int(target_w * 0.50)  # Each gets exactly half
        panel_h = target_h
        gap = 0  # No gap — seamless same room
        sparky_pos = (0, 0)
        nova_pos = (panel_w, 0)

    # ── Background — Shared Studio ─────────────────────────
    # Single unified studio background so it feels like ONE room
    try:
        studio_bg_arr = _create_studio_background(target_w, target_h, "SPARKY", niche)
        bg = ImageClip(studio_bg_arr, duration=total_duration)
    except Exception:
        bg = ColorClip(size=(target_w, target_h), color=(5, 5, 15), duration=total_duration)

    # ── Character Panels ──────────────────────────────────
    sparky_clips = _create_character_panel(
        character_images.get("sparky"), panel_w, panel_h, "SPARKY", total_duration,
        niche=niche, animated_video=sparky_animated)
    sparky_comp = CompositeVideoClip(sparky_clips, size=(panel_w, panel_h))
    sparky_comp = sparky_comp.with_position(sparky_pos).with_duration(total_duration)

    nova_clips = _create_character_panel(
        character_images.get("nova"), panel_w, panel_h, "NOVA", total_duration,
        niche=niche, animated_video=nova_animated)
    nova_comp = CompositeVideoClip(nova_clips, size=(panel_w, panel_h))
    nova_comp = nova_comp.with_position(nova_pos).with_duration(total_duration)

    # ── Center Divider (subtle for same-room feel) ─────────
    accent = NICHE_CAPTION_COLORS.get(niche, (0, 255, 136))
    if is_portrait:
        # Thin subtle divider for portrait
        divider = ColorClip(size=(target_w, gap), color=accent, duration=total_duration)
        divider = divider.with_position((0, panel_h)).with_opacity(0.3)
    else:
        # Very subtle center line for landscape (same room feel)
        dx = panel_w - 1
        divider = ColorClip(size=(2, target_h), color=accent, duration=total_duration)
        divider = divider.with_position((dx, 0)).with_opacity(0.15)

    # ── Active Speaker Glow ───────────────────────────────
    glow_clips = _create_active_speaker_glow(
        line_timings, panel_w, panel_h, target_w, target_h, is_portrait)

    # ── Section Titles ────────────────────────────────────
    section_clips = []
    seen_sections = set()
    for timing in line_timings:
        sec = timing.get("section", "")
        if sec and sec not in seen_sections:
            seen_sections.add(sec)
            section_clips.extend(_create_section_title_overlay(
                sec, max(0, timing["start"] - 0.5), target_w, target_h, niche))

    # ── Emotion Tags (premium styled badges for ALL 15 emotions) ─
    emotion_clips = []
    for timing in line_timings:
        em = timing.get("emotion", "")
        if em and em in EMOTION_BADGE_STYLES:
            try:
                em_duration = min(2.5, timing["end"] - timing["start"])
                badge_arr = _create_emotion_badge(em)
                em_clip = ImageClip(badge_arr, duration=em_duration)

                if is_portrait:
                    ex = int(target_w * 0.62)
                    ey = int(panel_h * 0.12) if timing["character"] == "SPARKY" else int(panel_h + 4 + panel_h * 0.12)
                else:
                    ex = int(panel_w * 0.08) if timing["character"] == "SPARKY" else int(panel_w + target_w * 0.04 + panel_w * 0.08)
                    ey = int(target_h * 0.06)
                em_clip = em_clip.with_position((ex, ey)).with_start(timing["start"])
                em_clip = em_clip.with_effects([vfx.CrossFadeIn(0.08), vfx.CrossFadeOut(0.25)])
                emotion_clips.append(em_clip)
            except Exception:
                pass

    # ── Podcast Captions ──────────────────────────────────
    caption_clips = _create_podcast_captions(line_timings, target_w, target_h, niche)
    print(f"[Podcast] Captions: {len(caption_clips)} phrases")

    # ── Hook Overlay ──────────────────────────────────────
    hook_clips = _create_hook_overlay(title, target_w, target_h, 3.0, niche) if title else []

    # ── Camera Angle Cuts ─────────────────────────────────
    camera_cuts = []
    try:
        camera_cuts = _create_camera_angle_cuts(
            line_timings,
            panel_positions={"SPARKY": sparky_pos, "NOVA": nova_pos},
            panel_sizes={"panel_w": panel_w, "panel_h": panel_h},
            target_w=target_w, target_h=target_h,
            total_duration=total_duration, niche=niche,
        )
    except Exception as e:
        print(f"[Podcast] Camera angle cuts failed: {e}")

    # ── Progress Bar ──────────────────────────────────────
    progress_clips = []
    try:
        progress_clips = create_video_progress_bar(total_duration, target_w, target_h, niche)
    except Exception:
        pass

    # ── Lower Third Bar (bottom 12%) ─────────────────────
    lower_third_clips = []
    try:
        lower_third_clips = _create_lower_third_bar(
            target_w, target_h, total_duration, niche=niche, title=title)
    except Exception as e:
        print(f"[Podcast] Lower third bar failed: {e}")

    # ── Top LIVE Bar (top 5%) ────────────────────────────
    top_bar_clips = []
    try:
        top_bar_clips = _create_top_live_bar(
            target_w, target_h, total_duration, niche=niche)
    except Exception as e:
        print(f"[Podcast] Top LIVE bar failed: {e}")

    # ── Compose ───────────────────────────────────────────
    all_clips = (
        [bg, sparky_comp, nova_comp, divider]
        + glow_clips + camera_cuts + section_clips + emotion_clips
        + lower_third_clips + top_bar_clips
        + progress_clips + hook_clips + caption_clips
    )
    video = CompositeVideoClip(all_clips, size=(target_w, target_h))

    # ── Audio Mixing ──────────────────────────────────────
    audio_tracks = [audio]

    # Background music
    music_path = _get_music_track()
    if music_path:
        try:
            music = AudioFileClip(music_path)
            if music.duration < total_duration:
                loops = int(total_duration / music.duration) + 1
                ml = [music] + [AudioFileClip(music_path) for _ in range(loops - 1)]
                from moviepy import concatenate_audioclips
                music = concatenate_audioclips(ml)
            music = music.subclipped(0, total_duration).with_volume_scaled(music_volume)
            audio_tracks.append(music)
        except Exception as e:
            print(f"[Podcast] Music failed: {e}")

    # Podcast SFX — section transitions + emotion reactions
    try:
        from modules.sfx_manager import generate_podcast_sfx
        sfx_placements = await generate_podcast_sfx(line_timings)
        for sfx in sfx_placements:
            try:
                sfx_clip = AudioFileClip(sfx["sfx_path"])
                sfx_clip = sfx_clip.with_start(max(0, sfx["start_time"]))
                sfx_clip = sfx_clip.with_volume_scaled(sfx.get("volume", 0.15))
                audio_tracks.append(sfx_clip)
            except Exception:
                pass
        if sfx_placements:
            print(f"[Podcast] Mixed {len(sfx_placements)} SFX into audio")
    except Exception as e:
        print(f"[Podcast] SFX mixing failed: {e}")

    final_audio = CompositeAudioClip(audio_tracks) if len(audio_tracks) > 1 else audio
    video = video.with_audio(final_audio).with_duration(total_duration)

    # ── Export ────────────────────────────────────────────
    print(f"[Podcast] Rendering {output_path.name} ({total_duration:.0f}s)...")
    # temp_audiofile_path must be a DIRECTORY in MoviePy v2
    # Use unique temp dir to avoid Windows PermissionError (WinError 32)
    import tempfile, time, gc
    temp_audio_dir = os.path.join(
        tempfile.gettempdir(), f"mpy_podcast_{int(time.time())}"
    )
    os.makedirs(temp_audio_dir, exist_ok=True)
    video.write_videofile(
        str(output_path), fps=fps, codec="libx264", audio_codec="aac",
        audio_bitrate="192k", bitrate="8000k", preset="medium",
        threads=4, logger=None, temp_audiofile_path=temp_audio_dir,
    )

    video.close()
    audio.close()
    gc.collect()
    # Clean up temp audio dir with retry (Windows file lock delay)
    import shutil
    for _attempt in range(5):
        try:
            time.sleep(0.5)
            if os.path.exists(temp_audio_dir):
                shutil.rmtree(temp_audio_dir, ignore_errors=True)
            break
        except (PermissionError, OSError):
            time.sleep(1)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[Podcast] Done: {output_path.name} ({total_duration:.0f}s, {file_size_mb:.1f}MB)")

    return {
        "output_path": str(output_path),
        "duration": total_duration,
        "format_type": format_type,
        "file_size_mb": file_size_mb,
        "resolution": f"{target_w}x{target_h}",
        "line_count": len(line_timings),
    }


# CLI test
if __name__ == "__main__":
    import asyncio
    from config import OUTPUT_DIR

    async def test():
        print("[Assembler] Module loaded successfully (MoviePy v2)")
        print(f"[Assembler] Available formats: {list(VIDEO_SETTINGS.keys())}")
        print("[Assembler] Podcast split-screen assembler: READY")

    asyncio.run(test())
