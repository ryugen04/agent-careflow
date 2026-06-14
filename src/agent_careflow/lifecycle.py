from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import ValidationError, case_dir, parse_front_matter_lines, require_fields, validate_discharge
from .templates import render_order

REVIEW_TOOLS = {"codex", "claude", "cursor", "human"}

PLACEHOLDER_REVIEW_TOKENS = (
    "placeholder",
    "auth unavailable",
    "authentication failure",
    "authentication_failed",
)

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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "learning"


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


def validate_review(path: Path, *, strict: bool = False) -> None:
    from .schema_validation import validate_data_against_schema

    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    validate_data_against_schema(data, "REVIEW", path)
    require_fields(data, ["review_id", "case_id", "status"], path)
    if data["status"] not in {"pass", "needs_changes", "blocked"}:
        raise ValidationError(f"{path}: invalid review status {data['status']!r}")
    tool = data.get("tool")
    if tool and tool not in REVIEW_TOOLS:
        raise ValidationError(f"{path}: invalid review tool {tool!r}")
    if strict:
        lowered = path.read_text(encoding="utf-8", errors="replace").lower()
        matched = [token for token in PLACEHOLDER_REVIEW_TOKENS if token in lowered]
        if matched:
            raise ValidationError(f"{path}: placeholder review evidence is not allowed in strict mode: {', '.join(matched)}")
        if "## findings" not in lowered or "## evidence reviewed" not in lowered or "## recommendation" not in lowered:
            raise ValidationError(f"{path}: strict review must include Findings, Evidence reviewed, and Recommendation sections")


def new_review(
    root: Path,
    case_id: str,
    *,
    tool: str,
    review_id: str | None = None,
    status: str = "pass",
    scope: str = "PLAN, ORDER, RESULT, and evidence",
    evidence: str = "See case evidence directory",
    recommendation: str = "No blocking findings recorded.",
) -> Path:
    if tool not in REVIEW_TOOLS:
        raise ValidationError(f"invalid review tool: {tool}")
    if status not in {"pass", "needs_changes", "blocked"}:
        raise ValidationError(f"invalid review status: {status}")
    cdir = case_dir(root, case_id)
    if not cdir.exists():
        raise ValidationError(f"case not found: {case_id}")
    reviews = cdir / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    number = len(list(reviews.glob("REVIEW-*.md"))) + 1
    rid = review_id or f"REVIEW-{number:03d}-{tool}"
    path = reviews / f"{rid}.review.md"
    if path.exists():
        raise ValidationError(f"review already exists: {path.name}")
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    rel_plan = Path(".careflow") / "cases" / case_id / "PLAN.md"
    rel_order = Path(".careflow") / "state.json"
    path.write_text(
        f"""# REVIEW: {rid}

review_id: {rid}
case_id: {case_id}
tool: {tool}
status: {status}
created_at: {now}
plan_path: {rel_plan.as_posix()}
state_path: {rel_order.as_posix()}

## Scope

{scope}

## Findings

- None recorded.

## Evidence reviewed

- {evidence}

## Recommendation

{recommendation}
""",
        encoding="utf-8",
    )
    validate_review(path)
    return path


def new_review_request(
    root: Path,
    case_id: str,
    *,
    tool: str,
    order_id: str,
    review_id: str | None = None,
    force: bool = False,
) -> Path:
    if tool not in REVIEW_TOOLS:
        raise ValidationError(f"invalid review tool: {tool}")
    cdir = case_dir(root, case_id)
    if not cdir.exists():
        raise ValidationError(f"case not found: {case_id}")
    order_path = cdir / "orders" / f"{order_id}.order.md"
    if not order_path.exists():
        raise ValidationError(f"order not found: {order_id}")
    request_dir = cdir / "reviews" / "requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    tool_upper = tool.upper()
    request_path = request_dir / f"REQUEST-{tool_upper}-{order_id}.md"
    if request_path.exists() and not force:
        raise ValidationError(f"review request exists: {request_path.name}; use --force to overwrite")
    rid = review_id or f"REVIEW-{tool_upper}-{order_id}"
    rel_plan = Path(".careflow") / "cases" / case_id / "PLAN.md"
    rel_order = Path(".careflow") / "cases" / case_id / "orders" / f"{order_id}.order.md"
    rel_result = Path(".careflow") / "cases" / case_id / "results" / f"{order_id}.result.md"
    rel_review = Path(".careflow") / "cases" / case_id / "reviews" / f"{rid}.review.md"
    rel_evidence = Path(".careflow") / "cases" / case_id / "evidence"
    request_path.write_text(
        f"""PLAN_FILE: {rel_plan.as_posix()}
ORDER_FILE: {rel_order.as_posix()}
SUBPLAN_FILE: {rel_order.as_posix()}
EXPECTED_RESULT_PATH: {rel_result.as_posix()}
CASE_ID: {case_id}
ORDER_ID: {order_id}
ASSIGNED_ROLE: reviewer
TARGET_TOOL: {tool}
EXPECTED_REVIEW_PATH: {rel_review.as_posix()}

# REVIEW REQUEST: {rid}

## Instructions

Read PLAN_FILE, ORDER_FILE, EXPECTED_RESULT_PATH, and the evidence directory before reviewing. Treat ORDER_FILE as the executable subplan for the work under review. Save the review exactly at EXPECTED_REVIEW_PATH.

## Scope

- Plan: `{rel_plan.as_posix()}`
- Order: `{rel_order.as_posix()}`
- Result: `{rel_result.as_posix()}`
- Evidence: `{rel_evidence.as_posix()}`

## Required Output Contract

Write a `.review.md` artifact with this front matter and sections:

```markdown
# REVIEW: {rid}

review_id: {rid}
case_id: {case_id}
tool: {tool}
status: pass|needs_changes|blocked
plan_path: {rel_plan.as_posix()}
order_path: {rel_order.as_posix()}
result_path: {rel_result.as_posix()}

## Scope

What was reviewed.

## Findings

- Severity: critical|major|minor|none; file/line; rationale.

## Evidence reviewed

- Exact commands, artifacts, and files inspected.

## Recommendation

Pass, request changes, or block with rationale.
```

## Strictness

Do not submit an auth-unavailable placeholder. If the review cannot be completed, write `status: blocked` and explain the external blocker with evidence.
""",
        encoding="utf-8",
    )
    return request_path


