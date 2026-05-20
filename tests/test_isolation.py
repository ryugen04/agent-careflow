from __future__ import annotations

from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.isolation import plan_isolation, render_isolation_plan


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
