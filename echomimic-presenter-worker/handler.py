# =============================================================================
# EchoMimicV3 (Flash) — RunPod Serverless handler
#
# Takes a REFERENCE IMAGE of a person (half-body, hands visible) + an AUDIO
# voiceover and returns an mp4 of that person speaking the audio with synced
# lips AND natural co-speech hand/arm gestures (news-presenter style).
#
# This is a faithful port of the model-loading + single-clip inference in
# antgroup/echomimic_v3  ->  infer_flash.py, wrapped so the heavy pipeline is
# built ONCE and reused across warm invocations.
#
#   input:
#     image     (REQUIRED)  base64 | data-uri | http(s) url  -> reference person
#     audio     (REQUIRED)  base64 | data-uri | http(s) url  -> voiceover wav/mp3
#     prompt    (optional)  text, default "A person is speaking."
#     steps     (optional)  int,   default 8   (Flash is tuned for 8)
#     seed      (optional)  int,   default 43
#     guidance  (optional)  float, default 6.0 (text CFG, 3-6)
#     audio_guidance (opt)  float, default 3.0 (audio CFG, 1.8-3)
#     max_seconds    (opt)  float, cap on generated length (default 20s)
#     width/height   (opt)  int,   default 768x768
#
#   returns:
#     {"video_base64": <b64 mp4>, "mp4_bytes": n, "seconds": t}   on success
#     {"error": "...", "trace": "..."}                            on failure
# =============================================================================

import os
import sys
import math
import time
import base64
import tempfile
import traceback

# --- Paths: everything heavy lives on the network volume ---------------------
VOLUME       = "/runpod-volume"
HF_HOME      = os.environ.setdefault("HF_HOME", os.path.join(VOLUME, "hf"))
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
MODELS_DIR   = os.path.join(VOLUME, "echomimic_v3")
BASE_DIR     = os.path.join(MODELS_DIR, "Wan2.1-Fun-V1.1-1.3B-InP")   # base model
WAV2VEC_DIR  = os.path.join(MODELS_DIR, "chinese-wav2vec2-base")      # audio enc
FLASH_DIR    = os.path.join(MODELS_DIR, "echomimicv3-flash-pro")      # DiT weights
FLASH_CKPT   = os.path.join(FLASH_DIR, "diffusion_pytorch_model.safetensors")
CONFIG_PATH  = "/app/config/config.yaml"

# src/ package is at /app; make sure it is importable regardless of cwd.
sys.path.insert(0, "/app")

import numpy as np
import requests

# Global cache — the pipeline is expensive to build (~24 GB of weights loaded
# onto the GPU) so we keep it alive between serverless invocations.
_PIPE = None
_VAE = None
_WAV2VEC_MODEL = None
_WAV2VEC_FE = None
_DEVICE = None
_DTYPE = None


# -----------------------------------------------------------------------------
# Input decoding (base64 / data-uri / http url) — matches our other workers
# -----------------------------------------------------------------------------
def _save_input(value, suffix, dst_dir):
    """Decode an input field to a real file on disk and return its path."""
    if value is None:
        raise ValueError("missing required input")
    fd, path = tempfile.mkstemp(suffix=suffix, dir=dst_dir)
    os.close(fd)

    if isinstance(value, str) and value.startswith("http"):
        r = requests.get(value, timeout=120)
        r.raise_for_status()
        data = r.content
    elif isinstance(value, str) and value.startswith("data:"):
        # data:<mime>;base64,<payload>
        data = base64.b64decode(value.split(",", 1)[1])
    else:
        # raw base64 (tolerate whitespace / missing padding)
        s = "".join(str(value).split())
        s += "=" * (-len(s) % 4)
        data = base64.b64decode(s)

    with open(path, "wb") as f:
        f.write(data)
    return path


