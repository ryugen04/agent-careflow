from __future__ import annotations

from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError, sha256_file, validate_discharge, validate_order, validate_plan, validate_research, write_plan_lock
from agent_careflow.research import scaffold_research
from agent_careflow.templates import render_order, render_plan


def test_research_scaffold_validates(tmp_path: Path) -> None:
    scaffold_research(tmp_path)
    validate_research(tmp_path)


def test_order_requires_plan_path(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    orders = case / "orders"
    orders.mkdir(parents=True)
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Test", "C1"), encoding="utf-8")
    order = orders / "ORD-1.order.md"
    order.write_text(
        """# ORDER: ORD-1

order_id: ORD-1
case_id: ACF-1
assigned_role: implementer
plan_hash: sha256:abc
allowed_actions:
  - read
deliverables:
  - result
forbidden_actions:
  - drift
expected_result_path: .careflow/cases/ACF-1/results/ORD-1.result.md
completion_criteria:
  - done
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="plan_path"):
        validate_order(order, tmp_path)


def test_order_rejects_mismatched_plan_hash(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    orders = case / "orders"
    results = case / "results"
    orders.mkdir(parents=True)
    results.mkdir()
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Test", "C1"), encoding="utf-8")
    order = orders / "ORD-1.order.md"
    order.write_text(render_order("ACF-1", "ORD-1", "implementer", plan, results / "ORD-1.result.md"), encoding="utf-8")
    plan.write_text(render_plan("ACF-1", "Changed", "C1"), encoding="utf-8")

    with pytest.raises(ValidationError, match="plan_hash mismatch"):
        validate_order(order, tmp_path)


def test_order_accepts_current_plan_hash(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    orders = case / "orders"
    results = case / "results"
    orders.mkdir(parents=True)
    results.mkdir()
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Test", "C1"), encoding="utf-8")
    rel_plan = Path(".careflow/cases/ACF-1/PLAN.md")
    rel_result = Path(".careflow/cases/ACF-1/results/ORD-1.result.md")
    order = orders / "ORD-1.order.md"
    content = render_order("ACF-1", "ORD-1", "implementer", plan, rel_result)
    content = content.replace(plan.as_posix(), rel_plan.as_posix()).replace(sha256_file(plan), sha256_file(plan))
    order.write_text(content, encoding="utf-8")

    validate_order(order, tmp_path)


def test_discharge_requires_evidence(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    case.mkdir(parents=True)
    discharge = case / "DISCHARGE.md"
    discharge.write_text(
        """# DISCHARGE: ACF-1

case_id: ACF-1
status: draft
evidence:
  - missing
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="evidence"):
        validate_discharge(discharge, case)



def test_plan_validate_requires_lock_when_requested(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    case.mkdir(parents=True)
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Test", "C1"), encoding="utf-8")

    with pytest.raises(ValidationError, match="missing PLAN lock"):
        validate_plan(plan, require_lock=True)

    write_plan_lock(plan)
    validate_plan(plan, require_lock=True)


def test_stale_plan_lock_is_rejected(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    case.mkdir(parents=True)
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Test", "C1"), encoding="utf-8")
    write_plan_lock(plan)
    plan.write_text(render_plan("ACF-1", "Changed", "C1"), encoding="utf-8")

    with pytest.raises(ValidationError, match="stale plan lock"):
        validate_plan(plan, require_lock=True)


def test_order_rejects_stale_plan_lock(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    orders = case / "orders"
    results = case / "results"
    orders.mkdir(parents=True)
    results.mkdir()
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Test", "C1"), encoding="utf-8")
    write_plan_lock(plan)
    rel_plan = Path(".careflow/cases/ACF-1/PLAN.md")
    rel_result = Path(".careflow/cases/ACF-1/results/ORD-1.result.md")
    order = orders / "ORD-1.order.md"
    content = render_order("ACF-1", "ORD-1", "implementer", plan, rel_result)
    content = content.replace(plan.as_posix(), rel_plan.as_posix())
    order.write_text(content, encoding="utf-8")
    plan.write_text(render_plan("ACF-1", "Changed", "C1"), encoding="utf-8")

    with pytest.raises(ValidationError, match="plan_hash mismatch"):
        validate_order(order, tmp_path)
