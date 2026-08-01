"""Smoke Signal CLI — local-first audio transcription with speaker diarization."""

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")

import click

from smoke_signal.config import load_env

from smoke_signal.commands.transcribe import transcribe
from smoke_signal.commands.profiles import enroll, profiles
from smoke_signal.commands.watcher import watch, classify_file, status
from smoke_signal.commands.retry import retry
from smoke_signal.commands.verify import verify
from smoke_signal.commands.setup import setup


@click.group()
def main():
    """Smoke Signal — local-first audio transcription with speaker diarization."""
    load_env()


main.add_command(transcribe)
main.add_command(enroll)
main.add_command(profiles)
main.add_command(verify)
main.add_command(watch)
main.add_command(classify_file, name="classify")
main.add_command(status)
main.add_command(retry)
main.add_command(setup)


if __name__ == "__main__":
    main()
