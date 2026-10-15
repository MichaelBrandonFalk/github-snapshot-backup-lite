# GithubSnapshot V1.5

GithubSnapshot V1.5 is a desktop utility for macOS, Windows, and Linux Mint that keeps weekly point-in-time ZIP snapshots of repositories owned by the authenticated GitHub account.

It is intentionally not a full GitHub archive. It backs up the current files from `main`, or the repository default branch when `main` does not exist. It does not preserve issues, pull requests, Actions history, every branch, tags, or full Git history.

The [download page](https://michaelbrandonfalk.github.io/github-snapshot-backup-lite/) has direct downloads and instructions for each platform. Python and Qt are bundled; installing Python is unnecessary.

## Downloads And Installation

- [Windows 10/11 x64 ZIP](https://github.com/MichaelBrandonFalk/github-snapshot-backup-lite/releases/download/v1.5.0/GithubSnapshot_V1.5_Windows_x64.zip): extract the entire ZIP to a permanent folder, then open `GithubSnapshot_V1.5.exe`. Use Install Required Tools for Git, GitHub CLI, and rclone through winget. If winget is missing, install Microsoft's App Installer. Reopen the app after tools are installed.
- [Linux Mint 21/22 amd64 installer](https://github.com/MichaelBrandonFalk/github-snapshot-backup-lite/releases/download/v1.5.0/GithubSnapshot_V1.5_LinuxMint_amd64.deb): open with Package Installer, or run `sudo apt install ./GithubSnapshot_V1.5_LinuxMint_amd64.deb`. Dependencies are installed through apt. Launch from the applications menu.
- [macOS Apple Silicon ZIP](https://github.com/MichaelBrandonFalk/github-snapshot-backup-lite/releases/download/v1.5.0/GithubSnapshot_V1.5_macOS.zip): extract and move the app to Applications. Use the setup buttons if prompted.

Windows builds are unsigned; macOS builds are not notarized. Linux Mint builds target x86-64 Mint 21 and 22 (Ubuntu 22.04/24.04 bases), not ARM devices or LMDE. Windows and Linux packages are built on native GitHub Actions runners and checked for GUI startup. A full Mint desktop backup and Google OAuth flow still require a real signed-in user session.

## Requirements

- macOS Apple Silicon, Windows 10/11 x64, or Linux Mint 21/22 x64
- Python 3.10 or newer for source installs
- `git`
- GitHub CLI, authenticated with `gh auth login` when prompted by the app
- `rclone` for direct Google Drive upload
- Optional: `git-lfs`

The app's setup buttons install missing tools using Homebrew on macOS, winget on Windows, or apt on Linux Mint. The Linux installer declares the tools and desktop libraries as package dependencies. Initial installation requires internet access and may require administrator approval. Sign in to GitHub once using the app.

For manual macOS setup:

```bash
brew install git gh git-lfs rclone
gh auth login
```

## What Gets Backed Up

- Public, private, archived, and forked repositories owned by the logged-in user
- All repositories by default, scanned at backup time so newly created repositories are included
- Optional selected-repository mode using `owner/repository` names, one per line
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

## Set-And-Forget Use

1. Open the app for your platform.
2. On macOS, install Homebrew if prompted. Windows uses winget; Linux Mint uses apt.
3. Use the app buttons to install GitHub tools and sign in if prompted.
4. Choose a backup destination: local folder, Google Drive, or both.
5. Leave `All Repositories (scan at backup time)` checked.
6. Leave Weekly enabled. The default is Wednesday at 10:00 AM in local time; choose a time when the computer is usually awake, signed in, and online.
7. Click Save Settings, then close the app. Keep it installed in the same location for scheduled backups.

Open the app again later to change the folder, schedule, retention count, destination mode, or switch to a selected repository list.

## Google Drive

Local folder backups work for any accessible folder. Direct Google Drive upload uses `rclone`: click Connect Google Drive once, complete Google's OAuth consent flow, and scheduled backups can upload after that without another sign-in.

## Missed Backups

Set the schedule for a time when the computer is usually awake, signed in, and online. Windows uses Task Scheduler with StartWhenAvailable; Linux uses a persistent systemd user timer. Both can catch up when the user session is available again. macOS may run a missed launchd job after waking. The app also checks `last_successful_backup` on launch and offers to run a missed backup.

## Backup Summary

Each completed snapshot includes:

```text
backup_manifest.json
backup_summary.txt
```

The summary text lists failed repositories and the recorded error for each one.

## Build The macOS App

```bash
./scripts/build_app.sh
```

The build creates:

```text
dist/GithubSnapshot_V1.5.app
downloads/GithubSnapshot_V1.5_macOS.zip
```

## Build Windows And Linux Mint Packages

Build on the target operating system; PyInstaller cannot cross-compile:

```bash
python -m pip install '.[build,test]' 'PySide6==6.7.3'
python -m pytest -q
python scripts/build_desktop.py
```

Linux builds use Ubuntu 22.04 and Python 3.12 to retain Mint 21 compatibility. The output is a versioned `.deb`; Windows produces a ZIP containing an executable and supporting files. The Desktop Distributions workflow builds both platforms on release tags, runs tests and packaged GUI startup checks, installs the `.deb`, and uploads assets plus SHA-256 files to the release. It can also be rerun for an existing tag with workflow_dispatch.

## Weekly Backups

The saved schedule uses a macOS LaunchAgent, a Windows Task Scheduler task named `GithubSnapshot Weekly Backup`, or a Linux systemd user timer named `github-snapshot-backup.timer`. Windows and Linux scheduled backups run in your signed-in user session; the app window can be closed. On macOS, the LaunchAgent is at:

```text
~/Library/LaunchAgents/com.githubsnapshotbackup.weekly.plist
```

The LaunchAgent runs:

```text
GithubSnapshot_V1.5.app/Contents/MacOS/GithubSnapshot_V1.5 --headless-backup
```

After upgrading or moving the app, open the new version and save settings to update the scheduled executable. Settings and logs live in the user's macOS Library, Windows AppData, or Linux XDG directories.

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
