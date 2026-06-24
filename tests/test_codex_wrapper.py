from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.codex_wrapper import extract_exec_prompt, run_guarded_codex_exec


def test_extract_exec_prompt_from_options_and_positional_prompt() -> None:
    args = ["--json", "--sandbox", "read-only", "-C", "/tmp/work", "refactor validator tests"]

    assert extract_exec_prompt(args, stdin_text="") == "refactor validator tests"


def test_extract_exec_prompt_combines_stdin_with_positional_prompt() -> None:
    args = ["--json", "summarize stdin"]

    assert extract_exec_prompt(args, stdin_text="secret token=abcdefghijklmnop") == "summarize stdin\nsecret token=abcdefghijklmnop"


def test_guarded_codex_exec_blocks_prompt_policy_denial(tmp_path: Path) -> None:
    log = tmp_path / "wrapper.jsonl"

    result = run_guarded_codex_exec(
        ["--json", "debug patient MRN: ABC123456 in this fixture"],
        stdin_text="",
        codex_bin="codex",
        dry_run=True,
        probe_output=log,
    )

    assert result.exit_code == 2
    assert not result.invoked
    assert "possible medical record identifier" in result.stderr
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert records[0]["schema"] == "codex.runtime_probe.v1"
    assert records[0]["event"] == "UserPromptSubmit"
    assert records[0]["probe"] == "agent-careflow-codex-wrapper-preflight"
    assert records[0]["verdict"] == "pass"
    assert records[0]["input_payload"]["blocked"] is True


def test_guarded_codex_exec_allows_benign_prompt_in_dry_run(tmp_path: Path) -> None:
    log = tmp_path / "wrapper.jsonl"

    result = run_guarded_codex_exec(
        ["--json", "refactor validator tests"],
        stdin_text="",
        codex_bin="codex",
        dry_run=True,
        probe_output=log,
    )

    assert result.exit_code == 0
    assert not result.invoked
    assert result.command == ["codex", "exec", "--json", "refactor validator tests"]
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert records[0]["verdict"] == "pass"
    assert records[0]["input_payload"]["blocked"] is False