# -----------------------------------------------------------------------------
# One-time weight download to the network volume (~24 GB, first cold start only)
# -----------------------------------------------------------------------------
def ensure_weights():
    from huggingface_hub import snapshot_download

    os.makedirs(MODELS_DIR, exist_ok=True)

    # 1) Wan2.1-Fun base model (~19.8 GB): VAE, umt5 T5 text encoder, CLIP
    #    xlm-roberta image encoder, tokenizer, and the base transformer whose
    #    config.json defines the DiT architecture the Flash weights override.
    if not os.path.exists(os.path.join(BASE_DIR, "config.json")):
        print("[weights] downloading Wan2.1-Fun-V1.1-1.3B-InP (~19.8 GB) ...", flush=True)
        snapshot_download(
            repo_id="alibaba-pai/Wan2.1-Fun-V1.1-1.3B-InP",
            local_dir=BASE_DIR,
            local_dir_use_symlinks=False,
        )

    # 2) Chinese wav2vec2 audio encoder (~380 MB). Skip the 1.14 GB fairseq
    #    .pt checkpoint — the HF Wav2Vec2Model only needs pytorch_model.bin.
    if not os.path.exists(os.path.join(WAV2VEC_DIR, "pytorch_model.bin")):
        print("[weights] downloading chinese-wav2vec2-base (~380 MB) ...", flush=True)
        snapshot_download(
            repo_id="TencentGameMate/chinese-wav2vec2-base",
            local_dir=WAV2VEC_DIR,
            local_dir_use_symlinks=False,
            allow_patterns=["*.json", "pytorch_model.bin", "*.txt"],
        )
    # Wav2Vec2FeatureExtractor.from_pretrained needs preprocessor_config.json.
    # The TencentGameMate repo ships a minimal one, but write a correct default
    # if it is absent so the feature extractor never fails to load.
    pcfg = os.path.join(WAV2VEC_DIR, "preprocessor_config.json")
    if not os.path.exists(pcfg):
        with open(pcfg, "w") as f:
            f.write(
                '{"do_normalize": true, "feature_extractor_type": '
                '"Wav2Vec2FeatureExtractor", "feature_size": 1, '
                '"padding_side": "right", "padding_value": 0.0, '
                '"return_attention_mask": true, "sampling_rate": 16000}'
            )

    # 3) EchoMimicV3 Flash DiT weights (~3.73 GB). Only the flash-pro folder.
    if not os.path.exists(FLASH_CKPT):
        print("[weights] downloading EchoMimicV3 flash-pro DiT (~3.73 GB) ...", flush=True)
        snapshot_download(
            repo_id="BadToBest/EchoMimicV3",
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False,
            allow_patterns=["echomimicv3-flash-pro/*"],
        )
    print("[weights] ready.", flush=True)


# -----------------------------------------------------------------------------
# Helpers ported verbatim from infer_flash.py
# -----------------------------------------------------------------------------
def _get_sample_size(pil_img, sample_size):
    w, h = pil_img.size
    ori_a = w * h
    default_a = sample_size[0] * sample_size[1]
    if default_a < ori_a:
        ratio_a = math.sqrt(ori_a / sample_size[0] / sample_size[1])
        w = w / ratio_a // 16 * 16
        h = h / ratio_a // 16 * 16
    else:
        w = w // 16 * 16
        h = h // 16 * 16
    return [int(h), int(w)]


def _loudness_norm(audio_array, sr=16000, lufs=-23):
    import pyloudnorm as pyln
    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(audio_array)
    if abs(loudness) > 100:
        return audio_array
    return pyln.normalize.loudness(audio_array, loudness, lufs)


def _get_audio_embed(mel_input, feature_extractor, audio_encoder,
                     video_length, sr=16000, device="cpu", dtype=None):
    import torch
    from einops import rearrange
    audio_feature = np.squeeze(
        feature_extractor(mel_input, sampling_rate=sr).input_values
    )
    audio_feature = torch.from_numpy(audio_feature).float().to(device=device)
    audio_feature = audio_feature.unsqueeze(0)
    with torch.no_grad():
        embeddings = audio_encoder(
            audio_feature, seq_len=int(video_length), output_hidden_states=True
        )
    audio_emb = torch.stack(embeddings.hidden_states[1:], dim=1).squeeze(0)
    audio_emb = rearrange(audio_emb, "b s d -> s b d")
    return audio_emb.cpu().detach()


