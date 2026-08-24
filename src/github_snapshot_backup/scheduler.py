from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from .config import AppConfig, BUNDLE_ID, launch_agent_path


def executable_for_launchd() -> str:
    bundle_executable = Path("/Applications/GithubSnapshot_V1.3.app/Contents/MacOS/GithubSnapshot_V1.3")
    if bundle_executable.exists():
        return str(bundle_executable)
    return "github-snapshot-backup"


def install_launch_agent(config: AppConfig, executable: str | None = None) -> Path:
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    program = executable or executable_for_launchd()
    plist = {
        "Label": BUNDLE_ID,
        "ProgramArguments": [program, "--headless-backup"],
        "StartCalendarInterval": {
            "Weekday": config.weekday + 1 if config.weekday < 6 else 0,
            "Hour": config.hour,
            "Minute": config.minute,
        },
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "GitHub Snapshot Backup" / "launchd.out.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "GitHub Snapshot Backup" / "launchd.err.log"),
    }
    with path.open("wb") as handle:
        plistlib.dump(plist, handle)
    subprocess.run(["launchctl", "unload", str(path)], capture_output=True, text=True, check=False)
    subprocess.run(["launchctl", "load", str(path)], capture_output=True, text=True, check=False)
    return path


def uninstall_launch_agent() -> None:
    path = launch_agent_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True, text=True, check=False)
        path.unlink()
