from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.acceptance import REQUIRED_SKILLS, _parse_json_lines, _event_text, render_acceptance_report, run_install_audit, run_objective_audit, run_objective_matrix, run_profile_acceptance, run_transcript_acceptance_from_file, run_transcript_acceptance_from_text


def test_profile_acceptance_checks_codex_and_claude_skill_roots(tmp_path: Path) -> None:
    report = run_profile_acceptance(Path.cwd(), "business", tmp_path / "business")

    assert report["status"] == "pass"
    check_names = {check["name"] for check in report["checks"]}
    assert (tmp_path / "business" / "skills").resolve().as_posix() in check_names
    assert (tmp_path / "business" / ".agents" / "skills").resolve().as_posix() in check_names
    assert (tmp_path / "business" / ".claude" / "skills").resolve().as_posix() in check_names
    assert "session-start-bootstrap" in check_names


def test_profile_acceptance_codex_only_does_not_require_claude_skill_root(tmp_path: Path) -> None:
    report = run_profile_acceptance(Path.cwd(), "codex-only", tmp_path / "codex-only")

    assert report["status"] == "pass"
    check_names = {check["name"] for check in report["checks"]}
    assert (tmp_path / "codex-only" / ".agents" / "skills").resolve().as_posix() in check_names
    assert (tmp_path / "codex-only" / ".claude" / "skills").resolve().as_posix() not in check_names


def test_acceptance_report_text_is_scan_friendly(tmp_path: Path) -> None:
    report = run_profile_acceptance(Path.cwd(), "codex-only", tmp_path / "codex-only")

    text = render_acceptance_report(report, fmt="text")

    assert "acceptance=pass profile=codex-only" in text
    assert "session-start-bootstrap" in text


def test_handoff_acceptance_writes_valid_order_and_result_contract(tmp_path: Path) -> None:
    from agent_careflow.acceptance import run_handoff_acceptance

    report = run_handoff_acceptance(tmp_path / "handoff")

    assert report["status"] == "pass"
    check_names = {check["name"] for check in report["checks"]}
    assert "handoff-artifacts" in check_names
    assert "claude-handoff-prompt" in check_names
    assert "codex-handoff-prompt" in check_names
    assert (tmp_path / "handoff" / ".careflow" / "cases" / "ACF-HANDOFF" / "results" / "ORD-HANDOFF.result.md").exists()


