"""SQLite state management for processed files and job history."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def init_db(db_path: Path) -> None:
    """Initialize the database and create tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_size INTEGER,
                recording_date TEXT,
                recording_time TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                meeting_type TEXT,
                description TEXT,
                profile TEXT,
                output_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                processing_time_seconds REAL
            )
        """)


def record_file(
    db_path: Path,
    file_path: Path,
    file_size: int,
    recording_date: str | None = None,
    recording_time: str | None = None,
    status: str = "pending",
    meeting_type: str | None = None,
    description: str | None = None,
    profile: str | None = None,
) -> int:
    """Insert a new file record. Returns the row ID."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO processed_files
                (file_path, file_size, recording_date, recording_time,
                 status, meeting_type, description, profile, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(file_path),
                file_size,
                recording_date,
                recording_time,
                status,
                meeting_type,
                description,
                profile,
                datetime.now().isoformat(),
            ),
        )
        return cursor.lastrowid


def is_processed(db_path: Path, file_path: Path) -> bool:
    """Check if a file has already been seen (any status)."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_files WHERE file_path = ?",
            (str(file_path),),
        ).fetchone()
        return row is not None


def get_pending(db_path: Path) -> list[dict]:
    """Get all files with status='pending', ordered by creation time."""
    return _query(
        db_path,
        "SELECT * FROM processed_files WHERE status = 'pending' ORDER BY created_at",
    )


def get_held(db_path: Path) -> list[dict]:
    """Get all files with status='held'."""
    return _query(
        db_path,
        "SELECT * FROM processed_files WHERE status = 'held' ORDER BY created_at",
    )


def update_status(db_path: Path, file_path: Path, status: str, **kwargs: Any) -> None:
    """Update the status and optional fields for a file."""
    sets = ["status = ?"]
    values: list[Any] = [status]

    if status == "completed":
        kwargs.setdefault("completed_at", datetime.now().isoformat())

    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        values.append(value)

    values.append(str(file_path))

    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE processed_files SET {', '.join(sets)} WHERE file_path = ?",
            values,
        )


def get_recent_jobs(db_path: Path, limit: int = 10) -> list[dict]:
    """Get the most recent jobs, regardless of status."""
    return _query(
        db_path,
        "SELECT * FROM processed_files ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


def reset_stale_processing(db_path: Path) -> int:
    """Reset any 'processing' rows to 'pending' (crash recovery). Returns count."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE processed_files SET status = 'pending' WHERE status = 'processing'"
        )
        return cursor.rowcount


def mark_existing_as_seen(db_path: Path, file_paths: list[Path]) -> int:
    """Mark a batch of existing files as 'seen' (first-run seeding). Returns count."""
    count = 0
    with _connect(db_path) as conn:
        for fp in file_paths:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO processed_files
                    (file_path, file_size, status, created_at)
                VALUES (?, ?, 'seen', ?)
                """,
                (str(fp), fp.stat().st_size if fp.exists() else 0, datetime.now().isoformat()),
            )
            count += cursor.rowcount
    return count


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def _query(db_path: Path, sql: str, params: tuple = ()) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
