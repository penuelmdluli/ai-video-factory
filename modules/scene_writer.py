"""
The AI writes the scene. Two people, a real situation, dialogue that plays.

Owner call 2026-08-27: "inject the help of AI in what we just built, we need
to build something real... these 2 are a couple for example".

He is right that the hand-written argument was the weak part. Six lines I
invented about a refereeing decision is a sketch, not a scene - and a channel
needs a new one every day, which is exactly the job to hand to a model.

What this asks for, and why each constraint is here:

  * A COUPLE, not debaters. The strongest short-form drama is two people who
    know each other too well, arguing about something small that is obviously
    about something bigger. "You said you'd be twenty minutes" is a better
    scene than any opinion.
  * SHORT LINES. Every line is a separate render and a separate voice take, so
    a forty-word speech is expensive and also bad television.
  * REACTIONS, not statements. Each line has to answer the one before it.
  * A TURN. Something changes by the end - somebody concedes, or lands a
    truth. A loop of two people repeating themselves is what a model writes
    if you do not ask for the turn.
  * NOTHING TOPICAL. No claims about real people or real matches; this page
    has a hard rule about invented facts and a drama script must not be the
    hole in it.

Returns the same shape build_conversation already consumes, so the writer and
the renderer stay independent.
"""
import json
import os
import re

SYSTEM = """You write very short two-hander scenes for a South African \
vertical-video channel. Your scenes are performed by 3D characters, so they \
must work on dialogue and behaviour alone - no props, no locations beyond a \
street at dusk, no stage directions that need animation you were not asked \
for.

RULES
- Exactly two speakers, indexed 0 and 1.
- 6 to 8 lines total, alternating, starting with speaker 0.
- Every line under 14 words. They are spoken aloud and rendered one at a time.
- Each line REACTS to the line before it. No speeches, no monologues.
- Ordinary South African English. Contractions. How people actually talk.
- There must be a TURN: by the last line something has shifted - a concession,
  an admission, or one of them landing a truth the other cannot answer.
- Funny is good. Warm is better than cruel. They like each other underneath.
- NEVER reference real people, real clubs, real matches, real events, or any \
checkable fact. This is fiction and must stay fiction.

Return ONLY valid JSON:
{"title": "...", "premise": "one line", "lines": [{"who": 0, "text": "..."}]}"""


def _extract_json(text: str) -> dict | None:
    """First balanced JSON object in the reply.

    A model that has been told to return only JSON still sometimes wraps it in
    prose or a fence, and a naive json.loads on the whole reply throws 'Extra
    data' - which has already killed one scheduled build on this project.
    """
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start = t.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(t[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None


def _validate(scene: dict) -> tuple[bool, str]:
    """Refuse a scene that would render badly, rather than render it."""
    if not scene or not isinstance(scene.get("lines"), list):
        return False, "no lines"
    lines = scene["lines"]
    if not (4 <= len(lines) <= 10):
        return False, f"{len(lines)} lines, want 4-10"
    for i, ln in enumerate(lines):
        if int(ln.get("who", -1)) not in (0, 1):
            return False, f"line {i} has no valid speaker"
        words = len(str(ln.get("text", "")).split())
        if not (1 <= words <= 20):
            return False, f"line {i} is {words} words"
    # alternating: two lines from the same person in a row is a monologue
    # split in half, and it breaks the shot/reverse-shot cut
    runs = sum(1 for a, b in zip(lines, lines[1:])
               if int(a["who"]) == int(b["who"]))
    if runs > 1:
        return False, f"{runs} consecutive same-speaker lines"
    return True, ""


async def write_scene(premise: str = "", cast=("her", "him"),
                      attempts: int = 3) -> dict | None:
    """Ask the model for a scene, validate it, retry on a bad one."""
    who = (f"Speaker 0 is {cast[0]}. Speaker 1 is {cast[1]}. "
           "They are a couple who have been together a while.")
    ask = premise or (
        "One of them has been waiting for the other. Something small was "
        "promised and not delivered. It is not really about that.")
    prompt = f"{who}\n\nWrite the scene. Premise: {ask}"

    last = ""
    for n in range(attempts):
        text = await _ask(SYSTEM, prompt if n == 0 else
                          prompt + f"\n\nYour last attempt was rejected: "
                                   f"{last}. Fix exactly that.")
        scene = _extract_json(text or "")
        ok, why = _validate(scene or {})
        if ok:
            print(f"[SceneWriter] '{scene.get('title','untitled')}' — "
                  f"{len(scene['lines'])} lines")
            return scene
        last = why
        print(f"[SceneWriter] attempt {n+1} rejected: {why}")
    return None


async def _ask(system: str, prompt: str) -> str:
    """Gemini first, Claude second. Both are already configured here."""
    key = os.getenv("GEMINI_API_KEY")
    if key:
        try:
            import httpx
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "gemini-2.0-flash:generateContent?key=" + key)
            body = {"contents": [{"parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": system}]},
                    "generationConfig": {"temperature": 1.0,
                                         "maxOutputTokens": 900}}
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(url, json=body)
                d = r.json()
            return (d["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            print(f"[SceneWriter] gemini failed: {str(e)[:90]}")

    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key,
                             "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-5-20250929",
                          "max_tokens": 900, "system": system,
                          "messages": [{"role": "user", "content": prompt}]})
                d = r.json()
            return d["content"][0]["text"]
        except Exception as e:
            print(f"[SceneWriter] claude failed: {str(e)[:90]}")
    return ""
