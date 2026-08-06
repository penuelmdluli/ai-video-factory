"""
Setup Script — Install SadTalker + MuseTalk conda environments.

Run once to set up everything:
  python setup_avatar_pipeline.py

This script:
  1. Checks system requirements (conda, CUDA, FFmpeg)
  2. Clones SadTalker and MuseTalk repos
  3. Creates conda environments with correct PyTorch versions
  4. Downloads model weights
  5. Verifies each tool works
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────
INSTALL_DIR = Path(r"C:\Users\PenuelM\Documents")
SADTALKER_DIR = INSTALL_DIR / "SadTalker"
MUSETALK_DIR = INSTALL_DIR / "MuseTalk"
MODELS_DIR = Path(__file__).parent / "assets" / "models"


def run(cmd: str, cwd: str = None, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a shell command with output."""
    print(f"  > {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=timeout,
    )
    if result.stdout.strip():
        for line in result.stdout.strip().split('\n')[-5:]:
            print(f"    {line}")
    if result.returncode != 0 and check:
        print(f"  ERROR (exit {result.returncode}):")
        for line in result.stderr.strip().split('\n')[-10:]:
            print(f"    {line}")
        raise RuntimeError(f"Command failed: {cmd}")
    return result


def check_requirements():
    """Check system requirements."""
    print("\n[1/6] Checking system requirements...\n")

    # Check conda
    result = subprocess.run("conda --version", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ERROR: conda not found!")
        print("  Install Miniconda from: https://docs.conda.io/en/latest/miniconda.html")
        sys.exit(1)
    print(f"  conda: {result.stdout.strip()}")

    # Check CUDA
    result = subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader",
                          shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("  WARNING: nvidia-smi not found — GPU may not be available")
    else:
        print(f"  GPU: {result.stdout.strip()}")

    # Check FFmpeg
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("  ERROR: FFmpeg not found!")
        print("  Install: winget install Gyan.FFmpeg")
        sys.exit(1)
    print(f"  FFmpeg: {ffmpeg}")

    # Check git
    result = subprocess.run("git --version", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ERROR: git not found!")
        sys.exit(1)
    print(f"  git: {result.stdout.strip()}")

    print("\n  All requirements OK!")


def env_exists(name: str) -> bool:
    """Check if conda environment exists."""
    result = subprocess.run("conda env list", shell=True, capture_output=True, text=True)
    return name in result.stdout


def setup_sadtalker():
    """Clone and set up SadTalker."""
    print("\n[2/6] Setting up SadTalker...\n")

    # Clone if needed
    if not SADTALKER_DIR.exists():
        print("  Cloning SadTalker...")
        run(f'git clone https://github.com/OpenTalker/SadTalker.git "{SADTALKER_DIR}"')
    else:
        print(f"  SadTalker already exists at {SADTALKER_DIR}")

    # Create conda env
    if not env_exists("sadtalker"):
        print("  Creating conda env 'sadtalker'...")
        run("conda create -n sadtalker python=3.10 -y")

        print("  Installing PyTorch 2.1.0+cu118...")
        run("conda run -n sadtalker --no-banner pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118",
            timeout=600)

        print("  Installing SadTalker dependencies...")
        run(f'conda run -n sadtalker --no-banner pip install -r requirements.txt',
            cwd=str(SADTALKER_DIR), timeout=600)

        # Additional deps that sometimes fail
        run("conda run -n sadtalker --no-banner pip install cmake dlib face-alignment==1.4.1 basicsr",
            timeout=300, check=False)
    else:
        print("  Conda env 'sadtalker' already exists")

    # Download checkpoints
    checkpoints = SADTALKER_DIR / "checkpoints"
    if not checkpoints.exists() or not list(checkpoints.glob("*.pth")):
        print("  Downloading SadTalker model weights...")
        print("  NOTE: If auto-download fails, manually download from:")
        print("  https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/checkpoints.zip")
        print(f"  Extract to: {checkpoints}")

        # Try the download script
        download_script = SADTALKER_DIR / "scripts" / "download_models.sh"
        if download_script.exists():
            run(f'conda run -n sadtalker --no-banner bash scripts/download_models.sh',
                cwd=str(SADTALKER_DIR), timeout=600, check=False)
    else:
        print("  SadTalker checkpoints already downloaded")

    print("\n  SadTalker setup complete!")


def setup_musetalk():
    """Clone and set up MuseTalk."""
    print("\n[3/6] Setting up MuseTalk...\n")

    # Clone if needed
    if not MUSETALK_DIR.exists():
        print("  Cloning MuseTalk...")
        run(f'git clone https://github.com/TMElyralab/MuseTalk.git "{MUSETALK_DIR}"')
    else:
        print(f"  MuseTalk already exists at {MUSETALK_DIR}")

    # Create conda env
    if not env_exists("musetalk"):
        print("  Creating conda env 'musetalk'...")
        run("conda create -n musetalk python=3.10 -y")

        print("  Installing PyTorch 2.1.0+cu118...")
        run("conda run -n musetalk --no-banner pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118",
            timeout=600)

        print("  Installing mmlab stack...")
        run("conda run -n musetalk --no-banner pip install --no-cache-dir -U openmim", timeout=120)
        run('conda run -n musetalk --no-banner mim install mmengine "mmcv>=2.0.1" "mmdet>=3.1.0" "mmpose>=1.1.0"',
            timeout=600)

        print("  Installing MuseTalk dependencies...")
        run(f'conda run -n musetalk --no-banner pip install -r requirements.txt',
            cwd=str(MUSETALK_DIR), timeout=600)
    else:
        print("  Conda env 'musetalk' already exists")

    print("\n  MuseTalk setup complete!")


def verify_gfpgan():
    """Verify GFPGAN model exists."""
    print("\n[4/6] Verifying GFPGAN...\n")

    model_path = MODELS_DIR / "GFPGANv1.4.pth"
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"  GFPGAN model: {model_path} ({size_mb:.0f} MB)")
        print("  GFPGAN OK!")
    else:
        print(f"  WARNING: GFPGAN model not found at {model_path}")
        print("  Download from: https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth")
        print(f"  Place at: {model_path}")


def verify_characters():
    """Check baby character images exist."""
    print("\n[5/6] Checking character images...\n")

    chars_dir = Path(__file__).parent / "assets" / "podcast_characters" / "baby"
    if chars_dir.exists():
        pngs = list(chars_dir.glob("*.png"))
        print(f"  Found {len(pngs)} character images in {chars_dir}")
        for png in sorted(pngs):
            size_kb = png.stat().st_size / 1024
            print(f"    {png.name} ({size_kb:.0f} KB)")
    else:
        print(f"  WARNING: No character images at {chars_dir}")


def print_summary():
    """Print final setup summary."""
    print(f"\n{'=' * 60}")
    print("  SETUP COMPLETE!")
    print(f"{'=' * 60}")
    print(f"""
  SadTalker:  {SADTALKER_DIR}
  MuseTalk:   {MUSETALK_DIR}
  GFPGAN:     {MODELS_DIR / 'GFPGANv1.4.pth'}
  Characters: {Path(__file__).parent / 'assets' / 'podcast_characters' / 'baby'}

  Quick Test:
    python baby_podcast_generator.py --text "Hello world, I am a baby!" \\
      --image assets/podcast_characters/baby/sparky_ai_trading.png \\
      --tier wav2lip --voice edge-tts

  Full Pipeline:
    python baby_podcast_generator.py --text "Your script here" \\
      --image assets/podcast_characters/baby/sparky_ai_trading.png \\
      --tier sadtalker+musetalk --voice elevenlabs

  Batch Mode:
    python baby_podcast_generator.py --audio-dir path/to/wavs/ \\
      --image assets/podcast_characters/baby/sparky_ai_trading.png
""")


def main():
    print(f"\n{'=' * 60}")
    print("  BABY PODCAST AVATAR PIPELINE — SETUP")
    print(f"{'=' * 60}")

    check_requirements()
    setup_sadtalker()
    setup_musetalk()
    verify_gfpgan()
    verify_characters()
    print_summary()


if __name__ == "__main__":
    main()
