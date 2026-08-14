"""
Club brand standards for Genesis News — PSL & Mzansi Football.

ONE source of truth for how each club is represented in image prompts, video
overlays and thumbnails. Import `CLUB_BRAND` anywhere a club needs colours,
a motif or a wordmark so the look stays consistent across reels, thumbs and blog.

IMPORTANT — these are OUR club-themed marks, not the clubs' crests.
Kaizer Chiefs, Orlando Pirates and Mamelodi Sundowns own their emblems. This
module encodes the colour system, the motif family and the wordmark treatment so
graphics read instantly as each club, while staying the page's own property.
Reproducing an official crest on monetised content invites a rightsholder strike
and makes the page look like a bootleg rather than an outlet. Colour + motif does
the same job for a fan scrolling at speed.
"""

# key -> full brand spec
CLUB_BRAND = {
    "chiefs": {
        "name": "Kaizer Chiefs",
        "nickname": "Amakhosi",
        "wordmark": "AMAKHOSI",
        "colors": {
            "primary": (255, 193, 7),      # gold
            "secondary": (10, 10, 10),     # black
            "accent": (255, 255, 255),     # white
        },
        "motif": "shield",                 # geometric warrior-chief profile in a shield
        "text_style": "bold 3D gold block lettering",
        "prompt_colors": "gold and black with white accents",
    },
    "pirates": {
        "name": "Orlando Pirates",
        "nickname": "Buccaneers",
        "wordmark": "BUCCANEERS",
        "colors": {
            "primary": (245, 245, 245),    # white
            "secondary": (10, 10, 10),     # black
            "accent": (176, 182, 190),     # silver
        },
        "motif": "circle",                 # modernised skull-and-crossbones in a circle
        "text_style": "sharp metallic white sans-serif",
        "prompt_colors": "black and white with silver accents",
    },
    "sundowns": {
        "name": "Mamelodi Sundowns",
        "nickname": "Masandawana",
        "wordmark": "MASANDAWANA",
        "colors": {
            "primary": (255, 221, 0),      # bright yellow
            "secondary": (0, 138, 82),     # emerald green
            "accent": (28, 61, 168),       # royal blue
        },
        "motif": "sun",                    # geometric rising sun badge
        "text_style": "bright gold/yellow bold typography",
        "prompt_colors": "bright yellow with emerald green and royal blue",
    },
}

# The rest of the 2025-26 Betway Premiership. Lighter specs than the big three —
# name for the kicker strip, primary colour for the accent, crest via official_badge().
CLUB_BRAND.update({
    "amazulu":      {"name": "AmaZulu",           "nickname": "Usuthu",
                     "colors": {"primary": (0, 122, 61)},
                     "prompt_colors": "green and white"},
    "chippa":       {"name": "Chippa United",     "nickname": "Chilli Boys",
                     "colors": {"primary": (20, 70, 150)},
                     "prompt_colors": "blue and white"},
    "durban_city":  {"name": "Durban City",       "nickname": "City",
                     "colors": {"primary": (30, 90, 170)},
                     "prompt_colors": "blue and white"},
    "arrows":       {"name": "Golden Arrows",     "nickname": "Abafana Bes'thende",
                     "colors": {"primary": (0, 130, 60)},
                     "prompt_colors": "green and gold"},
    "magesi":       {"name": "Magesi FC",         "nickname": "Dikwena tsa Meetse",
                     "colors": {"primary": (150, 30, 40)},
                     "prompt_colors": "maroon and white"},
    "gallants":     {"name": "Marumo Gallants",   "nickname": "Bahlabane ba Ntwa",
                     "colors": {"primary": (20, 60, 150)},
                     "prompt_colors": "blue and gold"},
    "orbit":        {"name": "Orbit College",     "nickname": "Mahikeng Stars",
                     "colors": {"primary": (120, 30, 90)},
                     "prompt_colors": "maroon and gold"},
    "polokwane":    {"name": "Polokwane City",    "nickname": "Rise and Shine",
                     "colors": {"primary": (30, 90, 180)},
                     "prompt_colors": "blue and white"},
    "richards_bay": {"name": "Richards Bay",      "nickname": "Natal Rich Boyz",
                     "colors": {"primary": (20, 80, 160)},
                     "prompt_colors": "blue and white"},
    "sekhukhune":   {"name": "Sekhukhune United", "nickname": "Babina Noko",
                     "colors": {"primary": (190, 30, 40)},
                     "prompt_colors": "red and white"},
    "siwelele":     {"name": "Siwelele FC",       "nickname": "Siwelele",
                     "colors": {"primary": (0, 130, 70)},
                     "prompt_colors": "green and white"},
    "stellenbosch": {"name": "Stellenbosch FC",   "nickname": "Stellies",
                     "colors": {"primary": (128, 0, 32)},
                     "prompt_colors": "maroon and white"},
    "galaxy":       {"name": "TS Galaxy",         "nickname": "The Rockets",
                     "colors": {"primary": (200, 30, 45)},
                     "prompt_colors": "red, white and blue"},
    # promoted for 2026-27 (replacing relegated Magesi and Orbit College)
    "kruger":       {"name": "Kruger United",     "nickname": "The Village Boys",
                     "colors": {"primary": (14, 74, 44)},
                     "prompt_colors": "green and gold"},
    "milford":      {"name": "Milford FC",        "nickname": "Milford",
                     "colors": {"primary": (30, 90, 170)},
                     "prompt_colors": "blue and white"},
})

