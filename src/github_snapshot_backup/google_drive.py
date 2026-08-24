from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .github import command_env, command_path, has_command

DEFAULT_REMOTE = "GithubSnapshotDrive"
DEFAULT_REMOTE_PATH = "GithubSnapshot Backups"


def rclone_available() -> bool:
    return has_command("rclone")


def remote_root(remote: str, remote_path: str) -> str:
    clean_path = remote_path.strip().strip("/")
    return f"{remote}:{clean_path}" if clean_path else f"{remote}:"


def remote_exists(remote: str) -> bool:
    if not rclone_available():
        return False
    result = _run(["rclone", "listremotes"])
    if result.returncode != 0:
        return False
    return f"{remote}:" in {line.strip() for line in result.stdout.splitlines()}


def configure_remote_command(remote: str) -> str:
    rclone = command_path("rclone") or "rclone"
    return f'{rclone} config create "{remote}" drive scope drive.file config_is_local true'


def upload_snapshot(snapshot_dir: Path, latest_json: Path, remote: str, remote_path: str) -> None:
    if not rclone_available():
        raise RuntimeError("Google Drive upload needs rclone. Use Install GitHub Tools to install it.")
    if not remote_exists(remote):
        raise RuntimeError("Connect Google Drive before choosing a Google Drive backup mode.")
    target = f"{remote_root(remote, remote_path)}/{snapshot_dir.name}"
    _check(["rclone", "copy", str(snapshot_dir), target, "--create-empty-src-dirs"])
    _check(["rclone", "copyto", str(latest_json), f"{remote_root(remote, remote_path)}/latest.json"])


def apply_retention(remote: str, remote_path: str, keep: int) -> None:
    if not rclone_available() or not remote_exists(remote):
        return
    result = _run(["rclone", "lsf", remote_root(remote, remote_path), "--dirs-only"])
    if result.returncode != 0:
        return
    folders = sorted(line.strip().strip("/") for line in result.stdout.splitlines() if line.strip())
    for folder in folders[:-max(1, keep)]:
        _run(["rclone", "purge", f"{remote_root(remote, remote_path)}/{folder}"])


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    resolved = command_path(args[0])
    command = [resolved or args[0], *args[1:]]
    return subprocess.run(command, text=True, capture_output=True, check=False, env=command_env())


def _check(args: list[str]) -> None:
    result = _run(args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"{args[0]} failed")

