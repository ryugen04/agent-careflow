from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.bootstrap_context import bootstrap_context
from agent_careflow.hooks import claude, codex
from agent_careflow.hooks.common import evaluate_session_start, load_payload

FIXTURES = Path(__file__).parent / "fixtures" / "hooks"


def test_bootstrap_context_loads_using_agent_careflow_skill() -> None:
    context = bootstrap_context()

    assert "You have agent-careflow" in context
    assert "Required Artifact Chain" in context
    assert "PLAN_FILE" in context
    assert "ORDER_FILE" in context
    assert "SUBPLAN_FILE" in context
    assert "EXPECTED_RESULT_PATH" in context
    assert "Do not replace them with generic CASE/PLAN/ORDER labels" in context


def test_codex_session_start_renders_additional_context_json() -> None:
    payload = load_payload((FIXTURES / "codex_session_start.json").read_text(encoding="utf-8"))
    rendered = json.loads(codex.render_session_start(evaluate_session_start(payload)))

    assert rendered["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "using-agent-careflow" in rendered["hookSpecificOutput"]["additionalContext"]


def test_claude_session_start_renders_additional_context_json() -> None:
    payload = load_payload((FIXTURES / "codex_session_start.json").read_text(encoding="utf-8"))
    rendered = json.loads(claude.render_session_start(evaluate_session_start(payload)))

    assert rendered["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Required Artifact Chain" in rendered["hookSpecificOutput"]["additionalContext"]
