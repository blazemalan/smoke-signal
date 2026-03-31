# CLAUDE.md

## What This Is

Smoke Signal is a local-first Python CLI tool for audio transcription with speaker diarization. It uses WhisperX (faster-whisper + pyannote.audio) to transcribe audio files and identify who said what.

## Tech Stack

- **Python 3.12** (conda env `scribe`)
- **WhisperX** — transcription + alignment + diarization
- **faster-whisper** — CTranslate2-optimized Whisper backend (bundled via WhisperX)
- **pyannote.audio 3.3.x** — speaker diarization (pinned below 4.0 to avoid VRAM regression)
- **PyTorch 2.10.0+cu128** — GPU inference on RTX 5070 Ti (Blackwell/sm_120)
- **Click** — CLI framework
- **Pydantic** — data models

## Hardware Target

- NVIDIA RTX 5070 Ti (16GB GDDR7, CUDA 13.0)
- float16 compute type (INT8 broken on Blackwell)
- Sequential GPU: Whisper (~10GB) then pyannote (~1.6GB), never simultaneous

## Project Structure

- `src/smoke_signal/cli.py` — Click CLI entry point
- `src/smoke_signal/config.py` — Config loading (.env + config.yaml)
- `src/smoke_signal/gpu.py` — GPU detection and VRAM checks
- `src/smoke_signal/audio.py` — ffmpeg preprocessing
- `src/smoke_signal/models.py` — Pydantic data models
- `src/smoke_signal/pipeline/local.py` — WhisperX orchestration
- `src/smoke_signal/enrollment/manager.py` — Speaker profile CRUD
- `src/smoke_signal/enrollment/matcher.py` — Cosine similarity matching
- `src/smoke_signal/output/markdown.py` — Markdown + YAML frontmatter output

## Key Decisions

- No API fallback — fully local only
- Speaker profiles stored as JSON in `profiles/` (git-ignored, biometric data)
- pyannote pinned to 3.3.x (4.0.x has 6x VRAM regression)
- Always use float16 compute type (Blackwell INT8 cuBLAS bug)
- Python 3.12 required (WhisperX incompatible with 3.13)
