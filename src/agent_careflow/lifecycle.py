from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .artifacts import ValidationError, case_dir, parse_front_matter_lines, require_fields, validate_discharge
from .templates import render_order

PHASES = [
    "intake",
    "planning",
    "research",
    "implementation_planning",
    "implementation",
    "verification",
    "review",
    "conference",
    "remediation",
    "discharge",
    "archive",
]


def _replace_scalar(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[index] = f"{key}: {value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def case_status(root: Path, case_id: str) -> dict[str, object]:
    cdir = case_dir(root, case_id)
    case_path = cdir / "CASE.yaml"
    if not case_path.exists():
        raise ValidationError(f"case not found: {case_id}")
    data = parse_front_matter_lines(case_path.read_text(encoding="utf-8"))
    incidents = list((cdir / "incidents").glob("*.md")) if (cdir / "incidents").exists() else []
    open_incidents = [p.name for p in incidents if "status: closed" not in p.read_text(encoding="utf-8")]
    evidence = list((cdir / "evidence").glob("*")) if (cdir / "evidence").exists() else []
    return {
        "case_id": data.get("case_id"),
        "phase": data.get("phase"),
        "status": data.get("status"),
        "open_incidents": open_incidents,
        "evidence_count": len([p for p in evidence if p.is_file()]),
    }


def advance_phase(root: Path, case_id: str, target_phase: str) -> None:
    if target_phase not in PHASES:
        raise ValidationError(f"invalid phase: {target_phase}")
    cdir = case_dir(root, case_id)
    case_path = cdir / "CASE.yaml"
    if not case_path.exists():
        raise ValidationError(f"case not found: {case_id}")
    if target_phase in {"review", "conference", "discharge"}:
        evidence_dir = cdir / "evidence"
        if not evidence_dir.exists() or not any(p.is_file() for p in evidence_dir.iterdir()):
            raise ValidationError(f"cannot advance to {target_phase}: required evidence is missing")
    if target_phase == "discharge":
        validate_discharge(cdir / "DISCHARGE.md", cdir)
    _replace_scalar(case_path, "phase", target_phase)


def issue_order(root: Path, case_id: str, order_id: str, role: str) -> Path:
    cdir = case_dir(root, case_id)
    plan = cdir / "PLAN.md"
    if not plan.exists():
        raise ValidationError(f"PLAN.md not found for case {case_id}")
    orders = cdir / "orders"
    results = cdir / "results"
    orders.mkdir(parents=True, exist_ok=True)
    results.mkdir(exist_ok=True)
    order_path = orders / f"{order_id}.order.md"
    if order_path.exists():
        raise ValidationError(f"order already exists: {order_id}")
    rel_plan = Path(".careflow") / "cases" / case_id / "PLAN.md"
    rel_result = Path(".careflow") / "cases" / case_id / "results" / f"{order_id}.result.md"
    order_path.write_text(render_order(case_id, order_id, role, root / rel_plan, rel_result), encoding="utf-8")
    text = order_path.read_text(encoding="utf-8").replace((root / rel_plan).as_posix(), rel_plan.as_posix())
    order_path.write_text(text, encoding="utf-8")
    return order_path


def validate_result(path: Path) -> None:
    from .schema_validation import validate_data_against_schema

    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    validate_data_against_schema(data, "RESULT", path)
    require_fields(data, ["order_id", "case_id", "status"], path)


def validate_review(path: Path) -> None:
    from .schema_validation import validate_data_against_schema

    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    validate_data_against_schema(data, "REVIEW", path)
    require_fields(data, ["review_id", "case_id", "status"], path)
    if data["status"] not in {"pass", "needs_changes", "blocked"}:
        raise ValidationError(f"{path}: invalid review status {data['status']!r}")


def new_incident(root: Path, case_id: str, trigger: str) -> Path:
    cdir = case_dir(root, case_id)
    incidents = cdir / "incidents"
    incidents.mkdir(parents=True, exist_ok=True)
    number = len(list(incidents.glob("INC-*.md"))) + 1
    incident_id = f"INC-{number:03d}-{trigger.replace('_', '-')}"
    path = incidents / f"{incident_id}.md"
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    path.write_text(
        f"""# INCIDENT: {incident_id}\n\nincident_id: {incident_id}\ncase_id: {case_id}\ntrigger: {trigger}\nstatus: open\ncreated_at: {now}\nseverity: medium\n\n## Summary\n\nPending triage.\n\n## Corrective action\n\nPending.\n""",
        encoding="utf-8",
    )
    return path
