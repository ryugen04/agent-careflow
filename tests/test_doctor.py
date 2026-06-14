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
        '{"hooks":{"SessionStart":[],"PreToolUse":[],"PostToolUse":[],"PermissionRequest":[],"UserPromptSubmit":[],"Stop":[]}}',
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


def test_doctor_accepts_ai_dlc_workspace_with_installed_codex_hooks(tmp_path: Path, monkeypatch) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "hooks.json").write_text(
        '{"hooks":{"SessionStart":[],"PreToolUse":[],"PostToolUse":[],"PermissionRequest":[],"UserPromptSubmit":[],"Stop":[]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    (tmp_path / ".aidlc").mkdir()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
    for rel in (
        "ai-dlc/overlay/test.yaml",
        "ai-dlc/bootstrap/test.yaml",
        "ai-dlc/plans/test.md",
        "ai-dlc/work-items/test.yaml",
        "ai-dlc/decisions/test.md",
        "ai-dlc/evidence/test.yaml",
        "ai-dlc/handoff/test.md",
        "ai-dlc/quality/test.md",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")
    (tmp_path / "workspace.yaml").write_text(
        """schema: ai-dlc.workspace.v1
id: test
workspace:
  root: /tmp/test
repos:
  root-system:
    path: .
controller:
  no_direct_edits: true
workflow:
  subagent_required: true
paths:
  local: .local
  overlay: ai-dlc/overlay/test.yaml
  bootstrap: ai-dlc/bootstrap/test.yaml
  plan: ai-dlc/plans/test.md
  work_items: ai-dlc/work-items/test.yaml
  decisions: ai-dlc/decisions/test.md
  evidence: ai-dlc/evidence/test.yaml
  handoff: ai-dlc/handoff/test.md
  quality: ai-dlc/quality/test.md
""",
        encoding="utf-8",
    )
    (tmp_path / ".aidlc" / "workspace.yaml").write_text(
        """version: 1
kind: monorepo
workspace_key: test
repos:
  - key: root-system
    path: .
""",
        encoding="utf-8",
    )

    checks = run_doctor(tmp_path)

    assert not doctor_failed(checks)
    assert any(check.name == "codex-hooks" and str(codex_home) in check.message for check in checks)
