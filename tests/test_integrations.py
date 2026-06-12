import pytest
import os
import subprocess

from smoke_signal.integrations import (
    get_summarize_command,
    build_summarize_argv,
    launch_summarize,
)

def test_get_summarize_command():
    assert get_summarize_command({}) is None
    assert get_summarize_command({"integrations": {}}) is None
    assert get_summarize_command({"integrations": {"summarize_command": ""}}) is None
    assert get_summarize_command({"integrations": {"summarize_command": "  "}}) is None
    assert get_summarize_command({"integrations": {"summarize_command": 123}}) is None
    assert get_summarize_command({"integrations": {"summarize_command": ["cmd"]}}) is None
    assert get_summarize_command({"integrations": {"summarize_command": ' claude "/transcribe {file}" '}}) == 'claude "/transcribe {file}"'

def test_build_summarize_argv():
    # Placeholder missing
    assert build_summarize_argv('claude /transcribe', "test.md") == ["claude", "/transcribe"]
    assert build_summarize_argv('claude /transcribe', None) == ["claude", "/transcribe"]

    # Placeholder empty/dropped
    # If the placeholder is alone in a quote, it becomes empty, so we drop it.
    assert build_summarize_argv('claude /transcribe "{file}"', None) == ["claude", "/transcribe"]

    # If it's part of a string, it replaces to empty, and we keep the remaining string
    assert build_summarize_argv('claude "/transcribe {file}"', None) == ["claude", "/transcribe "]

    # Quoted command names
    assert build_summarize_argv('"my program" --run {file}', "data.txt") == ["my program", "--run", "data.txt"]

    # Intentionally empty argument
    assert build_summarize_argv('cmd "" {file}', "data.txt") == ["cmd", "", "data.txt"]

    # Windows style paths with backslashes
    path = "C:\\Users\\x\\t.md"
    assert build_summarize_argv('claude "/transcribe {file}"', path) == ["claude", f"/transcribe {path}"]

def test_launch_summarize_exception(monkeypatch):
    def mock_popen(*args, **kwargs):
        raise Exception("Bogus command error")

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    # Should log warning and return False, not raise
    assert launch_summarize('bogus_command') is False
