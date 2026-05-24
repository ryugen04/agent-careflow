from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_careflow.artifacts import ValidationError
from agent_careflow.hooks import claude, codex, cursor
from agent_careflow.hooks.common import (
    evaluate_lifecycle_hook,
    evaluate_permission_request,
    evaluate_pre_tool_use,
    evaluate_user_prompt_submit,
    extract_command,
    extract_file_path,
    hook_context,
    load_payload,
)
from agent_careflow.policy.decisions import Decision

SCHEMA = "agent-careflow.adapter_conformance.v1"
ADAPTERS = {"codex", "claude", "cursor"}
EVENTS = {
    "pre-tool-use",
    "post-tool-use",
    "permission-request",
    "user-prompt-submit",
    "stop",
    "subagent-start",
    "subagent-stop",
}
STATUSES = {"pass", "fail", "unsupported", "environment_unavailable"}
ADAPTER_EVENTS = {
    "codex": {"pre-tool-use", "post-tool-use", "permission-request", "user-prompt-submit", "stop"},
    "claude": {"pre-tool-use", "post-tool-use", "stop", "subagent-start", "subagent-stop"},
    "cursor": {"pre-tool-use", "post-tool-use", "stop"},
}
REQUIRED_FIELDS = {
    "schema",
    "recorded_at",
    "adapter",
    "event",
    "fixture",
    "input_payload",
    "normalized_event",
    "decision",
    "rendered_output",
    "status",
    "notes",
}


