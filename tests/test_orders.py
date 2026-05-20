from __future__ import annotations

from pathlib import Path

from agent_careflow.lifecycle import issue_order
from agent_careflow.orders import order_status, render_order_prompt
from agent_careflow.templates import render_plan


def make_case(tmp_path: Path) -> Path:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    (case / "orders").mkdir(parents=True)
    (case / "results").mkdir()
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Prompt test", "C1"), encoding="utf-8")
    return case


def test_order_prompt_includes_required_paths(tmp_path: Path) -> None:
    make_case(tmp_path)
    issue_order(tmp_path, "ACF-1", "ORD-1", "reviewer")

    prompt = render_order_prompt(tmp_path, "ACF-1", "ORD-1", "codex")

    assert "plan_path: .careflow/cases/ACF-1/PLAN.md" in prompt
    assert "order_path: .careflow/cases/ACF-1/orders/ORD-1.order.md" in prompt
    assert "expected_result_path: .careflow/cases/ACF-1/results/ORD-1.result.md" in prompt
    assert "reviewer" in prompt


def test_order_status_is_incomplete_until_result_exists(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    issue_order(tmp_path, "ACF-1", "ORD-1", "verifier")

    assert order_status(tmp_path, "ACF-1", "ORD-1")["complete"] is False

    (case / "results" / "ORD-1.result.md").write_text("done", encoding="utf-8")

    assert order_status(tmp_path, "ACF-1", "ORD-1")["complete"] is True
