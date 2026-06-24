from __future__ import annotations

from pathlib import Path

from agent_careflow.claude_review import check_claude_auth, render_claude_auth_report, build_claude_review_prompt, run_claude_review
from agent_careflow.lifecycle import issue_order, validate_review
from agent_careflow.templates import render_plan


def make_case(tmp_path: Path) -> Path:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    for child in ["orders", "results", "evidence", "incidents", "reviews", "reviews/requests", "learnings"]:
        (case / child).mkdir(parents=True, exist_ok=True)
    (case / "CASE.yaml").write_text("case_id: ACF-1\nstatus: active\nphase: review\n", encoding="utf-8")
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Claude review test", "C2"), encoding="utf-8")
    (case / "results" / "ORD-1.result.md").write_text("order_id: ORD-1\ncase_id: ACF-1\nstatus: complete\n", encoding="utf-8")
    issue_order(tmp_path, "ACF-1", "ORD-1", "implementer")
    return case


def test_build_claude_review_prompt_contains_fixed_header_and_review_contract(tmp_path: Path) -> None:
    make_case(tmp_path)

    prompt = build_claude_review_prompt(tmp_path, "ACF-1", "ORD-1", review_id="REVIEW-CLAUDE-ORD-1")

    assert prompt.startswith("PLAN_FILE: .careflow/cases/ACF-1/PLAN.md\n")
    assert "ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in prompt
    assert "SUBPLAN_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in prompt
    assert "EXPECTED_RESULT_PATH: .careflow/cases/ACF-1/results/ORD-1.result.md" in prompt
    assert "EXPECTED_REVIEW_PATH: .careflow/cases/ACF-1/reviews/REVIEW-CLAUDE-ORD-1.review.md" in prompt
    assert "Return only the complete review artifact markdown" in prompt
    assert "Do not submit an auth-unavailable placeholder" in prompt


def test_run_claude_review_writes_and_validates_review_from_stdout(tmp_path: Path) -> None:
    make_case(tmp_path)
    fake_claude = tmp_path / "fake-claude"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "# REVIEW: REVIEW-CLAUDE-ORD-1\n\n"
        "review_id: REVIEW-CLAUDE-ORD-1\n"
        "case_id: ACF-1\n"
        "tool: claude\n"
        "status: pass\n"
        "plan_path: .careflow/cases/ACF-1/PLAN.md\n"
        "order_path: .careflow/cases/ACF-1/orders/ORD-1.order.md\n"
        "result_path: .careflow/cases/ACF-1/results/ORD-1.result.md\n\n"
        "## Scope\n\nPLAN, ORDER, RESULT, and evidence.\n\n"
        "## Findings\n\n- Severity: none; no blocking issues found.\n\n"
        "## Evidence reviewed\n\n- PLAN, ORDER, RESULT, and evidence directory.\n\n"
        "## Recommendation\n\nPass.\n"
        "EOF\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    review_path = run_claude_review(tmp_path, "ACF-1", "ORD-1", review_id="REVIEW-CLAUDE-ORD-1", claude_bin=fake_claude.as_posix())

    assert review_path == tmp_path / ".careflow" / "cases" / "ACF-1" / "reviews" / "REVIEW-CLAUDE-ORD-1.review.md"
    assert "tool: claude" in review_path.read_text(encoding="utf-8")
    validate_review(review_path, strict=True)


def test_run_claude_review_dry_run_writes_request_without_review(tmp_path: Path) -> None:
    case = make_case(tmp_path)

    review_path = run_claude_review(tmp_path, "ACF-1", "ORD-1", review_id="REVIEW-CLAUDE-ORD-1", dry_run=True)

    assert review_path == case / "reviews" / "REVIEW-CLAUDE-ORD-1.review.md"
    assert not review_path.exists()
    request = case / "reviews" / "requests" / "REQUEST-CLAUDE-ORD-1.md"
    assert request.exists()
    assert "EXPECTED_REVIEW_PATH: .careflow/cases/ACF-1/reviews/REVIEW-CLAUDE-ORD-1.review.md" in request.read_text(encoding="utf-8")


