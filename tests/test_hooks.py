from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.hooks import claude, codex, cursor
from agent_careflow.hooks.common import evaluate_lifecycle_hook, evaluate_pre_tool_use, load_payload, record_hook_incident
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
