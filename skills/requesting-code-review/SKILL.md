---
name: requesting-code-review
description: Use after implementation work or before merge/close to request focused code, behavior, and evidence review from Codex, Claude, or subagents.
---

# Requesting Careflow Code Review

Review is an artifact, not a chat opinion.

## Required Flow

1. Read PLAN, ORDER, RESULT, and evidence.
2. Dispatch reviewer with explicit paths and diff scope.
3. Ask reviewer to classify findings by severity and reference files/lines.
4. Save review to `.careflow/cases/<case_id>/reviews/<review_id>.review.md`.
5. Critical or major findings require corrective ORDERs before close.
6. Dual review is preferred for business profile: Claude plus Codex.

## Superpowers Source

Adapted from `third_party/superpowers/skills/requesting-code-review/SKILL.md`.
