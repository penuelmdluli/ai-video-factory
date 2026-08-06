"""Topic -> synced beats. Each beat is one short spoken line + its illustration:
a keyword+emoji card by default, or a data device (map / stat) when the line carries real
geography or a real number. The voice for each beat says exactly that line, so narration and
graphics stay locked together (the baby-channel formula). Nothing is fabricated — devices only
appear when the real text supplies their ingredients.
"""
import re

from modules.emoji_util import pick_emoji, pick_keyword, KEYWORD_EMOJI
from modules.stat_counter import extract_stat

# geography terms that justify a map beat
_GEO = ["south africa", "africa", "china", "russia", "united states", "america", "europe",
        "india", "brics", "nigeria", "kenya", "egypt", "sahel", "middle east", "gulf", "ukraine"]


def to_lines(text, max_words=9, max_lines=7):
    """Split narration into short spoken lines (<= max_words) at sentence + clause boundaries."""
    lines = []
    for sent in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        sent = sent.strip().rstrip(".!?")
        if not sent:
            continue
        words = sent.split()
        if len(words) <= max_words:
            lines.append(sent)
            continue
        parts = re.split(r",|\band\b|\bbut\b|\bwhile\b|\bas\b|\bwhich\b|\bthat\b", sent)
        cur = []
        for p in parts:
            pw = p.split()
            if not pw:
                continue
            if len(cur) + len(pw) <= max_words or not cur:
                cur += pw
            else:
                lines.append(" ".join(cur)); cur = pw
        if cur:
            lines.append(" ".join(cur))
    lines = [l.strip() for l in lines if len(l.split()) >= 2]
    return lines[:max_lines]


def build_beats(pkg, handle="Tech Pulse Africa"):
    """Return a list of beat dicts for make_synced_reel. First beat is the kinetic hook,
    last is the follow CTA; the middle beats illustrate each spoken line."""
    title = pkg.get("title", "")
    narr = pkg.get("narration", "")
    hook = pkg.get("hook_line") or title
    beats = [{"say": hook, "hook": True}]

    lines = pkg.get("lines") or to_lines(narr)
    used_map = used_stat = False
    for ln in lines:
        low = " " + ln.lower() + " "
        st = extract_stat(ln)
        if st and st[0] and float(st[0]) >= 1 and not used_stat:
            v, pre, suf, lbl = st
            beats.append({"say": ln, "device": {"type": "stat", "value": v, "prefix": pre,
                                                 "suffix": suf, "label": lbl or pick_keyword(ln).lower()}})
            used_stat = True
        elif (not used_map) and any(g in low for g in _GEO):
            beats.append({"say": ln, "device": {"type": "map", "headline": f"{title} {ln}"}})
            used_map = True
        else:
            beats.append({"say": ln, "keyword": pick_keyword(ln), "emoji": pick_emoji(ln)})

    beats.append({"say": f"Follow {handle}", "keyword": "FOLLOW", "emoji": "\U0001F514", "outro": True})
    return beats
