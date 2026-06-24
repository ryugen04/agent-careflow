from __future__ import annotations

from pathlib import Path

from agent_careflow.context import write_state
from agent_careflow.dashboard import render_dashboard, write_dashboard
from agent_careflow.templates import render_case, render_plan


def make_case(root: Path) -> Path:
    case = root / ".careflow" / "cases" / "ACF-1"
    (case / "orders").mkdir(parents=True)
    (case / "results").mkdir()
    (case / "evidence").mkdir()
    (case / "incidents").mkdir()
    (case / "reviews").mkdir()
    (case / "learnings").mkdir()
    (case / "CASE.yaml").write_text(render_case("ACF-1", "Visible planning", "C2"), encoding="utf-8")
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Visible planning", "C2"), encoding="utf-8")
    (case / "orders" / "ORD-1.order.md").write_text(
        "order_id: ORD-1\n"
        "case_id: ACF-1\n"
        "assigned_role: implementer\n"
        "plan_path: .careflow/cases/ACF-1/PLAN.md\n"
        "plan_hash: sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
        "allowed_actions:\n"
        "  - read\n"
        "forbidden_actions:\n"
        "  - drift\n"
        "deliverables:\n"
        "  - .careflow/cases/ACF-1/results/ORD-1.result.md\n"
        "expected_result_path: .careflow/cases/ACF-1/results/ORD-1.result.md\n"
        "completion_criteria:\n"
        "  - done\n",
        encoding="utf-8",
    )
    (case / "results" / "ORD-1.result.md").write_text("order_id: ORD-1\ncase_id: ACF-1\nstatus: complete\n", encoding="utf-8")
    (case / "incidents" / "INC-1.md").write_text("incident_id: INC-1\ncase_id: ACF-1\nstatus: open\n", encoding="utf-8")
    (case / "learnings" / "lesson.md").write_text("# Lesson\n", encoding="utf-8")
    return case


def test_dashboard_renders_active_handoff_and_artifact_links(tmp_path: Path) -> None:
    make_case(tmp_path)
    write_state(tmp_path, {"active_case": "ACF-1", "active_order": "ORD-1", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-1.result.md", "phase": "ordered"})

    text = render_dashboard(tmp_path)

    assert "# Agent Careflow Index" in text
    assert "workflow_root: `.`" in text
    assert str(tmp_path) not in text
    assert "PLAN_FILE: .careflow/cases/ACF-1/PLAN.md" in text
    assert "ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in text
    assert "EXPECTED_RESULT_PATH: .careflow/cases/ACF-1/results/ORD-1.result.md" in text
    assert "[.careflow/cases/ACF-1/incidents/INC-1.md]" in text
    assert "[.careflow/cases/ACF-1/learnings/lesson.md]" in text


def test_dashboard_write_uses_workflow_root_from_nested_worktree(tmp_path: Path) -> None:
    make_case(tmp_path)
    write_state(tmp_path, {"active_case": "ACF-1", "active_order": "ORD-1", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-1.result.md", "phase": "ordered"})
    nested = tmp_path / ".worktrees" / "feature" / "backend"
    nested.mkdir(parents=True)

    path = write_dashboard(nested)

    assert path == tmp_path / ".careflow" / "INDEX.md"
    assert "active_case: `ACF-1`" in path.read_text(encoding="utf-8")