# -----------------------------------------------------------------------------
# Build the pipeline once (mirrors infer_flash.py model loading)
# -----------------------------------------------------------------------------
def _build_pipeline():
    global _PIPE, _VAE, _WAV2VEC_MODEL, _WAV2VEC_FE, _DEVICE, _DTYPE
    if _PIPE is not None:
        return

    import torch
    from omegaconf import OmegaConf
    from transformers import AutoTokenizer, Wav2Vec2FeatureExtractor
    from diffusers import FlowMatchEulerDiscreteScheduler

    from src.wan_vae import AutoencoderKLWan
    from src.wan_image_encoder import CLIPModel
    from src.wan_text_encoder import WanT5EncoderModel
    from src.wan_transformer3d_audio_2512 import (
        WanTransformerAudioMask3DModel as WanTransformer,
    )
    from src.pipeline_wan_fun_inpaint_audio_2512 import WanFunInpaintAudioPipeline
    from src.wav2vec2 import Wav2Vec2Model
    from src.utils import filter_kwargs
    from src.fm_solvers import FlowDPMSolverMultistepScheduler        # noqa: F401
    from src.fm_solvers_unipc import FlowUniPCMultistepScheduler
    from src.cache_utils import get_teacache_coefficients

    _DEVICE = torch.device("cuda")
    _DTYPE = torch.bfloat16
    config = OmegaConf.load(CONFIG_PATH)

    # Audio encoder stays on CPU (matches infer_flash.py; it is cheap).
    _WAV2VEC_MODEL = Wav2Vec2Model.from_pretrained(
        WAV2VEC_DIR, local_files_only=True
    ).to("cpu")
    _WAV2VEC_MODEL.feature_extractor._freeze_parameters()
    _WAV2VEC_FE = Wav2Vec2FeatureExtractor.from_pretrained(
        WAV2VEC_DIR, local_files_only=True
    )

    # DiT: load base architecture from the Wan-Fun root, then override with the
    # EchoMimicV3 Flash audio-mask weights (strict=False — many extra keys).
    transformer = WanTransformer.from_pretrained(
        os.path.join(
            BASE_DIR,
            config["transformer_additional_kwargs"].get("transformer_subpath", "./"),
        ),
        transformer_additional_kwargs=OmegaConf.to_container(
            config["transformer_additional_kwargs"]
        ),
        low_cpu_mem_usage=True,
        torch_dtype=_DTYPE,
    )
    from safetensors.torch import load_file
    state_dict = load_file(FLASH_CKPT)
    state_dict = state_dict.get("state_dict", state_dict)
    m, u = transformer.load_state_dict(state_dict, strict=False)
    print(f"[dit] missing={len(m)} unexpected={len(u)}", flush=True)

    _VAE = AutoencoderKLWan.from_pretrained(
        os.path.join(BASE_DIR, config["vae_kwargs"].get("vae_subpath", "vae")),
        additional_kwargs=OmegaConf.to_container(config["vae_kwargs"]),
    ).to(_DTYPE)

    tokenizer = AutoTokenizer.from_pretrained(
        os.path.join(
            BASE_DIR,
            config["text_encoder_kwargs"].get("tokenizer_subpath", "tokenizer"),
        )
    )
    text_encoder = WanT5EncoderModel.from_pretrained(
        os.path.join(
            BASE_DIR,
            config["text_encoder_kwargs"].get("text_encoder_subpath", "text_encoder"),
        ),
        additional_kwargs=OmegaConf.to_container(config["text_encoder_kwargs"]),
        low_cpu_mem_usage=True,
        torch_dtype=_DTYPE,
    ).eval()
    clip_image_encoder = CLIPModel.from_pretrained(
        os.path.join(
            BASE_DIR,
            config["image_encoder_kwargs"].get("image_encoder_subpath", "image_encoder"),
        )
    ).to(_DTYPE).eval()

    # Flash uses the UniPC solver (shift forced to 1, per infer_flash.py).
    cfg_sched = OmegaConf.to_container(config["scheduler_kwargs"])
    cfg_sched["shift"] = 1
    scheduler = FlowUniPCMultistepScheduler(
        **filter_kwargs(FlowUniPCMultistepScheduler, cfg_sched)
    )

    pipe = WanFunInpaintAudioPipeline(
        transformer=transformer,
        vae=_VAE,
        tokenizer=tokenizer,
        text_encoder=text_encoder,
        scheduler=scheduler,
        clip_image_encoder=clip_image_encoder,
    )

    # TeaCache: Flash defaults to it (threshold 0.1, skip first 5 steps).
    coeffs = get_teacache_coefficients(BASE_DIR)
    if coeffs is not None:
        pipe.transformer.enable_teacache(
            coeffs, 8, 0.1, num_skip_start_steps=5, offload=False
        )

    # H100 80 GB — keep everything resident on the GPU (no CPU offload).
    pipe.to(device=_DEVICE)
    _PIPE = pipe
    print("[pipeline] built and resident on GPU.", flush=True)


# -----------------------------------------------------------------------------
# Inference (single image + audio) — mirrors the infer_flash.py inference block
# -----------------------------------------------------------------------------
NEG_PROMPT = (
    "Gesture is bad. Gesture is unclear. Strange and twisted hands. Bad hands. "
    "Bad fingers. Unclear and blurry hands. Unclear gestures, broken hands, "
    "fused fingers."
)


