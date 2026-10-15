from __future__ import annotations

import argparse
import sys

from .backup import BackupRunner
from .config import AppConfig
from .logging_utils import configure_logging


def run_headless() -> int:
    logger = configure_logging()
    config = AppConfig.load()
    try:
        manifest = BackupRunner(config, logger).run()
    except Exception as exc:
        logger.exception("headless backup failed")
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"Backup complete: {manifest['repositories_successful']} successful, "
        f"{manifest['repositories_failed']} failed"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GithubSnapshot V1.5.1")
    parser.add_argument("--headless-backup", action="store_true", help="Run a backup using saved preferences and exit.")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.smoke_test:
        import logging
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        from .gui import MainWindow

        app = QApplication([])
        with patch.object(AppConfig, "load", return_value=AppConfig()), \
             patch("github_snapshot_backup.gui.configure_logging", return_value=logging.getLogger("smoke")), \
             patch.object(MainWindow, "refresh_status"), \
             patch.object(MainWindow, "run_preflight_checks"):
            window = MainWindow()
            window.show()
            app.processEvents()
            if not window.isVisible() or window.time_edit.time().hour() != 10:
                return 1
            window.close()
        return 0
    if args.headless_backup:
        return run_headless()
    from .gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
