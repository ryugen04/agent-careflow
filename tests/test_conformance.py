from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from agent_careflow.artifacts import ValidationError
from agent_careflow.conformance import append_record, conformance_status, make_record, render_status_markdown, validate_file

FIXTURES = Path(__file__).parent / "fixtures" / "hooks"
DANGEROUS = "git reset --" + "hard HEAD"
DANGEROUS_REASON = "git reset --" + "hard is blocked by policy"


def test_codex_conformance_record_replays_dangerous_bash(tmp_path: Path) -> None:
    output = tmp_path / "conformance.jsonl"

    append_record(
        output=output,
        adapter="codex",
        event="pre-tool-use",
        fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json",
    )

    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["schema"] == "agent-careflow.adapter_conformance.v1"
    assert record["adapter"] == "codex"
    assert record["event"] == "pre-tool-use"
    assert record["normalized_event"]["command"] == DANGEROUS
    assert record["decision"]["status"] == "deny"
    assert record["rendered_output"]["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert record["status"] == "pass"


def test_claude_conformance_records_missing_context_warning() -> None:
    record = make_record(
        adapter="claude",
        event="pre-tool-use",
        fixture=FIXTURES / "claude_pre_tool_use_write_missing_context.json",
    )

    assert record.decision["status"] == "warn"
    assert "systemMessage" in record.rendered_output
    assert record.status == "pass"


def test_cursor_conformance_records_generic_block_renderer() -> None:
    record = make_record(
        adapter="cursor",
        event="pre-tool-use",
        fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json",
    )

    assert record.rendered_output == {"decision": "block", "reason": DANGEROUS_REASON}


def test_codex_prompt_guard_conformance_records_deny_json(tmp_path: Path) -> None:
    fixture = tmp_path / "prompt.json"
    fixture.write_text('{"prompt":"debug patient MRN: ABC123456"}', encoding="utf-8")

    record = make_record(adapter="codex", event="user-prompt-submit", fixture=fixture)

    assert record.decision["status"] == "deny"
    assert record.rendered_output["continue"] is False


def test_lifecycle_conformance_outputs_json_only() -> None:
    record = make_record(
        adapter="codex",
        event="stop",
        fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json",
    )

    assert record.rendered_output == {}
    assert record.status == "pass"


def test_conformance_validate_accepts_valid_record(tmp_path: Path) -> None:
    output = tmp_path / "conformance.jsonl"
    append_record(output=output, adapter="codex", event="pre-tool-use", fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json")

    assert validate_file(output) == 1


def test_conformance_validate_rejects_unknown_adapter_event_status_and_schema(tmp_path: Path) -> None:
    good = asdict(make_record(adapter="codex", event="pre-tool-use", fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json"))
    cases = [
        ("adapter", "unknown", "unsupported adapter"),
        ("event", "unknown", "unsupported event"),
        ("status", "inconclusive", "unsupported status"),
        ("schema", "codex.runtime_probe.v1", "unsupported schema"),
    ]
    for field, value, message in cases:
        path = tmp_path / f"bad-{field}.jsonl"
        bad = dict(good)
        bad[field] = value
        path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        try:
            validate_file(path)
        except ValidationError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"expected ValidationError for {field}")


def test_conformance_status_markdown_summarizes_by_adapter(tmp_path: Path) -> None:
    output = tmp_path / ".careflow" / "conformance" / "adapter.jsonl"
    append_record(output=output, adapter="codex", event="pre-tool-use", fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json")
    append_record(output=output, adapter="cursor", event="permission-request", fixture=FIXTURES / "codex_pre_tool_use_bash_danger.json")

    markdown = render_status_markdown(conformance_status(root=tmp_path))

    assert "| codex | 1 | 0 | 0 | 0 |" in markdown
    assert "| cursor | 0 | 0 | 1 | 0 |" in markdown


def test_old_runtime_probe_record_with_inconclusive_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "runtime-probe.jsonl"
    output.write_text(
        '{"schema":"codex.runtime_probe.v1","recorded_at":"now","probe":"unit","event":"Stop","command":[],"cwd":".","input_payload":{},"stdout":"","stderr":"","exit_code":0,"verdict":"inconclusive","notes":"old"}\n',
        encoding="utf-8",
    )

    try:
        validate_file(output)
    except ValidationError as exc:
        assert "unsupported schema" in str(exc)
    else:
        raise AssertionError("expected ValidationError")
