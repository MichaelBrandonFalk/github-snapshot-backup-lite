from pathlib import Path

import github_snapshot_backup.github as github


def test_command_path_checks_homebrew_paths(monkeypatch, tmp_path: Path) -> None:
    tool_dir = tmp_path / "bin"
    tool_dir.mkdir()
    tool = tool_dir / "gh"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o755)

    monkeypatch.setattr(github.shutil, "which", lambda _command: None)
    monkeypatch.setattr(github, "COMMAND_PATHS", [str(tool_dir)])

    assert github.command_path("gh") == str(tool)

