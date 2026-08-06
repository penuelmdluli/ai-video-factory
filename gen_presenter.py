"""Generate a photorealistic half-body news-anchor reference image for the avatar."""
import asyncio, sys
from pathlib import Path

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
OUT = ROOT / "assets" / "presenters"
OUT.mkdir(parents=True, exist_ok=True)

PROMPT = ("Photorealistic male news presenter, waist-up half-body shot, both hands and forearms "
          "clearly visible, one hand raised gesturing mid-speech, short brown hair, light blue shirt, "
          "confident expression, modern broadcast studio softly blurred, studio lighting, sharp focus, "
          "4k, highly detailed, realistic skin, looking at camera")


async def main():
    from modules.ai_images import generate_image
    out = OUT / "anchor_halfbody.png"
    try:
        res = await generate_image(PROMPT, out, size="832x1216", niche="tech_news")
        print("generate_image result:", res, flush=True)
    except TypeError:
        # signature fallback
        res = await generate_image(PROMPT, out)
        print("generate_image result (fallback sig):", res, flush=True)
    if out.exists():
        print(f"SAVED {out} ({out.stat().st_size/1e6:.2f}MB)", flush=True)
    else:
        # some generators return a path different from `out`
        pngs = sorted(OUT.glob("*.png"), key=lambda p: p.stat().st_mtime)
        print("dir contents:", [p.name for p in pngs], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
