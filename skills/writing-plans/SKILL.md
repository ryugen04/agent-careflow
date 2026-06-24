---
name: writing-plans
description: Use when requirements or a spec exist for a multi-step task, before touching code; creates decision-complete careflow PLAN and ORDER-ready task decomposition.
---

# Writing Careflow Plans

Create a plan that another agent can execute without making decisions.

## Required Flow

1. Locate active case from `.careflow/state.json` or create one.
2. Update `.careflow/cases/<case_id>/PLAN.md` with objective, non-goals, acceptance criteria, allowed scope, phase plan, evidence, rollback, and open questions.
3. Split by subsystem/repository/worktree when needed; child plans must reference the parent plan.
4. For each executable unit, issue an ORDER with `agent-careflow order issue` or write an equivalent `.order.md` artifact.
5. Every ORDER must have `plan_path`, `plan_hash`, `expected_result_path`, allowed actions, forbidden actions, deliverables, and completion criteria.
6. Do not mutate implementation files while writing the plan.

## Superpowers Source

Adapted from `third_party/superpowers/skills/writing-plans/SKILL.md`. Agent-careflow changes: plan location is `.careflow/cases/<case_id>/PLAN.md`, not `docs/superpowers/plans`.
