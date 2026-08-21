from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .config import logs_dir


def configure_logging(log_dir: Path | None = None) -> logging.Logger:
    target = log_dir or logs_dir()
    target.mkdir(parents=True, exist_ok=True)
    log_file = target / f"{datetime.now().date().isoformat()}.log"

    logger = logging.getLogger("github_snapshot_backup")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger

