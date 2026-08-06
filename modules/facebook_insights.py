"""
Facebook Insights — Page-level analytics collection and growth tracking.

Collects daily metrics from all Facebook pages:
- Follower counts, reach, impressions, engagement rate
- Per-post performance metrics
- Growth rate calculations (daily, weekly, monthly)
- Cross-page benchmarking

Stores everything in SQLite for historical analysis.
"""
import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, ROOT_DIR


# ── Constants ────────────────────────────────────────────────
GRAPH_API_BASE = "https://graph.facebook.com/v24.0"
DB_PATH = ROOT_DIR / "data" / "growth_analytics.db"

# Pages we can collect insights for (need both ID and token)
GROWTH_NICHES = [
    "ai_money", "tech_news", "motivation",
    "health_wellness", "blissful_moments", "limitless_you",
]

NICHE_PAGE_NAMES = {
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Blissful Moments",
    "daily_breakdown": "The Daily Breakdown",
    "shopmo_products": "ShopMO",
    "limitless_you": "Limitless You",
}


# ── Database Setup ───────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    """Get SQLite connection with WAL mode for concurrent access."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS page_metrics (
                date TEXT NOT NULL,
                niche TEXT NOT NULL,
                followers INTEGER DEFAULT 0,
                page_reach INTEGER DEFAULT 0,
                page_impressions INTEGER DEFAULT 0,
                page_engaged_users INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0.0,
                new_followers INTEGER DEFAULT 0,
                collected_at TEXT NOT NULL,
                PRIMARY KEY (date, niche)
            );

            CREATE TABLE IF NOT EXISTS post_metrics (
                post_id TEXT PRIMARY KEY,
                niche TEXT NOT NULL,
                content_type TEXT DEFAULT 'unknown',
                message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                reach INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                engagement INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0.0,
                collected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS growth_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                niche TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                notes TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_page_metrics_niche ON page_metrics(niche);
            CREATE INDEX IF NOT EXISTS idx_post_metrics_niche ON post_metrics(niche);
            CREATE INDEX IF NOT EXISTS idx_growth_log_date ON growth_log(date, niche);
        """)
        conn.commit()
    finally:
        conn.close()


# Initialize on import
init_db()


# ── Page Metrics Collection ─────────────────────────────────

async def collect_page_metrics(niche: str) -> dict | None:
    """
    Collect page-level metrics from Facebook Graph API.

    GET /{page_id}?fields=followers_count,fan_count
    GET /{page_id}/insights?metric=page_impressions,page_engaged_users&period=day
    """
    page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")

    if not page_id or not page_token:
        print(f"[Insights] No FB config for {niche}, skipping")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    metrics = {
        "niche": niche,
        "date": today,
        "followers": 0,
        "page_reach": 0,
        "page_impressions": 0,
        "page_engaged_users": 0,
        "engagement_rate": 0.0,
        "new_followers": 0,
        "collected_at": datetime.now().isoformat(),
    }

    try:
        # 1. Get follower count
        resp = requests.get(
            f"{GRAPH_API_BASE}/{page_id}",
            params={
                "fields": "followers_count,fan_count,name",
                "access_token": page_token,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            metrics["followers"] = data.get("followers_count", data.get("fan_count", 0))
            print(f"[Insights] {niche}: {metrics['followers']:,} followers")
        else:
            print(f"[Insights] Failed to get follower count for {niche}: {resp.status_code}")
            # Try to parse error
            try:
                err = resp.json().get("error", {}).get("message", "Unknown")
                print(f"[Insights]   Error: {err}")
            except Exception:
                pass

        # 2. Get page insights (reach, impressions, engaged users)
        # Try comprehensive insights first, fall back to post-level engagement
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                f"{GRAPH_API_BASE}/{page_id}/insights",
                params={
                    "metric": "page_impressions,page_engaged_users,page_post_engagements,page_fans",
                    "period": "day",
                    "since": yesterday,
                    "until": today,
                    "access_token": page_token,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                insights = resp.json().get("data", [])
                for metric_data in insights:
                    name = metric_data.get("name", "")
                    values = metric_data.get("values", [])
                    if values:
                        val = values[-1].get("value", 0)
                        if name == "page_impressions":
                            metrics["page_impressions"] = val
                        elif name == "page_engaged_users":
                            metrics["page_engaged_users"] = val
                        elif name == "page_fans":
                            metrics["page_reach"] = val
            else:
                # Fallback: estimate engagement from recent posts
                fallback_resp = requests.get(
                    f"{GRAPH_API_BASE}/{page_id}/posts",
                    params={
                        "fields": "likes.summary(true),comments.summary(true),shares",
                        "limit": 5,
                        "access_token": page_token,
                    },
                    timeout=15,
                )
                if fallback_resp.status_code == 200:
                    posts = fallback_resp.json().get("data", [])
                    total_engagement = 0
                    for post in posts:
                        total_engagement += post.get("likes", {}).get("summary", {}).get("total_count", 0)
                        total_engagement += post.get("comments", {}).get("summary", {}).get("total_count", 0) * 3
                        total_engagement += post.get("shares", {}).get("count", 0) * 5
                    if posts:
                        metrics["page_engaged_users"] = total_engagement // len(posts)
        except Exception as e:
            print(f"[Insights] Error fetching page insights for {niche}: {e}")

        # 3. Calculate engagement rate
        if metrics["followers"] > 0:
            metrics["engagement_rate"] = round(
                (metrics["page_engaged_users"] / metrics["followers"]) * 100, 2
            )

        # 4. Calculate new followers (compare to yesterday)
        metrics["new_followers"] = _calculate_new_followers(niche, metrics["followers"])

    except Exception as e:
        print(f"[Insights] Error collecting metrics for {niche}: {e}")

    return metrics


def _calculate_new_followers(niche: str, current_followers: int) -> int:
    """Compare current followers to most recent stored count."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT followers FROM page_metrics WHERE niche = ? ORDER BY date DESC LIMIT 1",
            (niche,),
        ).fetchone()
        if row:
            return current_followers - row["followers"]
        return 0
    finally:
        conn.close()


