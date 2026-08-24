from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .backup import BackupRunner, next_due_description
from .config import AppConfig, logs_dir
from .github import command_path, github_username, has_command, list_repositories
from .logging_utils import configure_logging
from .restore_help import RESTORE_HELP
from .scheduler import install_launch_agent, uninstall_launch_agent


class BackupSignals(QObject):
    progress = Signal(object, object, str, str)
    finished = Signal(dict)
    failed = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = AppConfig.load()
        self.logger = configure_logging()
        self.signals = BackupSignals()
        self.cancel_requested = False
        self.preflight_prompted = False
        self.setWindowTitle("GithubSnapshot V1.2")
        self.resize(640, 760)
        self._build_ui()
        self._connect_signals()
        self.refresh_status()
        QTimer.singleShot(500, self.run_preflight_checks)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("GithubSnapshot V1.2")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        grid = QGridLayout()
        self.github_label = QLabel("Checking...")
        self.repo_label = QLabel("Checking...")
        self.destination_label = QLabel(self.config.backup_destination or "No folder selected")
        self.last_backup_label = QLabel(self.config.last_successful_backup or "Never")
        self.schedule_label = QLabel(next_due_description(self.config))

        grid.addWidget(QLabel("GitHub"), 0, 0)
        grid.addWidget(self.github_label, 0, 1)
        grid.addWidget(QLabel("Repositories"), 1, 0)
        grid.addWidget(self.repo_label, 1, 1)
        grid.addWidget(QLabel("Backup Destination"), 2, 0)
        grid.addWidget(self.destination_label, 2, 1)
        grid.addWidget(QLabel("Last Backup"), 3, 0)
        grid.addWidget(self.last_backup_label, 3, 1)
        grid.addWidget(QLabel("Automatic Backup"), 4, 0)
        grid.addWidget(self.schedule_label, 4, 1)
        layout.addLayout(grid)

        repo_row = QHBoxLayout()
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["All discovered repositories", "Only repositories listed below"])
        self.scope_combo.setCurrentIndex(1 if self.config.backup_scope == "selected" else 0)
        self.fill_repos_button = QPushButton("Fill With Found Repositories")
        repo_row.addWidget(QLabel("Repository Mode"))
        repo_row.addWidget(self.scope_combo, 1)
        repo_row.addWidget(self.fill_repos_button)
        layout.addLayout(repo_row)

        self.repo_list_edit = QTextEdit()
        self.repo_list_edit.setPlaceholderText("owner/repository, one per line. Leave mode set to all for set-and-forget backups.")
        self.repo_list_edit.setFixedHeight(110)
        self.repo_list_edit.setPlainText("\n".join(self.config.selected_repositories))
        self.repo_list_edit.setEnabled(self.config.backup_scope == "selected")
        layout.addWidget(self.repo_list_edit)

        buttons = QHBoxLayout()
        self.choose_button = QPushButton("Choose Folder")
        self.destination_mode = QComboBox()
        self.destination_mode.addItems([
            "Local folder",
            "Direct Google Drive (needs OAuth setup)",
            "Local folder + Google Drive (local now)",
        ])
        mode_index = {"local": 0, "google_drive": 1, "both": 2}.get(self.config.destination_mode, 0)
        self.destination_mode.setCurrentIndex(mode_index)
        self.open_folder_button = QPushButton("Open Backup Folder")
        self.log_button = QPushButton("View Log")
        buttons.addWidget(self.choose_button)
        buttons.addWidget(self.destination_mode)
        buttons.addWidget(self.open_folder_button)
        buttons.addWidget(self.log_button)
        layout.addLayout(buttons)

        setup_row = QHBoxLayout()
        self.homebrew_button = QPushButton("Install Homebrew")
        self.install_tools_button = QPushButton("Install GitHub Tools")
        self.sign_in_button = QPushButton("Sign In To GitHub")
        setup_row.addWidget(self.homebrew_button)
        setup_row.addWidget(self.install_tools_button)
        setup_row.addWidget(self.sign_in_button)
        layout.addLayout(setup_row)

        schedule = QHBoxLayout()
        self.auto_check = QCheckBox("Weekly")
        self.auto_check.setChecked(self.config.automatic_backup)
        self.day_combo = QComboBox()
        self.day_combo.addItems(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        self.day_combo.setCurrentIndex(self.config.weekday)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("h:mm AP")
        self.time_edit.setTime(self.time_edit.time().fromString(f"{self.config.hour:02d}:{self.config.minute:02d}", "HH:mm"))
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 52)
        self.retention_spin.setValue(self.config.retention)
        schedule.addWidget(self.auto_check)
        schedule.addWidget(self.day_combo)
        schedule.addWidget(self.time_edit)
        schedule.addWidget(QLabel("Keep"))
        schedule.addWidget(self.retention_spin)
        schedule.addWidget(QLabel("backups"))
        layout.addLayout(schedule)

        self.progress = QProgressBar()
        self.status_text = QLabel("Ready")
        self.status_text.setWordWrap(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_text)

        action_row = QHBoxLayout()
        self.backup_button = QPushButton("BACK UP NOW")
        self.cancel_button = QPushButton("Cancel Backup")
        self.cancel_button.setEnabled(False)
        self.restore_button = QPushButton("Restore Help")
        self.save_button = QPushButton("Save Settings")
        action_row.addWidget(self.backup_button)
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.restore_button)
        layout.addLayout(action_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.choose_button.clicked.connect(self.choose_destination)
        self.backup_button.clicked.connect(self.start_backup)
        self.cancel_button.clicked.connect(self.request_cancel)
        self.open_folder_button.clicked.connect(self.open_backup_folder)
        self.log_button.clicked.connect(self.toggle_log)
        self.restore_button.clicked.connect(self.show_restore_help)
        self.save_button.clicked.connect(self.save_settings)
        self.homebrew_button.clicked.connect(self.open_homebrew)
        self.install_tools_button.clicked.connect(self.install_github_tools)
        self.sign_in_button.clicked.connect(self.sign_in_to_github)
        self.fill_repos_button.clicked.connect(self.fill_found_repositories)
        self.auto_check.stateChanged.connect(self.save_settings)
        self.day_combo.currentIndexChanged.connect(self.save_settings)
        self.time_edit.timeChanged.connect(self.save_settings)
        self.retention_spin.valueChanged.connect(self.save_settings)
        self.scope_combo.currentIndexChanged.connect(self.save_settings)
        self.destination_mode.currentIndexChanged.connect(self.save_settings)
        self.repo_list_edit.textChanged.connect(lambda: self.save_settings(update_scheduler=False))
        self.signals.progress.connect(self.on_progress)
        self.signals.finished.connect(self.on_finished)
        self.signals.failed.connect(self.on_failed)

    def refresh_status(self) -> None:
        try:
            if not has_command("git"):
                self.github_label.setText("Git setup needed. Install GitHub tools.")
            user = github_username()
            repos = list_repositories(user)
            self.github_label.setText(f"Logged in as {user}")
            self.homebrew_button.setVisible(False)
            self.install_tools_button.setVisible(False)
            self.sign_in_button.setVisible(False)
            if self.config.backup_scope == "selected":
                selected = len(self.config.selected_repositories)
                self.repo_label.setText(f"{len(repos)} found; {selected} selected")
            else:
                self.repo_label.setText(f"{len(repos)} found; backing up all")
        except Exception as exc:
            self.github_label.setText(str(exc))
            self.repo_label.setText("Unavailable")
            self._update_setup_buttons()

    def choose_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Backup Destination", self.config.backup_destination or str(Path.home()))
        if folder:
            self.config.backup_destination = folder
            self.destination_label.setText(folder)
            self.save_settings()

    def save_settings(self, update_scheduler: bool = True) -> None:
        self.config.automatic_backup = self.auto_check.isChecked()
        self.config.weekday = self.day_combo.currentIndex()
        time = self.time_edit.time()
        self.config.hour = time.hour()
        self.config.minute = time.minute()
        self.config.retention = self.retention_spin.value()
        self.config.destination_mode = ["local", "google_drive", "both"][self.destination_mode.currentIndex()]
        self.config.backup_scope = "selected" if self.scope_combo.currentIndex() == 1 else "all"
        self.config.selected_repositories = self._repo_lines()
        self.config.save()
        self.repo_list_edit.setEnabled(self.config.backup_scope == "selected")
        self.schedule_label.setText(next_due_description(self.config))
        if not update_scheduler:
            return
        if self.config.automatic_backup:
            install_launch_agent(self.config, sys.executable)
        else:
            uninstall_launch_agent()
        self.refresh_status()

    def install_github_tools(self) -> None:
        if not has_command("brew"):
            QMessageBox.warning(self, "Install GitHub Tools", "Install Homebrew first, then use this button again.")
            return
        self._open_terminal_command(f"{command_path('brew') or 'brew'} install git gh git-lfs")

    def open_homebrew(self) -> None:
        subprocess.run(["open", "https://brew.sh"], check=False)

    def sign_in_to_github(self) -> None:
        if not has_command("gh"):
            QMessageBox.warning(self, "Sign In To GitHub", "Install GitHub tools first, then sign in.")
            return
        self._open_terminal_command(f"{command_path('gh') or 'gh'} auth login")

    def _update_setup_buttons(self) -> None:
        has_brew = has_command("brew")
        has_gh = has_command("gh")
        self.homebrew_button.setVisible(not has_brew)
        self.install_tools_button.setVisible(has_brew and not has_gh)
        self.sign_in_button.setVisible(has_gh)

    def run_preflight_checks(self) -> None:
        if self.preflight_prompted:
            return
        self.preflight_prompted = True
        missing_tools = [tool for tool in ["git", "gh"] if not has_command(tool)]
        if missing_tools and has_command("brew"):
            answer = QMessageBox.question(
                self,
                "Preflight Setup",
                "GithubSnapshot needs GitHub tools to run backups. Install git, gh, and git-lfs now?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.install_github_tools()
            return
        if missing_tools:
            QMessageBox.information(
                self,
                "Preflight Setup",
                "GithubSnapshot needs Homebrew before it can install GitHub tools. Use Install Homebrew, then reopen the app.",
            )
            return
        try:
            github_username()
        except Exception:
            answer = QMessageBox.question(
                self,
                "GitHub Sign In",
                "GitHub tools are installed. Sign in to GitHub now?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.sign_in_to_github()

    def _open_terminal_command(self, command: str) -> None:
        escaped = command.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{escaped}"'])

    def _repo_lines(self) -> list[str]:
        return [
            line.strip()
            for line in self.repo_list_edit.toPlainText().splitlines()
            if line.strip()
        ]

    def fill_found_repositories(self) -> None:
        try:
            user = github_username()
            repos = list_repositories(user)
            self.repo_list_edit.setPlainText("\n".join(repo.name_with_owner for repo in repos))
            self.scope_combo.setCurrentIndex(1)
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Repository List", str(exc))

    def start_backup(self) -> None:
        self.save_settings()
        self.cancel_requested = False
        self.backup_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.status_text.setText("Backing up repositories...")

        def worker() -> None:
            runner = BackupRunner(
                self.config,
                self.logger,
                progress_callback=lambda i, t, r, m: self.signals.progress.emit(i, t, r, m),
                cancel_callback=lambda: self.cancel_requested,
            )
            try:
                manifest = runner.run()
                self.signals.finished.emit(manifest)
            except Exception as exc:
                self.signals.failed.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def request_cancel(self) -> None:
        self.cancel_requested = True
        self.status_text.setText("Cancelling after the current repository...")

    def on_progress(self, index, total, repo: str, message: str) -> None:
        if index and total:
            self.progress.setValue(int((index - 1) / total * 100))
            self.status_text.setText(f"{index} / {total}\n{repo}\n{message}")
        else:
            self.status_text.setText(f"{repo}\n{message}")

    def on_finished(self, manifest: dict) -> None:
        self.progress.setValue(100)
        self.backup_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.last_backup_label.setText(manifest["created_at"])
        self.status_text.setText(
            f"Backup complete. {manifest['repositories_successful']} successful, {manifest['repositories_failed']} failed."
        )
        self.refresh_status()

    def on_failed(self, message: str) -> None:
        self.backup_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_text.setText(message)

    def open_backup_folder(self) -> None:
        if self.config.backup_destination:
            subprocess.run(["open", self.config.backup_destination], check=False)

    def toggle_log(self) -> None:
        self.log_view.setVisible(not self.log_view.isVisible())
        log_files = sorted(logs_dir().glob("*.log"))
        if log_files:
            self.log_view.setPlainText(log_files[-1].read_text(encoding="utf-8", errors="replace")[-12000:])

    def show_restore_help(self) -> None:
        QMessageBox.information(self, "Restore Help", RESTORE_HELP)


def run_gui() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