def _install_expected_links(home: Path, careflow_repo: Path, *, codex: bool = True, claude: bool = True) -> None:
    if codex:
        (home / ".codex").mkdir(parents=True)
        (home / ".codex" / "hooks.json").symlink_to(careflow_repo / "rules" / "codex" / "hooks.json")
        (home / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
        (home / ".local" / "bin").mkdir(parents=True)
        (home / ".local" / "bin" / "codex-careflow").write_text(
            '#!/usr/bin/env bash\n# dotfiles managed codex-careflow\nexec agent-careflow codex exec "$@"\n',
            encoding="utf-8",
        )
        (home / ".agents" / "skills").mkdir(parents=True)
        for skill in REQUIRED_SKILLS:
            (home / ".agents" / "skills" / skill).symlink_to(careflow_repo / "skills" / skill)
    if claude:
        (home / ".claude" / "skills").mkdir(parents=True)
        (home / ".claude" / "settings.json").write_text('{"hooks":{"SessionStart":[{"hooks":[{"command":"agent-careflow hook claude session-start"}]}]}}\n', encoding="utf-8")
        (home / ".local" / "bin").mkdir(parents=True, exist_ok=True)
        (home / ".local" / "bin" / "claude-careflow").write_text(
            '#!/usr/bin/env bash\n# dotfiles managed claude-careflow\nagent-careflow dashboard --write >/dev/null\nagent-careflow workspace --write >/dev/null\nexec claude "$@"\n',
            encoding="utf-8",
        )
        for skill in REQUIRED_SKILLS:
            (home / ".claude" / "skills" / skill).symlink_to(careflow_repo / "skills" / skill)


def test_install_audit_passes_for_expected_codex_and_claude_links(tmp_path: Path) -> None:
    home = tmp_path / "home"
    careflow_repo = Path.cwd()
    _install_expected_links(home, careflow_repo)

    report = run_install_audit(careflow_repo, home, ["codex", "claude"])

    assert report["status"] == "pass"
    check_names = {check["name"] for check in report["checks"]}
    assert "codex-hooks" in check_names
    assert "codex-careflow-launcher" in check_names
    assert "codex-skill-using-agent-careflow" in check_names
    assert "claude-settings-careflow-hook" in check_names
    assert "claude-careflow-launcher" in check_names
    assert "claude-skill-using-agent-careflow" in check_names


def test_install_audit_fails_on_unmanaged_codex_skill_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    careflow_repo = Path.cwd()
    _install_expected_links(home, careflow_repo, codex=True, claude=False)
    skill_path = home / ".agents" / "skills" / "using-agent-careflow"
    skill_path.unlink()
    skill_path.mkdir()

    report = run_install_audit(careflow_repo, home, ["codex"])

    assert report["status"] == "fail"
    failure = next(check for check in report["checks"] if check["name"] == "codex-skill-using-agent-careflow")
    assert "unmanaged non-symlink" in failure["details"]


def test_install_audit_fails_when_codex_hooks_are_not_enabled(tmp_path: Path) -> None:
    home = tmp_path / "home"
    careflow_repo = Path.cwd()
    _install_expected_links(home, careflow_repo, codex=True, claude=False)
    (home / ".codex" / "config.toml").write_text("[features]\n", encoding="utf-8")

    report = run_install_audit(careflow_repo, home, ["codex"])

    assert report["status"] == "fail"
    failure = next(check for check in report["checks"] if check["name"] == "codex-config-hooks-enabled")
    assert "hooks = true" in failure["details"]


def test_install_audit_fails_when_codex_careflow_launcher_is_missing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    careflow_repo = Path.cwd()
    _install_expected_links(home, careflow_repo, codex=True, claude=False)
    (home / ".local" / "bin" / "codex-careflow").unlink()

    report = run_install_audit(careflow_repo, home, ["codex"])

    assert report["status"] == "fail"
    failure = next(check for check in report["checks"] if check["name"] == "codex-careflow-launcher")
    assert "missing:" in failure["details"]


def test_install_audit_fails_when_claude_careflow_launcher_is_missing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    careflow_repo = Path.cwd()
    _install_expected_links(home, careflow_repo, codex=False, claude=True)
    (home / ".local" / "bin" / "claude-careflow").unlink()

    report = run_install_audit(careflow_repo, home, ["claude"])

    assert report["status"] == "fail"
    failure = next(check for check in report["checks"] if check["name"] == "claude-careflow-launcher")
    assert "missing:" in failure["details"]


def test_transcript_acceptance_passes_for_careflow_contract_text() -> None:
    transcript = """using-agent-careflow
PLAN_FILE: .careflow/cases/ACF-1/PLAN.md
ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md
SUBPLAN_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md
EXPECTED_RESULT_PATH: .careflow/cases/ACF-1/results/ORD-1.result.md
RESULT: write the expected result artifact before completion
"""

    report = run_transcript_acceptance_from_text(transcript)

    assert report["status"] == "pass"


def test_transcript_acceptance_fails_when_order_contract_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "transcript.txt"
    path.write_text("using-agent-careflow\nPLAN_FILE: .careflow/cases/ACF-1/PLAN.md\nRESULT only\n", encoding="utf-8")

    report = run_transcript_acceptance_from_file(path)

    assert report["status"] == "fail"
    details = report["checks"][0]["details"]
    assert "ORDER_FILE" in details
    assert "EXPECTED_RESULT_PATH" in details


def test_claude_stream_json_helpers_preserve_hook_context_tokens() -> None:
    raw = '{"type":"system","subtype":"hook_response","hook_event":"SessionStart","output":"Skill: using-agent-careflow PLAN_FILE EXPECTED_RESULT_PATH"}\nnot-json\n{"type":"system","subtype":"init","skills":["using-agent-careflow"]}\n'

    events = _parse_json_lines(raw)
    text = _event_text(events)

    assert len(events) == 2
    assert "SessionStart" in text
    assert "PLAN_FILE" in text
    assert "using-agent-careflow" in text


def _write_objective_audit_fixture(root: Path, *, open_incident: bool = False, placeholder_claude_review: bool = False, user_prompt_verdict: str = "pass", mitigation_accepted: bool = False) -> str:
    case_id = "ACF-AUDIT"
    case_root = root / ".careflow" / "cases" / case_id
    for dirname in ("orders", "results", "evidence", "incidents", "reviews", "learnings"):
        (case_root / dirname).mkdir(parents=True, exist_ok=True)
    (root / ".careflow" / "state.json").write_text(
        '{"active_case":"ACF-AUDIT","active_order":"ORD-001","expected_result_path":".careflow/cases/ACF-AUDIT/results/ORD-001.result.md","phase":"ordered"}\n',
        encoding="utf-8",
    )
    (case_root / "CASE.yaml").write_text("case_id: ACF-AUDIT\nstatus: active\nphase: ordered\n", encoding="utf-8")
    (case_root / "PLAN.md").write_text("# PLAN\n\nobjective audit fixture\n", encoding="utf-8")
    (case_root / "orders" / "ORD-001.order.md").write_text(
        "PLAN_FILE: .careflow/cases/ACF-AUDIT/PLAN.md\n"
        "ORDER_FILE: .careflow/cases/ACF-AUDIT/orders/ORD-001.order.md\n"
        "SUBPLAN_FILE: .careflow/cases/ACF-AUDIT/orders/ORD-001.order.md\n"
        "EXPECTED_RESULT_PATH: .careflow/cases/ACF-AUDIT/results/ORD-001.result.md\n"
        "CASE_ID: ACF-AUDIT\nORDER_ID: ORD-001\nASSIGNED_ROLE: implementer\nTARGET_TOOL: codex\n",
        encoding="utf-8",
    )
    (case_root / "results" / "ORD-001.result.md").write_text(
        "order_id: ORD-001\ncase_id: ACF-AUDIT\nstatus: complete\n\n"
        "install-audit live-codex live-claude runtime-probe\n",
        encoding="utf-8",
    )
    (case_root / "evidence" / "git-status.txt").write_text("$ git status --short\nclean\n", encoding="utf-8")
    probe_record = {
        "schema": "codex.runtime_probe.v1",
        "recorded_at": "2026-06-14T00:00:00+00:00",
        "codex_version": "codex-cli test",
        "probe": "hook_payload_capture",
        "event": "UserPromptSubmit",
        "command": ["codex", "exec"],
        "cwd": root.as_posix(),
        "input_payload": {"prompt": "synthetic patient MRN ABC123456"},
        "stdout": "" if user_prompt_verdict == "pass" else "not blocked",
        "stderr": "",
        "exit_code": 0,
        "verdict": user_prompt_verdict,
        "notes": "UserPromptSubmit hook payload captured before model input" if user_prompt_verdict == "pass" else "UserPromptSubmit hook payload was not observed",
    }
    (case_root / "evidence" / "ORD-007-user-prompt-submit-probe.jsonl").write_text(json.dumps(probe_record, sort_keys=True) + "\n", encoding="utf-8")
    wrapper_record = {
        "schema": "codex.runtime_probe.v1",
        "recorded_at": "2026-06-14T00:00:00+00:00",
        "codex_version": "codex-cli test",
        "probe": "agent-careflow-codex-wrapper-preflight",
        "event": "UserPromptSubmit",
        "command": ["agent-careflow", "codex", "exec", "--", "debug patient MRN: ABC123456"],
        "cwd": root.as_posix(),
        "input_payload": {"prompt": "debug patient MRN: ABC123456", "blocked": True},
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "verdict": "pass",
        "notes": "wrapper blocked rejected prompt before Codex invocation",
    }
    (case_root / "evidence" / "ORD-009-codex-wrapper-preflight.jsonl").write_text(json.dumps(wrapper_record, sort_keys=True) + "\n", encoding="utf-8")
    install_audit_report = {
        "schema": "agent-careflow.acceptance.install_audit.v1",
        "target": (root / "fixture-home").as_posix(),
        "control_repo": root.as_posix(),
        "tools": ["codex", "claude"],
        "status": "pass",
        "checks": [
            {"name": "codex-careflow-launcher", "status": "pass", "details": "launcher contains agent-careflow codex exec"},
            {"name": "claude-careflow-launcher", "status": "pass", "details": "launcher contains agent-careflow workspace --write"},
            {"name": "claude-careflow-launcher-delegates", "status": "pass", "details": "launcher contains exec claude"},
        ],
    }
    (case_root / "evidence" / "ORD-010-install-audit.json").write_text(json.dumps(install_audit_report, sort_keys=True) + "\n", encoding="utf-8")
    if mitigation_accepted:
        mitigation = {
            "schema": "agent-careflow.acceptance.codex_exec_mitigation.v1",
            "case_id": case_id,
            "incident_id": "INC-001-codex-exec-user-prompt-submit-not-observed",
            "status": "accepted",
            "policy_boundary": "non_interactive_codex_exec_must_use_guarded_launcher",
            "native_user_prompt_submit_status": "runtime_observed_failing",
            "required_checks": [
                "codex-wrapper-preflight",
                "codex-careflow-launcher-distribution",
            ],
            "accepted_at": "2026-06-15T00:00:00+09:00",
            "accepted_by": "objective-audit-fixture",
        }
        (case_root / "evidence" / "ORD-011-codex-exec-mitigation.json").write_text(json.dumps(mitigation, sort_keys=True) + "\n", encoding="utf-8")

    for skill in REQUIRED_SKILLS:
        skill_dir = root / "skills" / skill
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_dir.joinpath("SKILL.md").write_text(
            f"---\nname: {skill}\n---\n# {skill}\n"
            "PLAN_FILE: ORDER_FILE: SUBPLAN_FILE: EXPECTED_RESULT_PATH: CASE_ID: ORDER_ID: ASSIGNED_ROLE: TARGET_TOOL:\n"
            ".careflow PLAN ORDER RESULT\n",
            encoding="utf-8",
        )
    superpowers = root / "third_party" / "superpowers" / "skills" / "using-superpowers"
    superpowers.mkdir(parents=True, exist_ok=True)
    superpowers.joinpath("SKILL.md").write_text("# Using Superpowers\n", encoding="utf-8")
    (root / "rules" / "codex").mkdir(parents=True, exist_ok=True)
    (root / "rules" / "codex" / "hooks.json").write_text('{"SessionStart":"agent-careflow hook codex session-start","Stop":"agent-careflow hook codex stop"}\n', encoding="utf-8")
    (root / "rules" / "claude").mkdir(parents=True, exist_ok=True)
    (root / "rules" / "claude" / "settings.json").write_text('{"SessionStart":"agent-careflow hook claude session-start","Stop":"agent-careflow hook claude stop"}\n', encoding="utf-8")
    (root / "src" / "agent_careflow").mkdir(parents=True, exist_ok=True)
    (root / "src" / "agent_careflow" / "context.py").write_text("worktrees root resolver\n", encoding="utf-8")
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "test_context.py").write_text("worktrees root resolver test\n", encoding="utf-8")

    (root / ".careflow" / "INDEX.md").write_text("ACF-AUDIT ORD-001 .careflow/cases/ACF-AUDIT/results/ORD-001.result.md\n", encoding="utf-8")
    (root / ".agent").mkdir()
    (root / ".agent" / "current.md").write_text("ACF-AUDIT ORD-001 .careflow/cases/ACF-AUDIT/results/ORD-001.result.md ../.careflow/cases/ACF-AUDIT/PLAN.md\n", encoding="utf-8")
    for name in ("reviews", "learnings", "incidents"):
        (root / ".agent" / name).mkdir()
        (root / ".agent" / name / "README.md").write_text("../../.careflow/cases/ACF-AUDIT\n", encoding="utf-8")

    learning = case_root / "learnings" / "LRN-001-audit.md"
    learning.write_text("learning_id: LRN-001-audit\ncase_id: ACF-AUDIT\nstatus: promoted\npromoted_to: docs/learnings/audit.md\n", encoding="utf-8")
    (root / "docs" / "learnings").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "learnings" / "audit.md").write_text("source_learning: .careflow/cases/ACF-AUDIT/learnings/LRN-001-audit.md\n", encoding="utf-8")

    for tool in ("codex", "claude"):
        body = "Artifact-level review placeholder because auth unavailable" if tool == "claude" and placeholder_claude_review else "Concrete review evidence"
        (case_root / "reviews" / f"REVIEW-{tool}.review.md").write_text(
            f"review_id: REVIEW-{tool}\ncase_id: ACF-AUDIT\ntool: {tool}\nstatus: pass\n\n"
            "## Scope\n\nPLAN, ORDER, RESULT, and evidence.\n\n"
            f"## Findings\n\n- None. {body}\n\n"
            "## Evidence reviewed\n\n- Concrete test evidence.\n\n"
            "## Recommendation\n\nPass.\n",
            encoding="utf-8",
        )
    if open_incident:
        (case_root / "incidents" / "INC-001-codex-exec-user-prompt-submit-not-observed.md").write_text(
            "incident_id: INC-001\ncase_id: ACF-AUDIT\nstatus: open\ntrigger: codex_exec_user_prompt_submit_not_observed\n",
            encoding="utf-8",
        )
    return case_id


