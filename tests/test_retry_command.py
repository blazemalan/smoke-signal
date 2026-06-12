import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from smoke_signal.cli import main
from smoke_signal.watcher.state import get_pending, init_db, record_file, update_status


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_db_path(tmp_path):
    db_path = tmp_path / "test.db"
    return db_path


def test_retry_no_db(runner, mock_db_path):
    with patch("smoke_signal.commands.retry.DEFAULT_DB_PATH", mock_db_path):
        result = runner.invoke(main, ["retry"])
        assert result.exit_code == 0
        assert "Watcher database not found. Start with: smoke-signal watch" in result.output


def test_retry_no_failed_jobs(runner, mock_db_path):
    init_db(mock_db_path)
    with patch("smoke_signal.commands.retry.DEFAULT_DB_PATH", mock_db_path):
        result = runner.invoke(main, ["retry"])
        assert result.exit_code == 0
        assert "No failed jobs found." in result.output


def test_retry_list(runner, mock_db_path):
    init_db(mock_db_path)
    file_path1 = Path("error1.mp3")
    file_path2 = Path("error2.mp3")

    record_file(mock_db_path, file_path1, 1024)
    update_status(mock_db_path, file_path1, "failed", error_message="CUDA OOM")

    record_file(mock_db_path, file_path2, 2048)
    update_status(mock_db_path, file_path2, "failed", error_message="Disk full")

    with patch("smoke_signal.commands.retry.DEFAULT_DB_PATH", mock_db_path):
        result = runner.invoke(main, ["retry", "--list"])

        assert result.exit_code == 0
        assert "Found 2 failed job(s):" in result.output
        assert "- error1.mp3: CUDA OOM" in result.output
        assert "- error2.mp3: Disk full" in result.output

        # State should not be changed
        pending = get_pending(mock_db_path)
        assert len(pending) == 0


def test_retry_requeue(runner, mock_db_path):
    init_db(mock_db_path)
    file_path1 = Path("error1.mp3")
    file_path2 = Path("error2.mp3")

    record_file(mock_db_path, file_path1, 1024)
    update_status(mock_db_path, file_path1, "failed", error_message="CUDA OOM")

    record_file(mock_db_path, file_path2, 2048)
    update_status(mock_db_path, file_path2, "failed", error_message="Disk full")

    with patch("smoke_signal.commands.retry.DEFAULT_DB_PATH", mock_db_path):
        result = runner.invoke(main, ["retry"])

        assert result.exit_code == 0
        assert "Re-queued 2 failed job(s)." in result.output
        assert "- error1.mp3" in result.output
        assert "- error2.mp3" in result.output
        assert "The watcher will pick these up automatically if it is running." in result.output

        pending = get_pending(mock_db_path)
        assert len(pending) == 2

        # Verify error messages are cleared
        conn = sqlite3.connect(mock_db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM processed_files").fetchall()
        for row in rows:
            assert row["status"] == "pending"
            assert row["error_message"] is None
        conn.close()
