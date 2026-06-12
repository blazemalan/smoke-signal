"""Tests for the single-instance guard."""

import socket
import threading
import time

from smoke_signal.watcher.single_instance import SingleInstance


def _free_port() -> int:
    """Ask the OS for a currently free port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _free_pair(port=None):
    port = port or _free_port()
    return SingleInstance(port=port), SingleInstance(port=port)


def test_first_instance_acquires():
    a = SingleInstance(port=_free_port())
    try:
        assert a.acquire() is True
    finally:
        a.release()


def test_second_instance_fails_to_acquire():
    a, b = _free_pair()
    try:
        assert a.acquire() is True
        assert b.acquire() is False
    finally:
        a.release()
        b.release()


def test_second_launch_pops_window():
    """Second launch signals the first instance, which fires on_show."""
    a, b = _free_pair()
    shown = threading.Event()
    try:
        assert a.acquire() is True
        a.listen(shown.set)

        # Simulate the second launch path: acquire fails -> notify_existing
        assert b.acquire() is False
        assert b.notify_existing() is True

        assert shown.wait(timeout=3), "on_show was not called within 3s"
    finally:
        a.release()
        b.release()


def test_release_allows_new_instance():
    a, b = _free_pair()
    try:
        assert a.acquire() is True
        a.release()
        assert b.acquire() is True
    finally:
        a.release()
        b.release()


def test_notify_without_running_instance_is_graceful():
    lone = SingleInstance(port=_free_port())
    assert lone.notify_existing() is False  # nothing listening — no crash
