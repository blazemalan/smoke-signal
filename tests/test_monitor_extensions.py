import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from smoke_signal.watcher.monitor import ICloudFileHandler, scan_existing
from smoke_signal.watcher.state import init_db


@pytest.fixture
def db_path():
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        yield db_path


def test_icloud_file_handler_extensions_normalization(db_path):
    # Test that varying cases and leading dots are handled properly
    handler = ICloudFileHandler(
        on_file_ready=lambda p: None,
        db_path=db_path,
        extensions=["wav", ".MP3", ".M4A", "WAV", ".ogg"]
    )

    assert handler.extensions == {".wav", ".mp3", ".m4a", ".ogg"}

    # Mock tracking
    handler._handle_file(Path("test.WAV"))
    assert str(Path("test.WAV")) in handler._tracking

    handler._handle_file(Path("test.mp3"))
    assert str(Path("test.mp3")) in handler._tracking

    # Should not track .txt
    handler._handle_file(Path("test.txt"))
    assert str(Path("test.txt")) not in handler._tracking


def test_icloud_file_handler_default_extension(db_path):
    handler = ICloudFileHandler(
        on_file_ready=lambda p: None,
        db_path=db_path,
    )

    assert handler.extensions == {".m4a"}

    handler._handle_file(Path("test.m4a"))
    assert str(Path("test.m4a")) in handler._tracking

    handler._handle_file(Path("test.wav"))
    assert str(Path("test.wav")) not in handler._tracking


def test_scan_existing_extensions(db_path, tmp_path):
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()

    # Create files of various extensions and sizes
    f1 = watch_dir / "test1.m4a"
    f2 = watch_dir / "test2.wav"
    f3 = watch_dir / "test3.mp3"
    f4 = watch_dir / "test4.txt"
    f5 = watch_dir / "test5.wav"

    # Write some bytes to bypass min_file_size filter
    data = b"0" * 100_000
    for f in [f1, f2, f3, f4, f5]:
        f.write_bytes(data)

    # Test default
    new_files = scan_existing(watch_dir, db_path, min_file_size=50_000)
    assert len(new_files) == 1
    assert new_files[0] == f1

    # Test configured extensions
    new_files = scan_existing(
        watch_dir,
        db_path,
        min_file_size=50_000,
        extensions=["wav", ".m4a", "mp3"]
    )

    assert len(new_files) == 4
    # All except .txt should be present
    assert set(new_files) == {f1, f2, f3, f5}
