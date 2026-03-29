"""Auto-classification of recordings from filename keywords and config."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Classification:
    meeting_type: str       # category name from config, or "unknown"
    profile: str            # smoke-signal config profile name
    description: str        # human-readable description
    confidence: str         # high|medium|low
    recording_date: str     # YYYY-MM-DD
    recording_time: str | None = None  # HH:MM:SS or None


# Default categories — used when no config is provided
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "meeting": ["meeting", "sync", "standup", "1on1", "check-in", "call"],
    "interview": ["interview", "candidate"],
    "lecture": ["lecture", "class", "course", "seminar"],
    "personal": ["journal", "note", "memo", "thought", "voice"],
}

# Date folder pattern: YYYY-MM-DD
DATE_FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Timestamp filename pattern: HH-MM-SS.m4a or HH-MM-SS 2.m4a (duplicate suffix)
TIMESTAMP_FILE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})(?:\s+\d+)?\.\w+$")


def classify(
    file_path: Path,
    categories: dict[str, list[str]] | None = None,
) -> Classification:
    """Classify a recording based on its filename keywords.

    Categories are loaded from config.yaml. Each category maps to a list of
    trigger keywords. First match wins. Timestamp-only filenames and
    unmatched custom names are returned as type='unknown' (held for user).
    """
    cats = categories or DEFAULT_CATEGORIES
    recording_date = _extract_date(file_path)
    recording_time = _extract_time(file_path)
    filename_stem = file_path.stem.lower()

    # Timestamp-only filenames have no classification signal
    if TIMESTAMP_FILE_RE.match(file_path.name):
        return Classification(
            meeting_type="unknown",
            profile="default",
            description="",
            confidence="low",
            recording_date=recording_date,
            recording_time=recording_time,
        )

    # Check each category's keywords against filename
    for category, keywords in cats.items():
        for keyword in keywords:
            if keyword.lower() in filename_stem:
                return Classification(
                    meeting_type=category,
                    profile="default",
                    description=_humanize_filename(file_path.stem),
                    confidence="high",
                    recording_date=recording_date,
                    recording_time=recording_time,
                )

    # Custom filename but no keyword match — still classify as general
    # so it gets transcribed (better than holding everything)
    return Classification(
        meeting_type="general",
        profile="default",
        description=_humanize_filename(file_path.stem),
        confidence="medium",
        recording_date=recording_date,
        recording_time=recording_time,
    )


def classify_from_description(
    file_path: Path,
    description: str,
    categories: dict[str, list[str]] | None = None,
) -> Classification:
    """Classify using a user-provided description (for held files)."""
    cats = categories or DEFAULT_CATEGORIES
    recording_date = _extract_date(file_path)
    recording_time = _extract_time(file_path)
    desc_lower = description.lower()

    for category, keywords in cats.items():
        for keyword in keywords:
            if keyword.lower() in desc_lower:
                return Classification(
                    meeting_type=category,
                    profile="default",
                    description=description,
                    confidence="high",
                    recording_date=recording_date,
                    recording_time=recording_time,
                )

    return Classification(
        meeting_type="general",
        profile="default",
        description=description,
        confidence="medium",
        recording_date=recording_date,
        recording_time=recording_time,
    )


def _extract_date(file_path: Path) -> str:
    """Extract recording date from the parent folder name (YYYY-MM-DD)."""
    parent = file_path.parent.name
    if DATE_FOLDER_RE.match(parent):
        return parent
    return datetime.now().strftime("%Y-%m-%d")


def _extract_time(file_path: Path) -> str | None:
    """Extract recording time from timestamp filenames (HH-MM-SS)."""
    match = TIMESTAMP_FILE_RE.match(file_path.name)
    if match:
        return f"{match.group(1)}:{match.group(2)}:{match.group(3)}"
    return None


def _humanize_filename(stem: str) -> str:
    """Convert a filename stem to a human-readable description."""
    result = stem.replace("-", " ").replace("_", " ")
    result = re.sub(r"\s+", " ", result).strip()
    return result.title()
