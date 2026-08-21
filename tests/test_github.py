from github_snapshot_backup.github import _repo_from_json


def test_repo_from_json_uses_default_branch_name() -> None:
    repo = _repo_from_json(
        {
            "name": "Tool",
            "nameWithOwner": "Owner/Tool",
            "url": "https://github.com/Owner/Tool",
            "defaultBranchRef": {"name": "production"},
            "isPrivate": True,
            "isArchived": False,
            "isFork": False,
            "pushedAt": "2026-08-21T00:00:00Z",
        }
    )
    assert repo.default_branch == "production"
    assert repo.name_with_owner == "Owner/Tool"
    assert repo.is_private is True

