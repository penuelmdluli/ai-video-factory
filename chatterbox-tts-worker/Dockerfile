# Chatterbox-TTS RunPod serverless worker (warm/expressive self-hosted voices).
# Model weights auto-download on first run into the mounted /runpod-volume (HF cache),
# so keep this image lean and attach a network volume to the endpoint.
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV HF_HOME=/runpod-volume/hf \
    HUGGINGFACE_HUB_CACHE=/runpod-volume/hf/hub \
    TORCH_HOME=/runpod-volume/torch \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY handler.py .
# Optional reference clips for voice cloning (warm_teacher.wav / news_anchor.wav)
COPY voices/ /app/voices/

CMD ["python", "-u", "handler.py"]
