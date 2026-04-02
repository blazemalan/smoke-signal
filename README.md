# Smoke Signal

Local-first audio transcription with speaker diarization. Records go in, labeled transcripts come out — no cloud APIs, everything runs on your GPU.

Smoke Signal uses [WhisperX](https://github.com/m-bain/whisperX) for transcription and [pyannote.audio](https://github.com/pyannote/pyannote-audio) for speaker diarization. It can identify **who** is speaking by matching against enrolled voice profiles.

## Features

- **Transcribe audio** with automatic speaker diarization (who said what)
- **Speaker enrollment** — enroll voices from sample audio, then auto-identify them in future recordings
- **File watcher** — auto-transcribe new recordings as they appear in a folder (e.g., synced from your phone)
- **System tray app** — runs in the background on Windows with notifications
- **Configurable profiles** — presets for model size, language, speaker count
- **Markdown output** with YAML frontmatter

## Requirements

### Hardware

- **NVIDIA GPU** with 10+ GB VRAM (tested on RTX 5070 Ti)
- CPU-only mode works but is very slow

### Software

- **Python 3.12** (3.13 is not supported by WhisperX)
- **Conda** (recommended for environment management)
- **ffmpeg** (for audio preprocessing)
- **Git**

### Accounts

- **HuggingFace account** with an access token (free) — required for speaker diarization models
  - Create a token at: https://huggingface.co/settings/tokens
  - Accept the terms for these models (click each link and agree):
    - https://huggingface.co/pyannote/speaker-diarization-3.1
    - https://huggingface.co/pyannote/segmentation-3.0

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/smoke-signal.git
cd smoke-signal
```

### 2. Create a conda environment

```bash
conda create -n smoke-signal python=3.12 -y
conda activate smoke-signal
```

### 3. Install PyTorch with CUDA

Visit https://pytorch.org/get-started/locally/ and select your CUDA version. Example for CUDA 12.8:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```

### 4. Install Smoke Signal

```bash
# Core transcription only
pip install -e .

# With file watcher and system tray (recommended)
pip install -e ".[watch]"
```

### 5. Set up configuration

```bash
# Copy the example configs
cp .env.example .env
cp config.yaml.example config.yaml
```

Edit `.env` and add your HuggingFace token:

```
HF_TOKEN=hf_your_token_here
```

Edit `config.yaml` to set your preferences. At minimum, if you want to use the file watcher, set `watch_dir` to the folder where your recordings appear:

```yaml
watcher:
  watch_dir: "C:\\Users\\you\\path\\to\\recordings"
```

### 6. Verify the installation

```bash
smoke-signal verify
```

This checks your GPU, Python version, dependencies, and HuggingFace token.

## Usage

### Transcribe a file

```bash
smoke-signal transcribe recording.m4a
```

With options:

```bash
smoke-signal transcribe meeting.m4a --model large-v3 --speakers 4 --identify
smoke-signal transcribe lecture.m4a --profile small-group
```

### Enroll a speaker

Provide 30-60 seconds of solo speech for best results:

```bash
smoke-signal enroll "Alice" alice-solo.m4a
```

Once enrolled, use `--identify` during transcription to label speakers by name.

### Manage speaker profiles

```bash
smoke-signal profiles list
smoke-signal profiles delete "Alice"
```

### Run the file watcher

The watcher monitors a folder for new audio files and transcribes them automatically:

```bash
# With system tray icon
smoke-signal watch

# Headless (no tray icon)
smoke-signal watch --no-tray

# Windowless on Windows (no console window, just tray icon)
smoke-signal-tray
```

### Check watcher status

```bash
smoke-signal status
```

### Manually classify a held recording

If the watcher can't auto-classify a file, it holds it for you:

```bash
smoke-signal classify recording.m4a "weekly team standup"
```

## Configuration

### config.yaml

| Section | What it controls |
|---------|-----------------|
| `defaults` | Model, language, compute type, batch size |
| `profiles` | Named presets (e.g., "work" = 4 speakers + identification) |
| `watcher` | Watch directory, file classification categories, notification settings |

See `config.yaml.example` for all options with comments.

### .env

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | HuggingFace access token (required for speaker diarization) |

## Troubleshooting

### "CUDA not available" or "No CUDA GPU detected"

- Make sure you installed PyTorch with CUDA support (step 3)
- Check that your NVIDIA drivers are up to date
- Run `python -c "import torch; print(torch.cuda.is_available())"` to test

### "HF_TOKEN not set"

- Make sure `.env` exists in the project root with `HF_TOKEN=hf_...`
- Or set it as an environment variable: `export HF_TOKEN=hf_...`

### "Access to model is restricted" / 403 error from HuggingFace

You need to accept the model terms on HuggingFace. Visit both of these links while logged in and click "Agree":
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

### "VRAM insufficient" or out-of-memory errors

Try a smaller model:

```bash
smoke-signal transcribe recording.m4a --model small
```

Or reduce batch size:

```bash
smoke-signal transcribe recording.m4a --batch-size 4
```

### Watch directory not found

Make sure `watch_dir` in `config.yaml` points to an existing folder on your machine.

## macOS

Smoke Signal is developed and tested on Windows with an NVIDIA GPU. On Mac:

- **Apple Silicon (M1/M2/M3/M4):** WhisperX can use MPS acceleration. Set `compute_type: float32` in config.yaml (float16 is not supported on MPS). Performance will be slower than NVIDIA CUDA but much faster than CPU.
- **Intel Mac:** CPU-only, will be slow.
- **Notifications:** The `winotify` package is Windows-only. Install without the watch extras and use `--no-tray` mode, or install `pystray` and `Pillow` manually (the tray icon works cross-platform, just not Windows toast notifications).

Mac support is not fully tested — contributions welcome.

## License

[MIT](LICENSE)
