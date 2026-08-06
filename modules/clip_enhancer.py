"""
Clip Enhancer — cleans up soft/warped AI video frames.

Per-frame pipeline:
  1. GFPGAN v1.4 — restores faces (fixes the "melty" AI/interpolation faces)
  2. Real-ESRGAN x2 — upscales the whole frame with detail (sharp background)
  3. Resize to the target output resolution (e.g. 1080x1920)

Loaded once, applied to a batch of clips, then unloaded to free VRAM.
Runs AFTER SVD-XT is unloaded so the two models never share VRAM.
"""
import gc
import subprocess
import tempfile
from pathlib import Path

_gfpgan = None

GFPGAN_MODEL = "assets/models/GFPGANv1.4.pth"
ESRGAN_MODEL = "assets/models/RealESRGAN_x2plus.pth"


def _load_enhancer():
    """Load GFPGAN (with Real-ESRGAN background upsampler) once."""
    global _gfpgan
    if _gfpgan is not None:
        return _gfpgan

    import torch
    from gfpgan import GFPGANer

    bg_upsampler = None
    try:
        if Path(ESRGAN_MODEL).exists():
            from realesrgan import RealESRGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet

            esr = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                          num_block=23, num_grow_ch=32, scale=2)
            bg_upsampler = RealESRGANer(
                scale=2,
                model_path=ESRGAN_MODEL,
                model=esr,
                tile=400,          # tile to stay within 11GB VRAM
                tile_pad=10,
                pre_pad=0,
                half=torch.cuda.is_available(),
            )
            print("[Enhance] Real-ESRGAN x2 background upsampler loaded")
    except Exception as e:
        print(f"[Enhance] Real-ESRGAN unavailable ({str(e)[:80]}); GFPGAN will resize bg")

    _gfpgan = GFPGANer(
        model_path=GFPGAN_MODEL,
        upscale=2,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=bg_upsampler,
    )
    print("[Enhance] GFPGAN v1.4 loaded")
    return _gfpgan


def unload_enhancer():
    global _gfpgan
    if _gfpgan is not None:
        del _gfpgan
        _gfpgan = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        print("[Enhance] Enhancer unloaded, VRAM freed")


def enhance_clip(clip_path: str, target_w: int, target_h: int, fps: int | None = None) -> bool:
    """
    Restore + upscale every frame of a clip in place. Returns True on success.
    """
    import cv2
    import numpy as np

    clip_path = Path(clip_path)
    restorer = _load_enhancer()

    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        print(f"[Enhance] Cannot open {clip_path.name}")
        return False
    src_fps = fps or cap.get(cv2.CAP_PROP_FPS) or 24

    frames_dir = Path(tempfile.mkdtemp(prefix="enh_"))
    idx = 0
    try:
        while True:
            ret, frame = cap.read()  # BGR
            if not ret:
                break
            try:
                _, _, restored = restorer.enhance(
                    frame, has_aligned=False, only_center_face=False, paste_back=True
                )
            except Exception as e:
                print(f"[Enhance] frame {idx} failed ({str(e)[:60]}); using resize")
                restored = None
            if restored is None:
                restored = frame
            # Normalize to target resolution
            if restored.shape[1] != target_w or restored.shape[0] != target_h:
                restored = cv2.resize(restored, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(str(frames_dir / f"f_{idx:05d}.png"), restored)
            idx += 1
        cap.release()

        if idx == 0:
            return False

        # Re-encode enhanced frames back to a clip (silent — clips carry no audio)
        tmp_out = clip_path.with_suffix(".enh.mp4")
        r = subprocess.run(
            ["ffmpeg", "-y", "-framerate", f"{src_fps}",
             "-i", str(frames_dir / "f_%05d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-preset", "slow", "-crf", "16", str(tmp_out)],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and tmp_out.exists() and tmp_out.stat().st_size > 0:
            tmp_out.replace(clip_path)
            return True
        print(f"[Enhance] re-encode failed: {r.stderr[-200:]}")
        return False
    finally:
        cap.release()
        for f in frames_dir.glob("*.png"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            frames_dir.rmdir()
        except Exception:
            pass


def enhance_clips(clip_paths: list[str], target_w: int, target_h: int) -> int:
    """Enhance a batch of clips. Loads once, unloads at the end. Returns count enhanced."""
    if not clip_paths:
        return 0
    done = 0
    try:
        for p in clip_paths:
            if p and Path(p).exists():
                if enhance_clip(p, target_w, target_h):
                    done += 1
                    print(f"[Enhance] {Path(p).name} -> restored + {target_w}x{target_h}")
    finally:
        unload_enhancer()
    return done
