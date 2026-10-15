from __future__ import annotations

import shlex
import subprocess
import sys
import os
import stat

from .github import command_env, command_path, has_command


def remove_readonly_file(function, path, exc_info) -> None:
    if not isinstance(exc_info[1], PermissionError):
        raise exc_info[1]
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    function(path)


def shell_command(args: list[str]) -> str:
    if sys.platform == "win32":
        return "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in args)
    return shlex.join(args)


def package_manager() -> str:
    return "winget" if sys.platform == "win32" else "brew" if sys.platform == "darwin" else "apt-get"


def install_tools_command() -> str:
    if sys.platform == "win32":
        return "; ".join(
            f"winget install --exact --id {package} --accept-package-agreements --accept-source-agreements"
            for package in ["Git.Git", "GitHub.cli", "Rclone.Rclone"]
        )
    if sys.platform == "darwin":
        return shell_command([command_path("brew") or "brew", "install", "git", "gh", "git-lfs", "rclone"])
    return "sudo apt-get update && sudo apt-get install -y git gh git-lfs rclone"


def open_terminal(command: str) -> None:
    if sys.platform == "darwin":
        escaped = command.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{escaped}"'])
    elif sys.platform == "win32":
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NoExit", "-Command", command], creationflags=subprocess.CREATE_NEW_CONSOLE, env=command_env())
    else:
        # Mint's default terminal supports -e with an argument vector.
        terminal = next((command_path(name) for name in ["x-terminal-emulator", "gnome-terminal", "xterm"] if has_command(name)), None)
        if not terminal:
            raise RuntimeError("No terminal found. Install xterm, then try again.")
        flag = "--" if terminal.endswith("gnome-terminal") else "-e"
        subprocess.Popen([terminal, flag, "sh", "-c", command + '; printf "\\nPress Enter to close..."; read reply'], env=command_env())
