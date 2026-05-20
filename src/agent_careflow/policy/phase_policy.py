from __future__ import annotations

from .decisions import Decision, allow, deny
from .file_scope import check_allowed_scope, is_code_path

PLANNING_WRITE_PATTERNS = [
    ".careflow/cases/*/CASE.yaml",
    ".careflow/cases/*/PLAN.md",
    ".careflow/cases/*/PLAN.lock.json",
    ".careflow/cases/*/orders/**",
    "research/**",
]
VERIFICATION_WRITE_PATTERNS = [
    ".careflow/cases/*/evidence/**",
    ".careflow/cases/*/results/*verification*.md",
]
REVIEW_WRITE_PATTERNS = [
    ".careflow/cases/*/reviews/**",
    ".careflow/cases/*/results/*review*.md",
]


def check_phase_file_access(
    *,
    phase: str,
    path: str,
    operation: str,
    allowed_scope: list[str],
    has_active_order: bool,
) -> Decision:
    operation = operation.lower()
    if operation not in {"read", "write"}:
        return deny(f"unsupported file operation: {operation}")
    if operation == "read":
        return allow("read allowed")

    if phase in {"planning", "intake"}:
        if is_code_path(path):
            return deny("planning phase cannot write code paths")
        return check_allowed_scope(path, PLANNING_WRITE_PATTERNS)

    if phase == "research":
        if is_code_path(path):
            return deny("research phase cannot write code paths")
        return allow("research write allowed outside code paths")

    if phase == "implementation":
        if not has_active_order:
            return deny("implementation write requires an active ORDER")
        return check_allowed_scope(path, allowed_scope)

    if phase == "verification":
        if is_code_path(path):
            return deny("verification phase cannot write code paths")
        return check_allowed_scope(path, VERIFICATION_WRITE_PATTERNS)

    if phase == "review":
        if is_code_path(path):
            return deny("review phase cannot write code paths")
        return check_allowed_scope(path, REVIEW_WRITE_PATTERNS)

    if phase in {"discharge", "archive"}:
        return deny(f"{phase} phase is read-only for file writes")

    return allow(f"no file-write restriction for phase {phase}")