# Aliases so a club can be resolved from whatever the script/headline called it.
ALIASES = {
    "kaizer chiefs": "chiefs", "chiefs": "chiefs", "amakhosi": "chiefs",
    "glamour boys": "chiefs",
    "orlando pirates": "pirates", "pirates": "pirates", "buccaneers": "pirates",
    "bucs": "pirates", "sea robbers": "pirates",
    "mamelodi sundowns": "sundowns", "sundowns": "sundowns",
    "masandawana": "sundowns", "the brazilians": "sundowns", "downs": "sundowns",
    "amazulu": "amazulu", "usuthu": "amazulu",
    "chippa united": "chippa", "chippa": "chippa", "chilli boys": "chippa",
    "durban city": "durban_city",
    "golden arrows": "arrows", "lamontville golden arrows": "arrows",
    "abafana bes'thende": "arrows",
    "magesi": "magesi",
    "marumo gallants": "gallants", "gallants": "gallants",
    "orbit college": "orbit",
    "polokwane city": "polokwane", "rise and shine": "polokwane",
    "richards bay": "richards_bay",
    "sekhukhune united": "sekhukhune", "sekhukhune": "sekhukhune",
    "babina noko": "sekhukhune",
    "siwelele": "siwelele",
    "stellenbosch": "stellenbosch", "stellies": "stellenbosch",
    "ts galaxy": "galaxy", "the rockets": "galaxy",
    "kruger united": "kruger", "village boys": "kruger",
    "milford": "milford",
}


def resolve_club(text: str) -> str | None:
    """Find which club a title/headline is about (e.g. 'chiefs', 'sekhukhune')."""
    t = (text or "").lower()
    # longest alias first so "kaizer chiefs" wins over "chiefs"
    for alias in sorted(ALIASES, key=len, reverse=True):
        if alias in t:
            return ALIASES[alias]
    return None


def resolve_clubs(text: str) -> list[str]:
    """
    ALL clubs mentioned, in order of first appearance — so "Chiefs vs Sundowns"
    returns ['chiefs', 'sundowns'] and a card can show both crests VS-style.
    """
    t = (text or "").lower()
    hits = []
    for alias, key in ALIASES.items():
        i = t.find(alias)
        if i >= 0:
            hits.append((i, key))
    seen, out = set(), []
    for i, key in sorted(hits):
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def brand_for(text: str) -> dict | None:
    key = resolve_club(text)
    return CLUB_BRAND.get(key) if key else None


from pathlib import Path as _Path

# Official club crests, supplied by the channel owner. Placed on every card so the
# reel reads instantly as the club it is about. Keyed by club id ('chiefs' etc.).
_BADGE_DIR = _Path(__file__).parent.parent / "assets" / "club_badges" / "official"


def official_badge(club_key: str):
    """Return the Path to the official crest for a club, or None if we don't have it."""
    if not club_key:
        return None
    p = _BADGE_DIR / f"{club_key}.png"
    return p if p.exists() else None


def prompt_fragment(club_key: str) -> str:
    """Colour wording to drop into an image prompt — never a crest or kit."""
    b = CLUB_BRAND.get(club_key)
    if not b:
        return "team colours, plain unbranded kit, no logos, no badges"
    return (
        f"supporters in {b['prompt_colors']}, plain unbranded kit, "
        f"no club crest, no sponsor logo, no badges"
    )
