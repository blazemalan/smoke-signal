Create a new file `tests/test_config.py` to test the configuration logic in `src/smoke_signal/config.py`.

Context: `config.py` manages loading the YAML configuration, .env variables, and resolving platform-specific data directories.

Requirements:
- Create NEW file `tests/test_config.py` only.
- Do NOT modify `src/smoke_signal/config.py` or any other existing files.
- Test `get_data_dir`, `load_config`, `get_profile`, `save_config`, and `is_setup_complete`.
- Mock out `platform.system`, `os.environ`, and filesystem operations (like `Path.exists`, `open`, `Path.mkdir`) to ensure isolation.
- Ensure all logic paths in `get_data_dir` (Windows, Darwin, default) are tested.
- Run `python -m unittest discover tests`; everything must pass.
- Follow standard Python testing best practices (use `unittest` or `pytest`).
