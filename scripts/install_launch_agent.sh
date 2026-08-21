#!/usr/bin/env bash
set -euo pipefail

APP="/Applications/GitHub Snapshot Backup.app/Contents/MacOS/GitHub Snapshot Backup"
if [[ ! -x "$APP" ]]; then
  echo "Install GitHub Snapshot Backup.app in /Applications first." >&2
  exit 1
fi

"$APP" --headless-backup

