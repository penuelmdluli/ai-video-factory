"""AI news brain — fetches the LATEST Africa/global-power news and writes a fresh,
non-repeating vertical-reel package (topic + narration + 8 shots + foley + graphics).

Gemini (with live Google Search grounding) primary -> Claude fallback. Dedupes
against logs/posted_topics.json so we never post the same story twice.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
LOG = ROOT / "logs" / "posted_topics.json"
LOG.parent.mkdir(exist_ok=True)

SCHEMA_HINT = """Return ONLY a JSON object (no markdown) with EXACTLY these keys:
{
 "title": "<punchy 4-8 word headline>",
 "angle": "<one line: the specific fresh angle, for dedup>",
 "narration": "<~70 word news-anchor voiceover, tense, factual, generic - NO real named individuals doing specific acts>",
 "ticker": "<one-line breaking-news ticker>",
 "caption": "<facebook caption, 1-2 sentences + 4 hashtags>",
 "lowerthird_label": "<3-5 word lower-third label>",
 "flags": ["<2-letter code>", "<2-letter code>"],
 "shots": [
   {"name":"01_x","prompt":"<PHOTOREAL DYNAMIC ACTION vertical shot, strong movement, real specific location, ends with 'photorealistic, dynamic motion, handheld, cinematic, 4k'>","foley":"<short sound hint>"},
   ... EXACTLY 8 shots named 01_.. through 08_..
 ]
}
Rules for shots — MAXIMUM ENERGY + PHOTOREAL + LOCATION-SPECIFIC (must be eye-catching, NOT static):
- Every shot MUST show strong MOVEMENT/ACTION: moving fast, exploding, running, crowds surging,
  protests/riots, vehicles speeding, aircraft banking, fire and smoke billowing — with camera
  dynamism (fast tracking, handheld shaky cam, rapid push-in, drone swoop, whip pan). NEVER a
  still/standing/calm scene.
- PHOTOREALISTIC and CLOSE TO REALITY — real-looking places, not abstract maps or diagrams.
- LOCATION-SPECIFIC: if the story involves SOUTH AFRICA, SHOW recognizable South Africa —
  Johannesburg or Cape Town skyline, Table Mountain, South African gold/platinum mines, the
  Union Buildings, SA highways, townships, the South African flag. For any other country, show
  THAT country's recognizable real settings.
- People may appear but ONLY as anonymous crowds/silhouettes/workers/soldiers — NEVER a real
  identifiable named individual, and never a claim to be authentic footage of a specific real event.
- End every prompt with 'photorealistic, dynamic motion, handheld, cinematic, 4k'."""


def _recent_titles(n=12):
    if not LOG.exists():
        return []
    try:
        data = json.loads(LOG.read_text())
        return [d.get("title", "") + " | " + d.get("angle", "") for d in data[-n:]]
    except Exception:
        return []


def _clean_json(t):
    t = re.sub(r"```(?:json)?", "", t).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    return m.group(0) if m else t


def _prompt(recent):
    today = datetime.now().strftime("%B %d, %Y")
    avoid = "\n".join(f"- {r}" for r in recent) if recent else "(none yet)"
    return (f"Today is {today}. Find the SINGLE most important CURRENT news story about Africa or South "
            f"Africa that connects to global powers (US, China, Russia, EU) — economy, resources, "
            f"security, diplomacy, energy, or trade. Base it on real current headlines.\n\n"
            f"Do NOT repeat any of these recently-posted angles:\n{avoid}\n\n"
            f"Write a fresh 20-25 second vertical news reel package about it.\n\n{SCHEMA_HINT}")


def _try_gemini(recent):
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        cfg = None
        try:
            cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        except Exception:
            cfg = None
        for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                r = client.models.generate_content(model=model, contents=_prompt(recent),
                                                    config=cfg) if cfg else \
                    client.models.generate_content(model=model, contents=_prompt(recent))
                if r and r.text:
                    d = json.loads(_clean_json(r.text))
                    if d.get("shots") and len(d["shots"]) >= 6:
                        d["source"] = f"{model}+grounding" if cfg else model
                        return d
            except Exception as e:
                print(f"[NewsBrain] {model}: {e}")
    except Exception as e:
        print(f"[NewsBrain] gemini unavailable: {e}")
    return None


def _try_claude(recent):
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        c = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        m = c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=2000,
                              messages=[{"role": "user", "content": _prompt(recent)}])
        d = json.loads(_clean_json(m.content[0].text))
        if d.get("shots"):
            d["source"] = "claude-haiku-4-5"
            return d
    except Exception as e:
        print(f"[NewsBrain] claude: {e}")
    return None


def get_fresh_topic():
    recent = _recent_titles()
    pkg = _try_gemini(recent) or _try_claude(recent)
    if not pkg:
        raise SystemExit("News brain failed (no Gemini/Claude result).")
    # normalise shot names
    for i, s in enumerate(pkg["shots"][:8], 1):
        s["name"] = f"{i:02d}_" + re.sub(r"[^a-z0-9]", "", (s.get("name", f"shot{i}").split('_')[-1].lower()))[:10] or f"{i:02d}_shot"
    pkg["shots"] = pkg["shots"][:8]
    pkg.setdefault("flags", ["ZA", "US"])
    return pkg


def log_posted(pkg):
    data = []
    if LOG.exists():
        try: data = json.loads(LOG.read_text())
        except Exception: data = []
    data.append({"date": datetime.now().isoformat(), "title": pkg.get("title"),
                 "angle": pkg.get("angle"), "source": pkg.get("source")})
    LOG.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    p = get_fresh_topic()
    print(json.dumps(p, indent=2)[:2500])
    print("\nsource:", p.get("source"))
