from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .archive import create_zip_from_folder, sha256_file, verify_zip
from .config import AppConfig, cache_dir
from .google_drive import apply_retention as apply_drive_retention
from .google_drive import remote_exists, remove_tree, upload_snapshot
from .github import Repository, branch_commit_sha, choose_branch, github_username, has_command, list_repositories
from .github import command_env, command_path


@dataclass(slots=True)
class RepoResult:
    name: str
    name_with_owner: str
    branch: str
    commit: str
    github_pushed_at: str
    private: bool
    archived: bool
    fork: bool
    status: str
    archive: str
    sha256: str = ""
    warning: str = ""
    error: str = ""


class BackupCancelled(RuntimeError):
    pass


class BackupRunner:
    def __init__(
        self,
        config: AppConfig,
        logger: logging.Logger,
        progress_callback=None,
        cancel_callback=None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback or (lambda: False)

    def run(self) -> dict:
        if self.config.destination_mode in {"local", "both"} and not self.config.backup_destination:
            raise RuntimeError("Choose a backup destination before running a backup.")
        destination = self._local_destination()
        destination.mkdir(parents=True, exist_ok=True)
        self._check_tools()

        user = github_username()
        repositories = self._select_repositories(list_repositories(user))
        self.logger.info("backup start user=%s repositories=%s", user, len(repositories))

        date_name = datetime.now().date().isoformat()
        in_progress = destination / f".in-progress-{date_name}"
        final_dir = destination / date_name
        if in_progress.exists():
            shutil.rmtree(in_progress)
        if final_dir.exists():
            suffix = datetime.now().strftime("%H%M%S")
            final_dir = destination / f"{date_name}-{suffix}"
            in_progress = destination / f".in-progress-{date_name}-{suffix}"
        in_progress.mkdir(parents=True)

        results: list[RepoResult] = []
        started = datetime.now().astimezone()
        previous_manifest = self._latest_manifest(destination)
        try:
            for index, repo in enumerate(repositories, start=1):
                if self.cancel_callback():
                    raise BackupCancelled("Backup cancelled before next repository.")
                self._progress(index, len(repositories), repo.name, "Starting")
                result = self._backup_repository(repo, in_progress, previous_manifest)
                results.append(result)
        except BackupCancelled:
            self.logger.warning("backup cancelled")
            raise
        finally:
            if self.cancel_callback() and in_progress.exists():
                (in_progress / "BACKUP_INCOMPLETE").write_text("cancelled\n", encoding="utf-8")

        manifest = self._write_manifest(in_progress, user, repositories, results, started)
        (in_progress / "backup_summary.txt").write_text(format_backup_summary(manifest), encoding="utf-8")
        (in_progress / "BACKUP_COMPLETE").write_text(datetime.now().astimezone().isoformat(), encoding="utf-8")
        in_progress.rename(final_dir)
        latest_path = destination / "latest.json"
        latest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if self.config.destination_mode in {"google_drive", "both"}:
            self._upload_to_google_drive(final_dir, latest_path)
        self.config.last_successful_backup = manifest["created_at"]
        self.config.save()
        self._apply_retention(destination)
        if self.config.destination_mode in {"google_drive", "both"}:
            apply_drive_retention(self.config.google_drive_remote, self.config.google_drive_path, self.config.retention)
        if self.config.destination_mode == "google_drive":
            remove_tree(destination)
        self.logger.info("backup completion success=%s failed=%s", manifest["repositories_successful"], manifest["repositories_failed"])
        return manifest

    def _check_tools(self) -> None:
        missing = [tool for tool in ["git", "gh"] if not has_command(tool)]
        if self.config.destination_mode in {"google_drive", "both"} and not has_command("rclone"):
            missing.append("rclone")
        if missing:
            hints = {"git": "brew install git", "gh": "brew install gh", "rclone": "brew install rclone"}
            raise RuntimeError("Missing required tool(s): " + ", ".join(f"{m} ({hints[m]})" for m in missing))
        if self.config.destination_mode in {"google_drive", "both"} and not remote_exists(self.config.google_drive_remote):
            raise RuntimeError("Google Drive is selected but not connected. Click Connect Google Drive before running a backup.")
        if not has_command("git-lfs"):
            self.logger.warning("git-lfs not found; LFS pointer files may be backed up instead of large assets.")

    def _backup_repository(self, repo: Repository, snapshot_dir: Path, previous_manifest: dict | None) -> RepoResult:
        archive_name = repo.name_with_owner.replace("/", "__") + ".zip"
        archive_path = snapshot_dir / archive_name
        branch = ""
        commit = ""
        try:
            branch = choose_branch(repo)
            commit = branch_commit_sha(repo.name_with_owner, branch)
            reused = self._try_reuse_previous(repo, commit, archive_path, previous_manifest)
            if reused:
                checksum = sha256_file(archive_path)
                self.logger.info("reused previous archive repo=%s branch=%s commit=%s", repo.name_with_owner, branch, commit)
                return self._success(repo, branch, commit, archive_name, checksum, "Reused unchanged previous snapshot")

            self._progress_repo(repo.name, f"Cloning {branch}")
            cache_dir().mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="repo-", dir=cache_dir()) as temp:
                clone_parent = Path(temp)
                clone_path = clone_parent / repo.name
                self._clone(repo.url, branch, clone_path)
                git_dir = clone_path / ".git"
                if git_dir.exists():
                    shutil.rmtree(git_dir)
                self._progress_repo(repo.name, "Creating ZIP")
                create_zip_from_folder(clone_path, archive_path)
            verify_zip(archive_path)
            checksum = sha256_file(archive_path)
            self.logger.info("repo success repo=%s branch=%s commit=%s sha256=%s", repo.name_with_owner, branch, commit, checksum)
            return self._success(repo, branch, commit, archive_name, checksum)
        except Exception as exc:
            self.logger.exception("repo failed repo=%s", repo.name_with_owner)
            return RepoResult(
                name=repo.name,
                name_with_owner=repo.name_with_owner,
                branch=branch,
                commit=commit,
                github_pushed_at=repo.pushed_at,
                private=repo.is_private,
                archived=repo.is_archived,
                fork=repo.is_fork,
                status="failed",
                archive=archive_name,
                error=str(exc),
            )

    def _clone(self, url: str, branch: str, clone_path: Path) -> None:
        args = [
            "git",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--branch",
            branch,
            "--recurse-submodules",
            "--shallow-submodules",
            url,
            str(clone_path),
        ]
        resolved = command_path("git")
        command = [resolved or "git", *args[1:]]
        result = subprocess.run(command, text=True, capture_output=True, check=False, env=command_env())
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git clone failed")

    def _local_destination(self) -> Path:
        if self.config.destination_mode == "google_drive":
            return cache_dir() / "google-drive-staging"
        return Path(self.config.backup_destination).expanduser()

    def _upload_to_google_drive(self, snapshot_dir: Path, latest_json: Path) -> None:
        self._progress_repo("Google Drive", "Uploading snapshot")
        upload_snapshot(snapshot_dir, latest_json, self.config.google_drive_remote, self.config.google_drive_path)
        self.logger.info(
            "google drive upload complete remote=%s path=%s snapshot=%s",
            self.config.google_drive_remote,
            self.config.google_drive_path,
            snapshot_dir.name,
        )

    def _try_reuse_previous(self, repo: Repository, commit: str, archive_path: Path, manifest: dict | None) -> bool:
        if not manifest:
            return False
        for item in manifest.get("repositories", []):
            if item.get("name_with_owner") != repo.name_with_owner or item.get("commit") != commit:
                continue
            previous_archive = Path(manifest.get("_snapshot_dir", "")) / item.get("archive", "")
            if not previous_archive.exists():
                return False
            if sha256_file(previous_archive) != item.get("sha256"):
                return False
            shutil.copy2(previous_archive, archive_path)
            verify_zip(archive_path)
            return True
        return False

    def _latest_manifest(self, destination: Path) -> dict | None:
        latest = destination / "latest.json"
        if not latest.exists():
            return None
        data = json.loads(latest.read_text(encoding="utf-8"))
        snapshot_name = data.get("snapshot_folder")
        if snapshot_name:
            data["_snapshot_dir"] = str(destination / snapshot_name)
        return data

    def _write_manifest(
        self,
        snapshot_dir: Path,
        user: str,
        repositories: list[Repository],
        results: list[RepoResult],
        started: datetime,
    ) -> dict:
        manifest = {
            "backup_version": 1,
            "created_at": started.isoformat(),
            "github_user": user,
            "backup_scope": self.config.backup_scope,
            "destination_mode": self.config.destination_mode,
            "google_drive_remote": self.config.google_drive_remote,
            "google_drive_path": self.config.google_drive_path,
            "selected_repositories": self.config.selected_repositories,
            "excluded_repositories": self.config.excluded_repositories,
            "repositories_found": len(repositories),
            "repositories_successful": sum(1 for r in results if r.status == "success"),
            "repositories_failed": sum(1 for r in results if r.status == "failed"),
            "snapshot_folder": snapshot_dir.name.removeprefix(".in-progress-"),
            "repositories": [asdict(result) for result in results],
        }
        (snapshot_dir / "backup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def _apply_retention(self, destination: Path) -> None:
        keep = max(1, int(self.config.retention))
        complete = []
        for child in destination.iterdir():
            if child.is_dir() and (child / "BACKUP_COMPLETE").exists():
                complete.append(child)
        complete.sort(key=lambda path: path.name)
        for old in complete[:-keep]:
            self.logger.info("retention removing=%s", old)
            shutil.rmtree(old)

    def _select_repositories(self, repositories: list[Repository]) -> list[Repository]:
        excluded = {name.strip() for name in self.config.excluded_repositories if name.strip()}
        filtered = [repo for repo in repositories if repo.name_with_owner not in excluded]
        if self.config.backup_scope != "selected":
            return filtered
        selected = {name.strip() for name in self.config.selected_repositories if name.strip()}
        return [repo for repo in filtered if repo.name_with_owner in selected]

    def _success(self, repo: Repository, branch: str, commit: str, archive: str, checksum: str, warning: str = "") -> RepoResult:
        return RepoResult(
            name=repo.name,
            name_with_owner=repo.name_with_owner,
            branch=branch,
            commit=commit,
            github_pushed_at=repo.pushed_at,
            private=repo.is_private,
            archived=repo.is_archived,
            fork=repo.is_fork,
            status="success",
            archive=archive,
            sha256=checksum,
            warning=warning,
        )

    def _progress(self, index: int, total: int, repo: str, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(index, total, repo, message)

    def _progress_repo(self, repo: str, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(None, None, repo, message)


def next_due_description(config: AppConfig) -> str:
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return f"{weekdays[config.weekday]} at {config.hour:02d}:{config.minute:02d}"


def latest_scheduled_time(config: AppConfig, now: datetime | None = None) -> datetime:
    current = now or datetime.now().astimezone()
    scheduled = current.replace(hour=config.hour, minute=config.minute, second=0, microsecond=0)
    days_since = (current.weekday() - config.weekday) % 7
    scheduled = scheduled - timedelta(days=days_since)
    if scheduled > current:
        scheduled = scheduled - timedelta(days=7)
    return scheduled


def is_backup_overdue(config: AppConfig, now: datetime | None = None) -> bool:
    if not config.automatic_backup or not config.last_successful_backup:
        return False
    try:
        last_success = datetime.fromisoformat(config.last_successful_backup)
    except ValueError:
        return True
    current = now or datetime.now().astimezone()
    if last_success.tzinfo is None and current.tzinfo is not None:
        last_success = last_success.replace(tzinfo=current.tzinfo)
    return last_success < latest_scheduled_time(config, current)


def format_backup_summary(manifest: dict) -> str:
    lines = [
        "GithubSnapshot Backup Summary",
        "",
        f"Created: {manifest.get('created_at', '')}",
        f"GitHub user: {manifest.get('github_user', '')}",
        f"Repositories found: {manifest.get('repositories_found', 0)}",
        f"Successful: {manifest.get('repositories_successful', 0)}",
        f"Failed: {manifest.get('repositories_failed', 0)}",
        "",
    ]
    failures = [repo for repo in manifest.get("repositories", []) if repo.get("status") == "failed"]
    if failures:
        lines.append("Failed repositories:")
        for repo in failures:
            name = repo.get("name_with_owner") or repo.get("name") or "Unknown repository"
            error = repo.get("error") or "No error recorded"
            lines.append(f"- {name}: {error}")
        lines.append("")
    warnings = [repo for repo in manifest.get("repositories", []) if repo.get("warning")]
    if warnings:
        lines.append("Warnings:")
        for repo in warnings:
            name = repo.get("name_with_owner") or repo.get("name") or "Unknown repository"
            lines.append(f"- {name}: {repo.get('warning')}")
        lines.append("")
    lines.append("See backup_manifest.json for full machine-readable details.")
    return "\n".join(lines) + "\n"
