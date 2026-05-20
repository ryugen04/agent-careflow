# agent-careflow

`agent-careflow` is a control repository for AI coding-agent workflows. It does not replace Codex, Claude Code, Cursor, or TAKT. It provides the artifact protocol, validators, templates, and future hook/policy entrypoints that keep those tools working against the same case record.

This project borrows workflow structure from healthcare operations: cases, plans, orders, handoffs, incidents, reviews, and discharge checks. It is not a medical system and does not provide clinical safety functionality.

## Repository split

Static control assets live in this repository:

- schemas
- templates
- rules and future adapter configs
- CLI validators
- research reports
- policies and hooks in later milestones

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

The validator rejects orders that omit the plan path or reference a stale plan hash.

## CLI

Run from the repository root during v0.1 development:

```bash
PYTHONPATH=src python -m agent_careflow.cli research validate
PYTHONPATH=src python -m agent_careflow.cli case new --title "Small bugfix" --risk C1
PYTHONPATH=src python -m agent_careflow.cli plan validate --case ACF-BOOTSTRAP
PYTHONPATH=src python -m agent_careflow.cli order validate --case ACF-BOOTSTRAP --order ORD-001-research
PYTHONPATH=src python -m agent_careflow.cli discharge validate --case ACF-BOOTSTRAP
```

If installed as a package, the console command is `agent-careflow`.

## Milestone status

Implemented in this initial pass:

- research scaffold and validation
- source authority level checks in report tables
- CASE, PLAN, ORDER, and DISCHARGE validators
- `case new`
- rejection of mismatched order plan hashes
- rejection of discharge without evidence
- focused tests

Deferred:

- hook adapters
- full policy engine
- target repository bootstrap profiles
- subagent prompt generation
- TAKT interop
