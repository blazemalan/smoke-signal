"""Transcription job orchestration — bridges watcher to existing pipeline."""

import logging
import time
from pathlib import Path

from smoke_signal.config import (
    DEFAULT_PROFILES_DIR,
    DEFAULT_TRANSCRIPTS_DIR,
    get_hf_token,
    get_profile,
    load_config,
)
from smoke_signal.watcher.state import update_status

logger = logging.getLogger(__name__)


def run_job(job: dict, db_path: Path) -> None:
    """Execute a full transcription job using the existing pipeline.

    This is called by the ProcessingQueue for each pending job.
    """
    from smoke_signal.gpu import check_gpu
    from smoke_signal.output.markdown import format_transcript, get_output_path
    from smoke_signal.pipeline.local import transcribe

    file_path = Path(job["file_path"])
    profile_name = job.get("profile", "work")
    meeting_type = job.get("meeting_type", "general")

    logger.info(f"Starting job: {file_path.name} (type={meeting_type}, profile={profile_name})")
    start = time.time()

    # Load config and profile
    config = load_config()
    prof = get_profile(config, profile_name)

    model = prof.get("model", "large-v3")
    compute_type = prof.get("compute_type", "float16")
    language = prof.get("language", "en")
    num_speakers = prof.get("speakers")
    identify = prof.get("identify", False)
    align = prof.get("align", True)
    batch_size = prof.get("batch_size", 16)

    # GPU check
    gpu_info = check_gpu()
    device = gpu_info["device"]

    if not gpu_info["available"]:
        logger.warning("No GPU available, transcription will be slow")

    # Run transcription
    result, audio_array = transcribe(
        audio_path=file_path,
        model_name=model,
        compute_type=compute_type,
        language=language,
        num_speakers=num_speakers,
        device=device,
        batch_size=batch_size,
        align=align,
        log_fn=logger.info,
    )

    # Speaker identification
    if identify:
        from smoke_signal.enrollment.matcher import identify_speakers
        hf_token = get_hf_token()
        result = identify_speakers(
            result, file_path, DEFAULT_PROFILES_DIR, hf_token, device,
            audio_array=audio_array,
        )

    # Format and write output
    markdown = format_transcript(result, vault_mode=False)
    DEFAULT_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = get_output_path(file_path, DEFAULT_TRANSCRIPTS_DIR, vault_mode=False)
    output_path.write_text(markdown, encoding="utf-8")

    elapsed = time.time() - start
    duration_str = _format_duration(result.duration)

    logger.info(
        f"Job complete: {file_path.name} → {output_path.name} "
        f"({duration_str}, {len(result.speakers)} speakers, {_format_duration(elapsed)} processing)"
    )

    # Update state
    update_status(
        db_path,
        file_path,
        "completed",
        output_path=str(output_path),
        processing_time_seconds=elapsed,
    )

    # Send notification
    from smoke_signal.watcher.notifier import notify_success
    recording_date = job.get("recording_date", result.date.strftime("%Y-%m-%d"))
    notify_success(
        meeting_type=meeting_type,
        recording_date=recording_date,
        output_path=output_path,
        duration_str=duration_str,
    )


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
