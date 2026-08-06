"""
Clip Library — SQLite asset cache for reusing AI-generated video clips.

Money-saving strategy:
- Every AI-generated clip is stored with rich metadata tags
- Before generating a new clip, search the library for reusable matches
- Clips are scored by keyword overlap + recency + quality
- Reuse rate target: 40-60% of clips come from library after 2 weeks of operation
- Estimated savings: $50-100/day at scale (3-5 videos/day across 8 niches)
"""

import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import ASSETS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLIP_LIBRARY_DIR = ASSETS_DIR / "clip_library"
DB_PATH = CLIP_LIBRARY_DIR / "clips.db"
MATCH_THRESHOLD = 0.35
AVG_API_COST_PER_CLIP = 2.0  # dollars

# Stop words stripped during keyword extraction
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "of", "in", "on", "at", "to", "for",
    "and", "or", "but", "with", "from", "by", "as", "be", "was", "were",
    "been", "being", "are", "am", "this", "that", "these", "those", "has",
    "have", "had", "do", "does", "did", "will", "would", "shall", "should",
    "can", "could", "may", "might", "must", "very", "really", "just",
    "about", "into", "over", "after", "before", "between", "under",
    "above", "below", "up", "down", "out", "off", "then", "than", "so",
    "no", "not", "only", "own", "same", "too", "also", "its", "his",
    "her", "their", "our", "my", "your", "some", "any", "all", "each",
    "every", "both", "few", "more", "most", "other", "such", "what",
    "which", "who", "whom", "when", "where", "why", "how", "if",
    "there", "here", "while", "during", "through", "because", "since",
    "until", "unless", "although", "though", "even", "still", "yet",
    "show", "showing", "shows", "shown", "scene", "clip", "video",
    "image", "shot", "footage", "visual", "background", "foreground",
    "looks", "looking", "look", "like", "view", "angle", "camera",
    "slowly", "quickly", "gently", "moving", "moves", "motion",
})

# Abstract/vague words that hurt search precision
_ABSTRACT_WORDS = frozenset({
    "thing", "things", "stuff", "something", "anything", "everything",
    "nothing", "way", "ways", "kind", "type", "types", "part", "parts",
    "lot", "lots", "bit", "bits", "area", "areas", "place", "places",
    "moment", "moments", "concept", "idea", "ideas", "aspect", "aspects",
    "element", "elements", "feature", "features", "point", "points",
    "good", "bad", "great", "nice", "cool", "amazing", "awesome",
    "beautiful", "pretty", "ugly", "big", "small", "large", "little",
    "new", "old", "young", "general", "specific", "various", "certain",
})

