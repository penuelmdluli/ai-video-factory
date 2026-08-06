# Baby Podcast AI Avatar Pipeline — Installation Guide

## System Requirements Verified
- GPU: NVIDIA RTX 2080 Ti (11GB VRAM)
- Python: 3.12.5 (main env)
- PyTorch: 2.6.0+cu124
- CUDA: 12.4 (driver 581.57)
- FFmpeg: 8.0 (already installed)
- Existing models: wav2lip_gan.pth, GFPGANv1.4.pth

---

## CRITICAL: Environment Strategy

SadTalker and MuseTalk require **older PyTorch versions** that CONFLICT with your
main env (PyTorch 2.6.0+cu124). We use **separate conda environments** and call
them as subprocesses from the main pipeline.

```
Main env (Python 3.12, torch 2.6.0+cu124) — orchestrator
  └── Calls SadTalker env (Python 3.10, torch 2.1.0+cu118) — subprocess
  └── Calls MuseTalk env (Python 3.10, torch 2.0.1+cu118) — subprocess
  └── GFPGAN runs in main env (already installed)
```

---

## Step 1: Install Conda (if not already installed)

```powershell
# Download Miniconda from:
# https://docs.conda.io/en/latest/miniconda.html
# Run the installer, add to PATH when prompted
conda --version  # verify
```

---

## Step 2: Install SadTalker

```powershell
# Clone SadTalker
cd C:\Users\PenuelM\Documents\
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker

# Create isolated environment
conda create -n sadtalker python=3.10 -y
conda activate sadtalker

# Install PyTorch (cu118 works best for RTX 2080 Ti with SadTalker)
pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118

# Install SadTalker dependencies
pip install -r requirements.txt

# Download model weights (run from SadTalker dir)
bash scripts/download_models.sh
# OR on Windows PowerShell, manually download:
# https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/checkpoints.zip
# Extract to SadTalker/checkpoints/

# Verify installation
python inference.py --help
```

**Common Windows Errors:**
- `dlib` build fails → `pip install cmake` first, then `pip install dlib`
- `face_alignment` error → `pip install face-alignment==1.4.1`
- CUDA OOM → Add `--preprocess crop` instead of `full` (uses less VRAM)
- `No module named 'basicsr'` → `pip install basicsr`

**Verify SadTalker works:**
```powershell
conda activate sadtalker
cd C:\Users\PenuelM\Documents\SadTalker
python inference.py ^
  --driven_audio examples/driven_audio/bus_chinese.wav ^
  --source_image examples/source_image/art_0.png ^
  --enhancer gfpgan ^
  --preprocess full ^
  --still ^
  --result_dir results/test
# Should produce a video in results/test/
```

---

## Step 3: Install MuseTalk 1.5

```powershell
cd C:\Users\PenuelM\Documents\
git clone https://github.com/TMElyralab/MuseTalk.git
cd MuseTalk

# Create isolated environment
conda create -n musetalk python=3.10 -y
conda activate musetalk

# Install PyTorch (cu118 for compatibility)
pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118

# Install mmlab dependencies
pip install --no-cache-dir -U openmim
mim install mmengine "mmcv>=2.0.1" "mmdet>=3.1.0" "mmpose>=1.1.0"

# Install MuseTalk requirements
pip install -r requirements.txt

# Download model weights
# MuseTalk auto-downloads on first run, OR manually:
# https://huggingface.co/TMElyralab/MuseTalk
# Place in MuseTalk/models/

# Set FFmpeg path
set FFMPEG_PATH=C:\Users\PenuelM\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin
```

**Common Windows Errors:**
- `mmcv` build fails → Use `mim install mmcv==2.1.0` (specific version)
- `mmpose` ImportError → `pip install mmpose==1.3.1`
- ffmpeg not found → Pass `--ffmpeg_path` explicitly or set env var
- CUDA OOM during inference → Reduce `--batch_size` to 2 (default is 4)

**Verify MuseTalk works:**
```powershell
conda activate musetalk
cd C:\Users\PenuelM\Documents\MuseTalk
python -m scripts.inference --video_path test_video.mp4 --audio_path test_audio.wav
```

---

## Step 4: GFPGAN (Already Installed)

You already have `GFPGANv1.4.pth` in `assets/models/`. The main pipeline
uses it via the existing `local_avatar.py`. No additional setup needed.

To verify:
```python
from gfpgan import GFPGANer
restorer = GFPGANer(
    model_path='assets/models/GFPGANv1.4.pth',
    upscale=1, arch='clean', channel_multiplier=2
)
print("GFPGAN loaded OK")
```

---

## Step 5: Run the Pipeline

After all environments are set up:

```powershell
# From your main project directory
cd C:\Users\PenuelM\Documents\ai-video-factory

# Single video
python baby_podcast_generator.py ^
  --audio path/to/audio.wav ^
  --image assets/podcast_characters/baby/sparky_ai_trading.png

# Batch processing (folder of WAV files)
python baby_podcast_generator.py ^
  --audio-dir path/to/wav_folder ^
  --image assets/podcast_characters/baby/sparky_ai_trading.png

# Full pipeline with ElevenLabs text-to-speech
python baby_podcast_generator.py ^
  --text "Your script text here" ^
  --image assets/podcast_characters/baby/sparky_ai_trading.png ^
  --voice elevenlabs

# Specify pipeline tier
python baby_podcast_generator.py ^
  --audio path/to/audio.wav ^
  --image assets/podcast_characters/baby/sparky_ai_trading.png ^
  --tier sadtalker+musetalk    # or: sadtalker, musetalk, wav2lip, audio-reactive
```

---

## Quality Settings for RTX 2080 Ti (11GB VRAM)

| Tool       | Setting              | Value       | Why                                          |
|------------|----------------------|-------------|----------------------------------------------|
| SadTalker  | --preprocess         | full        | Best quality, fits in 11GB                   |
| SadTalker  | --enhancer           | gfpgan      | Built-in face restoration                    |
| SadTalker  | --still              | (use flag)  | Reduces jitter for cartoon faces             |
| SadTalker  | --expression_scale   | 1.2         | Slightly exaggerated for baby character      |
| MuseTalk   | --batch_size         | 4           | 11GB handles this (reduce to 2 if OOM)       |
| MuseTalk   | --bbox_shift         | 8           | Cartoon baby faces need higher shift         |
| MuseTalk   | float16              | YES         | 11GB is plenty, fp16 is 2x faster           |
| GFPGAN     | upscale              | 1           | Don't upscale, just restore faces            |
| GFPGAN     | model                | v1.4        | Best for cartoon/artistic faces              |
| FFmpeg     | codec                | libx264     | Universal YouTube/TikTok compatibility       |
| FFmpeg     | crf                  | 18          | High quality, reasonable file size           |
| FFmpeg     | preset               | slow        | Better compression for upload                |
| FFmpeg     | resolution           | 1080x1920   | 9:16 vertical for Shorts/TikTok             |
