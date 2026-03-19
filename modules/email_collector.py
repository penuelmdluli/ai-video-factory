"""
Email Collector Module — SQLite-backed subscriber management.

Stores email subscribers per niche with lead magnet tracking.
Database auto-creates at data/email_subscribers.db on import.
"""

import csv
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Database Setup ──────────────────────────────────────────────────
_ROOT_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _ROOT_DIR / "data"
_DB_PATH = _DATA_DIR / "email_subscribers.db"

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS subscribers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    name        TEXT,
    niche       TEXT,
    source      TEXT    DEFAULT 'landing_page',
    lead_magnet TEXT,
    created_at  TEXT    NOT NULL,
    confirmed   INTEGER DEFAULT 0
);
"""

_CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_subscribers_niche ON subscribers(niche);",
    "CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);",
]


def _get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory set to dict-like rows."""
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _init_db() -> None:
    """Create the data directory and subscribers table if they don't exist."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        conn.execute(_CREATE_TABLE_SQL)
        for idx_sql in _CREATE_INDEX_SQL:
            conn.execute(idx_sql)
        conn.commit()
        logger.info("Email subscriber database initialized at %s", _DB_PATH)
    except sqlite3.Error as exc:
        logger.error("Failed to initialize subscriber database: %s", exc)
        raise
    finally:
        conn.close()


# Auto-initialize on import
_init_db()


# ── Validation ──────────────────────────────────────────────────────

def _validate_email(email: str) -> bool:
    """Validate an email address using RFC 5322 simplified regex."""
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_RE.match(email.strip()))


# ── Public API ──────────────────────────────────────────────────────

def add_subscriber(
    email: str,
    name: str = "",
    niche: str = "",
    source: str = "landing_page",
    lead_magnet: Optional[str] = None,
) -> bool:
    """
    Add or update a subscriber in the database.

    On duplicate email, updates name/niche/source/lead_magnet fields
    (upsert behavior) without overwriting the original created_at.

    Args:
        email: Subscriber email address.
        name: Subscriber's first name.
        niche: Content niche (e.g. 'ai_trading').
        source: Acquisition source (default 'landing_page').
        lead_magnet: Name of the lead magnet they signed up for.

    Returns:
        True if the subscriber was added or updated, False on validation
        failure or database error.
    """
    email = email.strip().lower()

    if not _validate_email(email):
        logger.warning("Invalid email rejected: %s", email)
        return False

    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO subscribers (email, name, niche, source, lead_magnet, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                name        = COALESCE(NULLIF(excluded.name, ''), subscribers.name),
                niche       = COALESCE(NULLIF(excluded.niche, ''), subscribers.niche),
                source      = excluded.source,
                lead_magnet = COALESCE(excluded.lead_magnet, subscribers.lead_magnet)
            """,
            (email, name.strip(), niche.strip(), source.strip(), lead_magnet, now),
        )
        conn.commit()
        logger.info("Subscriber added/updated: %s (niche=%s)", email, niche)
        return True
    except sqlite3.Error as exc:
        logger.error("Failed to add subscriber %s: %s", email, exc)
        return False
    finally:
        conn.close()


def get_subscribers(niche: Optional[str] = None) -> list[dict]:
    """
    Retrieve all subscribers, optionally filtered by niche.

    Args:
        niche: If provided, only return subscribers for this niche.

    Returns:
        List of subscriber dicts with keys: id, email, name, niche,
        source, lead_magnet, created_at, confirmed.
    """
    conn = _get_connection()
    try:
        if niche:
            cursor = conn.execute(
                "SELECT * FROM subscribers WHERE niche = ? ORDER BY created_at DESC",
                (niche.strip(),),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM subscribers ORDER BY created_at DESC"
            )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        logger.error("Failed to retrieve subscribers: %s", exc)
        return []
    finally:
        conn.close()


def get_subscriber_count(niche: Optional[str] = None) -> int:
    """
    Get the total number of subscribers, optionally filtered by niche.

    Args:
        niche: If provided, count only subscribers for this niche.

    Returns:
        Integer count of subscribers.
    """
    conn = _get_connection()
    try:
        if niche:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM subscribers WHERE niche = ?",
                (niche.strip(),),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM subscribers")
        return cursor.fetchone()[0]
    except sqlite3.Error as exc:
        logger.error("Failed to count subscribers: %s", exc)
        return 0
    finally:
        conn.close()


def export_subscribers_csv(filepath: str, niche: Optional[str] = None) -> bool:
    """
    Export subscribers to a CSV file.

    Args:
        filepath: Output CSV file path.
        niche: If provided, export only subscribers for this niche.

    Returns:
        True if export succeeded, False on error.
    """
    subscribers = get_subscribers(niche=niche)
    if not subscribers:
        logger.warning("No subscribers to export (niche=%s)", niche)
        return False

    fieldnames = [
        "id", "email", "name", "niche", "source",
        "lead_magnet", "created_at", "confirmed",
    ]

    try:
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(subscribers)
        logger.info(
            "Exported %d subscribers to %s (niche=%s)",
            len(subscribers), filepath, niche,
        )
        return True
    except (OSError, csv.Error) as exc:
        logger.error("Failed to export subscribers CSV: %s", exc)
        return False


def remove_subscriber(email: str) -> bool:
    """
    Remove a subscriber by email address.

    Args:
        email: The email address to remove.

    Returns:
        True if a subscriber was removed, False if not found or on error.
    """
    email = email.strip().lower()
    if not _validate_email(email):
        logger.warning("Invalid email for removal: %s", email)
        return False

    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM subscribers WHERE email = ?", (email,)
        )
        conn.commit()
        removed = cursor.rowcount > 0
        if removed:
            logger.info("Subscriber removed: %s", email)
        else:
            logger.warning("Subscriber not found for removal: %s", email)
        return removed
    except sqlite3.Error as exc:
        logger.error("Failed to remove subscriber %s: %s", email, exc)
        return False
    finally:
        conn.close()


def confirm_subscriber(email: str) -> bool:
    """
    Mark a subscriber as confirmed (double opt-in).

    Args:
        email: The email address to confirm.

    Returns:
        True if updated, False if not found or on error.
    """
    email = email.strip().lower()
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "UPDATE subscribers SET confirmed = 1 WHERE email = ?", (email,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as exc:
        logger.error("Failed to confirm subscriber %s: %s", email, exc)
        return False
    finally:
        conn.close()
