import pytest
import time
from pathlib import Path

from smoke_signal.watcher.queue import GpuLock

def test_gpulock_acquire_release(tmp_path: Path):
    lock_file = tmp_path / "gpu.lock"
    lock = GpuLock(lock_file)

    # Not locked initially
    assert not lock.is_locked

    # Acquire lock
    assert lock.acquire() is True
    assert lock.is_locked
    assert lock_file.exists()

    # Release lock
    lock.release()
    assert not lock.is_locked
    assert not lock_file.exists()

def test_gpulock_acquire_timeout(tmp_path: Path):
    lock_file = tmp_path / "gpu.lock"
    lock1 = GpuLock(lock_file)
    lock2 = GpuLock(lock_file)

    assert lock1.acquire() is True

    # Second lock should fail to acquire if timeout is very small
    start_time = time.time()
    assert lock2.acquire(timeout=0.1) is False
    assert time.time() - start_time >= 0.1

    lock1.release()

def test_gpulock_stale_lock_break(tmp_path: Path):
    lock_file = tmp_path / "gpu.lock"

    # Create a stale lock file (>30 minutes old)
    old_time = time.time() - 2000  # 2000 seconds ago
    lock_file.write_text(str(old_time))

    lock = GpuLock(lock_file)
    assert lock.is_locked

    # Should acquire lock by breaking the stale one
    assert lock.acquire() is True
    assert lock.is_locked

    # Ensure a new timestamp was written
    new_time = float(lock_file.read_text().strip())
    assert new_time > old_time + 1000

    lock.release()

def test_gpulock_corrupted_lock_break(tmp_path: Path):
    lock_file = tmp_path / "gpu.lock"

    # Create a corrupted lock file
    lock_file.write_text("not a float")

    lock = GpuLock(lock_file)
    assert lock.is_locked

    # Should acquire lock by breaking the corrupted one
    assert lock.acquire() is True
    assert lock.is_locked

    # Ensure a new timestamp was written
    new_time = float(lock_file.read_text().strip())
    assert new_time > 0

    lock.release()
