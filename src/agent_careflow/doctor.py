from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]

from .artifacts import ValidationError, validate_case, validate_discharge, validate_order, validate_plan, validate_research
from .constants import CASES_DIR
from .policy.config import parse_simple_yaml


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


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    return data


def _validate_hooks_file(path: Path, *, required_events: tuple[str, ...]) -> None:
    data = _load_json_object(path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        raise ValidationError(f"{path} is missing hooks object")
    for event in required_events:
        if event not in hooks:
            raise ValidationError(f"missing {event}")


def check_codex_hooks(root: Path) -> DoctorCheck:
    required_events = ("SessionStart", "PreToolUse", "PostToolUse", "PermissionRequest", "UserPromptSubmit", "Stop")
    paths = [
        root / ".codex" / "hooks.json",
        root / "rules" / "codex" / "hooks.json",
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "hooks.json",
    ]
    errors: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            _validate_hooks_file(path, required_events=required_events)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue
        return _ok("codex-hooks", str(path))
    detail = "; ".join(errors) if errors else "no Codex hooks source found"
    return _fail("codex-hooks", detail)


def _is_ai_dlc_workspace(root: Path) -> bool:
    return (root / "workspace.yaml").exists() or (root / ".aidlc" / "workspace.yaml").exists()


def check_ai_dlc_workspace(root: Path) -> DoctorCheck:
    try:
        project_manifest = root / "workspace.yaml"
        aidlc_manifest = root / ".aidlc" / "workspace.yaml"
        if not project_manifest.exists():
            raise ValidationError("workspace.yaml is missing")
        if not aidlc_manifest.exists():
            raise ValidationError(".aidlc/workspace.yaml is missing")
        project = parse_simple_yaml(project_manifest)
        aidlc_text = aidlc_manifest.read_text(encoding="utf-8")
        if project.get("schema") != "ai-dlc.workspace.v1":
            raise ValidationError("workspace.yaml schema must be ai-dlc.workspace.v1")
        if "kind: monorepo" not in aidlc_text:
            raise ValidationError(".aidlc/workspace.yaml kind must be monorepo")
        for key in ("workspace", "repos", "controller", "workflow"):
            if key not in project:
                raise ValidationError(f"workspace.yaml missing {key}")
        if "repos:" not in aidlc_text:
            raise ValidationError(".aidlc/workspace.yaml missing repos")
    except Exception as exc:
        return _fail("ai-dlc-workspace", exc)
    return _ok("ai-dlc-workspace", "workspace.yaml and .aidlc/workspace.yaml")


def check_ai_dlc_paths(root: Path) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    try:
        manifest = parse_simple_yaml(root / "workspace.yaml")
        paths = manifest.get("paths")
        if not isinstance(paths, dict):
            raise ValidationError("workspace.yaml missing paths")
        for key, value in sorted(paths.items()):
            if key == "local":
                continue
            rel = Path(str(value))
            path = root / rel
            if path.exists():
                checks.append(_ok(f"ai-dlc-path:{key}", str(rel)))
            else:
                checks.append(_fail(f"ai-dlc-path:{key}", f"{rel} is missing"))
    except Exception as exc:
        checks.append(_fail("ai-dlc-paths", exc))
    return checks


def check_codex_config(root: Path) -> DoctorCheck:
    path = root / ".codex" / "config.toml"
    try:
        if not path.exists():
            raise ValidationError(".codex/config.toml is missing")
        text = path.read_text(encoding="utf-8")
        if tomllib is not None:
            data = tomllib.loads(text)
            features = data.get("features")
            if not isinstance(features, dict) or features.get("hooks") is not True:
                raise ValidationError("[features].hooks must be true")
        elif "hooks = true" not in text:
            raise ValidationError("[features].hooks must be true")
    except Exception as exc:
        return _fail("codex-config", exc)
    return _ok("codex-config", ".codex/config.toml")


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
    if _is_ai_dlc_workspace(root):
        checks.append(check_ai_dlc_workspace(root))
        checks.extend(check_ai_dlc_paths(root))
        checks.append(check_codex_config(root))
        checks.append(check_codex_hooks(root))
        if (root / CASES_DIR).exists():
            checks.extend(check_cases(root))
        return checks
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