# Singleton connection — one per process, reused across calls
_connection: Optional[sqlite3.Connection] = None
_db_initialized = False


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection, creating the DB on first call."""
    global _connection, _db_initialized
    if _connection is None:
        CLIP_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(
            str(DB_PATH),
            check_same_thread=False,
            timeout=10,
        )
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
    if not _db_initialized:
        init_db(_connection)
        _db_initialized = True
    return _connection


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create tables and indexes if they don't exist."""
    c = conn or _get_conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS clips (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path       TEXT    NOT NULL UNIQUE,
            source          TEXT    NOT NULL,
            niche           TEXT,
            keywords        TEXT    NOT NULL DEFAULT '[]',
            mood            TEXT,
            style           TEXT,
            duration_seconds REAL,
            width           INTEGER,
            height          INTEGER,
            aspect_ratio    TEXT,
            quality_score   INTEGER NOT NULL DEFAULT 7,
            use_count       INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL,
            last_used_at    TEXT,
            file_size_bytes INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS clip_tags (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL,
            tag     TEXT    NOT NULL,
            FOREIGN KEY (clip_id) REFERENCES clips(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_clips_niche        ON clips(niche);
        CREATE INDEX IF NOT EXISTS idx_clips_mood          ON clips(mood);
        CREATE INDEX IF NOT EXISTS idx_clips_aspect_ratio  ON clips(aspect_ratio);
        CREATE INDEX IF NOT EXISTS idx_clips_source        ON clips(source);
        CREATE INDEX IF NOT EXISTS idx_clips_quality       ON clips(quality_score);
        CREATE INDEX IF NOT EXISTS idx_clips_created       ON clips(created_at);
        CREATE INDEX IF NOT EXISTS idx_clip_tags_tag       ON clip_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_clip_tags_clip_id   ON clip_tags(clip_id);
    """)
    c.commit()


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def extract_keywords(text: str) -> list[str]:
    """
    Extract 3-7 concrete, searchable keywords from a visual description.

    Strips stop words, abstract filler, and short tokens.  Keeps nouns,
    adjectives, and action verbs that are useful for clip matching.
    """
    if not text:
        return []

    # Lowercase, strip punctuation, split
    cleaned = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    tokens = cleaned.split()

    keywords: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        tok = tok.strip("-")
        if len(tok) < 3:
            continue
        if tok in _STOP_WORDS or tok in _ABSTRACT_WORDS:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        keywords.append(tok)

    # Cap at 7 — favour earlier (more prominent) words
    return keywords[:7]


# ---------------------------------------------------------------------------
# Aspect ratio helper
# ---------------------------------------------------------------------------

def _compute_aspect_ratio(width: int, height: int) -> str:
    """Return a human-friendly aspect ratio string like '16:9' or '9:16'."""
    if width <= 0 or height <= 0:
        return "unknown"
    from math import gcd
    divisor = gcd(width, height)
    w = width // divisor
    h = height // divisor
    # Normalise common ratios
    ratio_map = {
        (16, 9): "16:9",
        (9, 16): "9:16",
        (1, 1): "1:1",
        (4, 3): "4:3",
        (3, 4): "3:4",
        (21, 9): "21:9",
    }
    return ratio_map.get((w, h), f"{w}:{h}")


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------

def add_clip(
    file_path: str | Path,
    source: str,
    niche: str,
    keywords: list[str],
    mood: str = "",
    style: str = "",
    duration: float = 0.0,
    width: int = 0,
    height: int = 0,
    quality_score: int = 7,
) -> Optional[int]:
    """
    Register a new clip in the library.

    *file_path* is stored relative to the project root for portability.
    Returns the new clip_id, or None on failure.
    """
    try:
        conn = _get_conn()
        p = Path(file_path)

        # Store path relative to project root when possible
        try:
            from config import ROOT_DIR
            rel = p.resolve().relative_to(ROOT_DIR.resolve())
            stored_path = str(rel).replace("\\", "/")
        except (ValueError, ImportError):
            stored_path = str(p).replace("\\", "/")

        aspect_ratio = _compute_aspect_ratio(width, height) if width and height else ""
        file_size = p.stat().st_size if p.exists() else 0
        now = datetime.now(timezone.utc).isoformat()

        # Clamp quality
        quality_score = max(1, min(10, quality_score))

        cur = conn.execute(
            """
            INSERT INTO clips
                (file_path, source, niche, keywords, mood, style,
                 duration_seconds, width, height, aspect_ratio,
                 quality_score, use_count, created_at, last_used_at, file_size_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)
            """,
            (
                stored_path, source, niche, json.dumps(keywords),
                mood, style, duration, width, height, aspect_ratio,
                quality_score, now, file_size,
            ),
        )
        clip_id = cur.lastrowid

        # Insert tags (keywords + niche + mood) for fast lookup
        tags = set(keywords)
        if niche:
            tags.add(niche)
        if mood:
            tags.add(mood.lower())
        if style:
            tags.add(style.lower())

        conn.executemany(
            "INSERT INTO clip_tags (clip_id, tag) VALUES (?, ?)",
            [(clip_id, t.lower()) for t in tags if t],
        )
        conn.commit()
        logger.info("Clip added: id=%s source=%s niche=%s keywords=%s", clip_id, source, niche, keywords)
        return clip_id

    except sqlite3.IntegrityError:
        # Duplicate file_path — clip already registered
        logger.debug("Clip already in library: %s", file_path)
        conn.rollback()
        return None
    except Exception:
        logger.exception("Failed to add clip: %s", file_path)
        if _connection:
            _connection.rollback()
        return None


def get_clip_by_id(clip_id: int) -> Optional[dict]:
    """Return clip metadata as a dict, or None if not found."""
    try:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    except Exception:
        logger.exception("Failed to get clip id=%s", clip_id)
        return None


def record_usage(clip_id: int) -> None:
    """Increment use_count and update last_used_at for a clip."""
    try:
        conn = _get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE clips SET use_count = use_count + 1, last_used_at = ? WHERE id = ?",
            (now, clip_id),
        )
        conn.commit()
        logger.debug("Recorded usage for clip id=%s", clip_id)
    except Exception:
        logger.exception("Failed to record usage for clip id=%s", clip_id)


# ---------------------------------------------------------------------------
# Search & matching
# ---------------------------------------------------------------------------

def search_clips(
    keywords: list[str],
    niche: Optional[str] = None,
    mood: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    min_duration: Optional[float] = None,
    max_duration: Optional[float] = None,
    min_quality: int = 5,
    limit: int = 10,
) -> list[dict]:
    """
    Find reusable clips scored by keyword overlap (60%), recency (20%),
    and quality (20%).

    Returns a list of dicts sorted by descending composite score.
    """
    if not keywords:
        return []

    try:
        conn = _get_conn()

        # Build WHERE clause
        conditions = ["quality_score >= ?"]
        params: list = [min_quality]

        if niche:
            conditions.append("niche = ?")
            params.append(niche)
        if mood:
            conditions.append("mood = ?")
            params.append(mood)
        if aspect_ratio:
            conditions.append("aspect_ratio = ?")
            params.append(aspect_ratio)
        if min_duration is not None:
            conditions.append("duration_seconds >= ?")
            params.append(min_duration)
        if max_duration is not None:
            conditions.append("duration_seconds <= ?")
            params.append(max_duration)

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM clips WHERE {where}",  # noqa: S608
            params,
        ).fetchall()

        if not rows:
            return []

        search_set = {k.lower() for k in keywords}
        now_ts = time.time()
        scored: list[tuple[float, dict]] = []

        for row in rows:
            clip = _row_to_dict(row)
            clip_keywords = {k.lower() for k in clip["keywords"]}

            # --- Keyword overlap score (0-1) ---
            if not search_set:
                kw_score = 0.0
            else:
                overlap = len(search_set & clip_keywords)
                kw_score = overlap / len(search_set)

            # --- Recency score (0-1) — newer clips score higher ---
            try:
                created = datetime.fromisoformat(clip["created_at"]).timestamp()
            except (ValueError, TypeError):
                created = now_ts
            age_days = max((now_ts - created) / 86400, 0)
            # Decay: full score within 7 days, halves every 30 days
            recency_score = 1.0 / (1.0 + age_days / 30.0)

            # --- Quality score (0-1) ---
            quality_norm = clip["quality_score"] / 10.0

            # --- Composite ---
            composite = (0.60 * kw_score) + (0.20 * recency_score) + (0.20 * quality_norm)
            clip["_score"] = round(composite, 4)
            scored.append((composite, clip))

        # Sort descending by score, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    except Exception:
        logger.exception("Clip search failed")
        return []


def get_best_match(
    visual_description: str,
    niche: str,
    aspect_ratio: str = "9:16",
    min_duration: float = 3.0,
) -> Optional[dict]:
    """
    Smart matching: extract keywords from a visual description, search the
    library, and return the best clip if it exceeds MATCH_THRESHOLD.

    Returns a dict with clip metadata and ``_score``, or None.
    """
    keywords = extract_keywords(visual_description)
    if not keywords:
        return None

    results = search_clips(
        keywords=keywords,
        niche=niche,
        aspect_ratio=aspect_ratio,
        min_duration=min_duration,
        min_quality=5,
        limit=5,
    )
    if not results:
        # Retry without niche filter (cross-niche reuse)
        results = search_clips(
            keywords=keywords,
            aspect_ratio=aspect_ratio,
            min_duration=min_duration,
            min_quality=5,
            limit=5,
        )

    if not results:
        return None

    best = results[0]
    if best.get("_score", 0) >= MATCH_THRESHOLD:
        logger.info(
            "Library match (score=%.2f): '%s' -> clip %s",
            best["_score"], visual_description[:60], best["id"],
        )
        return best

    logger.debug(
        "No good match (best score=%.2f < %.2f) for: %s",
        best.get("_score", 0), MATCH_THRESHOLD, visual_description[:60],
    )
    return None


# ---------------------------------------------------------------------------
# Stats & maintenance
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """
    Return library statistics.

    Keys: total_clips, total_reuses, reuse_rate, clips_per_niche,
    estimated_savings_usd, db_size_bytes.
    """
    try:
        conn = _get_conn()

        total = conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
        total_reuses = conn.execute(
            "SELECT COALESCE(SUM(use_count), 0) FROM clips"
        ).fetchone()[0]

        niche_rows = conn.execute(
            "SELECT niche, COUNT(*) as cnt FROM clips GROUP BY niche ORDER BY cnt DESC"
        ).fetchall()
        clips_per_niche = {r["niche"] or "unknown": r["cnt"] for r in niche_rows}

        reuse_rate = 0.0
        if total > 0:
            reused_clips = conn.execute(
                "SELECT COUNT(*) FROM clips WHERE use_count > 0"
            ).fetchone()[0]
            reuse_rate = round(reused_clips / total, 4)

        estimated_savings = round(total_reuses * AVG_API_COST_PER_CLIP, 2)

        db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0

        return {
            "total_clips": total,
            "total_reuses": total_reuses,
            "reuse_rate": reuse_rate,
            "clips_per_niche": clips_per_niche,
            "estimated_savings_usd": estimated_savings,
            "db_size_bytes": db_size,
        }
    except Exception:
        logger.exception("Failed to get clip library stats")
        return {
            "total_clips": 0,
            "total_reuses": 0,
            "reuse_rate": 0.0,
            "clips_per_niche": {},
            "estimated_savings_usd": 0.0,
            "db_size_bytes": 0,
        }


def cleanup_old_clips(max_age_days: int = 90, min_quality: int = 3) -> int:
    """
    Remove clips older than *max_age_days* with quality below *min_quality*.

    Also deletes the clip file from disk if it still exists.
    Returns the number of clips removed.
    """
    try:
        conn = _get_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()

        rows = conn.execute(
            "SELECT id, file_path FROM clips WHERE created_at < ? AND quality_score < ?",
            (cutoff, min_quality),
        ).fetchall()

        if not rows:
            return 0

        removed = 0
        for row in rows:
            clip_id = row["id"]
            fp = row["file_path"]

            # Try to delete the file
            try:
                from config import ROOT_DIR
                full_path = ROOT_DIR / fp
                if full_path.exists():
                    full_path.unlink()
            except Exception:
                logger.debug("Could not delete file for clip %s: %s", clip_id, fp)

            # Delete from DB (cascade deletes clip_tags)
            conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
            removed += 1

        conn.commit()
        logger.info("Cleaned up %d old/low-quality clips (cutoff=%s, min_q=%d)", removed, cutoff, min_quality)
        return removed

    except Exception:
        logger.exception("Clip cleanup failed")
        if _connection:
            _connection.rollback()
        return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict, parsing JSON fields."""
    d = dict(row)
    # Parse keywords JSON
    try:
        d["keywords"] = json.loads(d.get("keywords", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["keywords"] = []
    return d
