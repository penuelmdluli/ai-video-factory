"""
AI Video Factory — Monetization Tracker

Revenue, click, and conversion tracking backed by SQLite.
Tables are auto-created on import so the module is ready to use immediately.

Database: data/monetization.db
"""

import sqlite3
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


# ── Database path ─────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "monetization.db"

# ── Valid niches (mirrors config.py) ──────────────────────────
NICHES = [
    "ai_trading", "ai_money", "tech_news",
    "motivation", "health_wellness", "blissful_moments",
]


# ── Database helpers ──────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tables() -> None:
    """Create tables if they don't exist."""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS revenue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                niche       TEXT NOT NULL,
                source      TEXT NOT NULL,
                type        TEXT NOT NULL,
                amount      REAL NOT NULL,
                currency    TEXT NOT NULL DEFAULT 'USD',
                description TEXT DEFAULT '',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clicks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                niche       TEXT NOT NULL,
                link_type   TEXT NOT NULL,
                link_url    TEXT NOT NULL,
                count       INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                niche       TEXT NOT NULL,
                funnel_stage TEXT NOT NULL,
                count       INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_revenue_date ON revenue(date);
            CREATE INDEX IF NOT EXISTS idx_revenue_niche ON revenue(niche);
            CREATE INDEX IF NOT EXISTS idx_clicks_date ON clicks(date);
            CREATE INDEX IF NOT EXISTS idx_conversions_date ON conversions(date);
        """)
        conn.commit()
    finally:
        conn.close()


# Auto-create tables on import
_init_tables()


# ── Recording functions ───────────────────────────────────────

def record_revenue(
    niche: str,
    source: str,
    type: str,
    amount: float,
    description: str = "",
    currency: str = "USD",
    date: Optional[str] = None,
) -> int:
    """
    Record a revenue event.

    Args:
        niche: One of the 6 niches (e.g. 'ai_trading').
        source: Revenue source (e.g. 'affiliate', 'adsense', 'sponsor').
        type: Revenue type (e.g. 'one_time', 'recurring', 'cpm').
        amount: Dollar amount.
        description: Optional note.
        currency: ISO currency code, defaults to 'USD'.
        date: ISO date string, defaults to today.

    Returns:
        Row ID of the inserted record.
    """
    now = datetime.utcnow().isoformat()
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO revenue (date, niche, source, type, amount, currency, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (date, niche, source, type, amount, currency, description, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def record_click(
    niche: str,
    link_type: str,
    link_url: str,
    count: int = 1,
    date: Optional[str] = None,
) -> int:
    """
    Record a link click event.

    Args:
        niche: Niche the click originated from.
        link_type: Type of link (e.g. 'affiliate', 'website', 'cta').
        link_url: The URL that was clicked.
        count: Number of clicks (batch recording).
        date: ISO date string, defaults to today.

    Returns:
        Row ID of the inserted record.
    """
    now = datetime.utcnow().isoformat()
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO clicks (date, niche, link_type, link_url, count, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, niche, link_type, link_url, count, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def record_conversion(
    niche: str,
    funnel_stage: str,
    count: int = 1,
    date: Optional[str] = None,
) -> int:
    """
    Record a conversion funnel event.

    Args:
        niche: Niche the conversion belongs to.
        funnel_stage: Stage name (e.g. 'view', 'click', 'signup', 'purchase').
        count: Number of conversions.
        date: ISO date string, defaults to today.

    Returns:
        Row ID of the inserted record.
    """
    now = datetime.utcnow().isoformat()
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO conversions (date, niche, funnel_stage, count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (date, niche, funnel_stage, count, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ── Query functions ───────────────────────────────────────────

def get_revenue_summary(days: int = 30, niche: Optional[str] = None) -> dict:
    """
    Get revenue totals grouped by source for the last N days.

    Args:
        days: Look-back window in days.
        niche: Optional niche filter.

    Returns:
        Dict with 'total', 'by_source' (dict), and 'period_days'.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        query = "SELECT source, SUM(amount) as total FROM revenue WHERE date >= ?"
        params = [cutoff]
        if niche:
            query += " AND niche = ?"
            params.append(niche)
        query += " GROUP BY source ORDER BY total DESC"
        rows = conn.execute(query, params).fetchall()

        by_source = {row["source"]: round(row["total"], 2) for row in rows}
        total = round(sum(by_source.values()), 2)

        return {
            "total": total,
            "by_source": by_source,
            "period_days": days,
        }
    finally:
        conn.close()


