from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.lifecycle import advance_phase, case_status, collect_evidence, issue_order, new_incident, new_learning, new_review, new_review_request, promote_learning, require_reviews, validate_result, validate_review
from agent_careflow.templates import render_discharge, render_plan


def make_case(tmp_path: Path, phase: str = "planning") -> Path:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    for child in ["orders", "results", "evidence", "incidents", "reviews", "learnings", "conferences"]:
        (case / child).mkdir(parents=True, exist_ok=True)
    (case / "CASE.yaml").write_text(
        f"""case_id: ACF-1
title: Lifecycle test
risk: C2
phase: {phase}
status: active
created_at: 2026-05-20T00:00:00+09:00
owner: test
allowed_scope:
  - src/**
  - .careflow/**
""",
        encoding="utf-8",
    )
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Lifecycle test", "C2"), encoding="utf-8")
    (case / "DISCHARGE.md").write_text(render_discharge("ACF-1"), encoding="utf-8")
    return case


def test_phase_status_reports_evidence_and_incidents(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    (case / "evidence" / "pytest.txt").write_text("ok", encoding="utf-8")
    new_incident(tmp_path, "ACF-1", "scope_violation")

    status = case_status(tmp_path, "ACF-1")

    assert status["evidence_count"] == 1
    assert status["open_incidents"] == ["INC-001-scope-violation.md"]


def test_phase_advance_to_review_requires_evidence(tmp_path: Path) -> None:
    make_case(tmp_path)

    with pytest.raises(ValidationError, match="evidence"):
        advance_phase(tmp_path, "ACF-1", "review")


def test_phase_advance_to_discharge_blocks_open_incident(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    (case / "evidence" / "pytest.txt").write_text("ok", encoding="utf-8")
    new_incident(tmp_path, "ACF-1", "scope_violation")

    with pytest.raises(ValidationError, match="open incident"):
        advance_phase(tmp_path, "ACF-1", "discharge")


def test_issue_order_creates_valid_order(tmp_path: Path) -> None:
    make_case(tmp_path)

    path = issue_order(tmp_path, "ACF-1", "ORD-2", "verifier")

    assert path.exists()
    assert "plan_path: .careflow/cases/ACF-1/PLAN.md" in path.read_text(encoding="utf-8")


def test_result_and_review_validate_required_fields(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    result = case / "results" / "ORD-1.result.md"
    result.write_text("""# RESULT

order_id: ORD-1
case_id: ACF-1
status: complete
""", encoding="utf-8")
    review = case / "reviews" / "REVIEW-1.md"
    review.write_text("""# REVIEW

review_id: REVIEW-1
case_id: ACF-1
status: pass
""", encoding="utf-8")

    validate_result(result)
    validate_review(review)



def test_close_validate_alias_uses_discharge_validator(tmp_path: Path, monkeypatch) -> None:
    from agent_careflow.cli import main

    make_case(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["close", "validate", "--case", "ACF-1"]) == 1


def test_collect_git_status_evidence(tmp_path: Path) -> None:
    make_case(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (tmp_path / "tracked.txt").write_text("changed", encoding="utf-8")

    path = collect_evidence(tmp_path, "ACF-1", "git-status")

    text = path.read_text(encoding="utf-8")
    assert path.name == "git-status.txt"
    assert "$ git status --short" in text
    assert "tracked.txt" in text


def test_collect_evidence_rejects_unknown_kind(tmp_path: Path) -> None:
    make_case(tmp_path)

    with pytest.raises(ValidationError, match="unsupported evidence kind"):
        collect_evidence(tmp_path, "ACF-1", "pytest")


def test_learning_new_and_promote_to_docs(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    incident = new_incident(tmp_path, "ACF-1", "runtime_gap")

    learning = new_learning(tmp_path, "ACF-1", "Codex prompt hook gap", source_incident=incident.relative_to(tmp_path).as_posix())

    text = learning.read_text(encoding="utf-8")
    assert learning.name.startswith("LRN-001-codex-prompt-hook-gap")
    assert "source_incident: .careflow/cases/ACF-1/incidents/INC-001-runtime-gap.md" in text
    target = promote_learning(tmp_path, "ACF-1", learning.name, Path("docs/learnings/codex-prompt-hook-gap.md"))

    assert target == tmp_path / "docs" / "learnings" / "codex-prompt-hook-gap.md"
    promoted = target.read_text(encoding="utf-8")
    assert "source_learning: .careflow/cases/ACF-1/learnings/" in promoted
    assert "# Codex prompt hook gap" in promoted
    assert "status: promoted" in promoted
    assert "status: promoted" in learning.read_text(encoding="utf-8")
    assert "promoted_to: docs/learnings/codex-prompt-hook-gap.md" in learning.read_text(encoding="utf-8")


def test_learning_promote_refuses_overwrite_without_force(tmp_path: Path) -> None:
    make_case(tmp_path)
    learning = new_learning(tmp_path, "ACF-1", "Overwrite guard")
    target = tmp_path / "docs" / "learning.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(ValidationError, match="promotion target exists"):
        promote_learning(tmp_path, "ACF-1", learning.name, Path("docs/learning.md"))

    promote_learning(tmp_path, "ACF-1", learning.name, Path("docs/learning.md"), force=True)
    assert "source_learning:" in target.read_text(encoding="utf-8")


def test_review_new_and_require_dual_tools(tmp_path: Path) -> None:
    case = make_case(tmp_path)

    codex = new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")

    assert "tool: codex" in codex.read_text(encoding="utf-8")
    with pytest.raises(ValidationError, match="missing passing review"):
        require_reviews(tmp_path, "ACF-1", ["codex", "claude"])
    claude = new_review(tmp_path, "ACF-1", tool="claude", review_id="REVIEW-CLAUDE")
    found = require_reviews(tmp_path, "ACF-1", ["codex", "claude"])

    assert found["codex"] == codex
    assert found["claude"] == claude


def test_review_require_ignores_non_passing_reviews(tmp_path: Path) -> None:
    make_case(tmp_path)
    new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX", status="needs_changes")

    with pytest.raises(ValidationError, match="missing passing review"):
        require_reviews(tmp_path, "ACF-1", ["codex"])

def test_review_request_starts_with_fixed_handoff_header_and_names_expected_review(tmp_path: Path) -> None:
    make_case(tmp_path)
    issue_order(tmp_path, "ACF-1", "ORD-1", "implementer")

    request = new_review_request(tmp_path, "ACF-1", tool="claude", order_id="ORD-1")

    text = request.read_text(encoding="utf-8")
    assert request == tmp_path / ".careflow" / "cases" / "ACF-1" / "reviews" / "requests" / "REQUEST-CLAUDE-ORD-1.md"
    assert text.startswith("PLAN_FILE: .careflow/cases/ACF-1/PLAN.md\n")
    assert "ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in text
    assert "SUBPLAN_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in text
    assert "EXPECTED_RESULT_PATH: .careflow/cases/ACF-1/results/ORD-1.result.md" in text
    assert "TARGET_TOOL: claude" in text
    assert "EXPECTED_REVIEW_PATH: .careflow/cases/ACF-1/reviews/REVIEW-CLAUDE-ORD-1.review.md" in text
    assert "Findings" in text
    assert "Evidence reviewed" in text


def test_validate_review_strict_rejects_placeholder_auth_unavailable(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    review = case / "reviews" / "REVIEW-CLAUDE.review.md"
    review.write_text("""# REVIEW

review_id: REVIEW-CLAUDE
case_id: ACF-1
tool: claude
status: pass

## Evidence reviewed

- Artifact-level review placeholder because local Claude auth is unavailable.
""", encoding="utf-8")

    validate_review(review)
    with pytest.raises(ValidationError, match="placeholder"):
        validate_review(review, strict=True)


def test_review_require_strict_rejects_placeholder_review(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    codex = new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")
    placeholder = case / "reviews" / "REVIEW-CLAUDE.review.md"
    placeholder.write_text("""# REVIEW

review_id: REVIEW-CLAUDE
case_id: ACF-1
tool: claude
status: pass

## Evidence reviewed

- Artifact-level review placeholder because local Claude auth is unavailable.
""", encoding="utf-8")

    with pytest.raises(ValidationError, match="placeholder"):
        require_reviews(tmp_path, "ACF-1", ["codex", "claude"], strict=True)
    found = require_reviews(tmp_path, "ACF-1", ["codex"], strict=True)
    assert found["codex"] == codex


def test_review_require_strict_skips_invalid_candidate_when_later_review_is_valid(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    codex = new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")
    (case / "reviews" / "REVIEW-CLAUDE-ORD-001.review.md").write_text("""# REVIEW

review_id: REVIEW-CLAUDE-ORD-001
case_id: ACF-1
tool: claude
status: pass

## Findings

- None.

## Evidence reviewed

- Artifact-level review placeholder because local Claude auth is unavailable.

## Recommendation

Pass.
""", encoding="utf-8")
    valid = case / "reviews" / "REVIEW-CLAUDE-ORD-002.review.md"
    valid.write_text("""# REVIEW

review_id: REVIEW-CLAUDE-ORD-002
case_id: ACF-1
tool: claude
status: pass

## Findings

- Severity: none; evidence.txt; concrete review evidence.

## Evidence reviewed

- Focused tests and result validation.

## Recommendation

Pass.
""", encoding="utf-8")

    found = require_reviews(tmp_path, "ACF-1", ["codex", "claude"], strict=True)

    assert found["codex"] == codex
    assert found["claude"] == valid
