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
    phase_policies: dict[str, object] | None = None,
) -> Decision:
    operation = operation.lower()
    if operation not in {"read", "write"}:
        return deny(f"unsupported file operation: {operation}")
    if operation == "read":
        return allow("read allowed")

    if phase_policies and phase in phase_policies and isinstance(phase_policies[phase], dict):
        policy = phase_policies[phase]
        if policy.get("deny_code_write") and is_code_path(path):
            return deny(f"{phase} phase cannot write code paths")
        if policy.get("require_active_order") and not has_active_order:
            return deny(f"{phase} write requires an active ORDER")
        allow_write = policy.get("allow_write")
        if isinstance(allow_write, list):
            return check_allowed_scope(path, [str(item) for item in allow_write])
        if policy.get("require_active_order"):
            return check_allowed_scope(path, allowed_scope)
        return allow(f"{phase} write allowed by policy")

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
