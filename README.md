# agent-careflow

`agent-careflow` is a control repository for AI coding-agent workflows. It does not replace Codex, Claude Code, Cursor, or TAKT. It provides artifact protocols, validators, policy checks, hook adapters, profile bootstrap, and comparison tools that keep those agents working against the same case record.

This project intentionally borrows mature workflow-control patterns from healthcare operations: cases, plans, orders, handoffs, incidents, reviews, and discharge checks. The target is engineering use of AI coding agents, not clinical care. The medical analogy is a governance model for planning, delegation, evidence, escalation, and closure.


## Quickstart

From a fresh checkout:

```bash
python -m pip install -e .
PYTHONPATH=src python -m agent_careflow.cli research validate
PYTHONPATH=src python -m agent_careflow.cli bootstrap --target /path/to/target --profile private --careflow-repo "$PWD"
PYTHONPATH=src python -m agent_careflow.cli case new --title "Small bugfix" --risk C1
```

After installation, the console script is `agent-careflow`. If your shell cannot find it, ensure Python's scripts directory is on `PATH` or run the module form shown above.

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

One-shot repository health check:

```bash
PYTHONPATH=src python -m agent_careflow.cli doctor
```

Core validation:

Plan locks bind ORDER execution to the exact PLAN content:

```bash
PYTHONPATH=src python -m agent_careflow.cli hash plan --case ACF-BOOTSTRAP --write-lock
PYTHONPATH=src python -m agent_careflow.cli plan validate --case ACF-BOOTSTRAP --require-lock
```

When `PLAN.lock.json` exists, ORDER validation checks that `plan_hash` matches both `PLAN.md` and the lock file. `close validate` is a technical alias for `discharge validate`; the artifact remains `DISCHARGE.md` to preserve the careflow metaphor. Runtime validators read the bundled schema files for required fields, enum values, const values, simple types, and hash patterns.

```bash
PYTHONPATH=src python -m agent_careflow.cli research validate
PYTHONPATH=src python -m agent_careflow.cli plan validate --case ACF-BOOTSTRAP
PYTHONPATH=src python -m agent_careflow.cli order validate --case ACF-BOOTSTRAP --order ORD-001-research
PYTHONPATH=src python -m agent_careflow.cli discharge validate --case ACF-BOOTSTRAP
PYTHONPATH=src python -m agent_careflow.cli close validate --case ACF-BOOTSTRAP
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


Policy behavior is configured from `rules/global/*.yaml` when those files exist. The Python defaults remain as fallback, but command and phase policy should be changed in:

- `rules/global/command-policy.yaml`
- `rules/global/phase-policy.yaml`

```bash
PYTHONPATH=src python -m agent_careflow.cli policy check-file --case ACF-BOOTSTRAP --path src/app.py --operation write
PYTHONPATH=src python -m agent_careflow.cli policy check-command --command "git reset --hard HEAD"
```

Hook adapters:


Prompt guard hooks can block likely secrets or PHI-like identifiers before they enter AI coding-agent context:

```bash
printf '{"prompt":"debug patient MRN: ABC123456"}' | \
  PYTHONPATH=src python -m agent_careflow.cli hook codex user-prompt-submit
```

This is an engineering guardrail for agent input hygiene; it does not perform clinical classification.


Hook payload capture can be used as a sidecar runtime probe:

```bash
printf '{"tool_name":"Bash","tool_input":{"command":"date"}}' | \
  PYTHONPATH=src python -m agent_careflow.cli hook capture \
  --event-name PreToolUse \
  --output .codex/probes/example/runtime-probe.jsonl \
  --probe smoke-capture
```

The output uses `codex.runtime_probe.v1` JSONL so it can be validated with the runtime probe validator.

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

v0.1 is handoff-ready for local control-repository use:

- research scaffold, source registry, and validation
- concrete artifact templates and runtime schema validation
- CASE, PLAN, PLAN.lock, ORDER, RESULT, INCIDENT, REVIEW, CONFERENCE, and DISCHARGE validation surface
- `doctor` one-shot repository health check
- case creation, phase status/advance, order issue/prompt/status, result/review validation, incident creation, and close/discharge validation
- YAML-backed policy engine for phase/file/command gates
- prompt guard for likely secrets and PHI-like identifiers before agent context entry
- Codex, Claude, and Cursor hook adapter entrypoints with fixtures
- hook payload capture command using `codex.runtime_probe.v1` JSONL
- target repository bootstrap profiles, including private profile without Claude
- isolation planning with worktree as default
- TAKT comparative analysis mode
- focused unit and fixture tests

Known external blockers and backlog:

- live Codex hook payload capture is inconclusive in this environment because repo-local hooks did not emit capture logs under `codex exec`, and temporary `CODEX_HOME` lacks auth
- Claude and Cursor live runtime payload capture still requires those tools to be available locally
- executing worktree/shared clone creation is intentionally still plan-only because cleanup can be destructive
- cryptographic signatures for plan locks are not enabled until a key-management decision exists; current locks are deterministic hash locks
