"""Markdown + YAML frontmatter output formatter."""

from datetime import datetime
from pathlib import Path

import yaml

from smoke_signal.models import Segment, TranscriptResult


def format_transcript(result: TranscriptResult, vault_mode: bool = False) -> str:
    """Format a TranscriptResult as markdown with YAML frontmatter."""
    parts = []

    # YAML frontmatter
    frontmatter = {
        "title": _infer_title(result, vault_mode),
        "date": result.date.strftime("%Y-%m-%d"),
        "duration": _format_duration(result.duration),
        "speakers": result.speakers,
        "model": result.model,
        "pipeline": result.pipeline,
        "language": result.language,
        "audio_file": result.audio_file,
    }
    parts.append("---")
    parts.append(yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip())
    parts.append("---")
    parts.append("")

    # Title
    title = frontmatter["title"]
    date_str = result.date.strftime("%Y-%m-%d")
    parts.append(f"# {title} — {date_str}")
    parts.append("")
    parts.append(f"**Duration:** {frontmatter['duration']} | **Speakers:** {', '.join(result.speakers)}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # Transcript body
    parts.extend(_format_segments(result.segments))

    if vault_mode:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("## Key Discussion Points")
        parts.append("")
        parts.append("-")
        parts.append("")
        parts.append("## Decisions Made")
        parts.append("")
        parts.append("-")
        parts.append("")
        parts.append("## Action Items")
        parts.append("")
        for speaker in result.speakers:
            parts.append(f"- [ ] **{speaker}:**")
        parts.append("")

    # Footer
    parts.append("---")
    parts.append("")
    timestamp = result.date.strftime("%Y-%m-%d at %I:%M %p")
    proc_time = _format_duration(result.processing_time)
    parts.append(
        f"*Transcribed locally with WhisperX ({result.model}) on {timestamp}. "
        f"Processing time: {proc_time}.*"
    )
    parts.append("")

    return "\n".join(parts)


def _format_segments(segments: list[Segment]) -> list[str]:
    """Format transcript segments with speaker labels and timestamps."""
    lines = []
    current_speaker = None

    for seg in segments:
        speaker = seg.speaker or "Unknown"
        timestamp = _format_timestamp(seg.start)

        if speaker != current_speaker:
            if current_speaker is not None:
                lines.append("")
            lines.append(f"**[{timestamp}] {speaker}:**")
            current_speaker = speaker

        lines.append(seg.text)

    return lines


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _infer_title(result: TranscriptResult, vault_mode: bool) -> str:
    stem = Path(result.audio_file).stem
    # Clean up common filename patterns
    title = stem.replace("-", " ").replace("_", " ").title()
    return title


def get_output_path(
    audio_path: Path, output_dir: Path, vault_mode: bool = False,
) -> Path:
    """Generate the output markdown file path."""
    stem = audio_path.stem
    date_str = datetime.now().strftime("%Y-%m-%d")

    if vault_mode:
        filename = f"{date_str}-{stem}.md"
    else:
        filename = f"{stem}.md"

    return output_dir / filename
