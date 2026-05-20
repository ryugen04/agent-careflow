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







TAKT comparison reports can be generated without making TAKT a dependency:

```bash
PYTHONPATH=src python -m agent_careflow.cli takt analyze --workflow path/to/workflow.yaml
```

The analyzer maps recognizable workflow signals such as persona, policy, output, review, provider, and worktree to agent-careflow artifacts.

Isolation planning is available before launching long-running agents:

```bash
PYTHONPATH=src python -m agent_careflow.cli isolation plan --target . --case ACF-BOOTSTRAP --strategy worktree
```

`worktree` is the default v0.x strategy. Shared/temp clone strategies are rendered as plans only and their destructive cleanup commands require explicit approval before execution.

Subagent order prompts can be rendered for supported tools:

```bash
PYTHONPATH=src python -m agent_careflow.cli order prompt --case ACF-BOOTSTRAP --order ORD-001-research --tool codex
PYTHONPATH=src python -m agent_careflow.cli order status --case ACF-BOOTSTRAP --order ORD-001-research
```

An order is incomplete until its `expected_result_path` exists.

Case lifecycle commands cover the first end-to-end case operations:

```bash
PYTHONPATH=src python -m agent_careflow.cli phase status --case ACF-BOOTSTRAP
PYTHONPATH=src python -m agent_careflow.cli phase advance --case ACF-BOOTSTRAP --to review
PYTHONPATH=src python -m agent_careflow.cli order issue --case ACF-BOOTSTRAP --order ORD-002 --role verifier
PYTHONPATH=src python -m agent_careflow.cli incident new --case ACF-BOOTSTRAP --trigger scope_violation
PYTHONPATH=src python -m agent_careflow.cli result validate --case ACF-BOOTSTRAP --result ORD-001-research.result.md
```

Phase advancement blocks review/conference/discharge when required evidence is missing, and discharge also blocks on open incidents.

Target repositories can be bootstrapped from the central control repo:

```bash
PYTHONPATH=src python -m agent_careflow.cli bootstrap --target /path/to/target --profile business --careflow-repo /path/to/agent-careflow
PYTHONPATH=src python -m agent_careflow.cli bootstrap --target /path/to/target --profile private --careflow-repo /path/to/agent-careflow
```

The `private` profile writes Codex and Cursor hook config but intentionally does not create `.claude/`.

Hook adapters are available as thin wrappers around the shared policy engine:

```bash
PYTHONPATH=src python -m agent_careflow.cli hook codex pre-tool-use < tests/fixtures/hooks/codex_pre_tool_use_bash_danger.json
PYTHONPATH=src python -m agent_careflow.cli hook claude pre-tool-use --on-missing-context deny < tests/fixtures/hooks/claude_pre_tool_use_write_missing_context.json
```

The hook adapter layer returns tool-specific JSON, while policy decisions remain centralized in `agent_careflow.policy`.

Policy checks are available for the Milestone 2 gate model:

```bash
PYTHONPATH=src python -m agent_careflow.cli policy check-file --case ACF-BOOTSTRAP --path src/app.py --operation write
PYTHONPATH=src python -m agent_careflow.cli policy check-command --command "git reset --hard HEAD"
```

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
