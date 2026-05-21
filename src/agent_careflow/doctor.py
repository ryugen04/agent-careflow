from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .artifacts import ValidationError, validate_case, validate_discharge, validate_order, validate_plan, validate_research
from .constants import CASES_DIR


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    message: str


def _ok(name: str, message: str = "ok") -> DoctorCheck:
    return DoctorCheck(name, True, message)


def _fail(name: str, error: Exception | str) -> DoctorCheck:
    return DoctorCheck(name, False, str(error))


def check_json_file(path: Path, name: str) -> DoctorCheck:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _fail(name, exc)
    return _ok(name, str(path))


def check_codex_hooks(root: Path) -> DoctorCheck:
    path = root / "rules" / "codex" / "hooks.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        hooks = data["hooks"]
        for event in ("PreToolUse", "PostToolUse", "PermissionRequest", "UserPromptSubmit"):
            if event not in hooks:
                raise ValidationError(f"missing {event}")
    except Exception as exc:
        return _fail("codex-hooks", exc)
    return _ok("codex-hooks", "rules/codex/hooks.json")


def check_schemas(root: Path) -> list[DoctorCheck]:
    schema_dir = root / "src" / "agent_careflow" / "schemas"
    checks: list[DoctorCheck] = []
    for path in sorted(schema_dir.glob("*.schema.json")):
        checks.append(check_json_file(path, f"schema:{path.name}"))
    if not checks:
        checks.append(_fail("schemas", "no schema files found"))
    return checks


def check_cases(root: Path) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    cases_root = root / CASES_DIR
    if not cases_root.exists():
        return [_fail("cases", "no .careflow/cases directory")]
    for case_dir in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        case_id = case_dir.name
        try:
            validate_case(case_dir / "CASE.yaml")
            checks.append(_ok(f"case:{case_id}:CASE"))
        except Exception as exc:
            checks.append(_fail(f"case:{case_id}:CASE", exc))
        try:
            validate_plan(case_dir / "PLAN.md", require_lock=(case_dir / "PLAN.lock.json").exists())
            checks.append(_ok(f"case:{case_id}:PLAN"))
        except Exception as exc:
            checks.append(_fail(f"case:{case_id}:PLAN", exc))
        for order in sorted((case_dir / "orders").glob("*.order.md")) if (case_dir / "orders").exists() else []:
            try:
                validate_order(order, root)
                checks.append(_ok(f"case:{case_id}:order:{order.name}"))
            except Exception as exc:
                checks.append(_fail(f"case:{case_id}:order:{order.name}", exc))
        discharge = case_dir / "DISCHARGE.md"
        if discharge.exists():
            try:
                validate_discharge(discharge, case_dir)
                checks.append(_ok(f"case:{case_id}:DISCHARGE"))
            except Exception as exc:
                checks.append(_fail(f"case:{case_id}:DISCHARGE", exc))
    return checks


def run_doctor(root: Path) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    try:
        validate_research(root)
        checks.append(_ok("research"))
    except Exception as exc:
        checks.append(_fail("research", exc))
    checks.extend(check_schemas(root))
    checks.append(check_codex_hooks(root))
    checks.extend(check_cases(root))
    return checks


def doctor_failed(checks: list[DoctorCheck]) -> bool:
    return any(not check.ok for check in checks)


def render_doctor(checks: list[DoctorCheck]) -> str:
    lines = []
    for check in checks:
        status = "ok" if check.ok else "fail"
        lines.append(f"{status}: {check.name}: {check.message}")
    return "\n".join(lines)
