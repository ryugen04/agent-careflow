from __future__ import annotations

from pathlib import Path

from agent_careflow.repo_status import discover_repositories, render_repo_status
from agent_careflow.workspace import write_workspace


def mark_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()


def test_discover_repositories_finds_direct_repos_and_branch_worktrees(tmp_path: Path) -> None:
    (tmp_path / ".careflow").mkdir()
    (tmp_path / ".careflow" / "state.json").write_text("{}", encoding="utf-8")
    mark_git_repo(tmp_path / "backend")
    mark_git_repo(tmp_path / "frontend")
    mark_git_repo(tmp_path / ".worktrees" / "feature-auth" / "backend")
    (tmp_path / "docs").mkdir()

    repos = discover_repositories(tmp_path)

    assert [repo["path"] for repo in repos] == [
        "backend",
        "frontend",
        ".worktrees/feature-auth/backend",
    ]
    assert repos[0]["kind"] == "repo"
    assert repos[2]["kind"] == "worktree"
    assert repos[2]["branch"] == "feature-auth"
    assert repos[2]["name"] == "backend"


def test_render_repo_status_names_command_roots(tmp_path: Path) -> None:
    (tmp_path / ".careflow").mkdir()
    (tmp_path / ".careflow" / "state.json").write_text("{}", encoding="utf-8")
    mark_git_repo(tmp_path / "backend")
    mark_git_repo(tmp_path / ".worktrees" / "feature-auth" / "frontend")

    text = render_repo_status(tmp_path)

    assert "# Repository Workspace" in text
    assert "backend" in text
    assert "git -C backend status --short" in text
    assert ".worktrees/feature-auth/frontend" in text
    assert "branch: feature-auth" in text
    assert "Canonical careflow artifacts remain under `.careflow/`" in text


def test_workspace_write_includes_repos_page(tmp_path: Path) -> None:
    (tmp_path / ".careflow" / "cases" / "ACF-1" / "orders").mkdir(parents=True)
    (tmp_path / ".careflow" / "state.json").write_text('{"active_case":"ACF-1"}\n', encoding="utf-8")
    mark_git_repo(tmp_path / "backend")

    written = write_workspace(tmp_path)

    assert tmp_path / ".agent" / "repos.md" in written
    repos = (tmp_path / ".agent" / "repos.md").read_text(encoding="utf-8")
    assert "git -C backend status --short" in repos
    readme = (tmp_path / ".agent" / "README.md").read_text(encoding="utf-8")
    assert "[Repositories](repos.md)" in readme
