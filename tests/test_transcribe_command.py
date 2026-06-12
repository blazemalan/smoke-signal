import sys
import types
from unittest.mock import MagicMock
from datetime import datetime
from pathlib import Path
import pytest

# Inject fake heavy dependencies before importing do_transcribe
fake_gpu = types.ModuleType("smoke_signal.gpu")
fake_gpu.check_gpu = MagicMock(return_value={"available": False, "device": "cpu", "name": "CPU", "vram_total_mb": 0, "cuda_version": None})
fake_gpu.check_vram_sufficient = MagicMock(return_value=(True, ""))

fake_pipeline = types.ModuleType("smoke_signal.pipeline.local")
from smoke_signal.models import TranscriptResult, Segment
def mock_transcribe(*args, **kwargs):
    result = TranscriptResult(
        segments=[Segment(text="test", start=0.0, end=1.0)],
        speakers=["Speaker 1"],
        language="en",
        duration=1.0,
        model=kwargs.get("model_name", "large-v3"),
        pipeline="local",
        processing_time=1.0,
        audio_file=str(kwargs.get("audio_path", "test.mp3")),
        date=datetime.now()
    )
    return result, [0.0]
fake_pipeline.transcribe = MagicMock(side_effect=mock_transcribe)

sys.modules["smoke_signal.gpu"] = fake_gpu
sys.modules["smoke_signal.pipeline.local"] = fake_pipeline

# Import the function to test
from smoke_signal.commands.transcribe import do_transcribe
import smoke_signal.commands.transcribe as transcribe_mod


@pytest.fixture
def mock_config(monkeypatch):
    def _patch_config(config_data):
        monkeypatch.setattr(transcribe_mod, "load_config", lambda: config_data)
    return _patch_config


@pytest.fixture
def dummy_audio(tmp_path):
    audio_path = tmp_path / "test.mp3"
    audio_path.touch()
    return audio_path


def test_unknown_profile_warning(mock_config, capsys, dummy_audio, monkeypatch, tmp_path):
    mock_config({"profiles": {"prof1": {}, "prof2": {}}})
    monkeypatch.setattr(transcribe_mod, "DEFAULT_TRANSCRIPTS_DIR", tmp_path)

    do_transcribe(
        audio_file=dummy_audio,
        model=None,
        language=None,
        speakers=None,
        identify=False,
        output=None,
        compute_type=None,
        profile="unknown_prof",
        vault=False,
        batch_size=8,
        no_align=False
    )

    captured = capsys.readouterr()
    assert "Warning: profile 'unknown_prof' not found in config.yaml" in captured.out
    assert "Available profiles: prof1, prof2" in captured.out


def test_known_profile_merges_over_defaults(mock_config, dummy_audio, monkeypatch, tmp_path):
    profile_out_dir = tmp_path / "prof_out"
    default_out_dir = tmp_path / "def_out"

    config_data = {
        "defaults": {"output_dir": str(default_out_dir), "model": "small"},
        "profiles": {
            "myprof": {"output_dir": str(profile_out_dir), "model": "large-v3"}
        }
    }
    mock_config(config_data)

    do_transcribe(
        audio_file=dummy_audio,
        model=None,
        language=None,
        speakers=None,
        identify=False,
        output=None,
        compute_type=None,
        profile="myprof",
        vault=False,
        batch_size=8,
        no_align=False
    )

    # Verify the output is written to profile_out_dir
    expected_file = profile_out_dir / "test.md"
    assert expected_file.exists()
    assert "large-v3" in expected_file.read_text()

    # Check default was not used
    assert not default_out_dir.exists() or not (default_out_dir / "test.md").exists()


def test_configured_output_dir_used(mock_config, dummy_audio, monkeypatch, tmp_path):
    config_out_dir = tmp_path / "config_out"
    config_data = {
        "defaults": {"output_dir": str(config_out_dir)}
    }
    mock_config(config_data)

    do_transcribe(
        audio_file=dummy_audio,
        model=None,
        language=None,
        speakers=None,
        identify=False,
        output=None,
        compute_type=None,
        profile=None,
        vault=False,
        batch_size=8,
        no_align=False
    )

    expected_file = config_out_dir / "test.md"
    assert expected_file.exists()


def test_no_output_dir_falls_back_to_default(mock_config, dummy_audio, monkeypatch, tmp_path):
    mock_config({}) # Empty config
    default_dir = tmp_path / "default_transcripts"
    monkeypatch.setattr(transcribe_mod, "DEFAULT_TRANSCRIPTS_DIR", default_dir)

    do_transcribe(
        audio_file=dummy_audio,
        model=None,
        language=None,
        speakers=None,
        identify=False,
        output=None,
        compute_type=None,
        profile=None,
        vault=False,
        batch_size=8,
        no_align=False
    )

    expected_file = default_dir / "test.md"
    assert expected_file.exists()


def test_explicit_output_path_wins(mock_config, dummy_audio, monkeypatch, tmp_path):
    config_out_dir = tmp_path / "config_out"
    mock_config({"defaults": {"output_dir": str(config_out_dir)}})

    explicit_out_file = tmp_path / "explicit" / "custom.md"
    explicit_out_file.parent.mkdir(parents=True)

    do_transcribe(
        audio_file=dummy_audio,
        model=None,
        language=None,
        speakers=None,
        identify=False,
        output=explicit_out_file,
        compute_type=None,
        profile=None,
        vault=False,
        batch_size=8,
        no_align=False
    )

    assert explicit_out_file.exists()
    assert not (config_out_dir / "test.md").exists()
