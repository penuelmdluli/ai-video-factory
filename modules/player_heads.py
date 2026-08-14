"""
Player headshots — licensed, cached, circle-cropped for lineup cards.

Real faces make a lineup graphic — but PSL player photography that we may
legally reuse is thin, so this is best-effort: a Wikimedia CC portrait when one
exists (cropped to a head circle, photographer credit kept), and the caller
falls back to the jersey-number dot when there isn't one. Never a scraped
club-site or Getty headshot.

Cache: assets/player_heads/<slug>.png + .json (credit sidecar). A miss is also
cached (empty .json) so we don't re-search Commons on every card.

Usage:
    from modules.player_heads import get_head
    head = await get_head("Mduduzi Shabalala")   # {"path", "credit"} | None
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

CACHE_DIR = Path(__file__).parent.parent / "assets" / "player_heads"
MISS_TTL_DAYS = 14


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _circle_head(src: Path, dst: Path, size: int = 256) -> bool:
    """Top-centred square crop (faces live in the top of a portrait) -> circle."""
    try:
        im = Image.open(src).convert("RGB")
        side = min(im.width, int(im.height * 0.75))
        x = (im.width - side) // 2
        y = int(im.height * 0.06)                  # just below the frame edge
        im = im.crop((x, y, x + side, min(y + side, im.height)))
        im = im.resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        out.save(dst)
        return True
    except Exception as e:
        print(f"[Heads] crop failed: {e}")
        return False


async def get_head(full_name: str) -> dict | None:
    """Cached head circle for a player, or None if no licensed photo exists."""
    import time
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(full_name)
    png = CACHE_DIR / f"{slug}.png"
    meta = CACHE_DIR / f"{slug}.json"

    if meta.exists():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            m = {}
        if png.exists() and m.get("credit"):
            return {"path": str(png), "credit": m["credit"]}
        if time.time() - m.get("at", 0) < MISS_TTL_DAYS * 86400:
            return None                            # recent confirmed miss

    from modules.free_press_images import photos_for_player, download
    hits = await photos_for_player(full_name, 1)
    if hits:
        raw = CACHE_DIR / f"{slug}_raw.jpg"
        got = await download(hits[0], raw)
        if got and _circle_head(raw, png):
            raw.unlink(missing_ok=True)
            meta.write_text(json.dumps({"credit": hits[0]["credit"],
                                        "at": __import__('time').time()}),
                            encoding="utf-8")
            print(f"[Heads] cached head: {full_name}")
            return {"path": str(png), "credit": hits[0]["credit"]}
        raw.unlink(missing_ok=True)
    meta.write_text(json.dumps({"at": __import__('time').time()}), encoding="utf-8")
    return None
