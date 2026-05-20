from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .constants import AUTHORITY_LEVELS, CASES_DIR, REQUIRED_REPORT_SECTIONS, REQUIRED_RESEARCH_REPORTS, RISK_CLASSES


class ValidationError(Exception):
    """Raised when an artifact does not satisfy the careflow contract."""


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    ok: bool
    message: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def parse_front_matter_lines(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            current_key = None
            continue
        if line.startswith("#") or line.startswith("##"):
            current_key = None
            continue
        if line.startswith("  - ") and current_key:
            value = data.setdefault(current_key, [])
            if isinstance(value, list):
                value.append(line[4:].strip())
            continue
        if ":" not in line or line.startswith("|") or line.startswith("-"):
            current_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_/-]+", key):
            current_key = None
            continue
        if value:
            data[key] = value
            current_key = None
        else:
            data[key] = []
            current_key = key
    return data


def require_fields(data: dict[str, object], fields: Iterable[str], path: Path) -> None:
    missing = [field for field in fields if field not in data or data[field] in ("", [])]
    if missing:
        raise ValidationError(f"{path}: missing required field(s): {', '.join(missing)}")


def case_dir(root: Path, case_id: str) -> Path:
    return root / CASES_DIR / case_id


def validate_case(case_path: Path) -> None:
    data = parse_front_matter_lines(case_path.read_text(encoding="utf-8"))
    require_fields(data, ["case_id", "title", "risk", "phase", "status", "created_at", "owner"], case_path)
    if data["risk"] not in RISK_CLASSES:
        raise ValidationError(f"{case_path}: invalid risk class {data['risk']!r}")


def validate_plan(plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    require_fields(data, ["case_id", "status", "risk", "owner"], plan_path)
    required_sections = [
        "## Objective",
        "## Non-goals",
        "## Acceptance criteria",
        "## Risk class",
        "## Allowed scope",
        "## Phase plan",
        "## Evidence requirements",
        "## Rollback plan",
        "## Unresolved questions",
    ]
    missing = [section for section in required_sections if section not in text]
    if missing:
        raise ValidationError(f"{plan_path}: missing section(s): {', '.join(missing)}")
    if data["risk"] not in RISK_CLASSES:
        raise ValidationError(f"{plan_path}: invalid risk class {data['risk']!r}")


def validate_order(order_path: Path, repo_root: Path | None = None) -> None:
    repo_root = repo_root or Path.cwd()
    text = order_path.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    require_fields(
        data,
        [
            "order_id",
            "case_id",
            "assigned_role",
            "plan_path",
            "plan_hash",
            "allowed_actions",
            "forbidden_actions",
            "deliverables",
            "expected_result_path",
            "completion_criteria",
        ],
        order_path,
    )
    plan_path = repo_root / str(data["plan_path"])
    if not plan_path.exists():
        raise ValidationError(f"{order_path}: plan_path does not exist: {plan_path}")
    actual_hash = sha256_file(plan_path)
    if data["plan_hash"] != actual_hash:
        raise ValidationError(f"{order_path}: plan_hash mismatch: expected {data['plan_hash']}, actual {actual_hash}")


def validate_discharge(discharge_path: Path, case_root: Path | None = None) -> None:
    text = discharge_path.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    require_fields(data, ["case_id", "status", "evidence"], discharge_path)
    case_root = case_root or discharge_path.parent
    evidence_dir = case_root / "evidence"
    if not evidence_dir.exists() or not any(evidence_dir.iterdir()):
        raise ValidationError(f"{discharge_path}: discharge requires at least one evidence file")
    incidents_dir = case_root / "incidents"
    if incidents_dir.exists():
        open_incidents = [p for p in incidents_dir.glob("*.md") if "status: closed" not in p.read_text(encoding="utf-8")]
        if open_incidents:
            names = ", ".join(p.name for p in open_incidents)
            raise ValidationError(f"{discharge_path}: open incident(s) block discharge: {names}")


def validate_research(root: Path) -> None:
    research_dir = root / "research"
    if not research_dir.exists():
        raise ValidationError("research directory is missing")
    registry_path = research_dir / "source-registry.json"
    if not registry_path.exists():
        raise ValidationError("research/source-registry.json is missing")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{registry_path}: invalid JSON: {exc}") from exc
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValidationError(f"{registry_path}: sources must be a non-empty list")
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValidationError(f"{registry_path}: source #{index + 1} must be an object")
        for field in ("id", "title", "url", "authority", "type"):
            if not source.get(field):
                raise ValidationError(f"{registry_path}: source #{index + 1} missing {field}")
        if source["authority"] not in AUTHORITY_LEVELS:
            raise ValidationError(f"{registry_path}: invalid authority {source['authority']!r}")
    missing_reports = [name for name in REQUIRED_RESEARCH_REPORTS if not (research_dir / name).exists()]
    if missing_reports:
        raise ValidationError(f"missing research report(s): {', '.join(missing_reports)}")
    for name in REQUIRED_RESEARCH_REPORTS:
        path = research_dir / name
        text = path.read_text(encoding="utf-8")
        missing_sections = [section for section in REQUIRED_REPORT_SECTIONS if section not in text]
        if missing_sections:
            raise ValidationError(f"{path}: missing section(s): {', '.join(missing_sections)}")
        authorities = set(re.findall(r"\|\s*([ABCD])\s*\|", text))
        if not authorities or not authorities <= AUTHORITY_LEVELS:
            raise ValidationError(f"{path}: no explicit source authority level found")
