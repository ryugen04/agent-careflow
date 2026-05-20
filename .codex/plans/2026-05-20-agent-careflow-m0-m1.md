# agent-careflow Milestone 0-1 Plan

Date: 2026-05-20 JST

## Objective

Implement the initial `agent-careflow` repository through Milestone 0 and Milestone 1:

- research scaffold and source registry validation
- core CASE / PLAN / ORDER / DISCHARGE artifact protocol
- Python package and `agent-careflow` CLI
- focused tests and README

## Constraints

- Create `.careflow/cases/ACF-BOOTSTRAP/CASE.yaml`, `PLAN.md`, and `orders/ORD-001-research.order.md` before implementation code.
- Keep policy logic in the CLI/package, not in tool-specific adapters.
- Do not require Claude for private/profile-neutral operation.
- Treat community sources as risk signals only.
- Runtime artifacts live under `.careflow/`.

## Steps

1. Create bootstrap case artifacts and research report stubs.
2. Create source registry and research validator.
3. Implement schemas, templates, and Python CLI commands.
4. Add validation for plan hash, required order fields, and discharge evidence.
5. Add tests for accepted and rejected artifacts.
6. Update README with central repository vs target repository workflow.

## Verification

- `python -m pytest`
- `python -m agent_careflow.cli research validate`
- `python -m agent_careflow.cli plan validate --case ACF-BOOTSTRAP`
- `python -m agent_careflow.cli order validate --case ACF-BOOTSTRAP --order ORD-001-research`
