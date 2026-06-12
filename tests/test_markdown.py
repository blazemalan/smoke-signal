import pytest
from datetime import datetime
from pathlib import Path
import yaml

from smoke_signal.models import Segment, TranscriptResult, Word
from smoke_signal.output.markdown import format_transcript, get_output_path, _format_duration


@pytest.fixture
def mock_result():
    segments = [
        Segment(text="Hello world.", start=0.0, end=2.0, speaker="SPEAKER_00", words=[]),
        Segment(text="Hi there.", start=2.5, end=3.5, speaker="SPEAKER_01", words=[]),
        Segment(text="Unlabeled text.", start=4.0, end=5.0, speaker=None, words=[]),
    ]
    return TranscriptResult(
        segments=segments,
        speakers=["SPEAKER_00", "SPEAKER_01"],
        language="en",
        duration=3665.0, # 1h 1m 5s
        model="large-v3",
        pipeline="whisperx",
        processing_time=15.5,
        audio_file="test_meeting-2023.mp3",
        date=datetime(2023, 10, 25, 14, 30)
    )

def test_format_transcript_frontmatter(mock_result):
    output = format_transcript(mock_result, vault_mode=False)

    # Extract YAML frontmatter
    parts = output.split("---")
    assert len(parts) >= 3
    frontmatter_yaml = parts[1].strip()

    frontmatter = yaml.safe_load(frontmatter_yaml)
    assert frontmatter["title"] == "Test Meeting 2023"
    assert frontmatter["date"] == "2023-10-25"
    assert frontmatter["duration"] == "1:01:05"
    assert frontmatter["speakers"] == ["SPEAKER_00", "SPEAKER_01"]
    assert frontmatter["model"] == "large-v3"
    assert frontmatter["pipeline"] == "whisperx"
    assert frontmatter["language"] == "en"
    assert frontmatter["audio_file"] == "test_meeting-2023.mp3"


def test_format_transcript_body_and_speakers(mock_result):
    output = format_transcript(mock_result, vault_mode=False)

    assert "**[00:00] SPEAKER_00:**" in output
    assert "Hello world." in output
    assert "**[00:02] SPEAKER_01:**" in output
    assert "Hi there." in output
    assert "**[00:04] Unknown:**" in output
    assert "Unlabeled text." in output

def test_format_transcript_vault_mode(mock_result):
    # Without vault_mode
    normal_output = format_transcript(mock_result, vault_mode=False)
    assert "## Key Discussion Points" not in normal_output
    assert "## Decisions Made" not in normal_output
    assert "## Action Items" not in normal_output

    # With vault_mode
    vault_output = format_transcript(mock_result, vault_mode=True)
    assert "## Key Discussion Points" in vault_output
    assert "## Decisions Made" in vault_output
    assert "## Action Items" in vault_output
    assert "- [ ] **SPEAKER_00:**" in vault_output
    assert "- [ ] **SPEAKER_01:**" in vault_output

def test_get_output_path():
    audio_path = Path("my_recording.wav")
    output_dir = Path("/tmp/output")

    normal_path = get_output_path(audio_path, output_dir, vault_mode=False)
    assert normal_path == Path("/tmp/output/my_recording.md")

    vault_path = get_output_path(audio_path, output_dir, vault_mode=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    assert vault_path == Path(f"/tmp/output/{date_str}-my_recording.md")

def test_format_duration_edge_cases():
    assert _format_duration(59.9) == "0:59"
    assert _format_duration(60.0) == "1:00"
    assert _format_duration(3599.9) == "59:59"
    assert _format_duration(3600.0) == "1:00:00"
    assert _format_duration(3665.0) == "1:01:05"
