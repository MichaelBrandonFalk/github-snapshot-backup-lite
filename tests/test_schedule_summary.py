from datetime import datetime
from zoneinfo import ZoneInfo

from github_snapshot_backup.backup import format_backup_summary, is_backup_overdue, latest_scheduled_time
from github_snapshot_backup.config import AppConfig


def test_default_schedule_is_wednesday_10_am() -> None:
    config = AppConfig()

    assert config.weekday == 2
    assert config.hour == 10
    assert config.minute == 0


def test_latest_scheduled_time_uses_current_week_when_time_passed() -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=ZoneInfo("America/Phoenix"))
    config = AppConfig(weekday=0, hour=2, minute=0)

    assert latest_scheduled_time(config, now) == datetime(2026, 8, 24, 2, 0, tzinfo=ZoneInfo("America/Phoenix"))


def test_backup_overdue_when_last_success_precedes_latest_schedule() -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=ZoneInfo("America/Phoenix"))
    config = AppConfig(
        automatic_backup=True,
        weekday=0,
        hour=2,
        minute=0,
        last_successful_backup="2026-08-17T02:30:00-07:00",
    )

    assert is_backup_overdue(config, now) is True


def test_backup_summary_lists_failed_repositories() -> None:
    summary = format_backup_summary(
        {
            "created_at": "2026-08-24T02:00:00-07:00",
            "github_user": "Me",
            "repositories_found": 2,
            "repositories_successful": 1,
            "repositories_failed": 1,
            "repositories": [
                {"name_with_owner": "Me/Good", "status": "success"},
                {"name_with_owner": "Me/Bad", "status": "failed", "error": "Authentication failed"},
            ],
        }
    )

    assert "Failed repositories:" in summary
    assert "- Me/Bad: Authentication failed" in summary
