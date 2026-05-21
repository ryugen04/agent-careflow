from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .artifacts import sha256_file


def render_case(case_id: str, title: str, risk: str) -> str:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return f"""case_id: {case_id}
title: {title}
risk: {risk}
phase: intake
status: active
created_at: {now}
owner: codex
allowed_scope:
  - .careflow/**
summary: {title}
"""


def render_plan(case_id: str, title: str, risk: str) -> str:
    return f"""# PLAN: {title}

case_id: {case_id}
status: active
risk: {risk}
owner: codex

## Objective

{title}

## Non-goals

- No non-goals recorded yet.

## Acceptance criteria

- Case artifacts validate.

## Risk class

{risk}

## Allowed scope

- .careflow/**

## Phase plan

- planning
- verification
- discharge

## Subagent utilization plan

No subagents assigned.

## Evidence requirements

- verification output

## Rollback plan

Remove generated case artifacts.

## Unresolved questions

- None yet.
"""


def render_order(case_id: str, order_id: str, role: str, plan_path: Path, result_path: Path) -> str:
    return f"""# ORDER: {order_id}

order_id: {order_id}
case_id: {case_id}
assigned_role: {role}
plan_path: {plan_path.as_posix()}
plan_hash: {sha256_file(plan_path)}
allowed_actions:
  - read assigned scope
  - write expected result
forbidden_actions:
  - edit outside allowed scope
  - ignore plan_path or order_path
deliverables:
  - {result_path.as_posix()}
expected_result_path: {result_path.as_posix()}
completion_criteria:
  - expected result exists

## Situation

A bounded order is required for the active case.

## Background

See PLAN.md.

## Assessment

The assigned role must produce the expected result path.

## Recommendation

Follow the PLAN and this ORDER exactly.
"""


def render_discharge(case_id: str) -> str:
    return f"""# DISCHARGE: {case_id}

case_id: {case_id}
status: draft
evidence:
  - evidence required

## Summary

Evidence has not been recorded yet.

## Verification

Verification evidence is required before closure.

## Open incidents

No incident review has been recorded yet.

## Final disposition

Not ready for closure.
"""
