from github_snapshot_backup.config import AppConfig
from github_snapshot_backup.backup import next_due_description


def test_next_due_description() -> None:
    config = AppConfig(weekday=6, hour=2, minute=0)
    assert next_due_description(config) == "Sunday at 02:00"

