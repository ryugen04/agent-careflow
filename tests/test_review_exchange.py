from __future__ import annotations

from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.lifecycle import issue_order, validate_review
from agent_careflow.review_exchange import export_review_bundle, import_review_artifact
from agent_careflow.templates import render_plan


def make_case(tmp_path: Path) -> Path:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    for child in ["orders", "results", "evidence", "incidents", "reviews", "reviews/requests", "learnings"]:
        (case / child).mkdir(parents=True, exist_ok=True)
    (case / "CASE.yaml").write_text("case_id: ACF-1\nstatus: active\nphase: review\n", encoding="utf-8")
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Review exchange test", "C2"), encoding="utf-8")
    (case / "results" / "ORD-1.result.md").write_text("order_id: ORD-1\ncase_id: ACF-1\nstatus: complete\n", encoding="utf-8")
    issue_order(tmp_path, "ACF-1", "ORD-1", "implementer")
    return case


def strict_review_text() -> str:
    return """# REVIEW: REVIEW-CLAUDE-ORD-1

review_id: REVIEW-CLAUDE-ORD-1
case_id: ACF-1
tool: claude
status: pass
plan_path: .careflow/cases/ACF-1/PLAN.md
order_path: .careflow/cases/ACF-1/orders/ORD-1.order.md
result_path: .careflow/cases/ACF-1/results/ORD-1.result.md

## Scope

PLAN, ORDER, RESULT, and evidence.

## Findings

- Severity: none; no blocking issues found.

## Evidence reviewed

- PLAN, ORDER, RESULT, and evidence directory.

## Recommendation

Pass.
"""


def test_export_review_bundle_writes_fixed_header_request(tmp_path: Path) -> None:
    make_case(tmp_path)
    output = tmp_path / "claude-review-request.md"

    bundle = export_review_bundle(tmp_path, "ACF-1", "ORD-1", tool="claude", review_id="REVIEW-CLAUDE-ORD-1", output=output)

    assert bundle == output
    text = output.read_text(encoding="utf-8")
    assert text.startswith("PLAN_FILE: .careflow/cases/ACF-1/PLAN.md\n")
    assert "ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in text
    assert "SUBPLAN_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md" in text
    assert "EXPECTED_RESULT_PATH: .careflow/cases/ACF-1/results/ORD-1.result.md" in text
    assert "EXPECTED_REVIEW_PATH: .careflow/cases/ACF-1/reviews/REVIEW-CLAUDE-ORD-1.review.md" in text
    assert "agent-careflow review import" in text


def test_import_review_artifact_validates_strictly_and_stores_review(tmp_path: Path) -> None:
    make_case(tmp_path)
    source = tmp_path / "returned-review.md"
    source.write_text(strict_review_text(), encoding="utf-8")

    stored = import_review_artifact(tmp_path, "ACF-1", source, strict=True)

    assert stored == tmp_path / ".careflow" / "cases" / "ACF-1" / "reviews" / "REVIEW-CLAUDE-ORD-1.review.md"
    assert stored.read_text(encoding="utf-8") == strict_review_text()
    validate_review(stored, strict=True)


def test_import_review_artifact_rejects_placeholder(tmp_path: Path) -> None:
    make_case(tmp_path)
    source = tmp_path / "placeholder-review.md"
    source.write_text(strict_review_text().replace("PLAN, ORDER, RESULT, and evidence directory.", "placeholder because auth unavailable"), encoding="utf-8")

    with pytest.raises(ValidationError, match="placeholder"):
        import_review_artifact(tmp_path, "ACF-1", source, strict=True)