def test_objective_audit_passes_when_original_requirement_evidence_exists(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path)

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "pass"
    check_names = {check["name"] for check in report["checks"]}
    assert "superpowers-vendored" in check_names
    assert "fixed-handoff-contract" in check_names
    assert "review-dual-codex-claude" in check_names
    assert "runtime-residuals-clear" in check_names
    assert "codex-user-prompt-submit-coverage" in check_names
    assert "codex-user-prompt-submit-proof" in check_names
    assert "codex-wrapper-preflight" in check_names
    assert "codex-careflow-launcher-distribution" in check_names
    assert "claude-careflow-launcher-distribution" in check_names


def test_objective_audit_fails_for_open_incident_and_placeholder_claude_review(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path, open_incident=True, placeholder_claude_review=True)

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "fail"
    failures = {check["name"]: check["details"] for check in report["checks"] if check["status"] == "fail"}
    assert "open-incidents" in failures
    assert "claude-review-not-placeholder" in failures
    assert "codex-user-prompt-submit-residual" in failures

def test_objective_audit_business_profile_requires_non_placeholder_claude_review(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path, placeholder_claude_review=True)

    report = run_objective_audit(tmp_path, case_id, profile="business")

    assert report["status"] == "fail"
    failures = {check["name"]: check["details"] for check in report["checks"] if check["status"] == "fail"}
    assert "review-dual-codex-claude" in failures
    assert "claude-review-not-placeholder" in failures


