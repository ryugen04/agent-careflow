from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_careflow.bootstrap_context import bootstrap_context
from agent_careflow.context import CareflowContext, resolve_context
from agent_careflow.artifacts import ValidationError
from agent_careflow.policy.decisions import Decision, DecisionStatus, allow, deny, warn
from agent_careflow.policy.engine import PolicyEngine
from agent_careflow.policy.prompt_policy import check_prompt_text, extract_prompt_text


def load_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid hook JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("hook payload must be a JSON object")
    return payload


def hook_context(payload: dict[str, Any]) -> CareflowContext:
    return resolve_context(payload)


def extract_command(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or tool_input.get("cmd")
        if isinstance(command, str):
            return command
    command = payload.get("command")
    return command if isinstance(command, str) else None


def extract_tool_name(payload: dict[str, Any]) -> str:
    value = payload.get("tool_name") or payload.get("tool") or payload.get("name")
    return str(value or "")


def extract_file_path(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    candidates: list[Any] = []
    if isinstance(tool_input, dict):
        candidates.extend([tool_input.get("file_path"), tool_input.get("path"), tool_input.get("target_file")])
    candidates.extend([payload.get("file_path"), payload.get("path")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


MUTATING_TOOLS = {"apply_patch", "Edit", "Write", "MultiEdit"}
MUTATING_COMMAND_MARKERS = (
    "git add",
    "git commit",
    "git push",
    "git merge",
    "git rebase",
    "git reset",
    "git checkout",
    "git switch",
    "npm install",
    "pnpm install",
    "yarn install",
    "pip install",
    "cargo add",
    "go get",
    "rm ",
    "mv ",
    "cp ",
    ">",
)
COMPLETION_MARKERS = (
    "done",
    "complete",
    "completed",
    "fixed",
    "implemented",
    "passes",
    "pass",
    "完了",
    "実装しました",
    "修正しました",
    "通りました",
)


def command_needs_careflow_context(command: str) -> bool:
    lowered = command.lower()
    return any(marker in lowered for marker in MUTATING_COMMAND_MARKERS)


def bypass_requested(payload: dict[str, Any]) -> bool:
    careflow = payload.get("careflow") if isinstance(payload.get("careflow"), dict) else {}
    for key in ("bypass", "bypass_reason", "user_bypass", "user_requested_bypass"):
        value = payload.get(key, careflow.get(key))
        if isinstance(value, bool) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def missing_context_decision(payload: dict[str, Any], reason: str, *, on_missing_context: str) -> Decision:
    if bypass_requested(payload):
        return warn(f"careflow bypass requested by user: {reason}")
    if on_missing_context in {"deny", "hybrid"}:
        return deny(reason)
    return warn(reason)


def evaluate_session_start(payload: dict[str, Any]) -> Decision:
    return allow(bootstrap_context())


def evaluate_pre_tool_use(payload: dict[str, Any], *, on_missing_context: str = "warn") -> Decision:
    context = hook_context(payload)
    engine = PolicyEngine(context.workflow_root)
    command = extract_command(payload)
    if command:
        decision = engine.check_command(command)
        if decision.status == DecisionStatus.DENY:
            return decision
    file_path = extract_file_path(payload)
    tool_name = extract_tool_name(payload)
    if file_path:
        if not context.case_id:
            return missing_context_decision(
                payload,
                "hook payload is missing careflow case_id; file policy not enforced",
                on_missing_context=on_missing_context,
            )
        try:
            return engine.check_file(
                case_id=context.case_id,
                path=file_path,
                operation="write",
                order_id=context.order_id,
            )
        except ValidationError as exc:
            return deny(str(exc))
    if command:
        if on_missing_context == "hybrid" and not context.case_id and command_needs_careflow_context(command):
            return missing_context_decision(
                payload,
                "mutating command requires active careflow case_id/order_id",
                on_missing_context=on_missing_context,
            )
        return allow("command allowed")
    if tool_name in MUTATING_TOOLS:
        return missing_context_decision(
            payload,
            "mutating tool requires careflow case_id/order_id and a supported file path",
            on_missing_context=on_missing_context,
        )
    if on_missing_context == "deny":
        return deny("hook payload did not contain a supported command or file path")
    return allow("tool has no careflow policy surface")


def evaluate_permission_request(payload: dict[str, Any], *, on_missing_context: str = "warn") -> Decision:
    return evaluate_pre_tool_use(payload, on_missing_context=on_missing_context)


def evaluate_user_prompt_submit(payload: dict[str, Any]) -> Decision:
    return check_prompt_text(extract_prompt_text(payload))


def dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))

def evaluate_stop(payload: dict[str, Any]) -> Decision:
    message = str(payload.get("last_assistant_message") or payload.get("message") or "")
    if not any(marker in message.lower() for marker in COMPLETION_MARKERS):
        return allow("stop accepted")
    context = hook_context(payload)
    careflow = payload.get("careflow") if isinstance(payload.get("careflow"), dict) else {}
    result_path = payload.get("expected_result_path") or careflow.get("expected_result_path") or context.expected_result_path
    if not context.case_id:
        return warn("completion claim has no active careflow case_id; start or activate a case for enforced close validation")
    if result_path:
        candidate = Path(str(result_path))
        if not candidate.is_absolute():
            candidate = context.workflow_root / candidate
        if candidate.exists():
            return allow("completion evidence result exists")
    return missing_context_decision(
        payload,
        "completion claim requires expected_result_path to exist before stopping",
        on_missing_context="hybrid",
    )


def evaluate_lifecycle_hook(payload: dict[str, Any]) -> Decision:
    event = str(payload.get("hook_event_name") or "")
    if event == "SessionStart":
        return evaluate_session_start(payload)
    if event == "Stop" or "last_assistant_message" in payload:
        return evaluate_stop(payload)
    return allow(f"{payload.get('hook_event_name') or 'hook'} accepted")


def record_hook_incident(payload: dict[str, Any], decision: Decision, *, trigger: str = "hook_policy_denied") -> Path | None:
    if decision.status != DecisionStatus.DENY:
        return None
    context = hook_context(payload)
    if not context.case_id:
        return None
    from agent_careflow.lifecycle import new_incident

    path = new_incident(context.workflow_root, context.case_id, trigger)
    text = path.read_text(encoding="utf-8")
    text = text.replace("Triage required.", f"Hook policy denied an action: {decision.reason}")
    path.write_text(text, encoding="utf-8")
    return path