def get_revenue_by_niche(days: int = 30) -> dict:
    """
    Get revenue totals grouped by niche for the last N days.

    Returns:
        Dict mapping niche name to total revenue.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT niche, SUM(amount) as total FROM revenue WHERE date >= ? GROUP BY niche ORDER BY total DESC",
            (cutoff,),
        ).fetchall()
        return {row["niche"]: round(row["total"], 2) for row in rows}
    finally:
        conn.close()


def get_revenue_trend(days: int = 30) -> list:
    """
    Get daily revenue totals for the last N days.

    Returns:
        List of dicts: [{'date': '2026-03-01', 'total': 42.50}, ...]
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT date, SUM(amount) as total FROM revenue WHERE date >= ? GROUP BY date ORDER BY date",
            (cutoff,),
        ).fetchall()
        return [{"date": row["date"], "total": round(row["total"], 2)} for row in rows]
    finally:
        conn.close()


def get_conversion_funnel(niche: Optional[str] = None, days: int = 30) -> dict:
    """
    Get conversion counts by funnel stage for the last N days.

    Returns:
        Dict mapping funnel_stage to total count,
        ordered: view -> click -> signup -> purchase.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        query = "SELECT funnel_stage, SUM(count) as total FROM conversions WHERE date >= ?"
        params = [cutoff]
        if niche:
            query += " AND niche = ?"
            params.append(niche)
        query += " GROUP BY funnel_stage"
        rows = conn.execute(query, params).fetchall()
        raw = {row["funnel_stage"]: row["total"] for row in rows}

        # Return in funnel order
        stage_order = ["view", "click", "signup", "trial", "purchase"]
        ordered = {}
        for stage in stage_order:
            if stage in raw:
                ordered[stage] = raw[stage]
        # Append any extra stages not in the predefined order
        for stage, count in raw.items():
            if stage not in ordered:
                ordered[stage] = count

        return ordered
    finally:
        conn.close()


def get_top_affiliates(days: int = 30, limit: int = 10) -> list:
    """
    Get top affiliate links by click count for the last N days.

    Returns:
        List of dicts: [{'link_url': '...', 'niche': '...', 'total_clicks': 42}, ...]
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT link_url, niche, SUM(count) as total_clicks
               FROM clicks
               WHERE date >= ? AND link_type = 'affiliate'
               GROUP BY link_url
               ORDER BY total_clicks DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [
            {"link_url": row["link_url"], "niche": row["niche"], "total_clicks": row["total_clicks"]}
            for row in rows
        ]
    finally:
        conn.close()


def get_monthly_recurring_revenue() -> float:
    """
    Calculate MRR from recurring revenue in the current calendar month.

    Returns:
        MRR as a float.
    """
    first_of_month = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT SUM(amount) as total FROM revenue WHERE date >= ? AND type = 'recurring'",
            (first_of_month,),
        ).fetchone()
        return round(row["total"] or 0.0, 2)
    finally:
        conn.close()


def get_subscriber_stats(days: int = 30) -> dict:
    """
    Get subscriber/signup stats from conversions.

    Returns:
        Dict with total signups, by niche breakdown, and daily trend.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        # Total signups
        row = conn.execute(
            "SELECT SUM(count) as total FROM conversions WHERE date >= ? AND funnel_stage = 'signup'",
            (cutoff,),
        ).fetchone()
        total = row["total"] or 0

        # By niche
        rows = conn.execute(
            "SELECT niche, SUM(count) as total FROM conversions WHERE date >= ? AND funnel_stage = 'signup' GROUP BY niche",
            (cutoff,),
        ).fetchall()
        by_niche = {r["niche"]: r["total"] for r in rows}

        # Daily trend
        rows = conn.execute(
            "SELECT date, SUM(count) as total FROM conversions WHERE date >= ? AND funnel_stage = 'signup' GROUP BY date ORDER BY date",
            (cutoff,),
        ).fetchall()
        trend = [{"date": r["date"], "count": r["total"]} for r in rows]

        return {"total": total, "by_niche": by_niche, "trend": trend}
    finally:
        conn.close()


def export_revenue_report(filepath: str) -> str:
    """
    Export all revenue records to a CSV file.

    Args:
        filepath: Destination path for the CSV.

    Returns:
        Absolute path of the written file.
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, date, niche, source, type, amount, currency, description, created_at FROM revenue ORDER BY date DESC"
        ).fetchall()

        out = Path(filepath)
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "date", "niche", "source", "type", "amount", "currency", "description", "created_at"])
            for row in rows:
                writer.writerow([row["id"], row["date"], row["niche"], row["source"],
                                 row["type"], row["amount"], row["currency"],
                                 row["description"], row["created_at"]])

        return str(out.resolve())
    finally:
        conn.close()


