"""Headless tests for the enrollment service (GPU modules stubbed)."""

import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def service(monkeypatch, tmp_path):
    # Stub the torch-importing modules before the service imports them
    gpu = types.ModuleType("smoke_signal.gpu")
    gpu.check_gpu = MagicMock(return_value={"device": "cuda"})
    manager = types.ModuleType("smoke_signal.enrollment.manager")
    manager.enroll_speaker = MagicMock(return_value=tmp_path / "p.json")
    manager.list_profiles = MagicMock(return_value=[])
    monkeypatch.setitem(sys.modules, "smoke_signal.gpu", gpu)
    monkeypatch.setitem(sys.modules, "smoke_signal.enrollment.manager", manager)

    import smoke_signal.config as config
    monkeypatch.setattr(config, "get_hf_token", lambda: "hf_test")

    from smoke_signal.enrollment import service as svc
    return svc, manager


class FakeLock:
    def __init__(self, busy=False):
        self.busy = busy
        self.released = False

    def acquire(self, timeout=0):
        return not self.busy

    def release(self):
        self.released = True


def test_enroll_success(service, tmp_path):
    svc, manager = service
    msgs = []
    lock = FakeLock()
    ok = svc.enroll_from_file("Ashley", tmp_path / "a.m4a", msgs.append, gpu_lock=lock)
    assert ok is True
    assert manager.enroll_speaker.call_args.kwargs["append"] is False
    assert any("Enrolled Ashley" in m for m in msgs)
    assert lock.released


def test_enroll_appends_to_existing_profile(service, tmp_path):
    svc, manager = service
    manager.list_profiles.return_value = [{"name": "Ashley"}]
    ok = svc.enroll_from_file("Ashley", tmp_path / "a.m4a", lambda m: None, gpu_lock=FakeLock())
    assert ok is True
    assert manager.enroll_speaker.call_args.kwargs["append"] is True


def test_enroll_gpu_busy(service, tmp_path):
    svc, manager = service
    msgs = []
    ok = svc.enroll_from_file("X", tmp_path / "a.m4a", msgs.append, gpu_lock=FakeLock(busy=True))
    assert ok is False
    assert manager.enroll_speaker.call_count == 0
    assert any("busy" in m for m in msgs)


def test_enroll_missing_token(service, tmp_path, monkeypatch):
    svc, _ = service
    import smoke_signal.config as config
    def boom():
        raise ValueError("no token")
    monkeypatch.setattr(config, "get_hf_token", boom)
    msgs = []
    ok = svc.enroll_from_file("X", tmp_path / "a.m4a", msgs.append)
    assert ok is False
    assert any("HF_TOKEN" in m for m in msgs)


def test_enroll_failure_releases_lock(service, tmp_path):
    svc, manager = service
    manager.enroll_speaker.side_effect = RuntimeError("model exploded")
    lock = FakeLock()
    msgs = []
    ok = svc.enroll_from_file("X", tmp_path / "a.m4a", msgs.append, gpu_lock=lock)
    assert ok is False
    assert lock.released
    assert any("failed" in m.lower() for m in msgs)


def test_recording_available_is_bool(service):
    svc, _ = service
    assert isinstance(svc.recording_available(), bool)