def test_run_claude_review_retries_default_thinking_error_with_sonnet(tmp_path: Path) -> None:
    make_case(tmp_path)
    fake_claude = tmp_path / "fake-claude"
    calls = tmp_path / "calls.txt"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'CALL %s\\0' \"$*\" >> {calls.as_posix()}\n"
        "if [[ \"$*\" != *\"--model sonnet\"* ]]; then\n"
        "  echo \"Using Claude with claude-opus-4-6 and 'thinking.type=enabled' is deprecated\" >&2\n"
        "  exit 1\n"
        "fi\n"
        "cat <<'EOF'\n"
        "# REVIEW: REVIEW-CLAUDE-ORD-1\n\n"
        "review_id: REVIEW-CLAUDE-ORD-1\n"
        "case_id: ACF-1\n"
        "tool: claude\n"
        "status: pass\n"
        "plan_path: .careflow/cases/ACF-1/PLAN.md\n"
        "order_path: .careflow/cases/ACF-1/orders/ORD-1.order.md\n"
        "result_path: .careflow/cases/ACF-1/results/ORD-1.result.md\n\n"
        "## Scope\n\nPLAN, ORDER, RESULT, and evidence.\n\n"
        "## Findings\n\n- Severity: none; no blocking issues found.\n\n"
        "## Evidence reviewed\n\n- PLAN, ORDER, RESULT, and evidence directory.\n\n"
        "## Recommendation\n\nPass.\n"
        "EOF\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    review_path = run_claude_review(tmp_path, "ACF-1", "ORD-1", review_id="REVIEW-CLAUDE-ORD-1", claude_bin=fake_claude.as_posix())

    assert review_path.exists()
    call_entries = [entry for entry in calls.read_text(encoding="utf-8").split("\0") if entry]
    assert len(call_entries) == 2
    assert "--model sonnet" not in call_entries[0]
    assert "--model sonnet" in call_entries[1]


def test_run_claude_review_does_not_retry_when_model_is_explicit(tmp_path: Path) -> None:
    make_case(tmp_path)
    fake_claude = tmp_path / "fake-claude"
    calls = tmp_path / "calls.txt"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'CALL %s\\0' \"$*\" >> {calls.as_posix()}\n"
        "echo \"Using Claude with claude-opus-4-6 and 'thinking.type=enabled' is deprecated\" >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    try:
        run_claude_review(
            tmp_path,
            "ACF-1",
            "ORD-1",
            review_id="REVIEW-CLAUDE-ORD-1",
            claude_bin=fake_claude.as_posix(),
            model="opus",
        )
    except Exception as exc:
        assert "thinking.type=enabled" in str(exc)
    else:
        raise AssertionError("explicit model failure should not be retried")

    assert len([entry for entry in calls.read_text(encoding="utf-8").split("\0") if entry]) == 1


def test_check_claude_auth_reports_pass_with_fallback_model(tmp_path: Path) -> None:
    fake_claude = tmp_path / "fake-claude"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" != *\"--model sonnet\"* ]]; then\n"
        "  echo \"Using Claude with claude-opus-4-6 and 'thinking.type=enabled' is deprecated\" >&2\n"
        "  exit 1\n"
        "fi\n"
        "echo ok\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    report = check_claude_auth(tmp_path, claude_bin=fake_claude.as_posix())

    assert report["status"] == "pass"
    assert report["model"] == "sonnet"
    assert report["fallback_used"] is True
    assert "auth=pass" in render_claude_auth_report(report)


def test_check_claude_auth_reports_auth_failure_without_placeholder(tmp_path: Path) -> None:
    fake_claude = tmp_path / "fake-claude"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        "echo \"Failed to authenticate. API Error: 401 Invalid authentication credentials\" >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    report = check_claude_auth(tmp_path, claude_bin=fake_claude.as_posix(), model="sonnet")

    assert report["status"] == "fail"
    assert report["exit_code"] == 1
    assert "401 Invalid authentication credentials" in report["details"]
    assert "placeholder" not in render_claude_auth_report(report).lower()