# ── Demo data seeder ──────────────────────────────────────────

def seed_demo_data() -> dict:
    """
    Seed the database with realistic sample data for testing and demos.

    Generates 30 days of revenue, clicks, and conversions across all niches.
    Idempotent-ish: clears existing data before seeding.

    Returns:
        Dict with counts of seeded rows.
    """
    conn = _get_conn()
    try:
        # Clear existing data
        conn.execute("DELETE FROM revenue")
        conn.execute("DELETE FROM clicks")
        conn.execute("DELETE FROM conversions")
        conn.commit()
    finally:
        conn.close()

    sources = {
        "affiliate":    {"type": "one_time",  "range": (5, 75)},
        "adsense":      {"type": "cpm",       "range": (2, 25)},
        "sponsor":      {"type": "one_time",  "range": (50, 500)},
        "subscription": {"type": "recurring", "range": (9.99, 49.99)},
        "product":      {"type": "one_time",  "range": (15, 99)},
    }

    affiliate_links = [
        "https://gettraderadar.com/ref/ai-signals",
        "https://gettraderadar.com/ref/pro-plan",
        "https://partner.example.com/health-supps",
        "https://affiliate.example.com/tech-gadgets",
        "https://shopmoo.co.za/ref/trending",
        "https://gettraderadar.com/ref/crypto-bot",
    ]

    funnel_stages = ["view", "click", "signup", "trial", "purchase"]

    revenue_count = 0
    click_count = 0
    conversion_count = 0

    today = datetime.utcnow()

    for day_offset in range(30):
        date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")

        for niche in NICHES:
            # Revenue: 0-3 entries per niche per day
            for _ in range(random.randint(0, 3)):
                source = random.choice(list(sources.keys()))
                info = sources[source]
                amount = round(random.uniform(*info["range"]), 2)
                # Weight: ai_trading and ai_money earn more
                if niche in ("ai_trading", "ai_money"):
                    amount *= random.uniform(1.2, 2.0)
                    amount = round(amount, 2)
                desc = f"{source.title()} revenue from {niche} content"
                record_revenue(niche, source, info["type"], amount, desc, date=date)
                revenue_count += 1

            # Clicks: 1-5 per niche per day
            for _ in range(random.randint(1, 5)):
                link_type = random.choice(["affiliate", "website", "cta"])
                link_url = random.choice(affiliate_links) if link_type == "affiliate" else f"https://gettraderadar.com/{niche}"
                clicks = random.randint(1, 50)
                record_click(niche, link_type, link_url, count=clicks, date=date)
                click_count += 1

            # Conversions: funnel with decreasing counts
            base_views = random.randint(100, 1000)
            for i, stage in enumerate(funnel_stages):
                # Each stage keeps ~30-60% of previous
                count = max(1, int(base_views * (0.45 ** i)))
                record_conversion(niche, stage, count=count, date=date)
                conversion_count += 1

    return {
        "revenue_rows": revenue_count,
        "click_rows": click_count,
        "conversion_rows": conversion_count,
        "days": 30,
        "niches": len(NICHES),
    }


# ── CLI entry point ───────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--seed":
        print("Seeding demo data...")
        result = seed_demo_data()
        print(f"Done: {result}")
    elif len(sys.argv) > 1 and sys.argv[1] == "--export":
        path = sys.argv[2] if len(sys.argv) > 2 else str(DATA_DIR / "revenue_report.csv")
        out = export_revenue_report(path)
        print(f"Exported to: {out}")
    else:
        summary = get_revenue_summary()
        print(f"Revenue Summary (30d): ${summary['total']:.2f}")
        print(f"  By source: {summary['by_source']}")
        mrr = get_monthly_recurring_revenue()
        print(f"  MRR: ${mrr:.2f}")
        by_niche = get_revenue_by_niche()
        print(f"  By niche: {by_niche}")
        print("\nUsage: python monetization_tracker.py [--seed | --export [path]]")
