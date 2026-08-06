"""Template library — many top $0 formats, one engine.

Every template is an ordered `spec` of devices (hook / map / stat / bars / versus / timeline /
chart / flow / quote / outro) that `story_template.make_story_reel` renders locally for ~$0.
`pick_template(pkg)` chooses the best-fit template from what REAL data the grounded topic
actually supplies — a number becomes a stat, a country becomes a map, two sides become a
versus. Nothing is fabricated: a template only activates when its ingredients are present.

    from modules.templates import pick_template
    name, spec = pick_template(pkg)     # pkg = grounded topic dict (title, narration, ...)
"""
import re

from modules.stat_counter import extract_stat


# ---- helpers (accurate — everything is pulled from the real grounded text) ----

def beats(narr, n=3, maxlen=40):
    """First `n` real sentences of the narration as short flow steps (real text, re-framed)."""
    out = []
    for s in re.split(r"(?<=[.!?])\s+", narr or ""):
        s = s.strip().rstrip(".!?")
        if len(s) < 6:
            continue
        if len(s) > maxlen:
            s = s[:maxlen].rsplit(" ", 1)[0] + "…"
        out.append(s)
        if len(out) >= n:
            break
    return out


def punch_line(narr, maxlen=64):
    """The shortest strong sentence — a real line from the narration, good for a quote card."""
    cands = [s.strip().rstrip(".!?") for s in re.split(r"(?<=[.!?])\s+", narr or "")]
    cands = [c for c in cands if 12 <= len(c) <= maxlen]
    return min(cands, key=len) if cands else ""


def _outro(pkg):
    return {"type": "outro", "text": pkg.get("outro") or "Follow Tech Pulse Africa"}


# ---- templates ----

def news_explainer(pkg):
    """hook -> map/route -> stat? -> flow -> outro. The workhorse for geopolitics."""
    title, narr = pkg.get("title", ""), pkg.get("narration", "")
    spec = [{"type": "hook", "text": pkg.get("hook_line") or title}]
    spec.append({"type": "map", "headline": f"{title} {narr}"})
    st = extract_stat(narr) or extract_stat(title)
    if st:
        v, pre, suf, lbl = st
        spec.append({"type": "stat", "value": v, "prefix": pre, "suffix": suf, "label": lbl})
    b = beats(narr, 3)
    if len(b) >= 2:
        spec.append({"type": "flow", "title": "What's happening", "steps": b})
    spec.append(_outro(pkg))
    return spec


def the_number(pkg):
    """hook -> stat -> map -> outro. When one killer figure carries the story."""
    title, narr = pkg.get("title", ""), pkg.get("narration", "")
    st = extract_stat(narr) or extract_stat(title)
    v, pre, suf, lbl = st
    return [
        {"type": "hook", "text": pkg.get("hook_line") or title},
        {"type": "stat", "value": v, "prefix": pre, "suffix": suf, "label": lbl, "seconds": 3.0},
        {"type": "map", "headline": f"{title} {narr}"},
        _outro(pkg),
    ]


def the_ranking(pkg):
    """hook -> bar-race -> outro. Needs pkg['items'] = [(label, value), ...]."""
    return [
        {"type": "hook", "text": pkg.get("hook_line") or pkg.get("title", "")},
        {"type": "bars", "title": pkg.get("bars_title", "The ranking"),
         "items": pkg["items"], "suffix": pkg.get("suffix", ""), "prefix": pkg.get("prefix", "")},
        _outro(pkg),
    ]


def versus(pkg):
    """hook -> versus -> stat? -> outro. Needs pkg['versus'] = {left:{...}, right:{...}}."""
    v = pkg["versus"]
    spec = [
        {"type": "hook", "text": pkg.get("hook_line") or pkg.get("title", "")},
        {"type": "versus", "left": v["left"], "right": v["right"], "title": v.get("title", "")},
    ]
    st = extract_stat(pkg.get("narration", ""))
    if st:
        vv, pre, suf, lbl = st
        spec.append({"type": "stat", "value": vv, "prefix": pre, "suffix": suf, "label": lbl})
    spec.append(_outro(pkg))
    return spec


def the_timeline(pkg):
    """hook -> timeline -> quote? -> outro. Needs pkg['events'] = [(when, what), ...]."""
    spec = [
        {"type": "hook", "text": pkg.get("hook_line") or pkg.get("title", "")},
        {"type": "timeline", "title": pkg.get("timeline_title", "How we got here"),
         "events": pkg["events"]},
    ]
    q = punch_line(pkg.get("narration", ""))
    if q:
        spec.append({"type": "quote", "quote": q, "by": pkg.get("lowerthird_label", "")})
    spec.append(_outro(pkg))
    return spec


def money(pkg):
    """hook -> chart? -> bars? -> flow -> outro. Finance niche. Needs points and/or items."""
    title, narr = pkg.get("title", ""), pkg.get("narration", "")
    spec = [{"type": "hook", "text": pkg.get("hook_line") or title}]
    if pkg.get("points"):
        spec.append({"type": "chart", "title": pkg.get("chart_title", "The trend"),
                     "points": pkg["points"], "prefix": pkg.get("prefix", ""), "suffix": pkg.get("suffix", "")})
    if pkg.get("items"):
        spec.append({"type": "bars", "title": pkg.get("bars_title", ""), "items": pkg["items"],
                     "suffix": pkg.get("suffix", "")})
    b = pkg.get("steps") or beats(narr, 3)
    if len(b) >= 2:
        spec.append({"type": "flow", "title": pkg.get("flow_title", "The play"), "steps": b})
    spec.append(_outro(pkg))
    return spec


def motivation(pkg):
    """kinetic hook -> quote -> stat? -> outro. Elevate You niche."""
    title, narr = pkg.get("title", ""), pkg.get("narration", "")
    spec = [{"type": "hook", "text": pkg.get("hook_line") or title}]
    q = pkg.get("quote") or punch_line(narr) or title
    if q:
        spec.append({"type": "quote", "quote": q, "by": pkg.get("by", "")})
    st = extract_stat(narr)
    if st:
        v, pre, suf, lbl = st
        spec.append({"type": "stat", "value": v, "prefix": pre, "suffix": suf, "label": lbl})
    spec.append(_outro(pkg))
    return spec


TEMPLATES = {
    "news_explainer": news_explainer, "the_number": the_number, "the_ranking": the_ranking,
    "versus": versus, "the_timeline": the_timeline, "money": money, "motivation": motivation,
}


def pick_template(pkg):
    """Choose the best-fit template from the real data the topic supplies. Returns (name, spec)."""
    # explicit niche override
    niche = (pkg.get("niche") or "").lower()
    if niche in ("motivation", "ai_money", "finance") and niche != "tech_news":
        fn = motivation if niche == "motivation" else money
        try:
            return niche, fn(pkg)
        except Exception:
            pass
    # structured data wins (richest formats)
    if pkg.get("versus"):
        return "versus", versus(pkg)
    if pkg.get("events"):
        return "the_timeline", the_timeline(pkg)
    if pkg.get("items"):
        return "the_ranking", the_ranking(pkg)
    if pkg.get("points"):
        return "money", money(pkg)
    # number-led vs geography-led, both from the real narration
    st = extract_stat(pkg.get("narration", "")) or extract_stat(pkg.get("title", ""))
    if st and st[0] and float(st[0]) >= 10:     # a headline-worthy real figure
        return "the_number", the_number(pkg)
    return "news_explainer", news_explainer(pkg)
