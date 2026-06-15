import pytest
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from smoke_signal.watcher.state import init_db, record_file, update_status, _query

@pytest.fixture
def db_path():
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        yield db_path

def test_init_db_creates_schema(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    assert db_path.exists()

    # Check that table and expected columns exist
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        # Verify table exists
        table_info = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_files'"
        ).fetchone()
        assert table_info is not None

        # Verify columns
        columns_info = conn.execute("PRAGMA table_info(processed_files)").fetchall()
        columns = {row["name"]: row["type"] for row in columns_info}

        expected_columns = {
            "id": "INTEGER",
            "file_path": "TEXT",
            "file_size": "INTEGER",
            "recording_date": "TEXT",
            "recording_time": "TEXT",
            "status": "TEXT",
            "meeting_type": "TEXT",
            "description": "TEXT",
            "profile": "TEXT",
            "output_path": "TEXT",
            "error_message": "TEXT",
            "created_at": "TEXT",
            "completed_at": "TEXT",
            "processing_time_seconds": "REAL"
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name] == col_type


def test_init_db_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    # Should not raise an exception
    init_db(db_path)

    # Check it still exists and works
    assert db_path.exists()


def test_update_status_sql_injection_prevention(db_path):
    file_path = Path("test.mp3")
    record_file(db_path, file_path, 1024)

    with pytest.raises(ValueError, match="Invalid column name: status = 'failed', meeting_type"):
        update_status(
            db_path,
            file_path,
            status="completed",
            **{"status = 'failed', meeting_type": "hacked"}
        )

    # Ensure status wasn't changed incorrectly (it should still be pending)
    result = _query(db_path, "SELECT status, meeting_type FROM processed_files WHERE file_path = ?", (str(file_path),))
    assert result[0]['status'] == "pending"
    assert result[0]['meeting_type'] is None

def test_update_status_valid_columns(db_path):
    file_path = Path("test.mp3")
    record_file(db_path, file_path, 1024)

    update_status(
        db_path,
        file_path,
        status="processing",
        meeting_type="conference",
        description="test description"
    )

    result = _query(db_path, "SELECT status, meeting_type, description FROM processed_files WHERE file_path = ?", (str(file_path),))
    assert result[0]['status'] == "processing"
    assert result[0]['meeting_type'] == "conference"
    assert result[0]['description'] == "test description"
