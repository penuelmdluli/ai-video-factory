# Deploy Wan 2.2 image-to-video on RunPod serverless

All the **code** is already done (`modules/runpod_wan.py`, wired into `visual_fetcher.py`
with LTX/WaveSpeed/stock fallback). This is the **one-time RunPod dashboard part**.
When you finish, tell Claude the endpoint id and it will flip the switch + test.

Result: every channel's video gets Wan 2.2 quality at **GPU-only cost (~$0.05–0.12/clip)**.

---

## 1. Create a network volume  *(RunPod → Storage → Network Volume)*
- **Size:** 100 GB · **Region:** pick one that offers **L40S** GPUs. **Note the region.**
- Cost: ~$5–7/month.

## 2. Spin up a temp pod to load the weights  *(RunPod → Pods → Deploy)*
- Any cheap GPU (RTX 4000 ~$0.20/hr), **attach the network volume** (mount `/workspace`).
- Open a terminal and run (installs hf CLI, downloads the 6 files into the exact folders):

```bash
pip install -U "huggingface_hub[cli]"
cd /workspace && mkdir -p models/diffusion_models models/text_encoders models/vae models/loras
R=Comfy-Org/Wan_2.2_ComfyUI_Repackaged
hf download $R split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors --local-dir /tmp/r
hf download $R split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors  --local-dir /tmp/r
hf download $R split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors              --local-dir /tmp/r
hf download $R split_files/vae/wan_2.1_vae.safetensors                                        --local-dir /tmp/r
mv /tmp/r/split_files/diffusion_models/* models/diffusion_models/
mv /tmp/r/split_files/text_encoders/*    models/text_encoders/
mv /tmp/r/split_files/vae/*              models/vae/
# LightX2V 4-step Lightning LoRAs (folder names in the repo may differ slightly —
# grab the two *i2v* 4-step files, high_noise + low_noise):
hf download lightx2v/Wan2.2-Lightning --local-dir /tmp/lx --include "*i2v*4*step*"
find /tmp/lx -iname "*high*noise*.safetensors" -exec cp {} models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \;
find /tmp/lx -iname "*low*noise*.safetensors"  -exec cp {} models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors \;
ls -lh models/diffusion_models models/text_encoders models/vae models/loras
```
Confirm sizes: two ~14 GB diffusion models, ~6.7 GB text encoder, ~0.25 GB VAE, two ~0.6 GB LoRAs.
**Keep the pod alive** for step 4, then terminate it.

## 3. Create the serverless endpoint  *(RunPod → Serverless → New Endpoint)*
- **Container image:** `runpod/worker-comfyui:5.6.0-base-cuda12.8.1`
- **Attach the same network volume** (mounts at `/runpod-volume`).
- Point ComfyUI at the volume's models: set the endpoint env var
  `COMFY_MODEL_PATH=/runpod-volume/models` **or** follow worker-comfyui's
  [network-volume model docs](https://github.com/runpod-workers/worker-comfyui) —
  verify the worker actually sees the 6 files (this is the one detail to get right).
- **GPU:** L40S 48 GB · **Active workers:** 0 · **Max:** 1–2 · **FlashBoot:** ON · **Timeout:** 600 s
- **Copy the Endpoint ID.**

## 4. Workflow graph
A ready starter graph is committed at `runpod-worker/workflows/wan22-i2v.json` (native
ComfyUI Wan 2.2 i2v + 4-step Lightning, referencing the exact filenames above).
**Recommended:** on the temp pod, open ComfyUI → load the official Wan 2.2 I2V template →
confirm it uses these filenames → **Save (API Format)** and overwrite that file, so it
matches your worker's node set exactly (e.g. native `SaveVideo` vs `VHS_VideoCombine`).
`runpod_wan.py` patches by node *type*, so either graph works.

## 5. Flip the switch  *(local .env)*
```
RUNPOD_WAN_ENDPOINT_ID=<your endpoint id>
I2V_BACKEND=wan
```
Then tell Claude — it runs the smoke test (`python -m modules.runpod_wan <img> out.mp4`),
pins the exact output key from the first live response, and validates one full pipeline
video before all channels go live on Wan.

## Rollback
Set `I2V_BACKEND=wavespeed` (or `runpod`) in `.env`. No code changes — the Wan branch is
additive and every old path is untouched. A dead endpoint auto-degrades Wan → LTX → WaveSpeed → stock.

## Gotchas (from the research)
- Volume **region must match** the endpoint region.
- Use the **Wan 2.1 VAE** with the 2.2 14B i2v models (correct, not a typo).
- Both **high+low noise experts** must load or you get black frames.
- First run is a cold start (weights disk→VRAM, ~1–2 min) even with the volume.
