"""
Caption alignment — burn the SCRIPT's words, not the transcriber's guesses.

The subtitle track for sa_pulse comes from transcribing the finished voiceover,
and a South African-accented read turns "Kaizer" into "Kiser", "Mamelodi" into
"Maim Lodi" and "Amakhosi" into "Emakosi" — misspelled captions on a news page
kill credibility instantly.

The narration TEXT is already correctly spelled (it is what the voice read).
So: align the narration's words onto the SRT's word timings with a sequence
match, and render the narration's spelling. Timing comes from the SRT, spelling
comes from the script — both sources doing the one job they're good at.

Usage:
    from modules.caption_align import align_captions
    segments = align_captions(narration_text, srt_segments)
"""
import re
from difflib import SequenceMatcher


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


def align_captions(narration: str, segments: list[dict]) -> list[dict]:
    """
    Map narration words onto SRT word timings.

    segments: [{"text","start","end"}, ...] one word (or few) per segment.
    Returns the same shape, with narration spellings. Falls back to the input
    segments untouched if there is nothing to align.
    """
    script_words = [w for w in (narration or "").split() if w.strip()]
    srt = [s for s in (segments or [])
           if (s.get("text") or "").strip() and float(s.get("end", 0)) > float(s.get("start", 0))]
    if not script_words or not srt:
        return segments

    a = [_norm(s["text"]) for s in srt]          # transcribed words (timing carriers)
    b = [_norm(w) for w in script_words]         # true words (spelling carriers)

    out = []
    sm = SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                s = srt[i1 + k]
                out.append({"text": script_words[j1 + k],
                            "start": float(s["start"]), "end": float(s["end"])})
        elif tag in ("replace", "insert"):
            words = script_words[j1:j2]
            if not words:
                continue
            # time window: the replaced SRT slots, or the gap between neighbours
            if tag == "replace":
                t0, t1 = float(srt[i1]["start"]), float(srt[i2 - 1]["end"])
            else:
                t0 = float(srt[i1 - 1]["end"]) if i1 > 0 else float(srt[0]["start"])
                t1 = float(srt[i1]["start"]) if i1 < len(srt) else t0
            if t1 <= t0:                          # zero gap — borrow a sliver
                t1 = t0 + 0.06 * len(words)
            per = (t1 - t0) / len(words)
            for k, w in enumerate(words):
                out.append({"text": w, "start": t0 + k * per, "end": t0 + (k + 1) * per})
        # tag == "delete": transcriber heard a word the script doesn't have — drop it

    fixed = sum(1 for tag, *_ in sm.get_opcodes() if tag != "equal")
    if fixed:
        print(f"[CaptionAlign] respelled {fixed} region(s) from the script text")
    return out or segments
