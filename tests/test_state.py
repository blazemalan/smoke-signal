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
