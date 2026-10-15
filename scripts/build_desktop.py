"""Build on the target OS; Python and Qt are included in each distribution."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))
from github_snapshot_backup import __version__

NAME = "GithubSnapshot_V" + __version__.removesuffix(".0")
OUT = ROOT / "downloads"


def main() -> None:
    if sys.platform not in {"win32", "linux"}:
        raise SystemExit("Use scripts/build_app.sh for macOS.")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise SystemExit("This distribution targets x64 computers.")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--name", NAME, "--windowed",
        "--clean", "--noconfirm", "--paths", "src", "--hidden-import",
        "github_snapshot_backup.gui", "scripts/pyinstaller_entry.py",
    ], check=True)
    bundle = ROOT / "dist" / NAME
    OUT.mkdir(exist_ok=True)
    if sys.platform == "win32":
        (bundle / "START_HERE.txt").write_text(
            f"Extract this entire ZIP to a permanent folder, then open {NAME}.exe.\n"
            "Python is included. Use Install Required Tools if prompted; Windows may ask for administrator approval.\n"
            "Sign in to GitHub, choose a destination, and save settings. Keep this folder in place for weekly backups.\n"
            "Scheduled backups run while you are signed in; the app can be closed.\n",
            encoding="utf-8",
        )
        shutil.make_archive(str(OUT / f"{NAME}_Windows_x64"), "zip", ROOT / "dist", NAME)
    else:
        package = ROOT / "build" / "deb"
        shutil.rmtree(package, ignore_errors=True)
        target = package / "opt" / NAME
        target.parent.mkdir(parents=True)
        shutil.copytree(bundle, target)
        control = package / "DEBIAN"
        control.mkdir()
        (control / "control").write_text(
            f"Package: github-snapshot-backup\nVersion: {__version__}\nArchitecture: amd64\n"
            "Maintainer: MichaelBrandonFalk <noreply@github.com>\nSection: utils\nPriority: optional\n"
            "Depends: git, gh, git-lfs, rclone, xterm, libgl1, libegl1, libopengl0, libdbus-1-3, "
            "libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, "
            "libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1, libxcb-shape0\n"
            "Description: Weekly GitHub repository snapshot backups\n"
            " Desktop app with local and Google Drive destinations. Python is included.\n",
            encoding="utf-8",
        )
        desktop = package / "usr" / "share" / "applications"
        desktop.mkdir(parents=True)
        (desktop / "github-snapshot-backup.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=GithubSnapshot V{__version__.removesuffix('.0')}\n"
            f"Exec=/opt/{NAME}/{NAME}\nIcon=document-save\nTerminal=false\nCategories=Utility;Archiving;\n",
            encoding="utf-8",
        )
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(package), str(OUT / f"{NAME}_LinuxMint_amd64.deb")], check=True)


if __name__ == "__main__":
    main()
