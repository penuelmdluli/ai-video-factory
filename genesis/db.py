"""
Genesis Content Engine — SQLite Database

Tables:
- genesis_trends    — daily fetched trending topics
- genesis_scripts   — AI-generated video scripts
- genesis_videos    — generated + branded videos
- genesis_posts     — all posts across all platforms
- genesis_analytics — daily performance metrics
- genesis_schedule  — posting schedule state
"""
import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from genesis.genesis_config import DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS genesis_trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        brand TEXT NOT NULL,
        topic TEXT NOT NULL,
        headline TEXT NOT NULL,
        score REAL DEFAULT 0,
        source TEXT,
        source_url TEXT,
        used INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS genesis_scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trend_id INTEGER,
        brand TEXT NOT NULL,
        script TEXT NOT NULL,
        hook_line TEXT,
        caption TEXT,
        word_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS genesis_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_id INTEGER REFERENCES genesis_scripts(id),
        brand TEXT NOT NULL,
        raw_video_url TEXT,
        raw_video_path TEXT,
        branded_video_path TEXT,
        production_id TEXT,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS genesis_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER,
        brand TEXT NOT NULL,
        platform TEXT NOT NULL,
        platform_post_id TEXT,
        caption TEXT,
        status TEXT DEFAULT 'pending',
        posted_at TEXT,
        views INTEGER DEFAULT 0,
        reactions INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        performance_score REAL DEFAULT 0,
        error_message TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS genesis_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        date TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        reactions INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        performance_score REAL DEFAULT 0,
        raw_data TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS genesis_pipeline_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        phase TEXT NOT NULL,
        brand TEXT,
        status TEXT NOT NULL,
        message TEXT,
        duration_seconds REAL,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_trends_date_brand ON genesis_trends(date, brand);
    CREATE INDEX IF NOT EXISTS idx_scripts_brand ON genesis_scripts(brand);
    CREATE INDEX IF NOT EXISTS idx_videos_status ON genesis_videos(status);
    CREATE INDEX IF NOT EXISTS idx_posts_platform ON genesis_posts(platform, brand);
    CREATE INDEX IF NOT EXISTS idx_pipeline_date ON genesis_pipeline_log(date, phase);
    """)
    conn.commit()
    conn.close()


# ── CRUD helpers ──────────────────────────────────────────

def save_trend(brand: str, topic: str, headline: str, score: float, source: str, source_url: str = "") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO genesis_trends (date, brand, topic, headline, score, source, source_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (date.today().isoformat(), brand, topic, headline, score, source, source_url)
    )
    trend_id = cur.lastrowid
    conn.commit()
    conn.close()
    return trend_id


def get_today_trends(brand: str = None) -> list:
    conn = get_db()
    if brand:
        rows = conn.execute(
            "SELECT * FROM genesis_trends WHERE date = ? AND brand = ? ORDER BY score DESC",
            (date.today().isoformat(), brand)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM genesis_trends WHERE date = ? ORDER BY score DESC",
            (date.today().isoformat(),)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_trend(brand: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM genesis_trends WHERE date = ? AND brand = ? AND used = 0 ORDER BY score DESC LIMIT 1",
        (date.today().isoformat(), brand)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_trend_used(trend_id: int):
    conn = get_db()
    conn.execute("UPDATE genesis_trends SET used = 1 WHERE id = ?", (trend_id,))
    conn.commit()
    conn.close()


def save_script(trend_id: int, brand: str, script: str, hook_line: str, caption: str) -> int:
    word_count = len(script.split())
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO genesis_scripts (trend_id, brand, script, hook_line, caption, word_count) VALUES (?, ?, ?, ?, ?, ?)",
        (trend_id, brand, script, hook_line, caption, word_count)
    )
    script_id = cur.lastrowid
    conn.commit()
    conn.close()
    return script_id


def get_latest_script(brand: str) -> dict | None:
    """Get the most recent script for a brand (today first, then any)."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, trend_id, brand, script, hook_line, caption FROM genesis_scripts "
        "WHERE brand = ? ORDER BY created_at DESC LIMIT 1",
        (brand,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "script_id": row[0],
        "trend_id": row[1],
        "brand": row[2],
        "script": row[3],
        "hook_line": row[4],
        "caption": row[5],
    }


def save_video(script_id: int, brand: str, production_id: str = "") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO genesis_videos (script_id, brand, production_id, status) VALUES (?, ?, ?, 'generating')",
        (script_id, brand, production_id)
    )
    video_id = cur.lastrowid
    conn.commit()
    conn.close()
    return video_id


def update_video(video_id: int, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [video_id]
    conn.execute(f"UPDATE genesis_videos SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def get_videos_by_status(status: str, brand: str = None) -> list:
    conn = get_db()
    if brand:
        rows = conn.execute(
            "SELECT * FROM genesis_videos WHERE status = ? AND brand = ? ORDER BY created_at DESC",
            (status, brand)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM genesis_videos WHERE status = ? ORDER BY created_at DESC",
            (status,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_videos() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT v.*, s.hook_line, s.caption, s.script FROM genesis_videos v JOIN genesis_scripts s ON v.script_id = s.id WHERE date(v.created_at) = ?",
        (date.today().isoformat(),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_post(video_id: int, brand: str, platform: str, caption: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO genesis_posts (video_id, brand, platform, caption, status) VALUES (?, ?, ?, ?, 'pending')",
        (video_id, brand, platform, caption)
    )
    post_id = cur.lastrowid
    conn.commit()
    conn.close()
    return post_id


def update_post(post_id: int, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [post_id]
    conn.execute(f"UPDATE genesis_posts SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def get_unposted_videos(brand: str = None) -> list:
    """Get branded videos that haven't been posted to all 3 platforms yet."""
    conn = get_db()
    if brand:
        rows = conn.execute("""
            SELECT v.*, s.hook_line, s.caption, s.script
            FROM genesis_videos v
            JOIN genesis_scripts s ON v.script_id = s.id
            WHERE v.status = 'branded' AND v.brand = ?
            AND v.id NOT IN (
                SELECT DISTINCT video_id FROM genesis_posts
                WHERE status = 'posted'
                GROUP BY video_id
                HAVING COUNT(DISTINCT platform) >= 3
            )
            ORDER BY v.created_at ASC
        """, (brand,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT v.*, s.hook_line, s.caption, s.script
            FROM genesis_videos v
            JOIN genesis_scripts s ON v.script_id = s.id
            WHERE v.status = 'branded'
            AND v.id NOT IN (
                SELECT DISTINCT video_id FROM genesis_posts
                WHERE status = 'posted'
                GROUP BY video_id
                HAVING COUNT(DISTINCT platform) >= 3
            )
            ORDER BY v.created_at ASC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_pipeline(phase: str, brand: str, status: str, message: str, duration: float = 0):
    conn = get_db()
    conn.execute(
        "INSERT INTO genesis_pipeline_log (date, phase, brand, status, message, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
        (date.today().isoformat(), phase, brand, status, message, duration)
    )
    conn.commit()
    conn.close()


def get_today_pipeline_log() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM genesis_pipeline_log WHERE date = ? ORDER BY created_at ASC",
        (date.today().isoformat(),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_posts_needing_analytics() -> list:
    """Posts that were posted but need analytics update."""
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, v.brand FROM genesis_posts p
        JOIN genesis_videos v ON p.video_id = v.id
        WHERE p.status = 'posted' AND p.platform_post_id IS NOT NULL
        ORDER BY p.posted_at DESC LIMIT 50
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
init_db()