@dataclass(frozen=True)
class ConformanceRecord:
    schema: str
    recorded_at: str
    adapter: str
    event: str
    fixture: str
    input_payload: dict[str, Any]
    normalized_event: dict[str, Any]
    decision: dict[str, str]
    rendered_output: dict[str, Any]
    status: str
    notes: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        return load_payload(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValidationError(f"fixture not found: {path}") from exc


def normalize_event(payload: dict[str, Any], *, event: str) -> dict[str, Any]:
    if event not in EVENTS:
        raise ValidationError(f"unsupported conformance event: {event}")
    context = hook_context(payload)
    normalized: dict[str, Any] = {
        "event": event,
        "case_id": context.case_id,
        "order_id": context.order_id,
        "cwd": str(context.cwd),
    }
    command = extract_command(payload)
    if command is not None:
        normalized["command"] = command
    file_path = extract_file_path(payload)
    if file_path is not None:
        normalized["file_path"] = file_path
    tool_name = payload.get("tool_name")
    if isinstance(tool_name, str):
        normalized["tool_name"] = tool_name
    prompt = payload.get("prompt")
    if isinstance(prompt, str):
        normalized["prompt"] = prompt
    return normalized


def evaluate_event(payload: dict[str, Any], *, event: str) -> Decision:
    if event == "permission-request":
        return evaluate_permission_request(payload, on_missing_context="deny")
    if event == "user-prompt-submit":
        return evaluate_user_prompt_submit(payload)
    if event in {"stop", "subagent-start", "subagent-stop"}:
        return evaluate_lifecycle_hook(payload)
    return evaluate_pre_tool_use(payload)


def render_adapter_output(adapter: str, event: str, decision: Decision) -> str:
    if adapter == "codex":
        if event == "permission-request":
            return codex.render_permission_request(decision)
        if event == "user-prompt-submit":
            return codex.render_user_prompt_submit(decision)
        if event == "post-tool-use":
            return codex.render_post_tool_use(decision)
        if event == "stop":
            return codex.render_stop(decision)
        return codex.render_pre_tool_use(decision)
    if adapter == "claude":
        if event == "post-tool-use":
            return claude.render_post_tool_use(decision)
        if event == "stop":
            return claude.render_stop(decision)
        if event == "subagent-start":
            return claude.render_subagent_start(decision)
        if event == "subagent-stop":
            return claude.render_subagent_stop(decision)
        return claude.render_pre_tool_use(decision)
    if adapter == "cursor":
        if event == "post-tool-use":
            return cursor.render_post_tool_use(decision)
        if event == "stop":
            return cursor.render_stop(decision)
        return cursor.render_pre_tool_use(decision)
    raise ValidationError(f"unsupported conformance adapter: {adapter}")


def make_record(*, adapter: str, event: str, fixture: Path, notes: str = "fixture replay") -> ConformanceRecord:
    if adapter not in ADAPTERS:
        raise ValidationError(f"unsupported conformance adapter: {adapter}")
    if event not in EVENTS:
        raise ValidationError(f"unsupported conformance event: {event}")
    payload = load_fixture(fixture)
    normalized = normalize_event(payload, event=event)
    decision = evaluate_event(payload, event=event)
    if event not in ADAPTER_EVENTS[adapter]:
        return ConformanceRecord(
            schema=SCHEMA,
            recorded_at=_timestamp(),
            adapter=adapter,
            event=event,
            fixture=fixture.as_posix(),
            input_payload=payload,
            normalized_event=normalized,
            decision={"status": decision.status.value, "reason": decision.reason},
            rendered_output={},
            status="unsupported",
            notes=f"{adapter} adapter does not support {event}",
        )
    rendered_text = render_adapter_output(adapter, event, decision)
    try:
        rendered = json.loads(rendered_text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"adapter rendered invalid JSON: {exc}") from exc
    return ConformanceRecord(
        schema=SCHEMA,
        recorded_at=_timestamp(),
        adapter=adapter,
        event=event,
        fixture=fixture.as_posix(),
        input_payload=payload,
        normalized_event=normalized,
        decision={"status": decision.status.value, "reason": decision.reason},
        rendered_output=rendered,
        status="pass",
        notes=notes,
    )


def append_record(*, output: Path, adapter: str, event: str, fixture: Path, notes: str = "fixture replay") -> ConformanceRecord:
    record = make_record(adapter=adapter, event=event, fixture=fixture, notes=notes)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
    return record


def validate_record(record: dict[str, Any], *, path: Path, line_number: int) -> None:
    if "schema" in record and record["schema"] != SCHEMA:
        raise ValidationError(f"{path}:{line_number}: unsupported schema {record['schema']!r}")
    missing = sorted(field for field in REQUIRED_FIELDS if field not in record)
    if missing:
        raise ValidationError(f"{path}:{line_number}: missing field(s): {', '.join(missing)}")
    if record["adapter"] not in ADAPTERS:
        raise ValidationError(f"{path}:{line_number}: unsupported adapter {record['adapter']!r}")
    if record["event"] not in EVENTS:
        raise ValidationError(f"{path}:{line_number}: unsupported event {record['event']!r}")
    if record["status"] not in STATUSES:
        raise ValidationError(f"{path}:{line_number}: unsupported status {record['status']!r}")
    for field in ("input_payload", "normalized_event", "decision", "rendered_output"):
        if not isinstance(record[field], dict):
            raise ValidationError(f"{path}:{line_number}: {field} must be an object")
    if not isinstance(record["fixture"], str) or not record["fixture"]:
        raise ValidationError(f"{path}:{line_number}: fixture must be a non-empty string")


def validate_file(path: Path) -> int:
    if not path.exists():
        raise ValidationError(f"conformance file not found: {path}")
    count = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValidationError(f"{path}:{line_number}: record must be an object")
        validate_record(record, path=path, line_number=line_number)
        count += 1
    if count == 0:
        raise ValidationError(f"{path}: no conformance records found")
    return count


def read_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        validate_file(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def discover_record_files(root: Path) -> list[Path]:
    return sorted((root / ".careflow" / "conformance").glob("**/*.jsonl"))


def conformance_status(*, root: Path, inputs: list[Path] | None = None) -> dict[str, Any]:
    paths = inputs if inputs is not None else discover_record_files(root)
    records = read_records(paths) if paths else []
    summary: dict[str, Any] = {
        "schema": "agent-careflow.conformance_status.v1",
        "recorded_at": _timestamp(),
        "records": len(records),
        "files": [path.as_posix() for path in paths],
        "adapters": {},
    }
    by_adapter: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        by_adapter[record["adapter"]][record["status"]] += 1
    for adapter in sorted(ADAPTERS):
        counts = {status: by_adapter[adapter].get(status, 0) for status in sorted(STATUSES)}
        summary["adapters"][adapter] = counts
    return summary


def render_status_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# Adapter Conformance Status",
        "",
        f"recorded_at: {status['recorded_at']}",
        f"records: {status['records']}",
        "",
        "| Adapter | Pass | Fail | Unsupported | Environment unavailable |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for adapter, counts in sorted(status["adapters"].items()):
        lines.append(
            f"| {adapter} | {counts['pass']} | {counts['fail']} | {counts['unsupported']} | {counts['environment_unavailable']} |"
        )
    lines.append("")
    if status["files"]:
        lines.extend(["## Files", ""])
        lines.extend(f"- {path}" for path in status["files"])
        lines.append("")
    return "\n".join(lines)
