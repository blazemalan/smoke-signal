"""Configuration loading from .env and config.yaml."""

import platform
import shutil
import sys
from importlib import resources
from pathlib import Path

import yaml
from dotenv import load_dotenv
import os


def get_data_dir() -> Path:
    """Return the app data directory, creating it if needed.

    Resolution order:
    1. SMOKE_SIGNAL_DATA_DIR env var (for dev/custom setups)
    2. Platform-specific user data dir:
       - Windows: %LOCALAPPDATA%/SmokeSignal
       - macOS:   ~/Library/Application Support/SmokeSignal
       - Linux:   ~/.local/share/smoke-signal
    """
    override = os.environ.get("SMOKE_SIGNAL_DATA_DIR")
    if override:
        return Path(override)

    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "SmokeSignal"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "SmokeSignal"
    else:
        return Path.home() / ".local" / "share" / "smoke-signal"


def _ensure_data_dir(data_dir: Path) -> None:
    """Create the data directory and seed default config if missing."""
    data_dir.mkdir(parents=True, exist_ok=True)

    config_path = data_dir / "config.yaml"
    if not config_path.exists():
        # Copy bundled config.yaml.example as the starting config
        example = resources.files("smoke_signal") / "config.yaml.example"
        if example.is_file():
            shutil.copy2(str(example), str(config_path))
        else:
            # Fallback: write minimal default
            config_path.write_text(
                "defaults:\n  model: large-v3-turbo\n  language: en\n  compute_type: float16\n",
                encoding="utf-8",
            )


DATA_DIR = get_data_dir()
_ensure_data_dir(DATA_DIR)

DEFAULT_CONFIG_PATH = DATA_DIR / "config.yaml"
DEFAULT_ENV_PATH = DATA_DIR / ".env"
DEFAULT_PROFILES_DIR = DATA_DIR / "profiles"
DEFAULT_TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
DEFAULT_DATA_DIR = DATA_DIR / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "watcher.db"
DEFAULT_LOGS_DIR = DATA_DIR / "logs"


def load_env(env_path: Path | None = None) -> None:
    path = env_path or DEFAULT_ENV_PATH
    load_dotenv(path)


def get_hf_token() -> str:
    token = os.getenv("HF_TOKEN", "")
    if not token:
        raise ValueError(
            "HF_TOKEN not set. Add it to .env or set the HF_TOKEN environment variable.\n"
            "Get a token at: https://huggingface.co/settings/tokens"
        )
    return token


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {"defaults": {}, "profiles": {}}
    with open(path) as f:
        return yaml.safe_load(f) or {"defaults": {}, "profiles": {}}


def get_profile(config: dict, profile_name: str) -> dict:
    defaults = config.get("defaults", {})
    profile = config.get("profiles", {}).get(profile_name, {})
    merged = {**defaults, **profile}
    return merged


def get_watcher_config(config: dict) -> dict:
    return config.get("watcher", {})