def test_objective_audit_private_profile_allows_codex_only_review(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path, placeholder_claude_review=True)

    report = run_objective_audit(tmp_path, case_id, profile="private")

    assert report["status"] == "pass"
    check_names = {check["name"] for check in report["checks"]}
    assert "review-private-codex-only" in check_names
    assert "review-dual-codex-claude" not in check_names
    assert "claude-review-not-placeholder" not in check_names

def test_objective_audit_fails_when_user_prompt_submit_probe_is_missing(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path)
    probe = tmp_path / ".careflow" / "cases" / case_id / "evidence" / "ORD-007-user-prompt-submit-probe.jsonl"
    probe.unlink()

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "fail"
    failures = {check["name"]: check["details"] for check in report["checks"] if check["status"] == "fail"}
    assert "codex-user-prompt-submit-proof" in failures
    assert "missing" in failures["codex-user-prompt-submit-proof"]


def test_objective_audit_fails_when_user_prompt_submit_probe_is_runtime_fail_without_mitigation(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path, user_prompt_verdict="fail")

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "fail"
    failures = {check["name"]: check["details"] for check in report["checks"] if check["status"] == "fail"}
    assert "codex-user-prompt-submit-coverage" in failures
    assert "runtime-observed failing" in failures["codex-user-prompt-submit-coverage"]


