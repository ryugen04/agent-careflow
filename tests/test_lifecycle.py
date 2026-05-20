from __future__ import annotations

from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.lifecycle import advance_phase, case_status, issue_order, new_incident, validate_result, validate_review
from agent_careflow.templates import render_discharge, render_plan


def make_case(tmp_path: Path, phase: str = "planning") -> Path:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    for child in ["orders", "results", "evidence", "incidents", "reviews", "conferences"]:
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
