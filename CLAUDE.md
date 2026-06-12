# CLAUDE.md

## What This Is

Smoke Signal is a local-first Python CLI tool for audio transcription with speaker diarization. It uses WhisperX (faster-whisper + pyannote.audio) to transcribe audio files and identify who said what. A file watcher with a system-tray app auto-transcribes new recordings.

## Tech Stack

- **Python 3.12** (conda env `scribe`)
- **WhisperX** — transcription + alignment + diarization
- **faster-whisper** — CTranslate2-optimized Whisper backend (bundled via WhisperX)
- **pyannote.audio 4.0.x** — speaker diarization. 4.x has a known VRAM spike on long recordings (pyannote-audio#1963, still open); mitigated in `pipeline/local.py` by setting `embedding_batch_size = 4`
- **PyTorch 2.10+cu128** — GPU inference on RTX 5070 Ti (Blackwell/sm_120)
- **Click** — CLI framework
- **Pydantic** — data models

## Hardware Target

- NVIDIA RTX 5070 Ti (16GB GDDR7, CUDA 13.0)
- float16 compute type (INT8 broken on Blackwell)
- Sequential GPU: Whisper (~10GB) then pyannote, never simultaneous

## Runtime Layout

- Live app data: `%LOCALAPPDATA%\SmokeSignal` (config.yaml, .env, profiles\, data\, logs\, transcripts\)
- `SMOKE_SIGNAL_DATA_DIR` env var overrides the data dir (used by `scripts\start-watcher-dev.bat` to sandbox against the repo root)
- Canonical launcher: flame-icon "Smoke Signal" desktop shortcut → `smoke-signal-tray.exe` (conda env `scribe`). Do not break this flow.

## Project Structure

- `src/smoke_signal/cli.py` — Click CLI entry point (thin; logic lives in commands/)
- `src/smoke_signal/commands/` — command business logic (transcribe, profiles, watcher)
- `src/smoke_signal/config.py` — config loading (.env + config.yaml in the data dir)
- `src/smoke_signal/gpu.py` — GPU detection and VRAM checks
- `src/smoke_signal/audio.py` — ffmpeg preprocessing
- `src/smoke_signal/models.py` — Pydantic data models
- `src/smoke_signal/pipeline/local.py` — WhisperX orchestration
- `src/smoke_signal/enrollment/` — speaker profile CRUD + cosine similarity matching
- `src/smoke_signal/output/` — markdown (YAML frontmatter) + structured (json/csv) output
- `src/smoke_signal/watcher/` — daemon, monitor, queue, classifier, job, state (SQLite), notifier, tray, Tk dashboard
- `src/smoke_signal/setup_wizard.py` — first-run Tk setup wizard
- `src/smoke_signal/tray_entry.py` — windowless tray entry point
- `src/smoke_signal/platform/` — per-OS helpers (notifications, GPU memory release)

## Key Decisions

- No API fallback — fully local only
- Speaker profiles stored as JSON in the data dir `profiles/` (git-ignored, biometric data)
- pyannote.audio 4.0.x with `embedding_batch_size = 4` workaround for the 4.x VRAM spike (pyannote-audio#1963); revisit when the issue is fixed upstream
- Always use float16 compute type (Blackwell INT8 cuBLAS bug)
- Python 3.12 required (WhisperX incompatible with 3.13)
- CLI and watcher must honor the same config (`defaults.output_dir` etc.)
- Line endings: enforced by .gitattributes (LF for code, CRLF for .bat/.ps1)
