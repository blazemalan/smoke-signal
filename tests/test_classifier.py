import pytest
from pathlib import Path
from datetime import datetime

from smoke_signal.watcher.classifier import (
    classify,
    classify_from_description,
    _extract_date,
    _extract_time,
    _humanize_filename,
)


def test_humanize_filename():
    assert _humanize_filename("my-test_file  name") == "My Test File Name"
    assert _humanize_filename("weekly_sync") == "Weekly Sync"
    assert _humanize_filename("  leading-and-trailing  ") == "Leading And Trailing"


def test_extract_time():
    assert _extract_time(Path("12-30-45.m4a")) == "12:30:45"
    assert _extract_time(Path("09-05-01 2.m4a")) == "09:05:01"
    assert _extract_time(Path("custom_name.m4a")) is None
    assert _extract_time(Path("12-30-45_suffix.m4a")) is None


def test_extract_date():
    path_with_date = Path("/some/path/2023-10-25/file.m4a")
    assert _extract_date(path_with_date) == "2023-10-25"

    path_without_date = Path("/some/path/other/file.m4a")
    # Date will be today's date if not matched
    assert _extract_date(path_without_date) == datetime.now().strftime("%Y-%m-%d")


def test_classify_timestamp_only():
    path = Path("2023-10-25/12-30-45.m4a")
    result = classify(path)
    assert result.meeting_type == "unknown"
    assert result.confidence == "low"
    assert result.recording_time == "12:30:45"
    assert result.recording_date == "2023-10-25"
    assert result.description == ""


def test_classify_timestamp_with_suffix():
    path = Path("2023-10-25/12-30-45 2.m4a")
    result = classify(path)
    assert result.meeting_type == "unknown"
    assert result.confidence == "low"
    assert result.recording_time == "12:30:45"
    assert result.recording_date == "2023-10-25"
    assert result.description == ""


def test_classify_keyword_match():
    # 'meeting' is a trigger for the 'meeting' category
    path = Path("2023-10-25/Weekly Meeting.m4a")
    result = classify(path)
    assert result.meeting_type == "meeting"
    assert result.confidence == "high"
    assert result.description == "Weekly Meeting"

    # 'candidate' is a trigger for the 'interview' category
    path = Path("2023-10-25/candidate_interview.m4a")
    result = classify(path)
    assert result.meeting_type == "interview"
    assert result.confidence == "high"
    assert result.description == "Candidate Interview"


def test_classify_custom_name_fallback():
    # 'brainstorming' does not match any default category keyword
    path = Path("2023-10-25/brainstorming_session.m4a")
    result = classify(path)
    assert result.meeting_type == "general"
    assert result.confidence == "medium"
    assert result.description == "Brainstorming Session"


def test_classify_from_description():
    path = Path("2023-10-25/12-30-45.m4a")

    # Matches 'interview' keyword
    result_high = classify_from_description(path, "Interview with Bob")
    assert result_high.meeting_type == "interview"
    assert result_high.confidence == "high"
    assert result_high.description == "Interview with Bob"

    # No match, falls back to 'general'
    result_med = classify_from_description(path, "Random musings")
    assert result_med.meeting_type == "general"
    assert result_med.confidence == "medium"
    assert result_med.description == "Random musings"
