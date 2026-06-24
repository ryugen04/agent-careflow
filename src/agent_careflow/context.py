from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import CARE_DIR


@dataclass(frozen=True)
class CareflowContext:
    cwd: Path
    workflow_root: Path
    case_id: str | None
    order_id: str | None
    expected_result_path: str | None


def find_workflow_root(cwd: Path) -> Path:
    current = cwd.resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        careflow_dir = candidate / CARE_DIR
        if (careflow_dir / "state.json").exists() or (careflow_dir / "careflow.yaml").exists() or (careflow_dir / "cases").exists():
            return candidate
    return current


def state_path(root: Path) -> Path:
    return root / CARE_DIR / "state.json"


def read_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_state(root: Path, updates: dict[str, Any]) -> Path:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_state(root)
    data.update(updates)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def resolve_context(payload: dict[str, Any]) -> CareflowContext:
    careflow = payload.get("careflow") if isinstance(payload.get("careflow"), dict) else {}
    cwd = Path(str(payload.get("cwd") or Path.cwd()))
    explicit_root = _string_or_none(payload.get("workflow_root") or careflow.get("workflow_root"))
    workflow_root = Path(explicit_root).expanduser().resolve() if explicit_root else find_workflow_root(cwd)
    state = read_state(workflow_root)
    case_id = _string_or_none(payload.get("case_id") or careflow.get("case_id") or state.get("active_case"))
    order_id = _string_or_none(payload.get("order_id") or careflow.get("order_id") or state.get("active_order"))
    expected_result_path = _string_or_none(payload.get("expected_result_path") or careflow.get("expected_result_path") or state.get("expected_result_path"))
    return CareflowContext(
        cwd=cwd,
        workflow_root=workflow_root,
        case_id=case_id,
        order_id=order_id,
        expected_result_path=expected_result_path,
    )
