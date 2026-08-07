#!/usr/bin/env python
"""New WILD MINDS episode from a topic.

An LLM writes a short talking-animal dialogue about your topic, Veo 3 renders each shot
(cheap defaults: veo3_lite, 6s), then the shots are stitched and branded.

  python new_episode.py "why do humans work all day"
  python new_episode.py "the meaning of the moon" --shots 4
  python new_episode.py "money" --model veo3_fast --duration 8      # higher quality, pricier

Needs KIE_API_KEY in .env.
"""
import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from make_animal_movie import STYLE, SCENE, stitch
from modules.veo_kie import generate_veo, check_key, estimate_cost
from modules.wild_brand import brand_video

VOICE_STYLE = {
    "lion": "a deep, wise rumbling voice",
    "tiger": "a smooth, smug, low voice",
    "rabbit": "a small, nervous, squeaky voice",
    "owl": "a slow, thoughtful voice",
    "monkey": "a fast, cheeky voice",
}


def write_script(topic, n=3):
    """LLM writes an n-line talking-animal dialogue about `topic`. Returns [(speaker, line), ...]."""
    from config import GEMINI_API_KEY, ANTHROPIC_API_KEY
    prompt = (
        f'Write a funny, slightly profound {n}-line dialogue for a viral talking-animal video about: '
        f'"{topic}". Characters: a wise lion, a smug tiger, and a nervous little rabbit, all sitting '
        f'together in a jungle. Each line is ONE short spoken sentence (max 18 words) by ONE animal, '
        f'building to a punchline on the final line. They are animals amused/baffled by humans. Keep it '
        f'clean and universally relatable. Return ONLY a JSON array of {n} objects like '
        f'[{{"speaker":"lion","line":"..."}}] using only lion, tiger, or rabbit.')
    txt = None
    if GEMINI_API_KEY:
        try:
            from google import genai
            c = genai.Client(api_key=GEMINI_API_KEY)
            r = c.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            txt = r.text
        except Exception as e:
            print(f"[script] gemini failed: {e}", flush=True)
    if not txt and ANTHROPIC_API_KEY:
        try:
            import anthropic
            m = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=700,
                messages=[{"role": "user", "content": prompt}])
            txt = m.content[0].text
        except Exception as e:
            print(f"[script] claude failed: {e}", flush=True)
    if not txt:
        raise SystemExit("script generation failed (no Gemini/Claude).")
    t = re.sub(r"```(?:json)?", "", txt).strip()
    mt = re.search(r"\[.*\]", t, re.DOTALL)
    data = json.loads(mt.group(0) if mt else t)
    out = []
    for d in data[:n]:
        spk = str(d.get("speaker", "lion")).lower()
        if spk not in ("lion", "tiger", "rabbit"):
            spk = "lion"
        out.append((spk, d.get("line", "").strip()))
    return [x for x in out if x[1]]


def build_prompt(speaker, line):
    v = VOICE_STYLE.get(speaker, "a distinctive voice")
    return STYLE + SCENE + f'The {speaker} says in {v}: "{line}"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--model", default="veo3_lite", choices=["veo3_lite", "veo3_fast", "veo3"])
    ap.add_argument("--duration", type=int, default=6, choices=[4, 6, 8])
    ap.add_argument("--shots", type=int, default=3)
    a = ap.parse_args()

    if not check_key():
        print("KIE_API_KEY not set — add it to .env (https://kie.ai).", flush=True)
        return

    print(f'=== WILD MINDS — topic: "{a.topic}" ===', flush=True)
    script = write_script(a.topic, a.shots)
    for s, l in script:
        print(f"  {s.upper()}: {l}", flush=True)
    est = sum(estimate_cost(a.model, a.duration) for _ in script)
    print(f"  {len(script)} shots x {a.duration}s ({a.model}) ~ ${est:.2f}", flush=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"wildminds_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, (spk, line) in enumerate(script):
        c = out / f"shot_{i}.mp4"
        try:
            generate_veo(build_prompt(spk, line), str(c), model=a.model, aspect="9:16",
                         resolution="720p", duration=a.duration)
            clips.append(str(c))
        except Exception as e:
            print(f"  shot {i} FAILED: {e}", flush=True)
    if not clips:
        print("no clips generated.", flush=True)
        return

    stitched = out / "stitched.mp4"
    if len(clips) == 1:
        shutil.copy(clips[0], stitched)
    else:
        stitch(clips, str(stitched))
    final = out / "episode.mp4"
    brand_video(str(stitched), str(final))
    print(f"EPISODE -> {final}", flush=True)


if __name__ == "__main__":
    main()
