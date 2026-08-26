"""
Community Manager — AI-powered comment reply automation for Facebook pages.

Facebook's algorithm heavily rewards pages that reply to comments.
This module:
- Fetches recent comments from all FB pages
- Uses Claude AI to generate contextual, human-sounding replies
- Rate-limits replies to avoid spam flags
- Tracks replied comments to avoid duplicates
- Prioritizes negative comments for damage control

Rate limiting: Max 10 replies per page per hour, 15s between replies.
"""
import os
import json
import sqlite3
import asyncio
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque

from config import NICHES, ROOT_DIR, ANTHROPIC_API_KEY, GEMINI_API_KEY


# ── Constants ────────────────────────────────────────────────
GRAPH_API_BASE = "https://graph.facebook.com/v24.0"
DB_PATH = ROOT_DIR / "data" / "growth_analytics.db"

# Owner call 2026-08-26: raise the cap so the 281-comment backlog clears
# faster. Backlog-AWARE rather than permanently high — it bursts while there
# is a queue and settles back once the page is caught up, so the page is not
# running at burst rate forever for no reason.
MAX_REPLIES_PER_HOUR = int(os.getenv("COMMUNITY_REPLY_MAX_PER_HOUR", "20"))
BURST_REPLIES = int(os.getenv("COMMUNITY_REPLY_BURST", "60"))
BURST_ABOVE = int(os.getenv("COMMUNITY_BURST_ABOVE", "40"))   # queue size
REPLY_DELAY_SECONDS = int(os.getenv("COMMUNITY_REPLY_DELAY", "8"))

# Niches with active FB pages
ACTIVE_NICHES = [
    "ai_money", "tech_news", "motivation",
    "health_wellness", "blissful_moments", "limitless_you", "sa_pulse",
]

NICHE_PAGE_NAMES = {
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Mzansi Careers",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "SAGA OF THE NORTH",
    "sa_pulse": "Genesis News",
    "limitless_you": "Limitless You",
}

# Page personality for AI replies
NICHE_PERSONALITY = {
    "ai_money": "You're the Smart Money AI page — friendly, knowledgeable about AI and making money online. Use money/business language naturally.",
    "tech_news": "You're Tech Pulse Africa — a calm, credible world war & geopolitics news page covering the biggest global conflicts of the moment and their impact on Africa, for a GLOBAL audience. Speak like a trusted, neutral war correspondent: factual, level-headed, and human.",
    "motivation": "You're Mzansi Careers — a South African jobs page. Warm, practical and encouraging with job seekers. Point people to the official application link in the post. NEVER invent vacancies, closing dates, salaries or requirements, and never promise anyone a job or offer to submit an application on their behalf. If you do not know, say so and point them to the official source.",
    "health_wellness": "You're Herbal Organic Life — caring, health-focused, and knowledgeable about natural wellness. Warm and nurturing tone.",
    "blissful_moments": "You're SAGA OF THE NORTH — a Viking/Norse storytelling page. Speak with the weight of a skald: short, strong, a little mythic. Never modern slang.",
    "limitless_you": "You're Limitless You — empowering, data-driven self-improvement. Motivating but grounded in science and AI insights.",
    # CHIEFS PAGE (owner call 2026-08-26). The old persona said "Chiefs,
    # Pirates and Sundowns fans are ALL welcome", and on the first big reply
    # round it produced "we back all the Mzansi teams here fam — Pirates,
    # Chiefs..." to a rival supporter. That is the page disowning the only
    # thing it is: a Kaizer Chiefs page. Rival fans are still welcome in the
    # comments — being welcoming to them is not the same as being neutral
    # about who we support, and a page with no allegiance has nothing for a
    # Chiefs fan to belong to.
    "sa_pulse": (
        "You're Genesis News — a KAIZER CHIEFS page, run by Amakhosi fans for "
        "Amakhosi fans. Warm, passionate, playful banter; treat every "
        "commenter like family in the group chat. Rival fans are welcome to "
        "argue here and you never insult them — but you are Chiefs and you "
        "never pretend to be neutral, never claim to support another club, "
        "and never say you back all teams. Ask for their predictions and "
        "takes. Never state scores/transfers as fact in replies; opinions "
        "only."),
}

