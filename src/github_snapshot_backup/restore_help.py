RESTORE_HELP = """To restore a repository:

1. Open your backup folder.
2. Open the latest dated backup.
3. Extract the repository ZIP.
4. Create a new repository on GitHub.
5. Open Terminal in the extracted folder.
6. Run:

   git init
   git add .
   git commit -m "Restore from GitHub Snapshot Backup"
   git branch -M main
   git remote add origin NEW_GITHUB_URL
   git push -u origin main
"""

