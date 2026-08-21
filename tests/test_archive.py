from pathlib import Path
import zipfile

from github_snapshot_backup.archive import create_zip_from_folder, sha256_file, verify_zip


def test_create_zip_excludes_git(tmp_path: Path) -> None:
    repo = tmp_path / "Repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text("secret", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    archive = tmp_path / "Repo.zip"

    create_zip_from_folder(repo, archive)
    verify_zip(archive)

    with zipfile.ZipFile(archive) as zip_file:
        names = zip_file.namelist()
    assert "Repo/src/app.py" in names
    assert "Repo/.git/config" not in names
    assert len(sha256_file(archive)) == 64

