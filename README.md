# agent-careflow

`agent-careflow` is a control repository for engineers who use AI coding agents such as Codex, Claude Code, and Cursor. It does not replace those agents. It gives them a recorded workflow: plan, order, result, evidence, incident, review, conference, and close.

The project deliberately borrows mature workflow-control patterns from healthcare operations. The target is engineering use of AI coding agents, not clinical care. The healthcare analogy is a governance model for planning, delegation, handoff, evidence, escalation, and closure.

Read the design first:

- [Design Philosophy](docs/design.md)
- [v0.1 Demo Flow](examples/v0.1-demo-flow.md)
- [Dotfiles Distribution Design](docs/dotfiles-distribution.md)

## Core Idea

A development task is a `Case`:

```text
.careflow/cases/<case_id>/
  CASE.yaml
  PLAN.md
  PLAN.lock.json
  orders/
  results/
  evidence/
  incidents/
  reviews/
  conferences/
  DISCHARGE.md
```

The central repo owns static controls:

- schemas and templates
- rules and adapter configs
- CLI validators and policy checks
- hook adapter entrypoints
- research reports and source registry
- profile and bootstrap definitions

Target repositories own runtime artifacts only under `.careflow/`. Tool-specific files such as `.codex/`, `.claude/`, and `.cursor/` are installed or linked by the user's global environment, not copied into each target repo.

## PLAN and ORDER

`PLAN.md` is the case-level direction: objective, non-goals, acceptance criteria, risk, scope, phase plan, evidence, rollback, and open questions.

`orders/*.order.md` is a bounded instruction to one role. Every order must include:

- `plan_path`
- `plan_hash`
- `expected_result_path`
- allowed and forbidden actions
- completion criteria

The validator rejects orders that omit the plan path or reference a stale plan hash. An order is incomplete until its `expected_result_path` exists.

## Quickstart

From a fresh checkout:

```bash
python -m pip install -e .
PYTHONPATH=src python -m agent_careflow.cli doctor
PYTHONPATH=src python -m agent_careflow.cli research validate
PYTHONPATH=src python -m agent_careflow.cli bootstrap --target /path/to/target --profile private --careflow-repo "$PWD"
```

After installation, the console script is `agent-careflow`. If your shell cannot find it, ensure Python's scripts directory is on `PATH` or run the module form shown above.

## Primary Lifecycle

```bash
agent-careflow case new --title "Fix auth callback bug" --risk C2
agent-careflow hash plan --case <case_id> --write-lock
agent-careflow hash plan --case <case_id> --write-lock --signing-key ~/.ssh/id_ed25519 --signing-principal you@example.com
agent-careflow plan validate --case <case_id> --require-lock
agent-careflow order issue --case <case_id> --order ORD-001 --role implementer
agent-careflow order prompt --case <case_id> --order ORD-001 --tool codex
agent-careflow result validate --case <case_id> --result ORD-001.result.md
agent-careflow phase advance --case <case_id> --to review
agent-careflow close validate --case <case_id>
```

`close validate` is a technical alias for `discharge validate`; the artifact remains `DISCHARGE.md` to preserve the careflow metaphor.

## Supporting Commands

Health and validation:

```bash
agent-careflow doctor
agent-careflow research validate
agent-careflow order status --case <case_id> --order ORD-001
agent-careflow evidence collect --case <case_id> --kind git-status
agent-careflow profile validate business
agent-careflow profile render business --target /tmp/agent-careflow-profile
```

Policy checks:

```bash
agent-careflow policy check-file --case <case_id> --path src/app.py --operation write
agent-careflow policy check-command --command "git reset --hard HEAD"
```

Hook adapters and prompt guard:

```bash
printf '{"prompt":"debug patient MRN: ABC123456"}' | agent-careflow hook codex user-prompt-submit
agent-careflow hook codex pre-tool-use < tests/fixtures/hooks/codex_pre_tool_use_bash_danger.json
agent-careflow hook runtime-status --format markdown --output .careflow/cases/<case_id>/evidence/runtime-probe-validation.txt
```

Bootstrap and planning support:

```bash
agent-careflow bootstrap --target /path/to/target --profile private --careflow-repo /path/to/agent-careflow
agent-careflow isolation plan --target . --case <case_id> --strategy worktree
agent-careflow isolation create --target . --case <case_id> --strategy worktree
agent-careflow isolation export-patch --work-dir /path/to/worktree --output /tmp/change.patch
agent-careflow takt analyze --workflow path/to/workflow.yaml
agent-careflow takt import-workflow --workflow path/to/workflow.yaml
agent-careflow takt export-policy --output /tmp/takt-policy.yaml
```

Policy behavior is configured from `rules/global/*.yaml` when those files exist. The Python defaults remain as fallback, but command and phase policy should be changed in:

- `rules/global/command-policy.yaml`
- `rules/global/phase-policy.yaml`

## v0.1 Scope

v0.1 is handoff-ready for local control-repository use:

- research scaffold, source registry, and validation
- concrete artifact templates and runtime schema validation
- CASE, PLAN, PLAN.lock, ORDER, RESULT, INCIDENT, REVIEW, CONFERENCE, and DISCHARGE validation surface
- `doctor` one-shot repository health check
- case creation, phase status/advance, order issue/prompt/status, evidence collection, result/review validation, incident creation, and close/discharge validation
- YAML-backed policy engine for phase/file/command gates
- prompt guard for likely secrets and PHI-like identifiers before agent context entry
- Codex, Claude, and Cursor hook adapter entrypoints with fixtures, Stop hooks, and opt-in incident creation on deny
- hook payload capture and validation commands using `codex.runtime_probe.v1` JSONL
- target repository bootstrap profiles that record tool intent while writing only `.careflow/` runtime files
- profile validate/render/install support for rendered tool configs
- isolation planning and guarded worktree/clone execution with patch export
- TAKT comparative analysis plus import/export reports
- focused unit and fixture tests

Known external blockers and backlog:

- live Codex hook payload capture is inconclusive in this environment because repo-local hooks did not emit capture logs under `codex exec`, and temporary `CODEX_HOME` lacks auth
- Claude and Cursor live runtime payload capture still requires controlled local runtime scenarios; Cursor CLI is not available on this machine
- PLAN locks support optional OpenSSH signatures; deployments still need an allowed signers/key-management policy
