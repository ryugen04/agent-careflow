from __future__ import annotations

from pathlib import Path

from .artifacts import ValidationError, case_dir, parse_front_matter_lines, require_fields, validate_order

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


def render_order_prompt(root: Path, case_id: str, order_id: str, tool: str) -> str:
    if tool not in TOOLS:
        raise ValidationError(f"unsupported tool: {tool}")
    path = order_path_for(root, case_id, order_id)
    validate_order(path, root)
    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    require_fields(data, ["assigned_role", "plan_path", "expected_result_path"], path)
    role = str(data["assigned_role"])
    role_instruction = ROLE_INSTRUCTIONS.get(role, "Follow the order exactly and keep work inside scope.")
    order_rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    return f"""You are acting as the {role} for agent-careflow case {case_id} using {tool}.

Required inputs:
- plan_path: {data['plan_path']}
- order_path: {order_rel}
- expected_result_path: {data['expected_result_path']}

Role instruction:
{role_instruction}

Execution rules:
- Read the PLAN before taking action.
- Read the ORDER before taking action.
- Keep all edits within the ORDER allowed actions and deliverables.
- Do not treat the task as complete unless expected_result_path exists.
- Report blockers explicitly in the expected result file.
"""
