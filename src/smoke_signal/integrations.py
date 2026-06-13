"""Integration module for external commands."""

import logging
import os
import shlex
import subprocess
import sys

logger = logging.getLogger(__name__)

def get_summarize_command(config: dict) -> str | None:
    """Get the summarize command from config."""
    try:
        cmd = config.get("integrations", {}).get("summarize_command")
        if isinstance(cmd, str) and cmd.strip():
            return cmd.strip()
    except Exception:
        pass
    return None

def build_summarize_argv(template: str, transcript_path=None) -> list[str]:
    """Build the argument vector by substituting {file}."""
    if transcript_path is None:
        template = template.replace("{file}", "")
    else:
        template = template.replace("{file}", str(transcript_path))

    argv = shlex.split(template, posix=(os.name != "nt"))

    if transcript_path is None:
        return [token for token in argv if token != ""]
    return argv

def launch_summarize(template: str, transcript_path=None) -> bool:
    """Launch the summarize command in a detached terminal window."""
    try:
        argv = build_summarize_argv(template, transcript_path)

        if sys.platform == "win32":
            # CREATE_NEW_CONSOLE opens the visible terminal directly and
            # explicitly opts out of the tray app's CREATE_NO_WINDOW default.
            cmd = ["cmd.exe", "/k"] + argv
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True
        elif sys.platform == "darwin":
            script = 'on run argv\n  tell app "Terminal" to do script (item 1 of argv)\nend run'
            cmd_str = shlex.join(argv)
            cmd = ["osascript", "-e", script, cmd_str]
        else:
            cmd = ["x-terminal-emulator", "-e"] + argv

        subprocess.Popen(cmd)
        return True
    except Exception as e:
        logger.warning(f"Could not launch summarize command: {e}")
        return False
