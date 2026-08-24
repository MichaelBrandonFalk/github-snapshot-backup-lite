from github_snapshot_backup.google_drive import remote_root


def test_remote_root_with_path() -> None:
    assert remote_root("GithubSnapshotDrive", "GithubSnapshot Backups") == "GithubSnapshotDrive:GithubSnapshot Backups"


def test_remote_root_without_path() -> None:
    assert remote_root("GithubSnapshotDrive", "") == "GithubSnapshotDrive:"

