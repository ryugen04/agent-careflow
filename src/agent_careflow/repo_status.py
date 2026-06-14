from __future__ import annotations

from pathlib import Path
from typing import Any


def _is_git_repo(path: Path) -> bool:
    git = path / ".git"
    return git.exists()


def _entry(root: Path, path: Path, *, kind: str, branch: str | None = None) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    return {
        "name": path.name,
        "path": rel,
        "kind": kind,
        "branch": branch,
        "status_command": f"git -C {rel} status --short",
    }


def discover_repositories(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    repos: list[dict[str, Any]] = []
    ignored = {".git", ".careflow", ".agent", ".agents", ".codex", ".claude", ".cursor", ".worktrees"}
    for child in sorted(root.iterdir(), key=lambda path: path.name) if root.exists() else []:
        if not child.is_dir() or child.name in ignored:
            continue
        if _is_git_repo(child):
            repos.append(_entry(root, child, kind="repo"))
    worktrees = root / ".worktrees"
    if worktrees.exists():
        for branch_dir in sorted((path for path in worktrees.iterdir() if path.is_dir()), key=lambda path: path.name):
            for repo_dir in sorted((path for path in branch_dir.iterdir() if path.is_dir()), key=lambda path: path.name):
                if _is_git_repo(repo_dir):
                    repos.append(_entry(root, repo_dir, kind="worktree", branch=branch_dir.name))
    return repos


def render_repo_status(root: Path) -> str:
    repos = discover_repositories(root)
    lines = [
        "# Repository Workspace",
        "",
        f"workflow_root: `{root.resolve().as_posix()}`",
        "",
        "Canonical careflow artifacts remain under `.careflow/`; do not create case/order/result artifacts inside child repos or worktrees.",
        "",
        "## Repositories",
        "",
    ]
    if not repos:
        lines.append("- No git repositories detected under this workflow root.")
    for repo in repos:
        detail = f"kind: {repo['kind']}"
        if repo.get("branch"):
            detail += f"; branch: {repo['branch']}"
        lines.extend([
            f"- `{repo['path']}` ({detail})",
            f"  - status: `{repo['status_command']}`",
        ])
    lines.append("")
    return "\n".join(lines)
