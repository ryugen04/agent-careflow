from __future__ import annotations

from pathlib import Path

from agent_careflow.lifecycle import new_review
from agent_careflow.review_status import render_review_status, review_status
from agent_careflow.templates import render_plan


def make_case(tmp_path: Path) -> Path:
    case = tmp_path / ".careflow" / "cases" / "ACF-1"
    for child in ["orders", "results", "evidence", "incidents", "reviews", "reviews/requests", "learnings"]:
        (case / child).mkdir(parents=True, exist_ok=True)
    (case / "CASE.yaml").write_text("case_id: ACF-1\nstatus: active\nphase: review\n", encoding="utf-8")
    (case / "PLAN.md").write_text(render_plan("ACF-1", "Review status test", "C2"), encoding="utf-8")
    (case / "orders" / "ORD-1.order.md").write_text("ORDER_FILE: .careflow/cases/ACF-1/orders/ORD-1.order.md\n", encoding="utf-8")
    (case / "results" / "ORD-1.result.md").write_text("order_id: ORD-1\ncase_id: ACF-1\nstatus: complete\n", encoding="utf-8")
    return case


def write_placeholder_claude(case: Path, review_id: str = "REVIEW-CLAUDE") -> None:
    (case / "reviews" / f"{review_id}.review.md").write_text(f"""# REVIEW

review_id: {review_id}
case_id: ACF-1
tool: claude
status: pass

## Findings

- None.

## Evidence reviewed

- placeholder because auth unavailable

## Recommendation

Pass.
""", encoding="utf-8")


def write_valid_claude(case: Path, review_id: str = "REVIEW-CLAUDE-ORD-2") -> Path:
    path = case / "reviews" / f"{review_id}.review.md"
    path.write_text(f"""# REVIEW

review_id: {review_id}
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
    return path


def test_review_status_business_reports_placeholder_claude_next_steps(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")
    write_placeholder_claude(case)

    status = review_status(tmp_path, "ACF-1", profile="business", order_id="ORD-1")

    assert status["status"] == "missing"
    assert status["required_tools"] == ["codex", "claude"]
    assert status["tools"]["codex"]["status"] == "satisfied"
    assert status["tools"]["claude"]["status"] == "invalid"
    assert "placeholder" in status["tools"]["claude"]["details"]
    assert not any("agent-careflow review claude-auth" in command for command in status["next_commands"])
    assert any("agent-careflow review export --case ACF-1 --tool claude --order ORD-1" in command for command in status["next_commands"])
    assert any("agent-careflow review import --case ACF-1 --source" in command for command in status["next_commands"])
    assert any("agent-careflow review require --case ACF-1 --tool codex --tool claude --strict" in command for command in status["next_commands"])
    assert status["diagnostic_commands"] == ["agent-careflow review claude-auth --model sonnet"]


def test_review_status_business_uses_latest_valid_claude_review(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")
    write_placeholder_claude(case, "REVIEW-CLAUDE-ORD-1")
    valid = write_valid_claude(case, "REVIEW-CLAUDE-ORD-2")

    status = review_status(tmp_path, "ACF-1", profile="business", order_id="ORD-1")

    assert status["status"] == "satisfied"
    assert status["tools"]["claude"]["status"] == "satisfied"
    assert status["tools"]["claude"]["details"] == valid.name
    assert status["next_commands"] == []
    assert status["diagnostic_commands"] == []


def test_review_status_private_requires_codex_only(tmp_path: Path) -> None:
    make_case(tmp_path)
    new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")

    status = review_status(tmp_path, "ACF-1", profile="private", order_id="ORD-1")

    assert status["status"] == "satisfied"
    assert status["required_tools"] == ["codex"]
    assert set(status["tools"]) == {"codex"}
    assert status["next_commands"] == []
    assert status["diagnostic_commands"] == []


def test_render_review_status_text_names_profile_and_next_commands(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    new_review(tmp_path, "ACF-1", tool="codex", review_id="REVIEW-CODEX")
    write_placeholder_claude(case)

    text = render_review_status(review_status(tmp_path, "ACF-1", profile="business", order_id="ORD-1"))

    assert "review-status=missing case=ACF-1 profile=business" in text
    assert "codex: satisfied" in text
    assert "claude: invalid" in text
    assert "next commands:" in text
    assert "agent-careflow review export" in text
    assert "diagnostic commands:" in text
    assert "agent-careflow review claude-auth" in text
