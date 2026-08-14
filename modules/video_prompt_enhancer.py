"""AI video-prompt enhancer — turns a raw topic into an LTX-optimized prompt.

Same pattern as script_writer: Gemini (primary, free) -> Claude (fallback).
LTX-Video responds best to ONE coherent scene described in rich detail with
explicit camera move, subject motion, lighting and film-stock cues. This module
encodes those best-practices into a meta-prompt so every clip we send to the
RunPod LTX worker is already tuned for maximum quality.

Returns: { prompt, negative_prompt, headline, source_ai } | None
"""
import json
import re

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY

# Strong default negative prompt for LTX (distilled 0.9.7).
DEFAULT_NEGATIVE = (
    "worst quality, inconsistent motion, blurry, jittery, distorted, warped faces, "
    "extra limbs, text artifacts, watermark, low resolution, flickering, morphing"
)

_META = """You are a world-class cinematographer writing prompts for the LTX-Video AI model.
Turn the TOPIC below into ONE vivid, single-scene video prompt that LTX will render beautifully.

Rules for a great LTX prompt:
- Describe exactly ONE coherent scene (no scene cuts, no "then").
- Lead with the subject and its MOTION, then the CAMERA move (dolly, pan, aerial, slow push-in),
  then LIGHTING and mood, then a film-stock/quality cue (e.g. "shot on 35mm film, cinematic, highly detailed, 4k").
- Keep it 40-70 words. Concrete nouns and verbs. No lists, no camera brand names, no dialogue.
- Avoid crowds or many small subjects (LTX distorts them); prefer 1-3 clear subjects.

TOPIC: {topic}
NICHE / CHANNEL VIBE: {niche}

Respond with ONLY a JSON object, no markdown:
{{"prompt": "<the cinematic video prompt>", "headline": "<punchy 3-6 word on-screen headline>"}}"""


def _clean_json(text: str) -> str:
    text = re.sub(r"```(?:json)?", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text


def _try_gemini(topic: str, niche: str) -> dict | None:
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = _META.format(topic=topic, niche=niche)
        for model_name in ("gemini-3.7-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"):
            try:
                r = client.models.generate_content(model=model_name, contents=prompt)
                if r and r.text:
                    d = json.loads(_clean_json(r.text))
                    if d.get("prompt"):
                        d["source_ai"] = model_name
                        return d
            except Exception as e:
                print(f"[PromptEnhancer] {model_name} failed: {e}")
                continue
    except Exception as e:
        print(f"[PromptEnhancer] Gemini unavailable: {e}")
    return None


def _try_claude(topic: str, niche: str) -> dict | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": _META.format(topic=topic, niche=niche)}],
        )
        d = json.loads(_clean_json(msg.content[0].text))
        if d.get("prompt"):
            d["source_ai"] = "claude-haiku-4-5"
            return d
    except Exception as e:
        print(f"[PromptEnhancer] Claude failed: {e}")
    return None


def enhance_video_prompt(topic: str, niche: str = "tech news") -> dict:
    """Gemini -> Claude -> graceful fallback. Always returns a usable dict."""
    result = _try_gemini(topic, niche) or _try_claude(topic, niche)
    if not result:
        # Deterministic fallback so the pipeline never blocks on AI quota.
        result = {
            "prompt": (f"A cinematic slow push-in on {topic}, dramatic volumetric lighting, "
                       "shallow depth of field, shot on 35mm film, highly detailed, 4k, cinematic color grade"),
            "headline": topic[:40],
            "source_ai": "fallback",
        }
    result.setdefault("negative_prompt", DEFAULT_NEGATIVE)
    result["topic"] = topic
    return result


if __name__ == "__main__":
    import sys
    t = " ".join(sys.argv[1:]) or "the newest AI smartphone chip launch"
    out = enhance_video_prompt(t, "tech news, fast-paced, futuristic")
    print(json.dumps(out, indent=2))