def _run(image_path, audio_path, prompt, steps, seed, guidance,
         audio_guidance, max_seconds, width, height, work_dir):
    import torch
    from PIL import Image
    import librosa
    from moviepy import VideoFileClip, AudioFileClip
    from src.utils import get_image_to_video_latent2, save_videos_grid

    fps = 25
    generator = torch.Generator(device=_DEVICE).manual_seed(int(seed))

    ref_image = Image.open(image_path).convert("RGB")
    ref_start = np.array(ref_image)

    audio_clip = AudioFileClip(audio_path)
    frame_cap = int(round(max_seconds * fps))
    video_length = min(int(audio_clip.duration * fps), frame_cap)
    # Snap to the VAE temporal compression grid (4x): 4k+1 frames.
    tcr = _VAE.config.temporal_compression_ratio
    video_length = (
        int((video_length - 1) // tcr * tcr) + 1 if video_length != 1 else 1
    )
    seconds = video_length / fps

    # Audio -> wav2vec embeddings
    mel_input, sr = librosa.load(audio_path, sr=16000)
    mel_input = _loudness_norm(mel_input, sr)
    mel_input = mel_input[: int(video_length / fps * sr)]
    audio_emb = _get_audio_embed(
        mel_input, _WAV2VEC_FE, _WAV2VEC_MODEL, video_length,
        sr=16000, device="cpu",
    ).to(device=_DEVICE, dtype=_DTYPE)

    # Window the per-frame audio features (+/-2 neighbours), as in infer_flash.
    indices = (torch.arange(2 * 2 + 1) - 2) * 1
    center = torch.arange(0, video_length, 1).unsqueeze(1) + indices.unsqueeze(0)
    center = torch.clamp(center, min=0, max=audio_emb.shape[0] - 1)
    audio_embeds = audio_emb[center].unsqueeze(0).to(device=_DEVICE)

    sh, sw = _get_sample_size(ref_image, [height, width])
    latent_frames = (video_length - 1) // tcr + 1

    # Long clips (>138 frames, ~5.5 s) need RIFLEx positional extrapolation.
    if latent_frames > (138 - 1) // tcr + 1:
        try:
            _PIPE.transformer.enable_riflex(k=6, L_test=latent_frames)
        except Exception as e:
            print(f"[riflex] could not enable: {e}", flush=True)

    input_video, input_video_mask, clip_image = get_image_to_video_latent2(
        Image.fromarray(ref_start).convert("RGB"), None,
        video_length=video_length, sample_size=[sh, sw],
    )

    with torch.no_grad():
        sample = _PIPE(
            prompt,
            num_frames=video_length,
            negative_prompt=NEG_PROMPT,
            audio_embeds=audio_embeds,
            audio_scale=1.0,
            ip_mask=None,             # Flash needs no face mask
            use_un_ip_mask=False,
            height=sh,
            width=sw,
            generator=generator,
            neg_scale=1.0,
            neg_steps=0,
            use_dynamic_cfg=False,
            use_dynamic_acfg=False,
            guidance_scale=float(guidance),
            audio_guidance_scale=float(audio_guidance),
            num_inference_steps=int(steps),
            video=input_video,
            mask_video=input_video_mask,
            clip_image=clip_image,
            cfg_skip_ratio=0.0,
            shift=5.0,
        ).videos

    # Save silent video, then mux the original audio track in.
    tmp_mp4 = os.path.join(work_dir, "tmp.mp4")
    out_mp4 = os.path.join(work_dir, "out.mp4")
    save_videos_grid(sample[:, :, :video_length], tmp_mp4, fps=fps)

    vclip = VideoFileClip(tmp_mp4)
    aclip = audio_clip.subclipped(0, seconds)
    vclip = vclip.with_audio(aclip)
    vclip.write_videofile(out_mp4, codec="libx264", audio_codec="aac", threads=2)
    vclip.close()
    audio_clip.close()
    return out_mp4, seconds


# -----------------------------------------------------------------------------
# RunPod entrypoint
# -----------------------------------------------------------------------------
def handler(event):
    t0 = time.time()
    work_dir = tempfile.mkdtemp(prefix="echomimic_")
    try:
        inp = event.get("input", {}) or {}
        if not inp.get("image"):
            return {"error": "missing required input 'image'"}
        if not inp.get("audio"):
            return {"error": "missing required input 'audio'"}

        ensure_weights()
        _build_pipeline()

        image_path = _save_input(inp["image"], ".png", work_dir)
        audio_path = _save_input(inp["audio"], ".wav", work_dir)

        out_mp4, seconds = _run(
            image_path=image_path,
            audio_path=audio_path,
            prompt=inp.get("prompt", "A person is speaking."),
            steps=inp.get("steps", 8),
            seed=inp.get("seed", 43),
            guidance=inp.get("guidance", 6.0),
            audio_guidance=inp.get("audio_guidance", 3.0),
            max_seconds=float(inp.get("max_seconds", 20)),
            width=int(inp.get("width", 768)),
            height=int(inp.get("height", 768)),
            work_dir=work_dir,
        )

        with open(out_mp4, "rb") as f:
            data = f.read()
        return {
            "video_base64": base64.b64encode(data).decode("utf-8"),
            "mp4_bytes": len(data),
            "seconds": round(seconds, 2),
            "elapsed": round(time.time() - t0, 1),
        }
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
    finally:
        try:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
