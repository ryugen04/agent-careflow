from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
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


def plan_lock_path(plan_path: Path) -> Path:
    return plan_path.with_name("PLAN.lock.json")


def build_plan_lock(plan_path: Path) -> dict[str, object]:
    data = parse_front_matter_lines(plan_path.read_text(encoding="utf-8"))
    require_fields(data, ["case_id", "risk", "status", "owner"], plan_path)
    return {
        "schema_version": 1,
        "case_id": data["case_id"],
        "plan_path": plan_path.name,
        "plan_hash": sha256_file(plan_path),
        "locked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


SIGNATURE_FIELDS = {"signature", "signature_namespace", "signature_principal", "signature_algorithm"}
DEFAULT_SIGNATURE_NAMESPACE = "agent-careflow-plan-lock"


def canonical_plan_lock_payload(lock: dict[str, object]) -> bytes:
    payload = {key: value for key, value in lock.items() if key not in SIGNATURE_FIELDS}
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sign_plan_lock(lock: dict[str, object], *, signing_key: Path, principal: str) -> dict[str, object]:
    if not signing_key.exists():
        raise ValidationError(f"signing key not found: {signing_key}")
    with tempfile.TemporaryDirectory() as tmp:
        message = Path(tmp) / "PLAN.lock.payload"
        message.write_bytes(canonical_plan_lock_payload(lock))
        result = subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", signing_key.as_posix(), "-n", DEFAULT_SIGNATURE_NAMESPACE, message.as_posix()],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise ValidationError(f"PLAN lock signing failed: {detail}")
        signature_path = message.with_suffix(message.suffix + ".sig")
        if not signature_path.exists():
            raise ValidationError("PLAN lock signing failed: signature file was not created")
        signed = dict(lock)
        signed["signature_algorithm"] = "openssh"
        signed["signature_namespace"] = DEFAULT_SIGNATURE_NAMESPACE
        signed["signature_principal"] = principal
        signed["signature"] = signature_path.read_text(encoding="utf-8")
        return signed


def verify_plan_lock_signature(lock: dict[str, object], lock_path: Path, *, allowed_signers: Path, principal: str | None = None) -> None:
    for field in ("signature", "signature_namespace", "signature_principal", "signature_algorithm"):
        if field not in lock or lock[field] in ("", None):
            raise ValidationError(f"{lock_path}: missing {field}")
    if lock["signature_algorithm"] != "openssh":
        raise ValidationError(f"{lock_path}: unsupported signature_algorithm {lock['signature_algorithm']!r}")
    if lock["signature_namespace"] != DEFAULT_SIGNATURE_NAMESPACE:
        raise ValidationError(f"{lock_path}: unsupported signature_namespace {lock['signature_namespace']!r}")
    lock_principal = str(lock["signature_principal"])
    if principal and lock_principal != principal:
        raise ValidationError(f"{lock_path}: signature_principal does not match requested principal")
    if not allowed_signers.exists():
        raise ValidationError(f"allowed signers file not found: {allowed_signers}")
    with tempfile.TemporaryDirectory() as tmp:
        signature_path = Path(tmp) / "PLAN.lock.sig"
        signature_path.write_text(str(lock["signature"]), encoding="utf-8")
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                allowed_signers.as_posix(),
                "-I",
                principal or lock_principal,
                "-n",
                str(lock["signature_namespace"]),
                "-s",
                signature_path.as_posix(),
            ],
            input=canonical_plan_lock_payload(lock),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip() or result.stdout.decode("utf-8", errors="replace").strip() or f"exit {result.returncode}"
            raise ValidationError(f"{lock_path}: PLAN lock signature verification failed: {detail}")


def write_plan_lock(plan_path: Path, *, signing_key: Path | None = None, signing_principal: str | None = None) -> Path:
    lock_path = plan_lock_path(plan_path)
    lock = build_plan_lock(plan_path)
    if signing_key:
        lock = sign_plan_lock(lock, signing_key=signing_key, principal=signing_principal or "agent-careflow")
    lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lock_path


def read_plan_lock(lock_path: Path) -> dict[str, object]:
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{lock_path}: invalid JSON: {exc}") from exc
    if not isinstance(lock, dict):
        raise ValidationError(f"{lock_path}: lock must be a JSON object")
    return lock


def validate_plan_lock(plan_path: Path, *, required: bool = False, require_signature: bool = False, allowed_signers: Path | None = None, signing_principal: str | None = None) -> None:
    lock_path = plan_lock_path(plan_path)
    if not lock_path.exists():
        if required:
            raise ValidationError(f"{lock_path}: missing PLAN lock")
        return
    lock = read_plan_lock(lock_path)
    for field in ("schema_version", "case_id", "plan_path", "plan_hash", "locked_at"):
        if field not in lock or lock[field] in ("", None):
            raise ValidationError(f"{lock_path}: missing {field}")
    if lock["schema_version"] != 1:
        raise ValidationError(f"{lock_path}: unsupported schema_version {lock['schema_version']!r}")
    plan_data = parse_front_matter_lines(plan_path.read_text(encoding="utf-8"))
    if lock["case_id"] != plan_data.get("case_id"):
        raise ValidationError(f"{lock_path}: case_id does not match PLAN.md")
    if lock["plan_path"] != plan_path.name:
        raise ValidationError(f"{lock_path}: plan_path must be {plan_path.name}")
    actual_hash = sha256_file(plan_path)
    if lock["plan_hash"] != actual_hash:
        raise ValidationError(f"{lock_path}: stale plan lock: expected {lock['plan_hash']}, actual {actual_hash}")
    if require_signature:
        if not allowed_signers:
            raise ValidationError("allowed signers file is required for PLAN lock signature verification")
        verify_plan_lock_signature(lock, lock_path, allowed_signers=allowed_signers, principal=signing_principal)


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
    from .schema_validation import validate_data_against_schema

    data = parse_front_matter_lines(case_path.read_text(encoding="utf-8"))
    validate_data_against_schema(data, "CASE", case_path)
    require_fields(data, ["case_id", "title", "risk", "phase", "status", "created_at", "owner"], case_path)
    if data["risk"] not in RISK_CLASSES:
        raise ValidationError(f"{case_path}: invalid risk class {data['risk']!r}")


def validate_plan(plan_path: Path, *, require_lock: bool = False, require_signature: bool = False, allowed_signers: Path | None = None, signing_principal: str | None = None) -> None:
    from .schema_validation import validate_data_against_schema

    text = plan_path.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    validate_data_against_schema(data, "PLAN", plan_path)
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
    validate_plan_lock(plan_path, required=require_lock or require_signature, require_signature=require_signature, allowed_signers=allowed_signers, signing_principal=signing_principal)


def validate_order(order_path: Path, repo_root: Path | None = None) -> None:
    from .schema_validation import validate_data_against_schema

    repo_root = repo_root or Path.cwd()
    text = order_path.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    validate_data_against_schema(data, "ORDER", order_path)
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
    lock_path = plan_lock_path(plan_path)
    if lock_path.exists():
        validate_plan_lock(plan_path, required=True)
        lock = read_plan_lock(lock_path)
        if data["plan_hash"] != lock["plan_hash"]:
            raise ValidationError(f"{order_path}: plan_hash does not match PLAN.lock.json")


def validate_discharge(discharge_path: Path, case_root: Path | None = None) -> None:
    from .schema_validation import validate_data_against_schema

    text = discharge_path.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    validate_data_against_schema(data, "DISCHARGE", discharge_path)
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
