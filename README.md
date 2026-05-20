# agent-careflow

`agent-careflow` is a control repository for AI coding-agent workflows. It does not replace Codex, Claude Code, Cursor, or TAKT. It provides artifact protocols, validators, policy checks, hook adapters, profile bootstrap, and comparison tools that keep those agents working against the same case record.

This project borrows workflow structure from healthcare operations: cases, plans, orders, handoffs, incidents, reviews, and discharge checks. It is not a medical system and does not provide clinical safety functionality.

## Repository split

Static control assets live in this repository:

- schemas and templates
- rules and adapter configs
- CLI validators and policy checks
- hook adapter entrypoints
- research reports and source registry
- profile and bootstrap definitions

Runtime artifacts for a target project live in that target repository under `.careflow/`:

```text
.careflow/
  cases/
    ACF-BOOTSTRAP/
      CASE.yaml
      PLAN.md
      orders/
      results/
      evidence/
      incidents/
      reviews/
      conferences/
      DISCHARGE.md
```

## PLAN and ORDER

`PLAN.md` is the case-level direction: objective, non-goals, acceptance criteria, risk, scope, phase plan, evidence, rollback, and open questions.

`orders/*.order.md` is a bounded instruction to one role. Every order must include:

- `plan_path`
- `plan_hash`
- `expected_result_path`
- allowed and forbidden actions
- completion criteria

The validator rejects orders that omit the plan path or reference a stale plan hash. An order is incomplete until its `expected_result_path` exists.

## CLI

Run from the repository root during local development with `PYTHONPATH=src`, or install the package and use the `agent-careflow` console script.

Core validation:

```bash
PYTHONPATH=src python -m agent_careflow.cli research validate
PYTHONPATH=src python -m agent_careflow.cli plan validate --case ACF-BOOTSTRAP
PYTHONPATH=src python -m agent_careflow.cli order validate --case ACF-BOOTSTRAP --order ORD-001-research
PYTHONPATH=src python -m agent_careflow.cli discharge validate --case ACF-BOOTSTRAP
```

Case lifecycle:

```bash
PYTHONPATH=src python -m agent_careflow.cli case new --title "Small bugfix" --risk C1
PYTHONPATH=src python -m agent_careflow.cli phase status --case ACF-BOOTSTRAP
PYTHONPATH=src python -m agent_careflow.cli phase advance --case ACF-BOOTSTRAP --to review
PYTHONPATH=src python -m agent_careflow.cli order issue --case ACF-BOOTSTRAP --order ORD-002 --role verifier
PYTHONPATH=src python -m agent_careflow.cli incident new --case ACF-BOOTSTRAP --trigger scope_violation
PYTHONPATH=src python -m agent_careflow.cli result validate --case ACF-BOOTSTRAP --result ORD-001-research.result.md
```

Policy checks:

```bash
PYTHONPATH=src python -m agent_careflow.cli policy check-file --case ACF-BOOTSTRAP --path src/app.py --operation write
PYTHONPATH=src python -m agent_careflow.cli policy check-command --command "git reset --hard HEAD"
```

Hook adapters:

```bash
PYTHONPATH=src python -m agent_careflow.cli hook codex pre-tool-use < tests/fixtures/hooks/codex_pre_tool_use_bash_danger.json
PYTHONPATH=src python -m agent_careflow.cli hook claude pre-tool-use --on-missing-context deny < tests/fixtures/hooks/claude_pre_tool_use_write_missing_context.json
```

Target repo bootstrap:

```bash
PYTHONPATH=src python -m agent_careflow.cli bootstrap --target /path/to/target --profile business --careflow-repo /path/to/agent-careflow
PYTHONPATH=src python -m agent_careflow.cli bootstrap --target /path/to/target --profile private --careflow-repo /path/to/agent-careflow
```

The `private` profile writes Codex and Cursor hook config but intentionally does not create `.claude/`.

Order prompts:

```bash
PYTHONPATH=src python -m agent_careflow.cli order prompt --case ACF-BOOTSTRAP --order ORD-001-research --tool codex
PYTHONPATH=src python -m agent_careflow.cli order status --case ACF-BOOTSTRAP --order ORD-001-research
```

Isolation and TAKT comparison:

```bash
PYTHONPATH=src python -m agent_careflow.cli isolation plan --target . --case ACF-BOOTSTRAP --strategy worktree
PYTHONPATH=src python -m agent_careflow.cli takt analyze --workflow path/to/workflow.yaml
```

`worktree` is the default v0.x isolation strategy. Shared/temp clone strategies are rendered as plans only and their destructive cleanup commands require explicit approval before execution. TAKT comparison maps recognizable workflow signals such as persona, policy, output, review, provider, and worktree to agent-careflow artifacts without making TAKT a dependency.

## Implemented scope

Implemented through Milestone 8:

- research scaffold, source registry, and validation
- CASE, PLAN, ORDER, RESULT, INCIDENT, REVIEW, CONFERENCE, and DISCHARGE artifact validation surface
- case creation, phase status/advance, order issue/prompt/status, result/review validation, and incident creation
- policy engine for phase/file/command gates
- Codex, Claude, and Cursor hook adapter entrypoints with fixtures
- target repository bootstrap profiles, including private profile without Claude
- isolation planning with worktree as default
- TAKT comparative analysis mode
- focused unit and fixture tests

Deferred beyond this pass:

- executing worktree/shared clone creation directly
- signed plan locks and stronger tamper detection
- production-grade JSON Schema coverage for every artifact field
- local runtime fixture capture for every vendor hook version
