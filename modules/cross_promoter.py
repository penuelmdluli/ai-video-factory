"""
Cross-Promoter — Leverage big pages to grow smaller ones.

Strategy:
- Blissful Moments (58K) promotes: health_wellness, motivation, limitless_you
- Tech Pulse Africa (10K) promotes: ai_money, limitless_you
- Max 1 cross-promo per promoting page per day
- Branded image cards with promoted page's Facebook URL
- Natural, organic-sounding cross-promotion posts
"""
import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, ROOT_DIR, ANTHROPIC_API_KEY, GEMINI_API_KEY


# ── Constants ────────────────────────────────────────────────
GRAPH_API_BASE = "https://graph.facebook.com/v24.0"
DB_PATH = ROOT_DIR / "data" / "growth_analytics.db"

NICHE_PAGE_NAMES = {
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Blissful Moments",
    "limitless_you": "Limitless You",
}

# Facebook page URLs for cross-linking
NICHE_FB_URLS = {
    "ai_money": "https://www.facebook.com/profile.php?id=107465491085378",
    "tech_news": "https://www.facebook.com/profile.php?id=100919755007786",
    "motivation": "https://www.facebook.com/profile.php?id=102206758210905",
    "health_wellness": "https://www.facebook.com/profile.php?id=106788301081578",
    "blissful_moments": "https://www.facebook.com/profile.php?id=112465853843545",
    "limitless_you": "https://www.facebook.com/profile.php?id=104120995511039",
}

# Promotion pairs: big pages promote smaller ones
# (promoter, promoted, reason for connection)
PROMO_PAIRS = [
    ("blissful_moments", "health_wellness", "wellness and inner peace"),
    ("blissful_moments", "motivation", "positive mindset and growth"),
    ("blissful_moments", "limitless_you", "personal development and joy"),
    ("tech_news", "ai_money", "AI technology for financial growth"),
    ("tech_news", "limitless_you", "AI-powered self-improvement"),
    ("ai_money", "tech_news", "cutting-edge AI technology"),
]

# Niche themes for content generation
NICHE_THEMES = {
    "ai_money": "making money with AI, side hustles, financial freedom",
    "tech_news": "AI breakthroughs, mind-bending technology, what-if scenarios",
    "motivation": "daily motivation, mindset, discipline, success stories",
    "health_wellness": "natural health, herbal remedies, organic living, wellness",
    "blissful_moments": "peace, gratitude, satisfying moments, joy, ASMR",
    "limitless_you": "AI-powered self-improvement, habit science, personal growth",
}


# ── Database ─────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tables():
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cross_promos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                promoter_niche TEXT NOT NULL,
                promoted_niche TEXT NOT NULL,
                post_id TEXT DEFAULT '',
                caption TEXT DEFAULT '',
                posted_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_crosspromo_date ON cross_promos(date, promoter_niche);
        """)
        conn.commit()
    finally:
        conn.close()


_init_tables()


# ── Promo History ────────────────────────────────────────────

def _already_promoted_today(promoter: str) -> bool:
    """Check if this promoter has already done a cross-promo today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM cross_promos WHERE date = ? AND promoter_niche = ?",
            (today, promoter),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _record_promo(promoter: str, promoted: str, post_id: str, caption: str):
    """Record a cross-promotion in the database."""
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO cross_promos (date, promoter_niche, promoted_niche, post_id, caption, posted_at) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d"), promoter, promoted, post_id, caption[:500], datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _get_recent_promos(promoter: str, promoted: str, days: int = 7) -> int:
    """Count how many times this pair has been promoted recently."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM cross_promos WHERE promoter_niche = ? AND promoted_niche = ? AND date >= ?",
            (promoter, promoted, cutoff),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


# ── Content Generation ───────────────────────────────────────

async def generate_cross_promo_content(promoter: str, promoted: str, connection: str) -> dict | None:
    """
    Generate natural-sounding cross-promotion content using AI.

    Returns: {caption, promoted_url}
    """
    promoter_name = NICHE_PAGE_NAMES.get(promoter, promoter)
    promoted_name = NICHE_PAGE_NAMES.get(promoted, promoted)
    promoted_url = NICHE_FB_URLS.get(promoted, "")
    promoted_theme = NICHE_THEMES.get(promoted, "great content")

    prompt = f"""You're the social media manager for "{promoter_name}" (a Facebook page).
Write a cross-promotion post recommending our sister page "{promoted_name}".

CONNECTION: Both pages share a focus on {connection}.
PROMOTED PAGE THEME: {promoted_theme}

