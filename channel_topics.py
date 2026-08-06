"""Channel topic brains — one fresh package per niche for the $0 graphic-reel engine.

tech_news uses the live grounded news brain. ai_money + motivation use Gemini (Claude fallback)
with EVERGREEN / educational prompts — deliberately no fabricated live market figures or breaking
stats, so the graphics stay accurate. Per-niche dedup (logs/posted_<niche>.json) so nothing repeats.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY

ROOT = Path(__file__).resolve().parent
LOGDIR = ROOT / "logs"
LOGDIR.mkdir(exist_ok=True)


def _clean_json(t):
    t = re.sub(r"```(?:json)?", "", t).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    return m.group(0) if m else t


def _log_path(niche):
    return LOGDIR / f"posted_{niche}.json"


def _recent(niche, n=12):
    p = _log_path(niche)
    if not p.exists():
        return []
    try:
        return [d.get("title", "") for d in json.loads(p.read_text())[-n:]]
    except Exception:
        return []


def log_posted(niche, pkg):
    p = _log_path(niche)
    data = []
    if p.exists():
        try:
            data = json.loads(p.read_text())
        except Exception:
            data = []
    data.append({"date": datetime.now().isoformat(), "title": pkg.get("title"), "source": pkg.get("source")})
    p.write_text(json.dumps(data, indent=2))


SCHEMAS = {
    "ai_money": (
        "You are a trusted finance educator. Write a fresh ~20-second vertical reel that teaches ONE "
        "evergreen money principle (e.g. compound interest, budgeting, index funds, emergency fund, "
        "avoiding high-interest debt, raising your savings rate). Base it ONLY on well-established "
        "personal-finance truths. Do NOT invent live market prices, current interest rates, or any "
        "breaking/specific figures; any number must be a widely-known general fact (e.g. the rule of 72). "
        "Return ONLY a JSON object (no markdown) with keys:\n"
        '{"title":"4-7 word punchy title","hook_line":"6-9 word scroll-stopper",'
        '"narration":"~55 word friendly voiceover teaching the principle",'
        '"steps":["short step 1","short step 2","short step 3"],'
        '"flow_title":"3-4 word label for the steps",'
        '"comment_prompt":"one engaging question","caption":"1-2 sentence caption + 4 hashtags"}'
    ),
    "motivation": (
        "You are a motivational creator. Write a fresh 15-20 second vertical reel with a powerful, "
        "positive message about discipline, consistency, self-belief, focus or growth. No factual "
        "claims or statistics. Return ONLY a JSON object (no markdown) with keys:\n"
        '{"title":"4-7 word punchy title","hook_line":"6-9 word scroll-stopper",'
        '"narration":"~45 word spoken message, second person, uplifting",'
        '"quote":"one short punchy line, 64 characters max",'
        '"comment_prompt":"one engaging question","caption":"1-2 sentence caption + 4 hashtags"}'
    ),
}


def _gen(niche):
    schema = SCHEMAS[niche]
    avoid = _recent(niche)
    prompt = schema + (("\n\nDo NOT repeat these recent titles:\n" + "\n".join("- " + t for t in avoid)) if avoid else "")
    if GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
                try:
                    r = client.models.generate_content(model=model, contents=prompt)
                    if r and r.text:
                        d = json.loads(_clean_json(r.text))
                        d["source"] = model
                        return d
                except Exception as e:
                    print(f"[topic:{niche}] {model}: {e}")
        except Exception as e:
            print(f"[topic:{niche}] gemini unavailable: {e}")
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            m = c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=1200,
                                  messages=[{"role": "user", "content": prompt}])
            d = json.loads(_clean_json(m.content[0].text))
            d["source"] = "claude-haiku-4-5"
            return d
        except Exception as e:
            print(f"[topic:{niche}] claude: {e}")
    return None


def get_topic(niche):
    """Return a fresh package for `niche` with the keys the template engine reads."""
    if niche == "tech_news":
        from news_topic_generator import get_fresh_topic
        pkg = get_fresh_topic()
        pkg["niche"] = "tech_news"
        return pkg
    if niche not in SCHEMAS:
        raise SystemExit(f"no topic brain for niche '{niche}'")
    d = _gen(niche)
    if not d:
        raise SystemExit(f"topic brain failed for {niche} (no Gemini/Claude result)")
    d["niche"] = niche
    return d


if __name__ == "__main__":
    import sys
    n = sys.argv[1] if len(sys.argv) > 1 else "ai_money"
    print(json.dumps(get_topic(n), indent=2)[:2000])
