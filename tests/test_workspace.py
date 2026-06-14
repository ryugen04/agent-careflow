from __future__ import annotations

from pathlib import Path

from agent_careflow.context import write_state
from agent_careflow.templates import render_case, render_plan
from agent_careflow.workspace import render_workspace_current, write_workspace


def make_case(root: Path) -> Path:
    case = root / ".careflow" / "cases" / "ACF-1"
    (case / "orders").mkdir(parents=True)
    (case / "results").mkdir()
    (case / "incidents").mkdir()
    (case / "reviews").mkdir()
    (case / "learnings").mkdir()
    (root / ".careflow" / "INDEX.md").parent.mkdir(parents=True, exist_ok=True)
    (root / ".careflow" / "INDEX.md").write_text("# Agent Careflow Index\n", encoding="utf-8")
    (case / "CASE.yaml").write_text(render_case("ACF-1", "Workspace", "C1"), encoding="utf-8")
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Workspace", "C1"), encoding="utf-8")
    (case / "orders" / "ORD-1.order.md").write_text("order_id: ORD-1\ncase_id: ACF-1\nstatus: active\n", encoding="utf-8")
    (case / "results" / "ORD-1.result.md").write_text("order_id: ORD-1\ncase_id: ACF-1\nstatus: complete\n", encoding="utf-8")
    (case / "incidents" / "INC-1.md").write_text("incident_id: INC-1\ncase_id: ACF-1\nstatus: open\n", encoding="utf-8")
    (case / "reviews" / "REVIEW-1.review.md").write_text("review_id: REVIEW-1\ncase_id: ACF-1\ntool: codex\nstatus: pass\n", encoding="utf-8")
    (case / "learnings" / "lesson.md").write_text("# Lesson\n", encoding="utf-8")
    return case


def test_workspace_current_renders_handoff_and_agent_links(tmp_path: Path) -> None:
    make_case(tmp_path)
    write_state(tmp_path, {"active_case": "ACF-1", "active_order": "ORD-1", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-1.result.md"})

    text = render_workspace_current(tmp_path)

    assert "workflow_root: `.`" in text
    assert str(tmp_path) not in text
    assert "PLAN_FILE: .careflow/cases/ACF-1/PLAN.md" in text
    assert "ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in text
    assert "EXPECTED_RESULT_PATH: .careflow/cases/ACF-1/results/ORD-1.result.md" in text
    assert "[.careflow/cases/ACF-1/incidents/INC-1.md](../.careflow/cases/ACF-1/incidents/INC-1.md)" in text
    assert "[.careflow/cases/ACF-1/reviews/REVIEW-1.review.md](../.careflow/cases/ACF-1/reviews/REVIEW-1.review.md)" in text
    assert "[.careflow/cases/ACF-1/learnings/lesson.md](../.careflow/cases/ACF-1/learnings/lesson.md)" in text


def test_workspace_write_from_nested_worktree_creates_agent_workspace(tmp_path: Path) -> None:
    make_case(tmp_path)
    write_state(tmp_path, {"active_case": "ACF-1", "active_order": "ORD-1", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-1.result.md"})
    nested = tmp_path / ".worktrees" / "feature" / "frontend"
    nested.mkdir(parents=True)

    written = write_workspace(nested)

    assert tmp_path / ".agent" / "README.md" in written
    assert tmp_path / ".agent" / "current.md" in written
    assert tmp_path / ".agent" / "incidents" / "README.md" in written
    assert tmp_path / ".agent" / "reviews" / "README.md" in written
    assert tmp_path / ".agent" / "learnings" / "README.md" in written
    assert "Canonical state remains in `.careflow/`" in (tmp_path / ".agent" / "README.md").read_text(encoding="utf-8")
    current = (tmp_path / ".agent" / "current.md").read_text(encoding="utf-8")
    assert "PLAN_FILE: .careflow/cases/ACF-1/PLAN.md" in current
    assert "(../.careflow/cases/ACF-1/PLAN.md)" in current
    incidents = (tmp_path / ".agent" / "incidents" / "README.md").read_text(encoding="utf-8")
    assert "(../../.careflow/cases/ACF-1/incidents/INC-1.md)" in incidents
    reviews = (tmp_path / ".agent" / "reviews" / "README.md").read_text(encoding="utf-8")
    assert "(../../.careflow/cases/ACF-1/reviews/REVIEW-1.review.md)" in reviews