RULES:
- 2-3 sentences MAX
- Sound natural and genuine, like recommending a friend's page
- Mention what the promoted page offers
- End with the page URL (I'll add it)
- Use 1-2 relevant emojis
- Do NOT say "sponsored" or "ad"
- Do NOT use corporate language
- Make it feel like a personal recommendation

Example style:
"If you love what we share here, you'll LOVE our sister page {promoted_name}! They focus on {promoted_theme} and the content is absolutely fire. Go follow them:"

Write the caption (no quotes):"""

    caption = None

    # Try Claude
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            caption = response.content[0].text.strip().strip('"')
        except Exception as e:
            print(f"[CrossPromo] Claude failed: {e}")

    # Fallback to Gemini
    if not caption and GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            response = model.generate_content(prompt)
            caption = response.text.strip().strip('"')
        except Exception as e:
            print(f"[CrossPromo] Gemini failed: {e}")

    # Final fallback
    if not caption:
        caption = (
            f"We love sharing amazing content with you, and our sister page "
            f"{promoted_name} does the same! They focus on {promoted_theme} "
            f"and you definitely need to check them out."
        )

    # Append the URL
    if promoted_url:
        caption += f"\n\nFollow them here: {promoted_url}"

    caption += f"\n\n#recommended #mustfollow #{promoted.replace('_', '')}"

    return {
        "caption": caption,
        "promoted_url": promoted_url,
        "promoter": promoter,
        "promoted": promoted,
    }


# ── Posting ──────────────────────────────────────────────────

async def post_cross_promo(promoter: str, content: dict) -> dict:
    """
    Post a cross-promotion to the promoter's Facebook page.

    Uses text post (not image) so the URL auto-generates a preview card.
    """
    from config import page_locked
    if page_locked(promoter):
        print(f"[CrossPromo] {promoter} page is locked to its own poster — skipping")
        return {"success": False, "error": "page_locked"}

    page_id = os.getenv(f"FB_PAGE_ID_{promoter}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{promoter}", "")

    if not page_id or not page_token:
        return {"success": False, "error": "no_config"}

    try:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/feed",
            data={
                "message": content["caption"],
                "access_token": page_token,
            },
            timeout=30,
        )

        result = resp.json()
        if "id" in result:
            print(f"[CrossPromo] Posted on {NICHE_PAGE_NAMES.get(promoter, promoter)}: promoting {content['promoted']}")
            _record_promo(promoter, content["promoted"], result["id"], content["caption"])
            return {"success": True, "post_id": result["id"]}
        else:
            error = result.get("error", {}).get("message", str(result))
            print(f"[CrossPromo] Post failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        print(f"[CrossPromo] Error: {e}")
        return {"success": False, "error": str(e)}


# ── Main Entry Point ─────────────────────────────────────────

def get_promotion_pairs() -> list[tuple[str, str, str]]:
    """
    Get today's promotion pairs, filtering out already-promoted and over-promoted.

    Returns list of (promoter, promoted, connection) tuples.
    """
    from config import page_locked
    pairs = []
    for promoter, promoted, connection in PROMO_PAIRS:
        # Never post on (or advertise) a page locked to its own poster
        if page_locked(promoter) or page_locked(promoted):
            continue

        # Skip if already promoted today
        if _already_promoted_today(promoter):
            continue

        # Skip if promoted too many times recently (max 3/week per pair)
        if _get_recent_promos(promoter, promoted, days=7) >= 3:
            continue

        # Check both pages are configured
        if not os.getenv(f"FB_PAGE_ID_{promoter}") or not os.getenv(f"FB_PAGE_TOKEN_{promoter}"):
            continue
        if not os.getenv(f"FB_PAGE_ID_{promoted}") or not os.getenv(f"FB_PAGE_TOKEN_{promoted}"):
            continue

        pairs.append((promoter, promoted, connection))

    return pairs


async def run_cross_promo_round() -> list[dict]:
    """
    Execute one round of cross-promotions.

    Returns list of results.
    """
    pairs = get_promotion_pairs()
    if not pairs:
        print("[CrossPromo] No promotions needed today (already done or no valid pairs)")
        return []

    results = []
    for promoter, promoted, connection in pairs:
        promoter_name = NICHE_PAGE_NAMES.get(promoter, promoter)
        promoted_name = NICHE_PAGE_NAMES.get(promoted, promoted)
        print(f"\n[CrossPromo] {promoter_name} -> promoting -> {promoted_name}")

        # Generate content
        content = await generate_cross_promo_content(promoter, promoted, connection)
        if not content:
            print(f"[CrossPromo] Failed to generate content for {promoter} -> {promoted}")
            continue

        # Post it
        result = await post_cross_promo(promoter, content)
        result["promoter"] = promoter
        result["promoted"] = promoted
        results.append(result)

    # Summary
    successful = sum(1 for r in results if r.get("success"))
    print(f"\n[CrossPromo] === Round Complete: {successful}/{len(results)} promos posted ===")
    return results


def get_promo_history(days: int = 30) -> list[dict]:
    """Get cross-promotion history."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM cross_promos WHERE date >= ? ORDER BY posted_at DESC",
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def print_promo_stats():
    """Print cross-promotion statistics."""
    history = get_promo_history(30)

    print("\n" + "=" * 60)
    print("  CROSS-PROMOTION STATS (Last 30 Days)")
    print("=" * 60)

    if not history:
        print("  No cross-promotions recorded yet.")
        print("=" * 60)
        return

    # Group by promoter
    from collections import Counter
    promoter_counts = Counter(h["promoter_niche"] for h in history)
    promoted_counts = Counter(h["promoted_niche"] for h in history)

    print(f"\n  Promoters (who's promoting):")
    for niche, count in promoter_counts.most_common():
        print(f"    {NICHE_PAGE_NAMES.get(niche, niche):<25} {count} promos")

    print(f"\n  Promoted (who's being promoted):")
    for niche, count in promoted_counts.most_common():
        print(f"    {NICHE_PAGE_NAMES.get(niche, niche):<25} {count} times")

    print(f"\n  Total promos: {len(history)}")
    print("=" * 60 + "\n")


# ── CLI Entry Point ──────────────────────────────────────────

async def main():
    import sys

    if "--stats" in sys.argv:
        print_promo_stats()
    elif "--pairs" in sys.argv:
        pairs = get_promotion_pairs()
        print(f"\n  Available promotion pairs for today:")
        for promoter, promoted, connection in pairs:
            print(f"    {NICHE_PAGE_NAMES.get(promoter, promoter)} -> {NICHE_PAGE_NAMES.get(promoted, promoted)} ({connection})")
        if not pairs:
            print("    None (already promoted today or no valid pairs)")
    else:
        await run_cross_promo_round()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
