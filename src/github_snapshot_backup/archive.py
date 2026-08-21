from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_zip_from_folder(source: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in sorted(source.rglob("*")):
            if file_path.is_dir():
                continue
            if ".git" in file_path.relative_to(source).parts:
                continue
            zip_file.write(file_path, file_path.relative_to(source.parent))


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as zip_file:
        bad_file = zip_file.testzip()
    if bad_file:
        raise RuntimeError(f"ZIP verification failed at {bad_file}")

