from __future__ import annotations

from pathlib import Path

from agent_careflow.artifacts import ValidationError, case_dir, parse_front_matter_lines, validate_order

from .command_policy import check_command
from .decisions import Decision, deny
from .phase_policy import check_phase_file_access


def _list_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


class PolicyEngine:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def case_data(self, case_id: str) -> dict[str, object]:
        path = case_dir(self.repo_root, case_id) / "CASE.yaml"
        if not path.exists():
            raise ValidationError(f"case not found: {case_id}")
        return parse_front_matter_lines(path.read_text(encoding="utf-8"))

    def check_command(self, command: str) -> Decision:
        return check_command(command)

    def check_file(self, *, case_id: str, path: str, operation: str, order_id: str | None = None) -> Decision:
        data = self.case_data(case_id)
        phase = str(data.get("phase", ""))
        allowed_scope = _list_value(data.get("allowed_scope"))
        has_active_order = False
        if order_id:
            order_name = order_id if order_id.endswith(".order.md") else f"{order_id}.order.md"
            order_path = case_dir(self.repo_root, case_id) / "orders" / order_name
            try:
                validate_order(order_path, self.repo_root)
            except (OSError, ValidationError) as exc:
                return deny(f"active ORDER is invalid: {exc}")
            has_active_order = True
        return check_phase_file_access(
            phase=phase,
            path=path,
            operation=operation,
            allowed_scope=allowed_scope,
            has_active_order=has_active_order,
        )
