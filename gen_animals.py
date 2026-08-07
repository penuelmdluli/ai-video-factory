"""Generate the talking-animal cast — photoreal close-up portraits, facing camera,
mouths parted mid-speech (ready for lip-sync later). $0 via local SDXL / Cloudflare FLUX."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
OUT = ROOT / "assets" / "animals"
OUT.mkdir(parents=True, exist_ok=True)

from modules.ai_images import generate_image

CHARS = {
    "lion": ("Photorealistic dramatic close-up portrait of a majestic male lion with a huge golden "
             "mane, facing the camera head-on, mouth slightly parted as if mid-sentence, intelligent "
             "soulful eyes, ultra-detailed fur, warm golden savanna at sunset softly blurred bokeh "
             "background, cinematic rim lighting, shallow depth of field, 4k, hyperrealistic wildlife "
             "photography, no text"),
    "tiger": ("Photorealistic dramatic close-up portrait of a Bengal tiger, facing the camera head-on, "
              "mouth slightly parted mid-sentence, piercing confident amber eyes, ultra-detailed orange "
              "and black striped fur, lush green jungle softly blurred bokeh background, cinematic rim "
              "lighting, shallow depth of field, 4k, hyperrealistic wildlife photography, no text"),
    "rabbit": ("Photorealistic dramatic close-up portrait of a fluffy brown rabbit, facing the camera "
               "head-on, mouth slightly parted mid-sentence, big nervous curious eyes, twitching "
               "whiskers, ultra-detailed soft fur, soft green meadow with wildflowers softly blurred "
               "bokeh background, cinematic rim lighting, shallow depth of field, 4k, hyperrealistic "
               "wildlife photography, no text"),
}


async def main():
    for name, prompt in CHARS.items():
        out = OUT / f"{name}.png"
        try:
            res = await generate_image(prompt, out, niche="", orientation="portrait")
            print(f"{name} -> {res}", flush=True)
        except Exception as e:
            print(f"{name} FAILED {e!r}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
