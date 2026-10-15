import os
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET
import sys
import subprocess
import pytest
import uuid

from github_snapshot_backup import config, github, platform_support, scheduler


def test_linux_xdg_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, "platform", "linux")
    for key in ["XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]:
        monkeypatch.setenv(key, str(tmp_path / key))
    assert config.app_support_dir() == tmp_path / "XDG_CONFIG_HOME" / "github-snapshot-backup"
    assert config.cache_dir() == tmp_path / "XDG_CACHE_HOME" / "github-snapshot-backup"
    assert config.logs_dir() == tmp_path / "XDG_STATE_HOME" / "github-snapshot-backup" / "logs"


def test_windows_user_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert config.app_support_dir() == tmp_path / "roaming" / config.APP_NAME
    assert config.cache_dir() == tmp_path / "local" / config.APP_NAME / "Cache"
    assert config.logs_dir() == tmp_path / "local" / config.APP_NAME / "Logs"


def test_windows_executable_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(github.sys, "platform", "win32")
    monkeypatch.setattr(github.shutil, "which", lambda command: None)
    monkeypatch.setattr(github, "COMMAND_PATHS", [str(tmp_path)])
    tool = tmp_path / "gh.exe"
    tool.touch()
    tool.chmod(0o755)
    assert github.command_path("gh") == str(tool)


def test_command_environment_uses_native_separator(monkeypatch):
    monkeypatch.setattr(github, "COMMAND_PATHS", ["first", "second"])
    monkeypatch.setenv("PATH", "existing")
    assert github.command_env()["PATH"] == os.pathsep.join(["first", "second", "existing"])


def test_windows_task_preserves_paths_and_catches_up():
    command = [r"C:\My Apps\GithubSnapshot_V1.5.exe", "--headless-backup"]
    xml = scheduler.windows_task_xml(config.AppConfig(), command, r"PC\User & Name")
    task = ET.fromstring(xml)
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert task.find("t:Actions/t:Exec/t:Command", ns).text == command[0]
    assert task.find("t:Principals/t:Principal/t:UserId", ns).text == r"PC\User & Name"
    assert task.find("t:Settings/t:StartWhenAvailable", ns).text == "true"
    assert task.find("t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek/t:Wednesday", ns) is not None
    assert "T10:00:00" in task.find("t:Triggers/t:CalendarTrigger/t:StartBoundary", ns).text


def test_linux_schedule_install_and_remove(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler.sys, "platform", "linux")
    monkeypatch.setattr(scheduler, "systemd_directory", lambda: tmp_path)
    monkeypatch.setattr(scheduler, "logs_dir", lambda: tmp_path / "logs")
    commands = []
    monkeypatch.setattr(scheduler, "_checked", commands.append)
    executable = '/opt/Some App/100%/$app'
    path = scheduler.install_schedule(config.AppConfig(), executable)
    assert "OnCalendar=Wed *-*-* 10:00:00" in path.read_text()
    assert "Persistent=true" in path.read_text()
    assert 'ExecStart="/opt/Some App/100%%/$$app" "--headless-backup"' in (tmp_path / "github-snapshot-backup.service").read_text()
    assert ["systemctl", "--user", "enable", "--now", "github-snapshot-backup.timer"] in commands
    scheduler.uninstall_schedule()
    assert not path.exists()
    assert not (tmp_path / "github-snapshot-backup.service").exists()


def test_source_schedule_uses_module(monkeypatch):
    monkeypatch.delattr(scheduler.sys, "frozen", raising=False)
    assert scheduler.backup_command()[1:] == ["-m", "github_snapshot_backup.app", "--headless-backup"]


def test_linux_installer_uses_apt(monkeypatch):
    monkeypatch.setattr(platform_support.sys, "platform", "linux")
    assert platform_support.install_tools_command() == "sudo apt-get update && sudo apt-get install -y git gh git-lfs rclone"


def test_windows_installer_uses_winget(monkeypatch):
    monkeypatch.setattr(platform_support.sys, "platform", "win32")
    command = platform_support.install_tools_command()
    assert "Git.Git" in command and "GitHub.cli" in command and "Rclone.Rclone" in command
    assert "brew" not in command


def test_schedule_failure_is_reported(monkeypatch):
    import pytest
    monkeypatch.setattr(scheduler.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="Access denied", stdout=""))
    with pytest.raises(RuntimeError, match="Access denied"):
        scheduler._checked(["schtasks"])


@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows PowerShell")
def test_native_windows_command_with_spaces(tmp_path):
    script = tmp_path / "path with spaces.py"
    script.write_text("import sys; print(sys.argv[1])", encoding="utf-8")
    command = platform_support.shell_command([sys.executable, str(script), "value with spaces & apostrophe's"])
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "value with spaces & apostrophe's"


@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows Task Scheduler")
def test_native_windows_schedule_roundtrip(monkeypatch, tmp_path):
    from datetime import datetime
    monkeypatch.setattr(scheduler, "TASK_NAME", "GithubSnapshot CI " + uuid.uuid4().hex)
    monkeypatch.setattr(scheduler, "app_support_dir", lambda: tmp_path)
    monkeypatch.setattr(scheduler, "logs_dir", lambda: tmp_path / "logs")
    tomorrow = (datetime.now().weekday() + 1) % 7
    try:
        scheduler.install_schedule(config.AppConfig(weekday=tomorrow))
        result = subprocess.run(["schtasks", "/Query", "/TN", scheduler.TASK_NAME, "/XML"], capture_output=True, text=True, check=True)
        assert "--headless-backup" in result.stdout
        assert "StartWhenAvailable" in result.stdout
    finally:
        scheduler.uninstall_schedule()
