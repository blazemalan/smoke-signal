import csv
import io

from smoke_signal.models import TranscriptResult

def format_json(result: TranscriptResult) -> str:
    """Format a TranscriptResult as JSON."""
    return result.model_dump_json(indent=2)

def format_csv(result: TranscriptResult) -> str:
    """Format a TranscriptResult as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["speaker", "start", "end", "text"])
    for segment in result.segments:
        speaker = segment.speaker or "Unknown"
        writer.writerow([speaker, f"{segment.start:.3f}", f"{segment.end:.3f}", segment.text])

    return output.getvalue()
