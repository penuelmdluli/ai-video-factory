# RunPod Wan 2.1 T2V Serverless Worker — Build & Deploy

Cheap serverless video (~$0.02–0.05/clip vs WaveSpeed's $0.15). Self-contained
image with Wan 2.1 T2V 14B fp8 models baked in (fast cold starts, no volume).

## 1. Build + push (you — needs Docker + a registry login)

```bash
cd C:/Users/PenuelM/Documents/ai-video-factory/runpod-worker

# Log in to your registry (Docker Hub shown; use your own username)
docker login

# Build — downloads ~26GB of models during build, so this takes a while
docker build -t YOUR_DOCKERHUB_USER/genesis-wan21-t2v:latest .

# Push (~30GB, one-time; depends on your upload speed)
docker push YOUR_DOCKERHUB_USER/genesis-wan21-t2v:latest
```

Tell me `YOUR_DOCKERHUB_USER/genesis-wan21-t2v:latest` when the push finishes and I'll do step 2–3 via the RunPod API.

## 2. Deploy the serverless endpoint (me, via API)
- Image: `YOUR_DOCKERHUB_USER/genesis-wan21-t2v:latest`
- GPU: RTX 4090 (cheapest that fits fp8 14B) → ~$1.10/hr
- Workers: min 0 (scale-to-zero), max 1 · Idle timeout 10s · FlashBoot ON
- No network volume (models baked in)

## 3. Wire + test (me)
- Point `modules/runpod_video.py` at the new endpoint (`RUNPOD_ENDPOINT_ID`).
- Generate a war clip, verify it matches the prompt + measure real cost.
- Keep `I2V_BACKEND=wavespeed` (default) until you approve the switch.

## Notes
- Model: **Wan 2.1 T2V 14B fp8** (single 14GB file — the current Wan 2.2 14B is a
  28GB two-model MoE; 2.1 is the cheaper/simpler choice with near-identical quality).
- This is **text-to-video**: the scene action-prompt → clip (no input image needed).
- Filenames in `download_models.sh` are matched exactly to the workflow node inputs
  in `modules/runpod_video.py` — don't rename one without the other.
