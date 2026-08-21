import logging
from pathlib import Path

from github_snapshot_backup.backup import BackupRunner
from github_snapshot_backup.config import AppConfig
from github_snapshot_backup.github import Repository


def test_retention_keeps_latest_completed_snapshots(tmp_path: Path) -> None:
    for name in ["2026-08-02", "2026-08-09", "2026-08-16", "2026-08-23", "2026-08-30"]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "BACKUP_COMPLETE").write_text("ok", encoding="utf-8")
    incomplete = tmp_path / ".in-progress-2026-09-06"
    incomplete.mkdir()

    runner = BackupRunner(AppConfig(backup_destination=str(tmp_path), retention=4), logging.getLogger("test"))
    runner._apply_retention(tmp_path)

    assert not (tmp_path / "2026-08-02").exists()
    assert (tmp_path / "2026-08-09").exists()
    assert (tmp_path / "2026-08-30").exists()
    assert incomplete.exists()


def test_select_repositories_defaults_to_all_except_excluded() -> None:
    repos = [
        Repository("One", "Me/One", "https://github.com/Me/One", "main", False, False, False, ""),
        Repository("Two", "Me/Two", "https://github.com/Me/Two", "main", False, False, False, ""),
    ]
    config = AppConfig(excluded_repositories=["Me/Two"])
    runner = BackupRunner(config, logging.getLogger("test"))

    selected = runner._select_repositories(repos)

    assert [repo.name_with_owner for repo in selected] == ["Me/One"]


def test_select_repositories_can_use_explicit_list() -> None:
    repos = [
        Repository("One", "Me/One", "https://github.com/Me/One", "main", False, False, False, ""),
        Repository("Two", "Me/Two", "https://github.com/Me/Two", "main", False, False, False, ""),
    ]
    config = AppConfig(backup_scope="selected", selected_repositories=["Me/Two"])
    runner = BackupRunner(config, logging.getLogger("test"))

    selected = runner._select_repositories(repos)

    assert [repo.name_with_owner for repo in selected] == ["Me/Two"]
