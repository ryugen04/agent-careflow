from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.context import find_workflow_root, read_state, resolve_context, write_state


def test_find_workflow_root_from_nested_repo(tmp_path: Path) -> None:
    root = tmp_path / "root-app"
    repo = root / "backend" / "src"
    repo.mkdir(parents=True)
    (root / ".careflow").mkdir()
    (root / ".careflow" / "state.json").write_text("{}", encoding="utf-8")

    assert find_workflow_root(repo) == root.resolve()


def test_find_workflow_root_from_branch_worktree_repo(tmp_path: Path) -> None:
    root = tmp_path / "root-app"
    repo = root / ".worktrees" / "feature-auth" / "backend"
    repo.mkdir(parents=True)
    (root / ".careflow").mkdir()
    (root / ".careflow" / "state.json").write_text("{}", encoding="utf-8")

    assert find_workflow_root(repo) == root.resolve()


def test_resolve_context_reads_active_case_order_and_result_from_state(tmp_path: Path) -> None:
    root = tmp_path / "root-app"
    repo = root / ".worktrees" / "feature-auth" / "backend"
    repo.mkdir(parents=True)
    write_state(root, {"active_case": "ACF-1", "active_order": "ORD-001", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-001.result.md"})

    context = resolve_context({"cwd": repo.as_posix()})

    assert context.workflow_root == root.resolve()
    assert context.case_id == "ACF-1"
    assert context.order_id == "ORD-001"
    assert context.expected_result_path == ".careflow/cases/ACF-1/results/ORD-001.result.md"


def test_payload_context_overrides_state(tmp_path: Path) -> None:
    root = tmp_path / "root-app"
    repo = root / "backend"
    repo.mkdir(parents=True)
    write_state(root, {"active_case": "ACF-1", "active_order": "ORD-001"})

    context = resolve_context({"cwd": repo.as_posix(), "case_id": "ACF-2", "order_id": "ORD-002"})

    assert context.case_id == "ACF-2"
    assert context.order_id == "ORD-002"
    assert read_state(root)["active_case"] == "ACF-1"
