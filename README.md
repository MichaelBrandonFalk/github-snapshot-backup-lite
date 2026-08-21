# GitHub Snapshot Backup Lite

GitHub Snapshot Backup Lite is a small macOS utility that keeps weekly point-in-time ZIP snapshots of every repository owned by the authenticated GitHub account.

It is intentionally not a full GitHub archive. It backs up the current files from `main`, or the repository default branch when `main` does not exist. It does not preserve issues, pull requests, Actions history, every branch, tags, or full Git history.

## Requirements

- macOS
- Python 3.10 or newer for source installs
- `git`
- GitHub CLI, authenticated with `gh auth login`
- Optional: `git-lfs`

Install the command-line dependencies with Homebrew:

```bash
brew install git gh git-lfs
gh auth login
```

## What Gets Backed Up

- Public, private, archived, and forked repositories owned by the logged-in user
- The `main` branch when it exists
- Otherwise the GitHub default branch
- Submodules when clone access allows it
- Git LFS files when `git-lfs` is installed

Each backup run creates a dated folder:

```text
GitHub Backup/
  2026-08-21/
    OWNER__REPO.zip
    backup_manifest.json
    BACKUP_COMPLETE
  latest.json
```

ZIP archives contain normal repository files and exclude `.git`.

## Run From Source

```bash
python3 -m pip install -e .
github-snapshot-backup
```

Run the saved configuration without opening the GUI:

```bash
github-snapshot-backup --headless-backup
```

## Build The macOS App

```bash
./scripts/build_app.sh
```

The build creates:

```text
dist/GitHub Snapshot Backup.app
downloads/GitHub_Snapshot_Backup_Lite_v1.0.0_macOS.zip
```

Copy `GitHub Snapshot Backup.app` to `/Applications` for the standard weekly LaunchAgent command.

## Weekly Backups

The GUI can install a user LaunchAgent at:

```text
~/Library/LaunchAgents/com.githubsnapshotbackup.weekly.plist
```

The LaunchAgent runs:

```text
/Applications/GitHub Snapshot Backup.app/Contents/MacOS/GitHub Snapshot Backup --headless-backup
```

The GUI does not need to remain open.

## Restore

Open the latest dated backup, extract the repository ZIP, create a new GitHub repository, then run:

```bash
git init
git add .
git commit -m "Restore from GitHub Snapshot Backup"
git branch -M main
git remote add origin NEW_GITHUB_URL
git push -u origin main
```

## Versioning

Each released edit should update `src/github_snapshot_backup/__init__.py`, rebuild the app ZIP, tag the commit, and publish the ZIP on GitHub Releases.

