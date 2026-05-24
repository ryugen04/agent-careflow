from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.isolation import cleanup_isolation, create_isolation, export_isolation_patch, plan_isolation, render_isolation_plan


def test_worktree_is_default_isolation_strategy(tmp_path: Path) -> None:
    target = tmp_path / "repo"
    target.mkdir()

    plan = plan_isolation(target=target, case_id="ACF-1")

    assert plan.strategy == "worktree"
    assert "worktree add" in plan.create_command
    assert "worktree remove" in plan.cleanup_command
    assert "default v0.x" in " ".join(plan.notes)


def test_shared_clone_plan_marks_destructive_cleanup(tmp_path: Path) -> None:
    target = tmp_path / "repo"
    target.mkdir()

    plan = plan_isolation(target=target, case_id="ACF-1", strategy="shared-clone")
    rendered = render_isolation_plan(plan)

    assert "git clone --shared" in rendered
    assert "requires explicit approval" in rendered


def test_isolation_rejects_missing_target(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="does not exist"):
        plan_isolation(target=tmp_path / "missing", case_id="ACF-1")

def init_git_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_create_cleanup_worktree_and_export_patch(tmp_path: Path) -> None:
    target = tmp_path / "repo"
    init_git_repo(target)

    work_dir = create_isolation(target=target, case_id="ACF-1", strategy="worktree")
    (work_dir / "file.txt").write_text("changed\n", encoding="utf-8")
    patch = export_isolation_patch(work_dir=work_dir, output=tmp_path / "change.patch")

    assert (work_dir / ".careflow-isolation.json").exists()
    assert "changed" in patch.read_text(encoding="utf-8")

    cleaned = cleanup_isolation(target=target, case_id="ACF-1", strategy="worktree", force=True)

    assert cleaned == work_dir
    assert not work_dir.exists()


def test_cleanup_rejects_unmarked_clone_directory(tmp_path: Path) -> None:
    target = tmp_path / "repo"
    init_git_repo(target)
    unmarked = tmp_path / "repo-ACF-1-shared-clone"
    unmarked.mkdir()

    with pytest.raises(ValidationError, match="marker missing"):
        cleanup_isolation(target=target, case_id="ACF-1", strategy="shared-clone", work_dir=unmarked)
