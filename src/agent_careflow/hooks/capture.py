from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_careflow.artifacts import ValidationError

ALLOWED_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "Stop", "config"}


def codex_version() -> str:
    try:
        proc = subprocess.run(["codex", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return proc.stdout.strip() or "unknown"


def append_capture_record(
    *,
    output: Path,
    event: str,
    probe: str,
    cwd: Path,
    input_payload: dict[str, Any],
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    verdict: str = "inconclusive",
    notes: str = "runtime-observed: captured hook stdin payload",
) -> None:
    if event not in ALLOWED_EVENTS:
        raise ValidationError(f"unsupported probe event: {event}")
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "codex.runtime_probe.v1",
        "recorded_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "codex_version": codex_version(),
        "probe": probe,
        "event": event,
        "command": ["agent-careflow", "hook", "capture"],
        "cwd": str(cwd),
        "input_payload": input_payload,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "verdict": verdict,
        "notes": notes,
    }
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")

REQUIRED_RECORD_FIELDS = {"schema", "recorded_at", "probe", "event", "command", "cwd", "input_payload", "stdout", "stderr", "exit_code", "verdict", "notes"}
ALLOWED_VERDICTS = {"pass", "fail", "inconclusive"}


def validate_capture_record(record: dict[str, Any], *, path: Path, line_number: int) -> None:
    missing = sorted(field for field in REQUIRED_RECORD_FIELDS if field not in record)
    if missing:
        raise ValidationError(f"{path}:{line_number}: missing field(s): {', '.join(missing)}")
    if record["schema"] != "codex.runtime_probe.v1":
        raise ValidationError(f"{path}:{line_number}: unsupported schema {record['schema']!r}")
    if record["event"] not in ALLOWED_EVENTS:
        raise ValidationError(f"{path}:{line_number}: unsupported event {record['event']!r}")
    if record["verdict"] not in ALLOWED_VERDICTS:
        raise ValidationError(f"{path}:{line_number}: unsupported verdict {record['verdict']!r}")
    if not isinstance(record["input_payload"], dict):
        raise ValidationError(f"{path}:{line_number}: input_payload must be an object")


def validate_capture_file(path: Path) -> int:
    if not path.exists():
        raise ValidationError(f"probe file not found: {path}")
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
        validate_capture_record(record, path=path, line_number=line_number)
        count += 1
    if count == 0:
        raise ValidationError(f"{path}: no probe records found")
    return count

def tool_version(command: str) -> dict[str, Any]:
    path = shutil.which(command)
    result: dict[str, Any] = {"command": command, "available": bool(path), "path": path, "version": None}
    if not path:
        return result
    try:
        proc = subprocess.run([command, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        result["version_error"] = str(exc)
        return result
    result["version"] = (proc.stdout.strip() or proc.stderr.strip() or None)
    result["version_exit_code"] = proc.returncode
    return result


def runtime_status(*, root: Path, probe_files: list[Path] | None = None) -> dict[str, Any]:
    probes = []
    for probe_file in probe_files or sorted((root / ".codex" / "probes").glob("*/runtime-probe.jsonl")):
        try:
            count = validate_capture_file(probe_file)
        except ValidationError as exc:
            probes.append({"path": probe_file.as_posix(), "ok": False, "error": str(exc)})
        else:
            probes.append({"path": probe_file.as_posix(), "ok": True, "records": count})
    return {
        "schema": "agent-careflow.runtime_status.v1",
        "recorded_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tools": {tool: tool_version(tool) for tool in ("codex", "claude", "cursor")},
        "probes": probes,
    }


def render_runtime_status(status: dict[str, Any]) -> str:
    lines = ["# Runtime Probe Status", "", f"recorded_at: {status['recorded_at']}", "", "## Tools", ""]
    for name, tool in status["tools"].items():
        available = "yes" if tool["available"] else "no"
        version = tool.get("version") or "unknown"
        path = tool.get("path") or "not found"
        lines.append(f"- {name}: available={available}; version={version}; path={path}")
    lines.extend(["", "## Probe Files", ""])
    if not status["probes"]:
        lines.append("- none")
    for probe in status["probes"]:
        if probe["ok"]:
            lines.append(f"- {probe['path']}: valid ({probe['records']} record(s))")
        else:
            lines.append(f"- {probe['path']}: invalid ({probe['error']})")
    lines.append("")
    return "\n".join(lines)
