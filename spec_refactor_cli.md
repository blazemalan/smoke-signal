Refactor the large `src/smoke_signal/cli.py` file to extract command business logic into a new `src/smoke_signal/commands` directory.

Context: `cli.py` is nearly 400 lines long and handles both Click routing and complex business logic for transcription, classifying, and watching. We want `cli.py` to act purely as the CLI router.

Requirements:
- Create a new directory: `src/smoke_signal/commands/` with an `__init__.py`.
- Extract the core logic of the `transcribe` command into `src/smoke_signal/commands/transcribe.py`.
- Extract the core logic of the `watch`, `classify_file`, and `status` commands into `src/smoke_signal/commands/watcher.py` (or similar).
- Extract the core logic of `enroll`, `profiles_list`, and `profiles_delete` into `src/smoke_signal/commands/profiles.py`.
- `cli.py` should import these newly created functions and call them, passing along the CLI arguments.
- Do NOT alter the CLI interface, argument names, or output text. The user experience must remain identical.
- Ensure all imports (like `from smoke_signal.gpu import check_gpu`) are moved or imported correctly to prevent circular dependencies or breakage.
- Run `python -m py_compile src/smoke_signal/cli.py` or equivalent syntax checks to ensure nothing is obviously broken.
