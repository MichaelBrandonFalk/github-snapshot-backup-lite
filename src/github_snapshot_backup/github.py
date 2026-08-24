from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Repository:
    name: str
    name_with_owner: str
    url: str
    default_branch: str
    is_private: bool
    is_archived: bool
    is_fork: bool
    pushed_at: str


def has_command(command: str) -> bool:
    return shutil.which(command) is not None


def run_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)


def github_username() -> str:
    if not has_command("gh"):
        raise RuntimeError("GitHub setup needed. Install GitHub CLI, then sign in once.")
    status = run_command(["gh", "auth", "status"], timeout=20)
    if status.returncode != 0:
        raise RuntimeError("GitHub setup needed. Sign in with GitHub CLI once.")
    result = run_command(["gh", "api", "user", "--jq", ".login"], timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to read GitHub username.")
    return result.stdout.strip()


def list_repositories(username: str) -> list[Repository]:
    result = run_command(
        [
            "gh",
            "repo",
            "list",
            username,
            "--limit",
            "1000",
            "--json",
            "name,nameWithOwner,url,defaultBranchRef,isPrivate,isArchived,isFork,pushedAt",
        ],
        timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to list repositories.")
    repos: list[Repository] = []
    for item in json.loads(result.stdout or "[]"):
        repos.append(_repo_from_json(item))
    return repos


def _repo_from_json(item: dict[str, Any]) -> Repository:
    default_ref = item.get("defaultBranchRef") or {}
    return Repository(
        name=item["name"],
        name_with_owner=item["nameWithOwner"],
        url=item["url"],
        default_branch=default_ref.get("name") or "main",
        is_private=bool(item.get("isPrivate")),
        is_archived=bool(item.get("isArchived")),
        is_fork=bool(item.get("isFork")),
        pushed_at=item.get("pushedAt") or "",
    )


def branch_exists(name_with_owner: str, branch: str) -> bool:
    result = run_command(["gh", "api", f"repos/{name_with_owner}/branches/{branch}", "--jq", ".name"], timeout=30)
    return result.returncode == 0 and result.stdout.strip() == branch


def choose_branch(repo: Repository) -> str:
    if branch_exists(repo.name_with_owner, "main"):
        return "main"
    return repo.default_branch or "main"


def branch_commit_sha(name_with_owner: str, branch: str) -> str:
    result = run_command(
        ["gh", "api", f"repos/{name_with_owner}/branches/{branch}", "--jq", ".commit.sha"],
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Unable to read commit for {name_with_owner}@{branch}.")
    return result.stdout.strip()
