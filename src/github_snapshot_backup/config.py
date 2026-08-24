from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

APP_NAME = "GitHub Snapshot Backup"
BUNDLE_ID = "com.githubsnapshotbackup.weekly"


def app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def cache_dir() -> Path:
    return Path.home() / "Library" / "Caches" / APP_NAME


def logs_dir() -> Path:
    return Path.home() / "Library" / "Logs" / APP_NAME


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.plist"


@dataclass(slots=True)
class AppConfig:
    backup_destination: str = ""
    automatic_backup: bool = True
    weekday: int = 6
    hour: int = 2
    minute: int = 0
    retention: int = 4
    destination_mode: str = "local"
    google_drive_folder_id: str = ""
    auto_run_missed_backup: bool = True
    backup_scope: str = "all"
    selected_repositories: list[str] = field(default_factory=list)
    excluded_repositories: list[str] = field(default_factory=list)
    last_successful_backup: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        config_path = path or app_support_dir() / "config.json"
        if not config_path.exists():
            return cls()
        data = json.loads(config_path.read_text(encoding="utf-8"))
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def save(self, path: Path | None = None) -> None:
        config_path = path or app_support_dir() / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
