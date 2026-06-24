from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import ValidationError, case_dir, parse_front_matter_lines
from .lifecycle import validate_review


def _required_tools(profile: str) -> list[str]:
    if profile == "business":
        return ["codex", "claude"]
    if profile == "private":
        return ["codex"]
    raise ValidationError(f"unsupported review status profile: {profile}")


def _find_latest_review(root: Path, case_id: str, tool: str) -> Path | None:
    reviews = case_dir(root, case_id) / "reviews"
    candidates: list[Path] = []
    for path in sorted(reviews.glob("*.review.md")) if reviews.exists() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        data = parse_front_matter_lines(text)
        if str(data.get("tool") or "") == tool:
            candidates.append(path)
    return candidates[-1] if candidates else None


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _tool_status(root: Path, case_id: str, tool: str) -> dict[str, Any]:
    path = _find_latest_review(root, case_id, tool)
    if path is None:
        return {"status": "missing", "path": None, "details": "missing review artifact"}
    try:
        validate_review(path, strict=True)
    except ValidationError as exc:
        return {"status": "invalid", "path": _display_path(root, path), "details": str(exc).replace(path.as_posix(), _display_path(root, path))}
    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    if data.get("status") != "pass":
        return {"status": "not_passing", "path": _display_path(root, path), "details": f"review status is {data.get('status')}"}
    return {"status": "satisfied", "path": _display_path(root, path), "details": path.name}


def _next_commands(case_id: str, profile: str, order_id: str, tools: dict[str, dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    claude = tools.get("claude")
    if profile == "business" and claude and claude.get("status") != "satisfied":
        review_id = f"REVIEW-CLAUDE-{order_id}"
        commands.extend([
            f"agent-careflow review export --case {case_id} --tool claude --order {order_id} --review-id {review_id} --output /tmp/{review_id}.request.md",
            f"agent-careflow review import --case {case_id} --source /path/to/{review_id}.review.md --strict --force",
            f"agent-careflow review require --case {case_id} --tool codex --tool claude --strict",
        ])
    return commands


def _diagnostic_commands(profile: str, tools: dict[str, dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    claude = tools.get("claude")
    if profile == "business" and claude and claude.get("status") != "satisfied":
        commands.append("agent-careflow review claude-auth --model sonnet")
    return commands


def review_status(root: Path, case_id: str, *, profile: str = "business", order_id: str = "ORD-001") -> dict[str, Any]:
    required = _required_tools(profile)
    tools = {tool: _tool_status(root, case_id, tool) for tool in required}
    satisfied = all(info["status"] == "satisfied" for info in tools.values())
    return {
        "schema": "agent-careflow.review_status.v1",
        "case_id": case_id,
        "profile": profile,
        "order_id": order_id,
        "required_tools": required,
        "status": "satisfied" if satisfied else "missing",
        "tools": tools,
        "next_commands": _next_commands(case_id, profile, order_id, tools),
        "diagnostic_commands": _diagnostic_commands(profile, tools),
    }


def render_review_status(status: dict[str, Any]) -> str:
    lines = [f"review-status={status['status']} case={status['case_id']} profile={status['profile']} order={status['order_id']}"]
    tools = status.get("tools", {})
    if isinstance(tools, dict):
        for tool, info in tools.items():
            if isinstance(info, dict):
                lines.append(f"{tool}: {info.get('status')} - {info.get('details')}")
    commands = status.get("next_commands")
    if commands:
        lines.append("next commands:")
        lines.extend(str(command) for command in commands)
    diagnostic_commands = status.get("diagnostic_commands")
    if diagnostic_commands:
        lines.append("diagnostic commands:")
        lines.extend(str(command) for command in diagnostic_commands)
    return "\n".join(lines)
