from __future__ import annotations

import json
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
