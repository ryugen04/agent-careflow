from __future__ import annotations

from pathlib import Path

from agent_careflow.doctor import doctor_failed, run_doctor
from agent_careflow.research import scaffold_research
from agent_careflow.templates import render_discharge, render_plan
from agent_careflow.artifacts import write_plan_lock, sha256_file


def test_doctor_reports_failures_for_empty_repo(tmp_path: Path) -> None:
    checks = run_doctor(tmp_path)

    assert doctor_failed(checks)
    assert any(check.name == "research" and not check.ok for check in checks)


def test_doctor_accepts_minimal_valid_repo(tmp_path: Path) -> None:
    scaffold_research(tmp_path)
    schema_dir = tmp_path / "src" / "agent_careflow" / "schemas"
    schema_dir.mkdir(parents=True)
    for name in ["CASE", "PLAN"]:
        (schema_dir / f"{name}.schema.json").write_text("{}", encoding="utf-8")
    rules = tmp_path / "rules" / "codex"
    rules.mkdir(parents=True)
    (rules / "hooks.json").write_text(
        '{"hooks":{"PreToolUse":[],"PostToolUse":[],"PermissionRequest":[],"UserPromptSubmit":[]}}',
        encoding="utf-8",
    )
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    (case / "orders").mkdir(parents=True)
    (case / "evidence").mkdir()
    (case / "results").mkdir()
    (case / "CASE.yaml").write_text(
        """case_id: ACF-1
title: Doctor
risk: C1
phase: discharge
status: active
created_at: 2026-05-21T00:00:00+09:00
owner: test
""",
        encoding="utf-8",
    )
    plan = case / "PLAN.md"
    plan.write_text(render_plan("ACF-1", "Doctor", "C1"), encoding="utf-8")
    write_plan_lock(plan)
    order = case / "orders" / "ORD-1.order.md"
    order.write_text(
        f"""# ORDER: ORD-1

order_id: ORD-1
case_id: ACF-1
assigned_role: verifier
plan_path: .careflow/cases/ACF-1/PLAN.md
plan_hash: {sha256_file(plan)}
allowed_actions:
  - verify
forbidden_actions:
  - edit source
deliverables:
  - .careflow/cases/ACF-1/results/ORD-1.result.md
expected_result_path: .careflow/cases/ACF-1/results/ORD-1.result.md
completion_criteria:
  - result exists
""",
        encoding="utf-8",
    )
    (case / "evidence" / "pytest.txt").write_text("ok", encoding="utf-8")
    (case / "DISCHARGE.md").write_text(render_discharge("ACF-1"), encoding="utf-8")

    checks = run_doctor(tmp_path)

    assert not doctor_failed(checks)
