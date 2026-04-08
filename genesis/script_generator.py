"""
Genesis Content Engine — Script Generator

Uses Claude claude-sonnet-4-20250514 to generate 40-second video scripts per brand.
Extracts hook line for caption. Stores in DB.
"""
import time
import anthropic

from genesis.genesis_config import ANTHROPIC_API_KEY, SCRIPT_PROMPTS, BRANDS
from genesis.db import save_script, mark_trend_used, log_pipeline


def generate_script(brand: str, trend: dict) -> dict | None:
    """Generate a video script for a brand using the trend's headline."""
    if not ANTHROPIC_API_KEY:
        log_pipeline("script_generate", brand, "failed", "ANTHROPIC_API_KEY not set")
        return None

    prompt_config = SCRIPT_PROMPTS.get(brand)
    if not prompt_config:
        log_pipeline("script_generate", brand, "failed", f"No prompt config for brand: {brand}")
        return None

    start = time.time()

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # Use adaptive prompt if we have performance data
        try:
            from genesis.intelligence import get_adaptive_prompt
            system_prompt = get_adaptive_prompt(brand)
        except Exception:
            system_prompt = prompt_config["system"]

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Write a script about: {trend['headline']}. Topic: {trend['topic']}"
            }]
        )

        script = message.content[0].text if message.content else ""

        if not script:
            log_pipeline("script_generate", brand, "failed", "Empty script returned", time.time() - start)
            return None

        # Extract hook line — first actual spoken line, not a header/title
        import re
        lines = [l.strip() for l in script.split("\n") if l.strip()]
        hook_line = trend["headline"]  # fallback
        for line in lines:
            # Skip markdown headers, titles, stage directions, and formatting
            if line.startswith("#") or line.startswith("**") or line.startswith("---"):
                continue
            if re.match(r'^\[.*\]$', line):  # pure stage direction line
                continue
            if re.match(r'^(TITLE|SCRIPT|DURATION|FORMAT|SCENE)', line, re.IGNORECASE):
                continue
            # Clean the line
            cleaned = re.sub(r'\[.*?\]', '', line).strip()
            cleaned = re.sub(r'^(NARRATOR|HOST|ANCHOR|SPEAKER|VOICEOVER|VO)[:\s]*', '', cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r'^\*\*?(.*?)\*\*?$', r'\1', cleaned).strip()  # remove bold
            if len(cleaned) >= 10:
                hook_line = cleaned
                break

        # Build caption
        brand_config = BRANDS[brand]
        prefix = prompt_config.get("caption_prefix", "")
        hashtags = " ".join(brand_config["hashtags"][:5])

        if prefix:
            caption = f"{prefix}: {hook_line[:100]}\n\n{hashtags}"
        else:
            caption = f"{hook_line[:100]}\n\n{hashtags}"

        # Save to DB
        trend_id = trend.get("id") or trend.get("trend_id", 0)
        script_id = save_script(trend_id, brand, script, hook_line, caption)

        if trend_id:
            mark_trend_used(trend_id)

        duration = time.time() - start
        log_pipeline("script_generate", brand, "success", f"Script: {len(script)} chars, {len(script.split())} words", duration)

        return {
            "script_id": script_id,
            "script": script,
            "hook_line": hook_line,
            "caption": caption,
            "word_count": len(script.split()),
        }

    except Exception as e:
        duration = time.time() - start
        log_pipeline("script_generate", brand, "failed", str(e), duration)
        print(f"  ❌ Script generation failed for {brand}: {e}")
        return None


def generate_all_scripts(trends: dict) -> dict:
    """Generate scripts for all brands that have trends."""
    print("\n📝 PHASE 2: Generating Scripts...")

    results = {}
    for brand, trend in trends.items():
        if not trend:
            print(f"  ⏭️  {BRANDS[brand]['name']}: No trend, skipping")
            continue

        result = generate_script(brand, trend)
        results[brand] = result

        if result:
            print(f"  ✅ {BRANDS[brand]['name']}: {result['word_count']} words — \"{result['hook_line'][:60]}\"")
        else:
            print(f"  ❌ {BRANDS[brand]['name']}: Script generation failed")

    return results


if __name__ == "__main__":
    # Test with a dummy trend
    test_trend = {
        "id": 0,
        "topic": "Test Topic",
        "headline": "Scientists discover AI can predict earthquakes 48 hours in advance",
        "score": 10.0,
    }
    result = generate_script("news", test_trend)
    if result:
        print(f"\nScript ({result['word_count']} words):\n{result['script']}")
