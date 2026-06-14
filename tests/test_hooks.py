from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.hooks import claude, codex, cursor
from agent_careflow.hooks.common import evaluate_lifecycle_hook, evaluate_pre_tool_use, load_payload, record_hook_incident
from agent_careflow.artifacts import sha256_file
from agent_careflow.policy.decisions import DecisionStatus

FIXTURES = Path(__file__).parent / "fixtures" / "hooks"

def test_codex_pre_tool_use_blocks_dangerous_bash() -> None:
    payload = load_payload((FIXTURES / "codex_pre_tool_use_bash_danger.json").read_text(encoding="utf-8"))
    decision = evaluate_pre_tool_use(payload)
    rendered = json.loads(codex.render_pre_tool_use(decision))

    assert decision.status == DecisionStatus.DENY
    assert rendered["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "git reset --hard" in rendered["hookSpecificOutput"]["permissionDecisionReason"]

def test_claude_pre_tool_use_warns_when_context_missing_by_default() -> None:
    payload = load_payload((FIXTURES / "claude_pre_tool_use_write_missing_context.json").read_text(encoding="utf-8"))
    decision = evaluate_pre_tool_use(payload)
    rendered = json.loads(claude.render_pre_tool_use(decision))

    assert decision.status == DecisionStatus.WARN
    assert "systemMessage" in rendered

def test_missing_context_can_fail_closed() -> None:
    payload = load_payload((FIXTURES / "claude_pre_tool_use_write_missing_context.json").read_text(encoding="utf-8"))
    decision = evaluate_pre_tool_use(payload, on_missing_context="deny")

    assert decision.status == DecisionStatus.DENY
    assert "case_id" in decision.reason

def test_cursor_renderer_uses_generic_block_shape() -> None:
    payload = load_payload((FIXTURES / "codex_pre_tool_use_bash_danger.json").read_text(encoding="utf-8"))
    decision = evaluate_pre_tool_use(payload)
    rendered = json.loads(cursor.render_pre_tool_use(decision))

    assert rendered == {"decision": "block", "reason": "git reset --hard is blocked by policy"}

def test_codex_user_prompt_submit_blocks_secret() -> None:
    from agent_careflow.hooks.common import evaluate_user_prompt_submit

    decision = evaluate_user_prompt_submit({"prompt": "please use api_key=sk-abcdefghijklmnopqrstuvwxyz123456"})
    rendered = json.loads(codex.render_user_prompt_submit(decision))

    assert rendered["continue"] is False
    assert "API key" in rendered["stopReason"]

def test_codex_user_prompt_submit_blocks_phi_like_identifier() -> None:
    from agent_careflow.hooks.common import evaluate_user_prompt_submit

    decision = evaluate_user_prompt_submit({"prompt": "debug patient MRN: ABC123456 in this fixture"})
    rendered = json.loads(codex.render_user_prompt_submit(decision))

    assert rendered["continue"] is False
    assert "medical record" in rendered["stopReason"]

def test_codex_user_prompt_submit_allows_benign_prompt() -> None:
    from agent_careflow.hooks.common import evaluate_user_prompt_submit

    decision = evaluate_user_prompt_submit({"prompt": "refactor the validator tests"})

    assert codex.render_user_prompt_submit(decision) == "{}"

def test_codex_stop_renders_json_only() -> None:
    decision = evaluate_lifecycle_hook({"hook_event_name": "Stop"})

    assert codex.render_stop(decision) == "{}"

def test_claude_subagent_events_render_json() -> None:
    decision = evaluate_lifecycle_hook({"hook_event_name": "SubagentStart"})

    assert claude.render_subagent_start(decision) == "{}"
    assert claude.render_subagent_stop(decision) == "{}"

def test_hook_denial_can_record_incident(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    (case / "incidents").mkdir(parents=True)
    payload = {
        "cwd": str(tmp_path),
        "case_id": "ACF-1",
        "tool_input": {"command": 'git reset --hard HEAD'},
    }
    decision = evaluate_pre_tool_use(payload)

    path = record_hook_incident(payload, decision)

    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "hook_policy_denied" in text
    assert ('git reset --' + 'hard') in text


def test_hybrid_gate_denies_mutating_write_without_case() -> None:
    payload = load_payload((FIXTURES / "claude_pre_tool_use_write_missing_context.json").read_text(encoding="utf-8"))
    decision = evaluate_pre_tool_use(payload, on_missing_context="hybrid")

    assert decision.status == DecisionStatus.DENY
    assert "case_id" in decision.reason


def test_hybrid_gate_warns_for_read_only_command_without_case() -> None:
    decision = evaluate_pre_tool_use(
        {
            "cwd": ".",
            "tool_name": "Bash",
            "tool_input": {"command": "git status --short"},
        },
        on_missing_context="hybrid",
    )

    assert decision.status == DecisionStatus.ALLOW


def test_hybrid_gate_allows_non_file_non_command_tool_without_noise() -> None:
    decision = evaluate_pre_tool_use(
        {
            "cwd": ".",
            "tool_name": "update_plan",
            "tool_input": {"plan": []},
        },
        on_missing_context="hybrid",
    )

    assert decision.status == DecisionStatus.ALLOW
    assert "no careflow policy surface" in decision.reason


def test_fail_closed_allows_non_file_non_command_tool_without_noise() -> None:
    decision = evaluate_pre_tool_use(
        {
            "cwd": ".",
            "tool_name": "functions.update_plan",
            "tool_input": {"plan": []},
        },
        on_missing_context="deny",
    )

    assert decision.status == DecisionStatus.ALLOW
    assert "no careflow policy surface" in decision.reason


def test_hybrid_gate_denies_pathless_namespaced_mutating_tool_without_case() -> None:
    decision = evaluate_pre_tool_use(
        {
            "cwd": ".",
            "tool_name": "functions.apply_patch",
            "tool_input": {},
        },
        on_missing_context="hybrid",
    )

    assert decision.status == DecisionStatus.DENY
    assert "mutating tool" in decision.reason


def test_hybrid_stop_warns_completion_claim_without_active_case(tmp_path: Path) -> None:
    decision = evaluate_lifecycle_hook(
        {
            "cwd": tmp_path.as_posix(),
            "hook_event_name": "Stop",
            "last_assistant_message": "Implementation complete.",
        }
    )

    assert decision.status == DecisionStatus.WARN
    assert "no active careflow case_id" in decision.reason


def test_hybrid_stop_blocks_completion_claim_with_case_but_without_result(tmp_path: Path) -> None:
    decision = evaluate_lifecycle_hook(
        {
            "cwd": tmp_path.as_posix(),
            "hook_event_name": "Stop",
            "case_id": "ACF-1",
            "last_assistant_message": "Implementation complete.",
        }
    )

    assert decision.status == DecisionStatus.DENY
    assert "expected_result_path" in decision.reason


def test_hybrid_stop_allows_completion_when_expected_result_exists(tmp_path: Path) -> None:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    result = case / "results" / "ORD-001.result.md"
    result.parent.mkdir(parents=True)
    result.write_text("result", encoding="utf-8")

    decision = evaluate_lifecycle_hook(
        {
            "cwd": str(tmp_path),
            "hook_event_name": "Stop",
            "case_id": "ACF-1",
            "expected_result_path": result.relative_to(tmp_path).as_posix(),
            "last_assistant_message": "Implementation complete.",
        }
    )

    assert decision.status == DecisionStatus.ALLOW


def test_hybrid_gate_uses_state_context_from_workflow_root(tmp_path: Path) -> None:
    from agent_careflow.context import write_state

    root = tmp_path / "root-app"
    repo = root / ".worktrees" / "feature-auth" / "backend"
    case = root / ".careflow" / "cases" / "ACF-1"
    orders = case / "orders"
    orders.mkdir(parents=True)
    (case / "CASE.yaml").write_text(
        "case_id: ACF-1\ntitle: Test\nrisk: C1\nphase: implementation\nstatus: open\ncreated_at: now\nowner: test\nallowed_scope:\n  - backend/src/app.py\n",
        encoding="utf-8",
    )
    (case / "PLAN.md").write_text(
        "case_id: ACF-1\nstatus: in_progress\nrisk: C1\nowner: test\n\n## Objective\n\nTest.\n",
        encoding="utf-8",
    )
    plan = case / "PLAN.md"
    order = orders / "ORD-001.order.md"
    order.write_text(
        f"order_id: ORD-001\ncase_id: ACF-1\nassigned_role: implementer\nplan_path: .careflow/cases/ACF-1/PLAN.md\nplan_hash: {sha256_file(plan)}\nallowed_actions:\n  - write backend/src/app.py\nforbidden_actions:\n  - outside scope\ndeliverables:\n  - result\nexpected_result_path: .careflow/cases/ACF-1/results/ORD-001.result.md\ncompletion_criteria:\n  - done\n",
        encoding="utf-8",
    )
    repo.mkdir(parents=True)
    write_state(root, {"active_case": "ACF-1", "active_order": "ORD-001", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-001.result.md"})

    decision = evaluate_pre_tool_use(
        {
            "cwd": repo.as_posix(),
            "tool_name": "Write",
            "tool_input": {"file_path": "backend/src/app.py"},
        },
        on_missing_context="hybrid",
    )

    assert decision.status != DecisionStatus.DENY
    assert "case_id" not in decision.reason


def test_hybrid_stop_uses_expected_result_from_state(tmp_path: Path) -> None:
    from agent_careflow.context import write_state

    root = tmp_path / "root-app"
    repo = root / "backend"
    result = root / ".careflow" / "cases" / "ACF-1" / "results" / "ORD-001.result.md"
    result.parent.mkdir(parents=True)
    result.write_text("result", encoding="utf-8")
    repo.mkdir(parents=True)
    write_state(root, {"active_case": "ACF-1", "active_order": "ORD-001", "expected_result_path": ".careflow/cases/ACF-1/results/ORD-001.result.md"})

    decision = evaluate_lifecycle_hook(
        {
            "cwd": repo.as_posix(),
            "hook_event_name": "Stop",
            "last_assistant_message": "Implementation complete.",
        }
    )

    assert decision.status == DecisionStatus.ALLOW
