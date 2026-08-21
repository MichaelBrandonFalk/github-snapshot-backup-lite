import logging
from pathlib import Path

from github_snapshot_backup.backup import BackupRunner
from github_snapshot_backup.config import AppConfig


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

