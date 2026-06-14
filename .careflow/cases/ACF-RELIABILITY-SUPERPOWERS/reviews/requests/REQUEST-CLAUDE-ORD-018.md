PLAN_FILE: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/PLAN.md
ORDER_FILE: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/orders/ORD-018.order.md
SUBPLAN_FILE: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/orders/ORD-018.order.md
EXPECTED_RESULT_PATH: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/results/ORD-018.result.md
CASE_ID: ACF-RELIABILITY-SUPERPOWERS
ORDER_ID: ORD-018
ASSIGNED_ROLE: reviewer
TARGET_TOOL: claude
EXPECTED_REVIEW_PATH: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/reviews/REVIEW-CLAUDE-ORD-018.review.md

# REVIEW REQUEST: REVIEW-CLAUDE-ORD-018

## Instructions

Read PLAN_FILE, ORDER_FILE, EXPECTED_RESULT_PATH, and the evidence directory before reviewing. Treat ORDER_FILE as the executable subplan for the work under review. Save the review exactly at EXPECTED_REVIEW_PATH.

## Scope

- Plan: `.careflow/cases/ACF-RELIABILITY-SUPERPOWERS/PLAN.md`
- Order: `.careflow/cases/ACF-RELIABILITY-SUPERPOWERS/orders/ORD-018.order.md`
- Result: `.careflow/cases/ACF-RELIABILITY-SUPERPOWERS/results/ORD-018.result.md`
- Evidence: `.careflow/cases/ACF-RELIABILITY-SUPERPOWERS/evidence`

## Required Output Contract

Write a `.review.md` artifact with this front matter and sections:

```markdown
# REVIEW: REVIEW-CLAUDE-ORD-018

review_id: REVIEW-CLAUDE-ORD-018
case_id: ACF-RELIABILITY-SUPERPOWERS
tool: claude
status: pass|needs_changes|blocked
plan_path: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/PLAN.md
order_path: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/orders/ORD-018.order.md
result_path: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/results/ORD-018.result.md

## Scope

What was reviewed.

## Findings

- Severity: critical|major|minor|none; file/line; rationale.

## Evidence reviewed

- Exact commands, artifacts, and files inspected.

## Recommendation

Pass, request changes, or block with rationale.
```

## Strictness

Do not submit an auth-unavailable placeholder. If the review cannot be completed, write `status: blocked` and explain the external blocker with evidence.
