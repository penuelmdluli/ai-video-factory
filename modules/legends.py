"""
Mzansi Legends — African folklore for the SAGA page.

The page already tells serialised mythology; it was just Norse. This keeps
the format and makes the stories ours: the tokoloshe, the lightning bird,
the Grootslang, the Mamlambo.

Two rules, because this is living cultural heritage and not a horror gimmick:

  1. It is always framed AS FOLKLORE. "In Nguni folklore the tokoloshe is
     said to be..." — never as a claim about the world, never as a warning
     that something is real.
  2. Every line comes from a cited source and the culture it belongs to is
     named. We are retelling, not inventing, and we say who tells it.

Imagery is clearly labelled as illustration — no photograph can exist of a
being from folklore, and pretending otherwise would be the same fabrication
problem we fixed everywhere else.
"""
import json
import re
from pathlib import Path

import requests

UA = "GenesisNews/1.0 (mdlulipenuel@gmail.com)"
CACHE = Path(__file__).parent.parent / "data" / "legends_cache.json"

# (wikipedia title, display name, the people whose story it is, art prompt)
LEGENDS = [
    # ART: atmosphere ONLY — no creature figures. The first pass asked for a
    # "dwarf-like water spirit" and the model produced what reads as a small
    # child alone at night, which we will not publish. Depicting someone's
    # living belief as a monster is also not ours to do. The place carries
    # the mood; the words carry the story.
    ("Tokoloshe", "The Tokoloshe", "Nguni folklore",
     "moonlit river at night, tall reeds, low mist over dark water, empty "
     "riverbank, no people, atmospheric landscape painting"),
    ("Lightning bird", "The Impundulu", "Zulu folklore",
     "lightning striking over a South African escarpment at night, storm "
     "clouds, no people, dramatic landscape painting"),
    ("Inkanyamba", "The Inkanyamba", "South African folklore",
     "a tall waterfall in the Drakensberg under heavy storm cloud, spray "
     "and dark rock, no people, atmospheric landscape painting"),
    ("Grootslang", "The Grootslang", "Richtersveld legend",
     "the mouth of a deep cave in the Richtersveld desert at dusk, red "
     "rock, long shadows, no people, atmospheric landscape painting"),
    ("Mamlambo", "The Mamlambo", "Zulu mythology",
     "a wide dark river at dusk in a South African valley, still water, "
     "reeds, no people, atmospheric landscape painting"),
]


def _summary(title: str) -> dict:
    r = requests.get(
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        + title.replace(" ", "_"),
        headers={"User-Agent": UA}, timeout=45)
    j = r.json()
    return {"extract": j.get("extract") or "",
            "url": (j.get("content_urls", {}).get("desktop", {})
                    .get("page", ""))}


def episode(index: int) -> dict | None:
    """One legend, with its sourced lines. None if the source is unreadable."""
    title, name, culture, art = LEGENDS[index % len(LEGENDS)]
    try:
        s = _summary(title)
    except Exception as e:
        print(f"[Legends] {title}: source unavailable ({e})")
        return None
    if not s["extract"]:
        return None

    lines = [x.strip() for x in re.split(r"(?<=[.!?])\s+", s["extract"])
             if len(x.strip()) > 30][:3]
    if not lines:
        return None
    return {
        "key": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        "name": name,
        "culture": culture,
        "lines": lines,
        "art_prompt": art,
        "source": f"Source: Wikipedia — {title}",
        "source_url": s["url"],
        # said out loud and printed: this is a story people tell
        "framing": f"In {culture}, it is said:",
    }


def all_episodes():
    return [e for e in (episode(i) for i in range(len(LEGENDS))) if e]

# The niche prompt-enhancer rewrites prompts in the page's usual style, and on
# this page that style is warm human moments — it answered "no people" with a
# mother holding a baby. Legends art is generated with the enhancer OFF and
# an explicit empty-landscape instruction.
NEGATIVE = ("deserted, uninhabited, nobody, no person, no figure, no people, "
            "no animals, no creature")


async def make_art(ep: dict, out_dir):
    """Atmosphere art for one legend, or None. Never depicts a being."""
    from pathlib import Path
    from modules.ai_images import generate_image_cloudflare
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prompt = f"{ep['art_prompt']}, {NEGATIVE}"
    try:
        return await generate_image_cloudflare(
            prompt, out / ep["key"], "", "portrait", False)
    except Exception as e:
        print(f"[Legends] art failed for {ep['name']}: {e}")
        return None
