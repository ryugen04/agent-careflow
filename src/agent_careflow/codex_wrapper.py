from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from agent_careflow.policy.decisions import DecisionStatus
from agent_careflow.policy.prompt_policy import check_prompt_text

VALUE_OPTIONS = {
    "-c",
    "--config",
    "-i",
    "--image",
    "-m",
    "--model",
    "--local-provider",
    "-p",
    "--profile",
    "-s",
    "--sandbox",
    "-C",
    "--cd",
    "--add-dir",
    "--output-schema",
    "--color",
    "-o",
    "--output-last-message",
}
EXEC_SUBCOMMANDS = {"resume", "review", "help"}


@dataclass(frozen=True)
class GuardedCodexResult:
    exit_code: int
    command: list[str]
    stdout: str
    stderr: str
    invoked: bool
    blocked: bool
    reason: str


def _option_name(arg: str) -> str:
    if "=" in arg and arg.startswith("--"):
        return arg.split("=", 1)[0]
    return arg


def extract_exec_prompt(args: Sequence[str], *, stdin_text: str = "") -> str:
    positionals: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            positionals.extend(args[index + 1 :])
            break
        if arg in EXEC_SUBCOMMANDS and not positionals:
            return stdin_text.strip()
        if arg == "-":
            if stdin_text:
                positionals.append(stdin_text)
            index += 1
            continue
        if arg.startswith("-"):
            opt = _option_name(arg)
            if opt in VALUE_OPTIONS and "=" not in arg:
                index += 2
            else:
                index += 1
            continue
        positionals.extend(args[index:])
        break
    prompt = " ".join(part for part in positionals if part)
    if stdin_text and stdin_text not in positionals:
        prompt = f"{prompt}\n{stdin_text}" if prompt else stdin_text
    return prompt


def _codex_version(codex_bin: str) -> str:
    try:
        result = subprocess.run([codex_bin, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20)
    except OSError as exc:
        return f"unavailable: {exc}"
    return result.stdout.strip() or result.stderr.strip() or "unknown"


def _write_probe_record(
    path: Path | None,
    *,
    codex_bin: str,
    command: list[str],
    cwd: Path,
    prompt: str,
    blocked: bool,
    exit_code: int,
    stdout: str,
    stderr: str,
    reason: str,
    invoked: bool,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "codex.runtime_probe.v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "codex_version": _codex_version(codex_bin),
        "probe": "agent-careflow-codex-wrapper-preflight",
        "event": "UserPromptSubmit",
        "command": command,
        "cwd": cwd.as_posix(),
        "input_payload": {"prompt": prompt, "blocked": blocked, "invoked": invoked},
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "verdict": "pass",
        "notes": reason,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def run_guarded_codex_exec(
    args: Sequence[str],
    *,
    stdin_text: str = "",
    codex_bin: str = "codex",
    dry_run: bool = False,
    probe_output: Path | None = None,
    cwd: Path | None = None,
) -> GuardedCodexResult:
    cwd = cwd or Path.cwd()
    prompt = extract_exec_prompt(args, stdin_text=stdin_text)
    decision = check_prompt_text(prompt)
    command = [codex_bin, "exec", *args]
    if decision.status == DecisionStatus.DENY:
        stderr = decision.reason
        _write_probe_record(
            probe_output,
            codex_bin=codex_bin,
            command=command,
            cwd=cwd,
            prompt=prompt,
            blocked=True,
            exit_code=2,
            stdout="",
            stderr=stderr,
            reason=f"wrapper blocked prompt before Codex invocation: {decision.reason}",
            invoked=False,
        )
        return GuardedCodexResult(2, command, "", stderr, False, True, decision.reason)

    if dry_run:
        stdout = "dry-run: prompt allowed"
        _write_probe_record(
            probe_output,
            codex_bin=codex_bin,
            command=command,
            cwd=cwd,
            prompt=prompt,
            blocked=False,
            exit_code=0,
            stdout=stdout,
            stderr="",
            reason="wrapper allowed prompt before Codex invocation (dry-run)",
            invoked=False,
        )
        return GuardedCodexResult(0, command, stdout, "", False, False, decision.reason)

    completed = subprocess.run(command, text=True, input=stdin_text if stdin_text else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, cwd=cwd)
    _write_probe_record(
        probe_output,
        codex_bin=codex_bin,
        command=command,
        cwd=cwd,
        prompt=prompt,
        blocked=False,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        reason="wrapper allowed prompt before Codex invocation",
        invoked=True,
    )
    return GuardedCodexResult(completed.returncode, command, completed.stdout, completed.stderr, True, False, decision.reason)
