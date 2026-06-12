"""Tests for ProcessingQueue pause/resume behavior."""

import threading
import time

from smoke_signal.watcher.queue import GpuLock, ProcessingQueue
from smoke_signal.watcher.state import init_db, record_file


def _make_queue(tmp_path, process_fn):
    db_path = tmp_path / "watcher.db"
    init_db(db_path)
    lock = GpuLock(tmp_path / "gpu.lock")
    return db_path, ProcessingQueue(db_path, process_fn, lock)


def test_pause_flag_round_trip(tmp_path):
    _, queue = _make_queue(tmp_path, lambda job: None)
    assert not queue.is_paused
    queue.pause()
    assert queue.is_paused
    queue.resume()
    assert not queue.is_paused


def test_paused_queue_does_not_pick_up_jobs(tmp_path):
    processed = []
    db_path, queue = _make_queue(tmp_path, lambda job: processed.append(job))

    audio = tmp_path / "rec.m4a"
    audio.write_bytes(b"x" * 10)
    record_file(db_path, audio, file_size=10, recording_date="2026-06-12",
                status="pending", meeting_type="meeting", profile="default")

    queue.pause()
    t = threading.Thread(target=queue.run_loop, daemon=True)
    t.start()
    queue.enqueue_wake()
    time.sleep(0.5)
    assert processed == []  # paused: nothing picked up

    queue.resume()
    deadline = time.time() + 5
    while not processed and time.time() < deadline:
        time.sleep(0.05)
    queue.stop()
    t.join(timeout=5)
    assert len(processed) == 1  # resumed: job ran
