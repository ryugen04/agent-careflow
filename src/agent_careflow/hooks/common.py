from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_careflow.artifacts import ValidationError
from agent_careflow.policy.decisions import Decision, DecisionStatus, allow, deny, warn
from agent_careflow.policy.engine import PolicyEngine
from agent_careflow.policy.prompt_policy import check_prompt_text, extract_prompt_text


@dataclass(frozen=True)
class HookContext:
    case_id: str | None
    order_id: str | None
    cwd: Path


def load_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid hook JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("hook payload must be a JSON object")
    return payload


def hook_context(payload: dict[str, Any]) -> HookContext:
    careflow = payload.get("careflow") if isinstance(payload.get("careflow"), dict) else {}
    cwd = Path(str(payload.get("cwd") or Path.cwd()))
    case_id = payload.get("case_id") or careflow.get("case_id")
    order_id = payload.get("order_id") or careflow.get("order_id")
    return HookContext(case_id=str(case_id) if case_id else None, order_id=str(order_id) if order_id else None, cwd=cwd)


def extract_command(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or tool_input.get("cmd")
        if isinstance(command, str):
            return command
    command = payload.get("command")
    return command if isinstance(command, str) else None


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


def evaluate_pre_tool_use(payload: dict[str, Any], *, on_missing_context: str = "warn") -> Decision:
    context = hook_context(payload)
    engine = PolicyEngine(context.cwd)
    command = extract_command(payload)
    if command:
        decision = engine.check_command(command)
        if decision.status == DecisionStatus.DENY:
            return decision
    file_path = extract_file_path(payload)
    if file_path:
        if not context.case_id:
            if on_missing_context == "deny":
                return deny("hook payload is missing careflow case_id")
            return warn("hook payload is missing careflow case_id; file policy not enforced")
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
        return allow("command allowed")
    if on_missing_context == "deny":
        return deny("hook payload did not contain a supported command or file path")
    return warn("hook payload did not contain a supported command or file path")


def evaluate_permission_request(payload: dict[str, Any], *, on_missing_context: str = "warn") -> Decision:
    return evaluate_pre_tool_use(payload, on_missing_context=on_missing_context)


def evaluate_user_prompt_submit(payload: dict[str, Any]) -> Decision:
    return check_prompt_text(extract_prompt_text(payload))


def dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))
