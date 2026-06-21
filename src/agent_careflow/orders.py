from __future__ import annotations

from pathlib import Path

from .artifacts import ValidationError, case_dir, parse_front_matter_lines, require_fields, validate_order
from .lifecycle import validate_result

ROLES = {"researcher", "implementer", "verifier", "reviewer", "incident-commander"}
TOOLS = {"codex", "claude", "cursor"}

ROLE_INSTRUCTIONS = {
    "researcher": "Review sources and produce a bounded research result. Do not edit implementation code.",
    "implementer": "Make scoped code changes only within the order boundary and record verification notes.",
    "verifier": "Run verification, collect evidence, and avoid source edits unless explicitly ordered.",
    "reviewer": "Review behavior, risk, and test evidence without changing implementation files.",
    "incident-commander": "Triage incidents, propose corrective action, and avoid unrelated code changes.",
}


def order_path_for(root: Path, case_id: str, order_id: str) -> Path:
    name = order_id if order_id.endswith(".order.md") else f"{order_id}.order.md"
    return case_dir(root, case_id) / "orders" / name


def order_status(root: Path, case_id: str, order_id: str) -> dict[str, object]:
    path = order_path_for(root, case_id, order_id)
    validate_order(path, root)
    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    result_path = root / str(data["expected_result_path"])
    return {
        "order_id": data["order_id"],
        "case_id": data["case_id"],
        "expected_result_path": data["expected_result_path"],
        "complete": result_path.exists(),
    }


def _order_data(root: Path, case_id: str, order_id: str) -> tuple[Path, dict[str, object]]:
    path = order_path_for(root, case_id, order_id)
    validate_order(path, root)
    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    require_fields(data, ["assigned_role", "plan_path", "expected_result_path"], path)
    return path, data


def render_order_handoff_header(root: Path, case_id: str, order_id: str, tool: str) -> str:
    if tool not in TOOLS:
        raise ValidationError(f"unsupported tool: {tool}")
    path, data = _order_data(root, case_id, order_id)
    order_rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    return "\n".join(
        [
            f"PLAN_FILE: {data['plan_path']}",
            f"ORDER_FILE: {order_rel}",
            f"SUBPLAN_FILE: {order_rel}",
            f"EXPECTED_RESULT_PATH: {data['expected_result_path']}",
            f"CASE_ID: {case_id}",
            f"ORDER_ID: {data['order_id']}",
            f"ASSIGNED_ROLE: {data['assigned_role']}",
            f"TARGET_TOOL: {tool}",
        ]
    )


def render_order_prompt(root: Path, case_id: str, order_id: str, tool: str) -> str:
    path, data = _order_data(root, case_id, order_id)
    if tool not in TOOLS:
        raise ValidationError(f"unsupported tool: {tool}")
    role = str(data["assigned_role"])
    role_instruction = ROLE_INSTRUCTIONS.get(role, "Follow the order exactly and keep work inside scope.")
    order_rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    header = render_order_handoff_header(root, case_id, order_id, tool)
    return f"""{header}

You are acting as the {role} for agent-careflow case {case_id} using {tool}.

Required inputs:
- plan_path: {data['plan_path']}
- order_path: {order_rel}
- subplan_path: {order_rel}
- expected_result_path: {data['expected_result_path']}

Role instruction:
{role_instruction}

Execution rules:
- Keep the PLAN_FILE and ORDER_FILE lines visible when handing this to another agent.
- Read the PLAN before taking action.
- Read the ORDER before taking action.
- Treat ORDER_FILE as the subplan for this assignment.
- Keep all edits within the ORDER allowed actions and deliverables.
- Write the RESULT artifact at EXPECTED_RESULT_PATH before claiming completion.
- Do not treat the task as complete unless expected_result_path exists.
- Report blockers explicitly in the expected result file.

Kitty/agmsg lane:
- Start a kitty controller/worker tab with: `careflow-kitty-start --case {case_id} --order {data['order_id']} --controller claude --worker {tool}`
- Use `--controller codex` when Codex should own planning.
- After PLAN/ORDER approval and explicit go, send work with: `careflow-kitty-go --case {case_id} --order {data['order_id']}`
- If blocked, record and notify the controller with: `careflow-escalate-left --case {case_id} --order {data['order_id']} --blocker "<one sentence>" --decision-needed "<one sentence>"`
- agmsg files live under `.careflow/cases/{case_id}/messages/`; do not replace PLAN, ORDER, RESULT, Evidence, or Incident artifacts.
- Do not use cmux for careflow agent handoff.
"""


def render_result_skeleton(root: Path, case_id: str, order_id: str, *, status: str = "complete") -> str:
    path, data = _order_data(root, case_id, order_id)
    order_rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    return f"""# RESULT: {data['order_id']}

order_id: {data['order_id']}
case_id: {case_id}
status: {status}
plan_path: {data['plan_path']}
order_path: {order_rel}
expected_result_path: {data['expected_result_path']}

## Summary

- Replace this with the outcome of the ORDER.

## Changes

- Record changed files or state that no source files changed.

## Evidence

- Record verification commands, review notes, or blocker evidence.

## Blockers

- None recorded.
"""


def write_result_skeleton(root: Path, case_id: str, order_id: str, *, force: bool = False, status: str = "complete") -> Path:
    _, data = _order_data(root, case_id, order_id)
    result_path = root / str(data["expected_result_path"])
    if result_path.exists() and not force:
        raise ValidationError(f"result already exists: {result_path}")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(render_result_skeleton(root, case_id, order_id, status=status), encoding="utf-8")
    validate_result(result_path)
    return result_path
