# Artifact Locks and Schemas Plan

Date: 2026-05-21 JST

## Objective

Strengthen the artifact protocol before moving deeper into hook/policy work:

- implement PLAN.lock.json generation and validation
- require ORDER plan_hash to match both PLAN.md and PLAN.lock.json when lock exists
- replace placeholder schemas for core artifacts with concrete required fields
- expose CLI commands for plan hash/lock validation

## Steps

1. Add plan lock helper functions and validation tests.
2. Add `agent-careflow hash plan` and wire lock validation into `plan validate`.
3. Update bootstrap case with `PLAN.lock.json`.
4. Replace placeholder JSON schemas for core artifacts.
5. Run tests and CLI validation.
6. Commit the completed work.

## Acceptance Criteria

- A stale `PLAN.lock.json` is rejected.
- An ORDER with mismatched plan hash is rejected.
- Bootstrap `PLAN.md`, `PLAN.lock.json`, and ORD-001 all validate.
- Core JSON schema files are no longer generic placeholders.
- `python -m pytest` passes.