def test_objective_audit_accepts_codex_exec_mitigation_for_runtime_fail(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path, user_prompt_verdict="fail", mitigation_accepted=True)

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "pass"
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["codex-user-prompt-submit-proof"]["status"] == "fail"
    assert checks["codex-user-prompt-submit-coverage"]["status"] == "pass"
    assert "accepted mitigation" in checks["codex-user-prompt-submit-coverage"]["details"]


def test_objective_matrix_maps_original_requirements_and_passes_private_profile(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(
        tmp_path,
        placeholder_claude_review=True,
        user_prompt_verdict="fail",
        mitigation_accepted=True,
    )

    report = run_objective_matrix(tmp_path, case_id, profile="private")

    assert report["status"] == "pass"
    requirement_ids = {item["id"] for item in report["requirements"]}
    assert {
        "unified_tool_settings",
        "durable_planning",
        "agent_workspace_outputs",
        "troubles_and_learnings",
        "fixed_handoff_contract",
        "order_as_subplan",
        "superpowers_style_enforcement",
        "activation_forgetting_failure_mode",
        "multi_repo_worktree_layout",
        "distribution_launchers",
        "business_private_review_policy",
        "objective_completion_audit",
    }.issubset(requirement_ids)
    activation = next(item for item in report["requirements"] if item["id"] == "activation_forgetting_failure_mode")
    assert "codex-user-prompt-submit-coverage" in activation["checks"]
    assert "accepted mitigation" in activation["details"]
    text = render_acceptance_report(report, fmt="text")
    assert "acceptance=pass objective-matrix" in text
    assert "objective-unified_tool_settings" in text


def test_objective_matrix_business_profile_keeps_real_claude_review_strict(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path, placeholder_claude_review=True)

    report = run_objective_matrix(tmp_path, case_id, profile="business")

    assert report["status"] == "fail"
    requirements = {item["id"]: item for item in report["requirements"]}
    assert requirements["business_private_review_policy"]["status"] == "fail"
    assert "review-dual-codex-claude" in requirements["business_private_review_policy"]["checks"]
    assert "claude-review-not-placeholder" in requirements["business_private_review_policy"]["checks"]

def test_objective_audit_fails_when_codex_wrapper_preflight_evidence_is_missing(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path)
    probe = tmp_path / ".careflow" / "cases" / case_id / "evidence" / "ORD-009-codex-wrapper-preflight.jsonl"
    probe.unlink()

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "fail"
    failures = {check["name"]: check["details"] for check in report["checks"] if check["status"] == "fail"}
    assert "codex-wrapper-preflight" in failures
    assert "missing" in failures["codex-wrapper-preflight"]


def test_objective_audit_fails_when_codex_launcher_distribution_evidence_is_missing(tmp_path: Path) -> None:
    case_id = _write_objective_audit_fixture(tmp_path)
    evidence = tmp_path / ".careflow" / "cases" / case_id / "evidence" / "ORD-010-install-audit.json"
    evidence.unlink()

    report = run_objective_audit(tmp_path, case_id)

    assert report["status"] == "fail"
    failures = {check["name"]: check["details"] for check in report["checks"] if check["status"] == "fail"}
    assert "codex-careflow-launcher-distribution" in failures
    assert "missing" in failures["codex-careflow-launcher-distribution"]

