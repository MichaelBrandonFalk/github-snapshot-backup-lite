from __future__ import annotations

import plistlib
import subprocess
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .config import AppConfig, BUNDLE_ID, app_support_dir, launch_agent_path, logs_dir

TASK_NAME = "GithubSnapshot Weekly Backup"
UNIT_NAME = "github-snapshot-backup"


def backup_command(executable: str | None = None) -> list[str]:
    if executable:
        return [executable, "--headless-backup"]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--headless-backup"]
    return [sys.executable, "-m", "github_snapshot_backup.app", "--headless-backup"]


def _checked(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("Unable to save weekly schedule: " + (result.stderr.strip() or result.stdout.strip()))


def systemd_directory() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd" / "user"


def systemd_exec(args: list[str]) -> str:
    # systemd command lines have their own quoting and specifier expansion.
    return " ".join('"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"' for arg in args)


def windows_task_xml(config: AppConfig, command: list[str], user: str) -> str:
    namespace = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    ET.register_namespace("", namespace)
    def child(parent, name, text=None, **attrs):
        node = ET.SubElement(parent, f"{{{namespace}}}{name}", attrs)
        node.text = text
        return node
    task = ET.Element(f"{{{namespace}}}Task", {"version": "1.2"})
    trigger = child(child(task, "Triggers"), "CalendarTrigger")
    boundary = datetime.now().replace(hour=config.hour, minute=config.minute, second=0, microsecond=0)
    child(trigger, "StartBoundary", boundary.isoformat())
    child(trigger, "Enabled", "true")
    weekly = child(trigger, "ScheduleByWeek")
    child(weekly, "WeeksInterval", "1")
    child(child(weekly, "DaysOfWeek"), ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][config.weekday])
    principal = child(child(task, "Principals"), "Principal", id="Author")
    child(principal, "UserId", user)
    child(principal, "LogonType", "InteractiveToken")
    child(principal, "RunLevel", "LeastPrivilege")
    settings = child(task, "Settings")
    child(settings, "MultipleInstancesPolicy", "IgnoreNew")
    child(settings, "DisallowStartIfOnBatteries", "false")
    child(settings, "StopIfGoingOnBatteries", "false")
    child(settings, "StartWhenAvailable", "true")
    child(settings, "ExecutionTimeLimit", "PT0S")
    action = child(child(task, "Actions", Context="Author"), "Exec")
    child(action, "Command", command[0])
    child(action, "Arguments", subprocess.list2cmdline(command[1:]))
    return ET.tostring(task, encoding="unicode")


def install_schedule(config: AppConfig, executable: str | None = None) -> Path:
    command = backup_command(executable)
    logs_dir().mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        return install_launch_agent(config, command=command)
    if sys.platform == "win32":
        user = subprocess.run(["whoami"], capture_output=True, text=True, check=True).stdout.strip()
        path = app_support_dir() / "weekly-task.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(windows_task_xml(config, command, user), encoding="utf-16")
        _checked(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(path), "/F"])
        return path
    directory = systemd_directory()
    directory.mkdir(parents=True, exist_ok=True)
    service = directory / f"{UNIT_NAME}.service"
    service.write_text("[Unit]\nDescription=GitHub snapshot backup\n\n[Service]\nType=oneshot\nExecStart=" + systemd_exec(command) + "\n", encoding="utf-8")
    timer = directory / f"{UNIT_NAME}.timer"
    day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][config.weekday]
    timer.write_text(f"[Unit]\nDescription=Weekly GitHub snapshot backup\n\n[Timer]\nOnCalendar={day} *-*-* {config.hour:02d}:{config.minute:02d}:00\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n", encoding="utf-8")
    _checked(["systemctl", "--user", "daemon-reload"])
    _checked(["systemctl", "--user", "enable", "--now", f"{UNIT_NAME}.timer"])
    _checked(["systemctl", "--user", "restart", f"{UNIT_NAME}.timer"])
    return timer


def uninstall_schedule() -> None:
    if sys.platform == "darwin":
        uninstall_launch_agent()
    elif sys.platform == "win32":
        result = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
        if result.returncode == 0:
            _checked(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    else:
        directory = systemd_directory()
        timer = directory / f"{UNIT_NAME}.timer"
        if timer.exists():
            _checked(["systemctl", "--user", "disable", "--now", timer.name])
            timer.unlink()
            (directory / f"{UNIT_NAME}.service").unlink(missing_ok=True)
            _checked(["systemctl", "--user", "daemon-reload"])


def executable_for_launchd() -> str:
    bundle_executable = Path("/Applications/GithubSnapshot_V1.5.app/Contents/MacOS/GithubSnapshot_V1.5.2")
    if bundle_executable.exists():
        return str(bundle_executable)
    return "github-snapshot-backup"


def install_launch_agent(config: AppConfig, executable: str | None = None, command: list[str] | None = None) -> Path:
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    program = executable or executable_for_launchd()
    plist = {
        "Label": BUNDLE_ID,
        "ProgramArguments": command or [program, "--headless-backup"],
        "StartCalendarInterval": {
            "Weekday": config.weekday + 1 if config.weekday < 6 else 0,
            "Hour": config.hour,
            "Minute": config.minute,
        },
        "StandardOutPath": str(logs_dir() / "launchd.out.log"),
        "StandardErrorPath": str(logs_dir() / "launchd.err.log"),
    }
    with path.open("wb") as handle:
        plistlib.dump(plist, handle)
    subprocess.run(["launchctl", "unload", str(path)], capture_output=True, text=True, check=False)
    _checked(["launchctl", "load", str(path)])
    return path


def uninstall_launch_agent() -> None:
    path = launch_agent_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True, text=True, check=False)
        path.unlink()