async def collect_all_pages() -> list[dict]:
    """Collect metrics for all configured pages."""
    results = []
    for niche in GROWTH_NICHES:
        metrics = await collect_page_metrics(niche)
        if metrics:
            store_metrics(metrics)
            results.append(metrics)

    if results:
        print(f"\n[Insights] === Collection Complete ===")
        print(f"[Insights] Pages collected: {len(results)}")
        total_followers = sum(m["followers"] for m in results)
        total_new = sum(m["new_followers"] for m in results)
        print(f"[Insights] Total followers: {total_followers:,}")
        print(f"[Insights] New followers today: {total_new:+,}")

    return results


async def collect_post_metrics(niche: str, limit: int = 25) -> list[dict]:
    """
    Collect per-post metrics for recent posts.

    GET /{page_id}/posts?fields=id,message,type,created_time,
        likes.summary(true),comments.summary(true),shares
    """
    page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")

    if not page_id or not page_token:
        return []

    posts = []
    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/{page_id}/posts",
            params={
                "fields": "id,message,type,created_time,likes.summary(true),comments.summary(true),shares",
                "limit": limit,
                "access_token": page_token,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[Insights] Failed to get posts for {niche}: {resp.status_code}")
            return []

        data = resp.json().get("data", [])
        conn = _get_db()
        try:
            for post in data:
                likes = post.get("likes", {}).get("summary", {}).get("total_count", 0)
                comments = post.get("comments", {}).get("summary", {}).get("total_count", 0)
                shares = post.get("shares", {}).get("count", 0)
                engagement = likes + (comments * 3) + (shares * 5)

                post_data = {
                    "post_id": post["id"],
                    "niche": niche,
                    "content_type": post.get("type", "unknown"),
                    "message": (post.get("message", "") or "")[:200],
                    "created_at": post.get("created_time", ""),
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "engagement": engagement,
                    "engagement_rate": 0.0,
                    "collected_at": datetime.now().isoformat(),
                }

                conn.execute("""
                    INSERT OR REPLACE INTO post_metrics
                    (post_id, niche, content_type, message, created_at, likes, comments, shares, engagement, engagement_rate, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_data["post_id"], niche, post_data["content_type"],
                    post_data["message"], post_data["created_at"],
                    likes, comments, shares, engagement, post_data["engagement_rate"],
                    post_data["collected_at"],
                ))
                posts.append(post_data)

            conn.commit()
            print(f"[Insights] Stored {len(posts)} post metrics for {niche}")
        finally:
            conn.close()

    except Exception as e:
        print(f"[Insights] Error fetching posts for {niche}: {e}")

    return posts


# ── Storage ──────────────────────────────────────────────────

def store_metrics(metrics: dict):
    """Store page metrics in SQLite (upsert)."""
    conn = _get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO page_metrics
            (date, niche, followers, page_reach, page_impressions, page_engaged_users,
             engagement_rate, new_followers, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metrics["date"], metrics["niche"], metrics["followers"],
            metrics["page_reach"], metrics["page_impressions"],
            metrics["page_engaged_users"], metrics["engagement_rate"],
            metrics["new_followers"], metrics["collected_at"],
        ))
        conn.commit()
    finally:
        conn.close()


# ── Growth Analytics ─────────────────────────────────────────

def get_growth_rate(niche: str, period: str = "weekly") -> dict:
    """
    Calculate follower growth rate for a niche.

    Args:
        period: "daily", "weekly", or "monthly"

    Returns dict with: current, previous, delta, growth_percent
    """
    days_map = {"daily": 1, "weekly": 7, "monthly": 30}
    days = days_map.get(period, 7)

    conn = _get_db()
    try:
        # Most recent follower count
        current_row = conn.execute(
            "SELECT followers FROM page_metrics WHERE niche = ? ORDER BY date DESC LIMIT 1",
            (niche,),
        ).fetchone()

        # Follower count N days ago
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        previous_row = conn.execute(
            "SELECT followers FROM page_metrics WHERE niche = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (niche, cutoff),
        ).fetchone()

        current = current_row["followers"] if current_row else 0
        previous = previous_row["followers"] if previous_row else current

        delta = current - previous
        growth_pct = round((delta / previous) * 100, 2) if previous > 0 else 0.0

        return {
            "niche": niche,
            "period": period,
            "current": current,
            "previous": previous,
            "delta": delta,
            "growth_percent": growth_pct,
        }
    finally:
        conn.close()


def get_page_benchmarks() -> list[dict]:
    """
    Compare all pages side-by-side.

    Returns sorted list (by followers desc) with growth rates.
    """
    benchmarks = []
    for niche in GROWTH_NICHES:
        weekly = get_growth_rate(niche, "weekly")
        monthly = get_growth_rate(niche, "monthly")

        # Get latest engagement rate
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT engagement_rate FROM page_metrics WHERE niche = ? ORDER BY date DESC LIMIT 1",
                (niche,),
            ).fetchone()
            eng_rate = row["engagement_rate"] if row else 0.0
        finally:
            conn.close()

        benchmarks.append({
            "niche": niche,
            "page_name": NICHE_PAGE_NAMES.get(niche, niche),
            "followers": weekly["current"],
            "weekly_growth": weekly["delta"],
            "weekly_growth_pct": weekly["growth_percent"],
            "monthly_growth": monthly["delta"],
            "monthly_growth_pct": monthly["growth_percent"],
            "engagement_rate": eng_rate,
        })

    benchmarks.sort(key=lambda x: x["followers"], reverse=True)
    return benchmarks


def get_best_content_types(niche: str, top_n: int = 5) -> list[dict]:
    """Identify best-performing content types for a niche."""
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT content_type,
                   COUNT(*) as count,
                   AVG(engagement) as avg_engagement,
                   AVG(likes) as avg_likes,
                   AVG(comments) as avg_comments,
                   AVG(shares) as avg_shares
            FROM post_metrics
            WHERE niche = ? AND content_type != 'unknown'
            GROUP BY content_type
            HAVING count >= 3
            ORDER BY avg_engagement DESC
            LIMIT ?
        """, (niche, top_n)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_top_posts(niche: str, top_n: int = 10) -> list[dict]:
    """Get the top performing posts for a niche."""
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT post_id, content_type, message, created_at,
                   likes, comments, shares, engagement
            FROM post_metrics
            WHERE niche = ?
            ORDER BY engagement DESC
            LIMIT ?
        """, (niche, top_n)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_follower_history(niche: str, days: int = 30) -> list[dict]:
    """Get follower count history for charting."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT date, followers, new_followers, engagement_rate FROM page_metrics WHERE niche = ? AND date >= ? ORDER BY date",
            (niche, cutoff),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Reporting ────────────────────────────────────────────────

def print_dashboard():
    """Print a formatted growth dashboard to console."""
    benchmarks = get_page_benchmarks()

    print("\n" + "=" * 70)
    print("  FACEBOOK GROWTH DASHBOARD")
    print("=" * 70)
    print(f"  {'Page':<25} {'Followers':>10} {'Weekly':>10} {'Monthly':>10} {'Eng %':>8}")
    print("-" * 70)

    for b in benchmarks:
        weekly_str = f"{b['weekly_growth']:+,}" if b['weekly_growth'] else "N/A"
        monthly_str = f"{b['monthly_growth']:+,}" if b['monthly_growth'] else "N/A"
        print(
            f"  {b['page_name']:<25} {b['followers']:>10,} {weekly_str:>10} "
            f"{monthly_str:>10} {b['engagement_rate']:>7.1f}%"
        )

    total = sum(b["followers"] for b in benchmarks)
    total_weekly = sum(b["weekly_growth"] for b in benchmarks)
    print("-" * 70)
    print(f"  {'TOTAL':<25} {total:>10,} {total_weekly:>+10,}")
    print("=" * 70 + "\n")


# ── CLI Entry Point ──────────────────────────────────────────

async def main():
    """Standalone collection + dashboard display."""
    print("[Insights] Starting collection...")
    await collect_all_pages()

    # Also collect post metrics for each niche
    for niche in GROWTH_NICHES:
        await collect_post_metrics(niche)

    print_dashboard()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
