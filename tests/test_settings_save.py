"""Headless tests for the dashboard Settings tab save logic.

tkinter is stubbed so these run without a display or python3-tk.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def dash(monkeypatch):
    monkeypatch.setitem(sys.modules, "tkinter", MagicMock())
    sys.modules.pop("smoke_signal.watcher.dashboard", None)
    import smoke_signal.watcher.dashboard as dashboard
    yield dashboard
    sys.modules.pop("smoke_signal.watcher.dashboard", None)


class FakeWidget:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


class FakeStatus:
    def __init__(self):
        self.text = None
        self.fg = None

    def configure(self, text=None, fg=None):
        self.text, self.fg = text, fg


def _stub(widgets):
    base = {
        "model": FakeWidget("large-v3-turbo"),
        "language": FakeWidget("en"),
        "speakers": FakeWidget(""),
        "identify": FakeWidget(False),
        "notifications": FakeWidget(True),
        "stability": FakeWidget("30"),
        "extensions": FakeWidget(".m4a"),
        "summarize_command": FakeWidget(""),
    }
    base.update(widgets)
    return types.SimpleNamespace(_settings_widgets=base, _settings_status=FakeStatus())


def test_save_happy_path(dash, monkeypatch):
    saved = {}
    monkeypatch.setattr(dash, "load_config", lambda: {"defaults": {}, "watcher": {}})
    monkeypatch.setattr(dash, "save_config", lambda cfg: saved.update(cfg))

    stub = _stub({
        "speakers": FakeWidget("4"),
        "stability": FakeWidget("45"),
        "extensions": FakeWidget("m4a, .WAV, ,mp3"),
        "summarize_command": FakeWidget('claude "/transcribe {file}"'),
    })
    dash.DashboardWindow._save_settings(stub)

    assert saved["defaults"]["speakers"] == 4
    assert saved["watcher"]["stability_seconds"] == 45
    assert saved["watcher"]["extensions"] == [".m4a", ".wav", ".mp3"]
    assert saved["integrations"]["summarize_command"] == 'claude "/transcribe {file}"'
    assert "Saved" in stub._settings_status.text


def test_save_rejects_bad_numbers_without_writing(dash, monkeypatch):
    saved = {}
    monkeypatch.setattr(dash, "load_config", lambda: {})
    monkeypatch.setattr(dash, "save_config", lambda cfg: saved.update(cfg))

    for field, value in [("speakers", "four"), ("speakers", "0"),
                         ("stability", "abc"), ("stability", "-5")]:
        stub = _stub({field: FakeWidget(value)})
        dash.DashboardWindow._save_settings(stub)
        assert saved == {}, f"config written despite bad {field}={value!r}"
        assert stub._settings_status.text  # error shown


def test_blank_fields_remove_keys(dash, monkeypatch):
    saved = {}
    monkeypatch.setattr(
        dash, "load_config",
        lambda: {"defaults": {"speakers": 4},
                 "integrations": {"summarize_command": "old"}},
    )
    monkeypatch.setattr(dash, "save_config", lambda cfg: saved.update(cfg))

    stub = _stub({"speakers": FakeWidget(""), "summarize_command": FakeWidget("  ")})
    dash.DashboardWindow._save_settings(stub)

    assert "speakers" not in saved["defaults"]
    assert "summarize_command" not in saved.get("integrations", {})
