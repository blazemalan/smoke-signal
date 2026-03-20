"""Configuration loading from .env and config.yaml."""

from pathlib import Path

import yaml
from dotenv import load_dotenv
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_PROFILES_DIR = PROJECT_ROOT / "profiles"
DEFAULT_TRANSCRIPTS_DIR = PROJECT_ROOT / "transcripts"


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
