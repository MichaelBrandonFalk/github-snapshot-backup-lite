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
    parser = argparse.ArgumentParser(description="GitHub Snapshot Backup")
    parser.add_argument("--headless-backup", action="store_true", help="Run a backup using saved preferences and exit.")
    args = parser.parse_args(argv)
    if args.headless_backup:
        return run_headless()
    from .gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
