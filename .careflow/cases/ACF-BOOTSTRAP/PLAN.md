# PLAN: Bootstrap agent-careflow Milestone 0 and 1

case_id: ACF-BOOTSTRAP
status: active
risk: C2
owner: codex

## Objective

Create the initial control repository structure for `agent-careflow`, including research scaffolding, source registry validation, artifact schemas/templates, core CLI commands, tests, and README documentation.

## Non-goals

- Do not implement hook adapters.
- Do not implement full policy engine phase gates.
- Do not depend on Claude, Cursor, or TAKT.
- Do not implement subagent orchestration beyond artifact contracts.

## Acceptance criteria

- Required research reports exist and validate.
- Source registry exists and includes authority levels.
- `agent-careflow case new` creates a valid case directory.
- `agent-careflow plan validate` accepts this plan.
- `agent-careflow order validate` rejects missing `plan_path` and plan hash mismatches.
- `agent-careflow discharge validate` rejects missing evidence.
- Tests cover the core validation paths.

## Risk class

C2. The repository is new, but the CLI and artifact protocol will become shared workflow infrastructure.

## Allowed scope

- `.careflow/**`
- `research/**`
- `src/agent_careflow/**`
- `tests/**`
- `README.md`
- `pyproject.toml`
- `AGENTS.md`

## Phase plan

- planning: create bootstrap CASE, PLAN, and ORDER.
- research: create required report stubs and source registry.
- implementation: implement package, CLI, schemas, and templates.
- verification: run focused tests and validation commands.
- review: record bootstrap conference note with residual gaps.
- discharge: deferred until evidence exists.

## Subagent utilization plan

No subagents are started in this run because the active environment requires explicit user authorization for subagent delegation. The bootstrap ORDER still documents the expected bounded research review contract.

## Evidence requirements

- pytest output
- research validation output
- plan validation output
- order validation output

## Rollback plan

Remove the initial package, tests, research scaffold, and bootstrap `.careflow` case if the layout proves unsuitable before v0.1 is tagged.

## Unresolved questions

- Whether report contents should remain stubs in v0.1 or be promoted to accepted research after live source review.
- Whether future templates should expose medical terms directly or add technical aliases.