def require_reviews(root: Path, case_id: str, tools: list[str], *, strict: bool = False) -> dict[str, Path]:
    if not tools:
        raise ValidationError("at least one review tool is required")
    invalid = [tool for tool in tools if tool not in REVIEW_TOOLS]
    if invalid:
        raise ValidationError(f"invalid review tool(s): {', '.join(invalid)}")
    cdir = case_dir(root, case_id)
    if not cdir.exists():
        raise ValidationError(f"case not found: {case_id}")
    reviews = cdir / "reviews"
    found: dict[str, Path] = {}
    for path in sorted(reviews.glob("*.review.md")) if reviews.exists() else []:
        validate_review(path, strict=False)
        data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
        tool = str(data.get("tool") or "")
        status = str(data.get("status") or "")
        if tool in tools and status == "pass" and tool not in found:
            if strict:
                validate_review(path, strict=True)
            found[tool] = path
    missing = [tool for tool in tools if tool not in found]
    if missing:
        raise ValidationError(f"missing passing review(s): {', '.join(missing)}")
    return found


def new_incident(root: Path, case_id: str, trigger: str) -> Path:
    cdir = case_dir(root, case_id)
    incidents = cdir / "incidents"
    incidents.mkdir(parents=True, exist_ok=True)
    number = len(list(incidents.glob("INC-*.md"))) + 1
    incident_id = f"INC-{number:03d}-{trigger.replace('_', '-')}"
    path = incidents / f"{incident_id}.md"
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    path.write_text(
        f"""# INCIDENT: {incident_id}\n\nincident_id: {incident_id}\ncase_id: {case_id}\ntrigger: {trigger}\nstatus: open\ncreated_at: {now}\nseverity: medium\n\n## Summary\n\nTriage required.\n\n## Corrective action\n\nCorrective action required.\n""",
        encoding="utf-8",
    )
    return path


def new_learning(root: Path, case_id: str, title: str, *, source_incident: str | None = None) -> Path:
    cdir = case_dir(root, case_id)
    if not cdir.exists():
        raise ValidationError(f"case not found: {case_id}")
    learnings = cdir / "learnings"
    learnings.mkdir(parents=True, exist_ok=True)
    number = len(list(learnings.glob("LRN-*.md"))) + 1
    learning_id = f"LRN-{number:03d}-{_slugify(title)}"
    path = learnings / f"{learning_id}.md"
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    source_line = f"source_incident: {source_incident}" if source_incident else "source_incident: none"
    path.write_text(
        f"""# LEARNING: {learning_id}

learning_id: {learning_id}
case_id: {case_id}
title: {title}
{source_line}
status: captured
created_at: {now}
promoted_to: none

## Observation

Record the concrete trouble, behavior, or discovery.

## Implication

Record what should change in workflow, docs, hooks, skills, tests, or policy.

## Follow-up

Record the next action or ORDER candidate.
""",
        encoding="utf-8",
    )
    return path


def promote_learning(root: Path, case_id: str, learning: str, target: Path, *, force: bool = False) -> Path:
    cdir = case_dir(root, case_id)
    learnings = cdir / "learnings"
    name = learning if learning.endswith(".md") else f"{learning}.md"
    source = learnings / name
    if not source.exists():
        raise ValidationError(f"learning not found: {name}")
    destination = target if target.is_absolute() else root / target
    if destination.exists() and not force:
        raise ValidationError(f"promotion target exists: {destination}; use --force to overwrite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = parse_front_matter_lines(source.read_text(encoding="utf-8"))
    title = str(data.get("title") or data.get("learning_id") or source.stem)
    rel_source = source.relative_to(root).as_posix() if source.is_relative_to(root) else source.as_posix()
    rel_destination = destination.relative_to(root).as_posix() if destination.is_relative_to(root) else destination.as_posix()
    _replace_scalar(source, "status", "promoted")
    _replace_scalar(source, "promoted_to", rel_destination)
    body = source.read_text(encoding="utf-8")
    destination.write_text(
        f"""# {title}

source_learning: {rel_source}
case_id: {case_id}

## Summary

This document was promoted from an agent-careflow learning artifact. Edit this docs page for readers, but keep the source learning linked for traceability.

## Source Learning

```markdown
{body.rstrip()}
```
""",
        encoding="utf-8",
    )
    return destination


def collect_evidence(root: Path, case_id: str, kind: str) -> Path:
    if kind != "git-status":
        raise ValidationError(f"unsupported evidence kind: {kind}")
    cdir = case_dir(root, case_id)
    if not cdir.exists():
        raise ValidationError(f"case not found: {case_id}")
    evidence = cdir / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ValidationError(f"git status failed: {detail}")
    output = result.stdout.rstrip() or "clean"
    path = evidence / "git-status.txt"
    path.write_text(f"$ git status --short\n{output}\n", encoding="utf-8")
    return path