# Negative sentiment keywords for prioritization
NEGATIVE_KEYWORDS = [
    "scam", "fake", "spam", "hate", "terrible", "worst", "awful",
    "refund", "stolen", "fraud", "report", "block", "unfollow",
    "disappointed", "waste", "garbage", "trash", "boring", "stupid",
    "lie", "lying", "misleading", "clickbait", "stop",
]

# Escalation keywords (don't auto-reply, flag for human review)
ESCALATION_KEYWORDS = [
    "suicide", "kill", "die", "harm", "threat", "lawyer",
    "lawsuit", "police", "arrest", "illegal",
]

# Rate limiter: page_id -> deque of reply timestamps
# maxlen must cover the BURST cap, not the resting one — sized at the resting
# cap it silently discards the oldest timestamp and the limiter never trips.
_reply_timestamps: dict[str, deque] = defaultdict(
    lambda: deque(maxlen=max(BURST_REPLIES, MAX_REPLIES_PER_HOUR)))


# ── Database ─────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_tables():
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS replied_comments (
                comment_id TEXT PRIMARY KEY,
                niche TEXT NOT NULL,
                comment_text TEXT DEFAULT '',
                reply_text TEXT DEFAULT '',
                sentiment TEXT DEFAULT 'neutral',
                replied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id TEXT NOT NULL,
                niche TEXT NOT NULL,
                comment_text TEXT DEFAULT '',
                commenter_name TEXT DEFAULT '',
                post_id TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                flagged_at TEXT NOT NULL,
                resolved INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS community_stats (
                date TEXT NOT NULL,
                niche TEXT NOT NULL,
                comments_found INTEGER DEFAULT 0,
                replies_sent INTEGER DEFAULT 0,
                positive_comments INTEGER DEFAULT 0,
                negative_comments INTEGER DEFAULT 0,
                escalations INTEGER DEFAULT 0,
                PRIMARY KEY (date, niche)
            );

            CREATE INDEX IF NOT EXISTS idx_replied_niche ON replied_comments(niche);
            CREATE INDEX IF NOT EXISTS idx_replied_at ON replied_comments(replied_at);
        """)
        conn.commit()
    finally:
        conn.close()


_init_tables()


# ── Comment Fetching ─────────────────────────────────────────

# How many recent posts to sweep for comments. This was 10, which sounds like
# plenty until you count posts rather than days: the page publishes three to six
# times a day, so a post fell out of the window after about two days — while it
# was still collecting comments. On 2026-08-24 three fan comments sat unanswered
# on post #22, all of them posted that same morning, invisible to every round.
# A comment ages out on the 48h rule below; it must not age out on post count.
POST_SWEEP = int(os.getenv("COMMUNITY_POST_SWEEP", "300"))
POST_PAGES_MAX = 12               # posts pages to walk before stopping
COMMENT_PAGES_MAX = 6             # comment pages per post
COMMENTS_PER_POST_MAX = 400
# 48 hours meant a comment left on a Friday reel was ignored by Monday. The
# owner wants old threads answered too, so this is months rather than days —
# still bounded, because a reply to a comment from last season reads as a bot.
COMMENT_MAX_AGE_DAYS = int(os.getenv("COMMUNITY_MAX_AGE_DAYS", "120"))


async def _get(url: str, params: dict) -> dict:
    try:
        r = requests.get(url, params=params, timeout=25)
        if r.status_code != 200:
            print(f"[Community] {r.status_code} on {url.rsplit('/', 1)[-1]}")
            return {}
        return r.json() or {}
    except Exception as e:
        print(f"[Community] fetch failed: {str(e)[:110]}")
        return {}


async def _all_comments_on(post_id: str, token: str) -> list[dict]:
    """Every top-level comment on one post, following the comment pages.

    The comments edge returns about twenty-five by default. The predicted XI
    on 24 Aug drew a hundred and twenty-two, so replying only to what came
    back in the first page meant four fifths of that thread was never even
    looked at.
    """
    out, url = [], f"{GRAPH_API_BASE}/{post_id}/comments"
    params = {"fields": "id,message,from,created_time,parent",
              "limit": 100, "filter": "toplevel", "order": "reverse_chronological",
              "access_token": token}
    for _ in range(COMMENT_PAGES_MAX):
        data = await _get(url, params)
        out.extend(data.get("data") or [])
        nxt = ((data.get("paging") or {}).get("next") or "")
        if not nxt or len(out) >= COMMENTS_PER_POST_MAX:
            break
        url, params = nxt, {}
    return out


async def fetch_recent_comments(niche: str, limit: int = POST_SWEEP) -> list[dict]:
    """
    Every unanswered top-level comment on the page, old posts included.

    Owner call 2026-08-26: "always comment to all post old or new, always
    engage with the followers". Three separate ceilings stopped that, and
    lifting one without the others would not have helped:

      · posts were capped at one page of forty, with no pagination
      · comments were capped at the first page the edge happened to return,
        so a hundred-and-twenty-two-comment thread was mostly invisible
      · anything older than 48 hours was skipped outright

    All three are now walked, bounded by explicit caps so a page with years of
    history cannot turn one sweep into an unbounded crawl. The reply rate
    limiter is untouched — engaging with everyone is the goal, but tripping
    Facebook's spam detection would end the engagement altogether.
    """
    page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
    if not page_id or not page_token:
        return []

    comments = []
    seen_posts = 0
    cutoff = datetime.utcnow() - timedelta(days=COMMENT_MAX_AGE_DAYS)

    # Comments come back NESTED in the posts call. Asking per post cost one
    # HTTP round trip each — 202 posts made a single sweep take over ten
    # minutes, which is useless to a task that runs every thirty. Nested at
    # limit 100 the same sweep is about five calls, and only a post that
    # actually returns a full hundred needs a follow-up.
    url = f"{GRAPH_API_BASE}/{page_id}/posts"
    params = {"fields": "id,message,created_time,"
                        "comments.limit(100){id,message,from,created_time,parent}",
              "limit": 50, "access_token": page_token}
    try:
        for _ in range(POST_PAGES_MAX):
            data = await _get(url, params)
            posts = data.get("data") or []
            if not posts:
                break

            for post in posts:
                if seen_posts >= limit:
                    break
                seen_posts += 1
                post_message = (post.get("message", "") or "")[:200]

                nested = (post.get("comments") or {}).get("data") or []
                if len(nested) >= 100:
                    # only this post is deep enough to be worth paging
                    nested = await _all_comments_on(post["id"], page_token)
                for comment in nested:
                    if is_already_replied(comment["id"]):
                        continue
                    commenter_id = comment.get("from", {}).get("id", "")
                    if commenter_id == page_id:
                        continue
                    if comment.get("parent"):
                        continue
                    try:
                        ct = datetime.strptime(comment["created_time"][:19],
                                               "%Y-%m-%dT%H:%M:%S")
                        if ct < cutoff:
                            continue
                    except (ValueError, KeyError):
                        pass
                    comments.append({
                        "id": comment["id"],
                        "message": comment.get("message", ""),
                        "from_name": comment.get("from", {}).get("name", "Someone"),
                        "from_id": commenter_id,
                        "created_time": comment.get("created_time", ""),
                        "post_id": post["id"],
                        "post_context": post_message,
                    })

            if seen_posts >= limit:
                break
            nxt = ((data.get("paging") or {}).get("next") or "")
            if not nxt:
                break
            url, params = nxt, {}
    except Exception as e:
        print(f"[Community] Error fetching comments for {niche}: {e}")

    print(f"[Community] {niche}: swept {seen_posts} posts, "
          f"{len(comments)} unanswered comment(s)")
    return comments


# ── Sentiment Analysis ───────────────────────────────────────

def analyze_sentiment(comment_text: str) -> str:
    """
    Quick sentiment classification: positive, neutral, negative, complaint.
    Uses keyword matching for speed (no API call needed).
    """
    text_lower = comment_text.lower()

    # Check for escalation keywords first
    for keyword in ESCALATION_KEYWORDS:
        if keyword in text_lower:
            return "escalation"

    # Check for negative sentiment
    negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    if negative_count >= 2:
        return "complaint"
    if negative_count >= 1:
        return "negative"

    # Check for positive indicators
    positive_indicators = [
        "love", "amazing", "great", "awesome", "thank", "best",
        "beautiful", "wonderful", "perfect", "excellent", "helpful",
        "fire", "goat", "legend", "bless", "inspire",
    ]
    # Emoji positivity
    positive_emojis = ["❤", "🔥", "👏", "😍", "🙏", "💯", "👍", "💪", "✨", "🎉"]

    positive_count = sum(1 for kw in positive_indicators if kw in text_lower)
    positive_count += sum(1 for em in positive_emojis if em in comment_text)

    if positive_count >= 1:
        return "positive"

    return "neutral"


# ── AI Reply Generation ──────────────────────────────────────

async def generate_reply(comment: dict, niche: str) -> str | None:
    """
    Generate a contextual, human-sounding reply using Claude AI.

    Rules:
    - Max 2 sentences
    - Friendly, not corporate
    - Include subtle CTA ~20% of the time
    - Match page personality
    - Never argue with negative comments
    """
    import random

    comment_text = comment.get("message", "")
    commenter_name = comment.get("from_name", "")
    post_context = comment.get("post_context", "")
    sentiment = analyze_sentiment(comment_text)

    # Only a genuinely empty comment has nothing to answer. Short ones ("No",
    # "Ok", a single emoji) are still engagement and still deserve a reply —
    # they just don't need an AI round-trip. Previously the <3 guard dropped
    # them silently, and because nothing was recorded the same comment was
    # re-fetched and re-dropped on every subsequent round, forever.
    if not comment_text.strip():
        return None
    if len(comment_text.strip()) < 3:
        return _get_fallback_reply(sentiment, commenter_name)

    # Build personality-aware prompt
    personality = NICHE_PERSONALITY.get(niche, "You're a friendly social media page.")
    include_cta = random.random() < 0.2  # 20% chance of CTA

    # War/geopolitics pages must stay strictly neutral to keep a global audience.
    neutrality_doctrine = ""
    if NICHES.get(niche, {}).get("topic_focus") or niche == "tech_news":
        neutrality_doctrine = """
WAR-NEWS REPLY DOCTRINE (CRITICAL — this page has an international audience):
- Stay STRICTLY NEUTRAL. NEVER take any side in any conflict, never cheer death,
  destruction, or any nation. No political opinions, no "who is right".
- Your job is to keep BOTH sides and all nationalities engaged and welcome.
- If a comment is inflammatory, partisan, or baiting: de-escalate calmly, acknowledge
  the person's feelings, and steer back to facts — do NOT argue or pick a side.
- If asked a factual question: answer briefly and accurately, attribute to "reports".
- If you don't know or it's unverified: say it's still developing / unconfirmed.
- Be respectful of civilians and loss of life on ALL sides. Compassionate, not political.
- Encourage discussion ("what's your read on this?") to boost engagement, never division.
"""

    # PSL pages get the live facts pack so replies can quote REAL numbers —
    # log positions, results, next kickoffs — and answer fixture questions
    # accurately instead of vaguely (owner: "smarter and more relevant").
    facts_block = ""
    if niche == "sa_pulse":
        try:
            from modules.psl_facts import facts_pack
            _facts = await facts_pack()
            if _facts:
                facts_block = (
                    "\nLIVE LEAGUE FACTS — the ONLY facts you may state:\n"
                    f"{_facts}\n"
                    "FACT RULES (CRITICAL): quote numbers exactly as shown. "
                    "If what the fan asks is NOT in these facts (e.g. a "
                    "fixture not listed), say it isn't confirmed yet and "
                    "invite them to follow for the announcement — NEVER "
                    "invent fixtures, dates, scores or stats.\n")
        except Exception:
            pass

    prompt = f"""You are a social media community manager replying to a comment on Facebook.

{personality}
{neutrality_doctrine}{facts_block}
RULES:
- Reply in 1-2 short sentences MAX
- Sound human and warm, NOT like a bot or corporate account
- Use the commenter's first name if natural
- Match the energy of the comment (excited reply to excited comment, etc.)
- For negative comments: be understanding, don't argue, offer to help
- For positive comments: express genuine gratitude
- For questions: give a brief helpful answer
- NEVER use phrases like "Thank you for your comment" or "We appreciate your feedback"
- Use emojis sparingly (max 1-2)
{"- Include a subtle call-to-action like 'Follow for more!' or 'Share with someone who needs this!'" if include_cta else "- Do NOT include any call-to-action"}

COMMENT from {commenter_name}: "{comment_text}"
{"POST CONTEXT: " + post_context if post_context else ""}
SENTIMENT: {sentiment}

Reply (1-2 sentences only, no quotes):"""

    # Try Claude first
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            reply = response.content[0].text.strip()
            # Clean up any quotes
            reply = reply.strip('"').strip("'")
            if len(reply) > 5:
                return reply
        except Exception as e:
            print(f"[Community] Claude failed: {e}")

    # Fallback to Gemini
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-flash-lite-latest")
            response = model.generate_content(prompt)
            reply = response.text.strip().strip('"').strip("'")
            if len(reply) > 5:
                return reply
        except Exception as e:
            print(f"[Community] Gemini failed: {e}")

    # Final fallback: simple template replies
    return _get_fallback_reply(sentiment, commenter_name)


def _get_fallback_reply(sentiment: str, name: str) -> str:
    """Simple template replies when AI is unavailable."""
    import random

    first_name = name.split()[0] if name else ""

    positive_replies = [
        f"So glad this resonated with you{', ' + first_name if first_name else ''}! 🙏",
        f"This made our day{', ' + first_name if first_name else ''}! Thank you! ❤",
        f"Love hearing this! {first_name + ', you' if first_name else 'You'} made our day! 🔥",
    ]
    negative_replies = [
        f"We hear you{', ' + first_name if first_name else ''}. Thanks for the honest feedback.",
        f"Appreciate your perspective{', ' + first_name if first_name else ''}. We're always looking to improve.",
    ]
    neutral_replies = [
        f"Thanks for sharing your thoughts{', ' + first_name if first_name else ''}! 💯",
        f"Great point{', ' + first_name if first_name else ''}! Love the engagement here.",
        f"Appreciate you being here{', ' + first_name if first_name else ''}! 🙌",
    ]

    if sentiment == "positive":
        return random.choice(positive_replies)
    elif sentiment in ("negative", "complaint"):
        return random.choice(negative_replies)
    return random.choice(neutral_replies)


# ── Reply Posting ────────────────────────────────────────────

async def post_reply(comment_id: str, reply_text: str, niche: str) -> dict:
    """
    Post a reply to a Facebook comment.

    POST /{comment_id}/comments with {message, access_token}
    """
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")

    if not page_token:
        return {"success": False, "error": "no_token"}

    try:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{comment_id}/comments",
            data={
                "message": reply_text,
                "access_token": page_token,
            },
            timeout=15,
        )

        result = resp.json()
        if "id" in result:
            return {"success": True, "reply_id": result["id"]}
        else:
            error = result.get("error", {}).get("message", str(result))
            print(f"[Community] Reply failed for {niche}: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        print(f"[Community] Error posting reply: {e}")
        return {"success": False, "error": str(e)}


# ── Rate Limiting ────────────────────────────────────────────

# set per round from the size of the queue actually found
_round_cap: dict[str, int] = {}


def _set_round_cap(page_id: str, backlog: int):
    cap = BURST_REPLIES if backlog >= BURST_ABOVE else MAX_REPLIES_PER_HOUR
    _round_cap[page_id] = cap
    print(f"[Community] backlog {backlog} -> replying up to {cap} this round "
          f"({REPLY_DELAY_SECONDS}s apart)")


def _can_reply(page_id: str) -> bool:
    """Check if we can reply (within rate limits)."""
    now = datetime.now()
    timestamps = _reply_timestamps[page_id]

    # Remove timestamps older than 1 hour
    while timestamps and (now - timestamps[0]).total_seconds() > 3600:
        timestamps.popleft()

    return len(timestamps) < _round_cap.get(page_id, MAX_REPLIES_PER_HOUR)


def _record_reply(page_id: str):
    """Record a reply timestamp for rate limiting."""
    _reply_timestamps[page_id].append(datetime.now())


# ── Deduplication ────────────────────────────────────────────

def is_already_replied(comment_id: str) -> bool:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM replied_comments WHERE comment_id = ?", (comment_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_as_replied(comment_id: str, niche: str, comment_text: str, reply_text: str, sentiment: str):
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO replied_comments (comment_id, niche, comment_text, reply_text, sentiment, replied_at) VALUES (?, ?, ?, ?, ?, ?)",
            (comment_id, niche, comment_text, reply_text, sentiment, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _flag_escalation(comment: dict, niche: str, reason: str):
    """Flag a comment for human review."""
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO escalations (comment_id, niche, comment_text, commenter_name, post_id, reason, flagged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (comment["id"], niche, comment.get("message", ""),
             comment.get("from_name", ""), comment.get("post_id", ""),
             reason, datetime.now().isoformat()),
        )
        conn.commit()
        print(f"[Community] ESCALATION flagged for {niche}: {reason}")
    finally:
        conn.close()


# ── Stats Tracking ───────────────────────────────────────────

def _update_stats(niche: str, comments_found: int, replies_sent: int,
                  positive: int, negative: int, escalations: int):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM community_stats WHERE date = ? AND niche = ?",
            (today, niche),
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE community_stats SET
                    comments_found = comments_found + ?,
                    replies_sent = replies_sent + ?,
                    positive_comments = positive_comments + ?,
                    negative_comments = negative_comments + ?,
                    escalations = escalations + ?
                WHERE date = ? AND niche = ?
            """, (comments_found, replies_sent, positive, negative, escalations, today, niche))
        else:
            conn.execute("""
                INSERT INTO community_stats (date, niche, comments_found, replies_sent, positive_comments, negative_comments, escalations)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (today, niche, comments_found, replies_sent, positive, negative, escalations))

        conn.commit()
    finally:
        conn.close()


def get_reply_stats(days: int = 7) -> dict:
    """Get reply stats for the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT niche, SUM(replies_sent) as total_replies,
                   SUM(comments_found) as total_comments,
                   SUM(positive_comments) as positive,
                   SUM(negative_comments) as negative,
                   SUM(escalations) as escalations
            FROM community_stats
            WHERE date >= ?
            GROUP BY niche
        """, (cutoff,)).fetchall()

        return {row["niche"]: dict(row) for row in rows}
    finally:
        conn.close()


# ── Main Entry Point ─────────────────────────────────────────

async def run_community_round(niches: list[str] | None = None) -> dict:
    """
    Main entry point: fetch comments, generate replies, post them.

    Args:
        niches: List of niches to process (default: all active)

    Returns:
        Summary dict with per-niche stats
    """
    if niches is None:
        niches = ACTIVE_NICHES

    summary = {}

    for niche in niches:
        page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
        if not page_id:
            continue

        print(f"\n[Community] Processing {NICHE_PAGE_NAMES.get(niche, niche)}...")

        # Fetch comments
        comments = await fetch_recent_comments(niche)
        if not comments:
            print(f"[Community] No new comments for {niche}")
            summary[niche] = {"comments": 0, "replies": 0}
            continue

        print(f"[Community] Found {len(comments)} new comments for {niche}")

        # Sort by sentiment: negatives first (damage control)
        sentiment_priority = {"escalation": 0, "complaint": 1, "negative": 2, "neutral": 3, "positive": 4}
        for c in comments:
            c["sentiment"] = analyze_sentiment(c.get("message", ""))
        comments.sort(key=lambda c: sentiment_priority.get(c["sentiment"], 3))

        _set_round_cap(page_id, len(comments))
        replies_sent = 0
        stats = {"positive": 0, "negative": 0, "escalations": 0}

        for comment in comments:
            # Check rate limit
            if not _can_reply(page_id):
                print(f"[Community] Rate limit reached for {niche}, stopping")
                break

            sentiment = comment["sentiment"]

            # Track sentiment counts
            if sentiment == "positive":
                stats["positive"] += 1
            elif sentiment in ("negative", "complaint"):
                stats["negative"] += 1

            # Handle escalations
            if sentiment == "escalation":
                _flag_escalation(comment, niche, "Escalation keywords detected")
                stats["escalations"] += 1
                mark_as_replied(comment["id"], niche, comment.get("message", ""), "[ESCALATED]", sentiment)
                continue

            # Generate reply
            reply_text = await generate_reply(comment, niche)
            if not reply_text:
                # Record it, otherwise this comment is re-fetched and skipped
                # again on every future round with nothing written to the log.
                print(f"[Community] No reply generated for {comment['id']} "
                      f"({comment.get('message','')[:40]!r}) — marking handled")
                mark_as_replied(comment["id"], niche,
                                comment.get("message", ""), "[NO_REPLY]", sentiment)
                continue

            # Post reply
            result = await post_reply(comment["id"], reply_text, niche)
            if result["success"]:
                replies_sent += 1
                _record_reply(page_id)
                mark_as_replied(
                    comment["id"], niche,
                    comment.get("message", ""), reply_text, sentiment,
                )
                print(f"[Community] Replied to {comment.get('from_name', 'user')}: {reply_text[:60]}...")

                # Delay between replies
                await asyncio.sleep(REPLY_DELAY_SECONDS)
            else:
                print(f"[Community] Failed to reply: {result.get('error', 'unknown')}")

        # Update stats
        _update_stats(niche, len(comments), replies_sent, stats["positive"], stats["negative"], stats["escalations"])
        summary[niche] = {
            "comments": len(comments),
            "replies": replies_sent,
            "positive": stats["positive"],
            "negative": stats["negative"],
            "escalations": stats["escalations"],
        }

        print(f"[Community] {niche}: {replies_sent}/{len(comments)} replies sent")

    # Print summary
    total_replies = sum(s.get("replies", 0) for s in summary.values())
    total_comments = sum(s.get("comments", 0) for s in summary.values())
    print(f"\n[Community] === Round Complete: {total_replies} replies sent ({total_comments} comments found) ===")

    return summary


def print_stats():
    """Print community management stats."""
    stats = get_reply_stats(7)

    print("\n" + "=" * 60)
    print("  COMMUNITY MANAGEMENT STATS (Last 7 Days)")
    print("=" * 60)
    print(f"  {'Page':<25} {'Replies':>8} {'Comments':>10} {'Neg':>5} {'Esc':>5}")
    print("-" * 60)

    for niche in ACTIVE_NICHES:
        s = stats.get(niche, {})
        print(
            f"  {NICHE_PAGE_NAMES.get(niche, niche):<25} "
            f"{s.get('total_replies', 0):>8} "
            f"{s.get('total_comments', 0):>10} "
            f"{s.get('negative', 0):>5} "
            f"{s.get('escalations', 0):>5}"
        )
    print("=" * 60 + "\n")


# ── CLI Entry Point ──────────────────────────────────────────

async def main():
    print("[Community] Starting community management round...")
    summary = await run_community_round()
    print_stats()
    return summary


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
