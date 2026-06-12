Create a new file `tests/test_audio.py` to test the audio preprocessing logic in `src/smoke_signal/audio.py`.

Context: `audio.py` wraps `ffmpeg` and `ffprobe` to validate and preprocess audio files.

Requirements:
- Create NEW file `tests/test_audio.py` only.
- Do NOT modify `src/smoke_signal/audio.py` or any other existing files.
- Test `validate_audio_file`, `get_audio_duration`, and `preprocess_audio`.
- Comprehensively mock `subprocess.run` to simulate `ffprobe` and `ffmpeg` success and failure cases.
- Test `validate_audio_file` with both supported and unsupported extensions, and missing files.
- Run `python -m unittest discover tests`; everything must pass.
- Follow standard Python testing best practices (use `unittest.mock`).
