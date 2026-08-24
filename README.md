# GithubSnapshot V1.1

GithubSnapshot V1.1 is a small macOS utility that keeps weekly point-in-time ZIP snapshots of every repository owned by the authenticated GitHub account.

It is intentionally not a full GitHub archive. It backs up the current files from `main`, or the repository default branch when `main` does not exist. It does not preserve issues, pull requests, Actions history, every branch, tags, or full Git history.

The public website is for instructions and direct app downloads. Real backups require the installed macOS app because the app must authenticate with GitHub, clone repositories, read/write local folders, and install a LaunchAgent for weekly set-and-forget scheduling.

## Requirements

- macOS
- Python 3.10 or newer for source installs
- `git`
- GitHub CLI, authenticated with `gh auth login` when prompted by the app
- Optional: `git-lfs`

Install the command-line dependencies with Homebrew:

```bash
brew install git gh git-lfs
gh auth login
```

## What Gets Backed Up

- Public, private, archived, and forked repositories owned by the logged-in user
- All discovered repositories by default
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

1. Open the macOS app.
2. If Homebrew is missing, use the app's Install Homebrew button to open the official Homebrew instructions.
3. Use the app buttons to install GitHub tools and sign in if prompted.
4. Choose a backup destination such as a local folder or a Google Drive for desktop folder.
5. Leave Repository Mode set to `All discovered repositories`.
6. Leave Weekly enabled and choose the day/time.
7. Close the app. The LaunchAgent keeps running scheduled headless backups.

Open the app again later to change the folder, schedule, retention count, destination mode, or switch to a selected repository list.

## Google Drive

Local folder backups work now, including folders synced by Google Drive for desktop. Direct Google Drive API upload is listed separately in the app because it requires Google OAuth app setup before it can be enabled safely. There is no built-in GitHub-to-Google-Drive backup connection that avoids authentication.

## Build The macOS App

```bash
./scripts/build_app.sh
```

The build creates:

```text
dist/GithubSnapshot_V1.1.app
downloads/GithubSnapshot_V1.1_macOS.zip
```

The LaunchAgent uses the exact app executable that saved the settings, so the app bundle can keep its versioned filename.

## Weekly Backups

The GUI can install a user LaunchAgent at:

```text
~/Library/LaunchAgents/com.githubsnapshotbackup.weekly.plist
```

The LaunchAgent runs:

```text
GithubSnapshot_V1.1.app/Contents/MacOS/GithubSnapshot_V1.1 --headless-backup
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
