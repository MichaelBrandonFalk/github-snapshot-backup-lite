#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv .venv
  PYTHON="$ROOT_DIR/.venv/bin/python"
fi

VERSION="$("$PYTHON" - <<'PY'
from pathlib import Path
text = Path("src/github_snapshot_backup/__init__.py").read_text()
for line in text.splitlines():
    if line.startswith("__version__"):
        print(line.split("=")[1].strip().strip('"'))
        break
PY
)"

"$PYTHON" -m pip install --no-build-isolation -e ".[build]"
"$PYTHON" -m PyInstaller \
  --name "GithubSnapshot_V1.1" \
  --windowed \
  --clean \
  --noconfirm \
  --paths src \
  --hidden-import github_snapshot_backup.gui \
  scripts/pyinstaller_entry.py

mkdir -p downloads
ZIP_NAME="GithubSnapshot_V1.1_macOS.zip"
ditto -c -k --sequesterRsrc --keepParent "dist/GithubSnapshot_V1.1.app" "downloads/${ZIP_NAME}"
echo "Created downloads/${ZIP_NAME}"
