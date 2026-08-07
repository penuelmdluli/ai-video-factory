"""Color-emoji + keyword helper for the faceless graphics engine.

On Windows, PIL 11 renders full-color emoji from Segoe UI Emoji with embedded_color=True,
so we can illustrate any spoken keyword with a real emoji at $0 — no assets, no network.
`pick_emoji(text)` maps a line/keyword to the best emoji; `render_emoji(e, px)` rasterizes it.
"""
import os
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

_EMOJI_FONT = None
for _p in (r"C:\Windows\Fonts\seguiemj.ttf", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"):
    if os.path.exists(_p):
        _EMOJI_FONT = _p
        break


@lru_cache(maxsize=48)
def _font(size):
    return ImageFont.truetype(_EMOJI_FONT, size) if _EMOJI_FONT else None


@lru_cache(maxsize=128)
def render_emoji(emoji, px=240):
    """Return an RGBA PIL image of `emoji` (cropped to content), or None if unavailable."""
    if not _EMOJI_FONT or not emoji:
        return None
    try:
        fnt = _font(px)
        img = Image.new("RGBA", (int(px * 2.2), int(px * 1.6)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((img.width // 2, img.height // 2), emoji, font=fnt, embedded_color=True, anchor="mm")
        bbox = img.getbbox()
        return img.crop(bbox) if bbox else img
    except Exception:
        return None


def emoji_available():
    return bool(_EMOJI_FONT)


# keyword substring -> emoji (checked in order; most specific first)
KEYWORD_EMOJI = {
    # geopolitics / news
    "south africa": "🇿🇦", "africa": "🌍", "china": "🇨🇳", "russia": "🇷🇺", "united states": "🇺🇸",
    "america": "🇺🇸", "europe": "🇪🇺", "india": "🇮🇳", "brics": "🌐", "nato": "🎖️", "border": "🛂",
    "dollar": "💵", "currency": "💱", "trade": "🤝", "tariff": "📦", "sanction": "🚫", "oil": "🛢️",
    "gold": "🥇", "diamond": "💎", "mineral": "⛏️", "gas": "🔥", "port": "⚓", "ship": "🚢",
    "pipeline": "🛢️", "military": "🎖️", "army": "🪖", "troop": "🪖", "war": "⚔️", "weapon": "🚀",
    "missile": "🚀", "drone": "🛸", "election": "🗳️", "protest": "✊", "power": "⚡", "energy": "⚡",
    "deal": "🤝", "summit": "🏛️", "treaty": "📜", "spy": "🕵️", "cyber": "💻",
    # money / finance
    "money": "💰", "bank": "🏦", "invest": "📈", "stock": "📈", "market": "📊", "save": "🐷",
    "savings": "🐷", "debt": "💳", "credit": "💳", "loan": "🏦", "budget": "📊", "interest": "📈",
    "compound": "🔁", "fund": "💰", "emergency": "🚨", "rich": "💎", "wealth": "💎", "income": "💵",
    "expense": "🧾", "tax": "🧾", "salary": "💵", "profit": "📈", "loss": "📉", "inflation": "🎈",
    "retire": "🌴", "goal": "🎯",
    # motivation / mindset
    "mind": "🧠", "focus": "🎯", "discipline": "🔥", "consistency": "🔁", "habit": "🔁",
    "win": "🏆", "success": "🏆", "dream": "✨", "believe": "🌟", "grow": "🌱", "growth": "🌱",
    "time": "⏳", "today": "☀️", "work": "💪", "strong": "💪", "fear": "😨", "fail": "❌",
    "start": "🚀", "step": "👣", "effort": "💪", "change": "🔄", "future": "🔮",
    # tech
    "phone": "📱", "tech": "💻", "computer": "💻", "chip": "🧠", "data": "📊", "internet": "🌐",
    "app": "📱", "battery": "🔋", "car": "🚗", "space": "🚀", "climate": "🌡️",
    "ai": "🤖", "robot": "🤖",
    # wellness / herbal / natural living
    "hydrate": "💧", "water": "💧", "sleep": "😴", "rest": "🛌", "tea": "🍵", "herbal": "🌿",
    "herb": "🌿", "organic": "🌱", "plant": "🌱", "seed": "🌰", "vegetable": "🥦", "veggie": "🥦",
    "fruit": "🍎", "salad": "🥗", "whole food": "🥗", "sugar": "🧁", "exercise": "🏃", "walk": "🚶",
    "movement": "🏃", "stretch": "🧘", "yoga": "🧘", "breathe": "🌬️", "breath": "🌬️", "sunlight": "☀️",
    "sunshine": "☀️", "gut": "🦠", "immune": "🛡️", "skin": "✨", "detox": "🍋", "lemon": "🍋",
    "ginger": "🫚", "garlic": "🧄", "honey": "🍯", "natural": "🌿", "healthy": "🥗", "body": "🧘",
    "energy boost": "⚡", "morning": "🌅",
    # calm / gratitude / blissful
    "gratitude": "🙏", "grateful": "🙏", "thankful": "🙏", "peace": "🕊️", "calm": "🌊",
    "mindful": "🧘", "kindness": "🤍", "kind": "🤍", "smile": "😊", "joy": "✨", "happy": "😊",
    "love": "❤️", "heart": "❤️", "soul": "✨", "nature": "🌿", "flower": "🌸", "ocean": "🌊",
    "sky": "🌤️", "moment": "🌸", "gentle": "🕊️", "bless": "🙏", "hope": "🌟", "light": "🌟",
}


_STOP = set("the a an and or of to in on for with by from is are was were be been this that these "
            "those it its as at into over under new more most will can could would should may".split())


def pick_emoji(text):
    """Best emoji for a line or keyword — matched by known vocabulary, else a neutral pin."""
    t = " " + (text or "").lower() + " "
    for k, v in KEYWORD_EMOJI.items():
        if k in t:
            return v
    return "📌"


def pick_keyword(text, maxwords=2):
    """The most illustrative 1-2 words of a line (a mapped term if present, else the longest word)."""
    words = re.findall(r"[A-Za-z$%\d][A-Za-z$%\d'-]*", text or "")
    low = (text or "").lower()
    for k in KEYWORD_EMOJI:
        if " " not in k and k in low:
            for w in words:
                if k in w.lower():
                    return w.upper()
    cands = [w for w in words if w.lower() not in _STOP]
    if not cands:
        return (words[0].upper() if words else "")
    cands.sort(key=len, reverse=True)
    return " ".join(cands[:1]).upper()
