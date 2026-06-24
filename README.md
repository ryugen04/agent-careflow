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

`.careflow/INDEX.md` is the human-visible entrypoint. Generate it with `agent-careflow dashboard --write` so a later Claude, Codex, Cursor, or subagent session can immediately find the active PLAN, ORDER, expected RESULT, incidents, reviews, learnings, and next step without relying on chat memory.

`.agent/` is an optional operator workspace generated from `.careflow/`. Use `agent-careflow workspace --write` to create `.agent/current.md`, `.agent/incidents/README.md`, `.agent/reviews/README.md`, `.agent/learnings/README.md`, and `.agent/repos.md`. Agents may read `.agent/` first, but canonical plans, orders, results, evidence, incidents, reviews, and learnings remain under `.careflow/`. Use `agent-careflow repo status` to list direct child git repositories and `.worktrees/<branch>/<repo>` worktrees from the workflow root.

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
agent-careflow order result-skeleton --case <case_id> --order ORD-001 --write
agent-careflow dashboard --write
agent-careflow workspace --write
agent-careflow result validate --case <case_id> --result ORD-001.result.md
agent-careflow phase advance --case <case_id> --to review
agent-careflow review status --case <case_id> --profile business --order ORD-001
agent-careflow review request --case <case_id> --tool claude --order ORD-001
agent-careflow review export --case <case_id> --tool claude --order ORD-001 --review-id REVIEW-CLAUDE-ORD-001 --output /tmp/claude-review-request.md
agent-careflow review import --case <case_id> --source /path/to/REVIEW-CLAUDE-ORD-001.review.md --strict
agent-careflow review new --case <case_id> --tool codex --status pass
agent-careflow review validate --case <case_id> --review REVIEW-CLAUDE-ORD-001.review.md --strict
agent-careflow review require --case <case_id> --tool codex --tool claude --strict
agent-careflow close validate --case <case_id>
```

`close validate` is a technical alias for `discharge validate`; the artifact remains `DISCHARGE.md` to preserve the careflow metaphor.

## Supporting Commands

Health and validation:

```bash
agent-careflow doctor
agent-careflow dashboard
agent-careflow workspace
agent-careflow repo status
agent-careflow research validate
agent-careflow order status --case <case_id> --order ORD-001
agent-careflow evidence collect --case <case_id> --kind git-status
agent-careflow learning new --case <case_id> --title "Codex prompt hook gap" --source-incident .careflow/cases/<case_id>/incidents/INC-001-example.md
agent-careflow learning promote --case <case_id> --learning LRN-001-codex-prompt-hook-gap.md --target docs/learnings/codex-prompt-hook-gap.md
agent-careflow profile validate business
agent-careflow profile render business --target /tmp/agent-careflow-profile
agent-careflow acceptance profile --profile business --target /tmp/agent-careflow-acceptance
agent-careflow acceptance handoff --target /tmp/agent-careflow-handoff
agent-careflow acceptance install-audit --target-home "$HOME" --tool codex --tool claude
agent-careflow acceptance transcript --live-codex --workdir /tmp/agent-careflow-live-codex
agent-careflow acceptance transcript --live-claude --workdir /tmp/agent-careflow-live-claude
agent-careflow acceptance objective-audit --case <case_id>
agent-careflow acceptance objective-matrix --case <case_id> --profile business --format json
```

Review artifacts:

```bash
# Business/C3 dual review
agent-careflow review status --case <case_id> --profile business --order ORD-001
agent-careflow review request --case <case_id> --tool claude --order ORD-001
agent-careflow review export --case <case_id> --tool claude --order ORD-001 --review-id REVIEW-CLAUDE-ORD-001 --output /tmp/claude-review-request.md
agent-careflow review import --case <case_id> --source /path/to/REVIEW-CLAUDE-ORD-001.review.md --strict
agent-careflow review claude-run --case <case_id> --order ORD-001 --review-id REVIEW-CLAUDE-ORD-001
agent-careflow review new --case <case_id> --tool codex --status pass
agent-careflow review validate --case <case_id> --review REVIEW-CLAUDE-ORD-001.review.md --strict
agent-careflow review require --case <case_id> --tool codex --tool claude --strict

# Private/Codex-only review
agent-careflow review status --case <case_id> --profile private --order ORD-001
agent-careflow review require --case <case_id> --tool codex --strict

# Optional local Claude diagnostics, not a substitute for strict review evidence
agent-careflow review claude-auth --model sonnet
```

Reviews must be saved under `.careflow/cases/<case_id>/reviews/`; chat approval alone is not review evidence.

Use `review status` to see which profile-specific review gates are satisfied and the exact next commands for missing reviews. For business/C3 work, the primary missing-Claude path is export, external review, strict import, then require. Use `review claude-auth --model sonnet` only as an optional local diagnostic; do not treat local Claude auth or CLI remediation as required careflow implementation work unless that scope is explicitly reopened. Use `review request` to create a fixed-header handoff package under `.careflow/cases/<case_id>/reviews/requests/` for Claude, Codex, Cursor, or human reviewers. Use `review export` to write a portable request bundle for another machine, and `review import --strict` to store a returned `.review.md` only after strict validation. Use `review claude-run` on a Claude-authenticated machine to send that contract to Claude, capture stdout as the expected `.review.md` artifact, and validate it in strict mode. Use `--dry-run` to prepare the request without calling Claude. Use `--strict` when validating or requiring reviews for close; strict mode rejects auth-unavailable placeholders and requires findings, evidence, and recommendation sections.

`acceptance objective-audit --profile business|private` checks the original reliability requirements across Superpowers vendoring, native skills, hooks, handoff, dashboard, `.agent`, learning promotion, reviews, install/runtime evidence, and residual incidents. `acceptance objective-matrix --profile business|private` renders the same end state as a requirement-by-requirement traceability matrix with concrete audit checks and evidence paths. The business profile intentionally fails while placeholder Claude review artifacts remain; the private profile requires Codex review only.

Learning capture and promotion:

```bash
agent-careflow learning new --case <case_id> --title "Reusable lesson"
agent-careflow learning promote --case <case_id> --learning LRN-001-reusable-lesson.md --target docs/learnings/reusable-lesson.md
```

`learning promote` writes reader-facing docs with a `source_learning` link and refuses to overwrite an existing target unless `--force` is supplied. The canonical learning remains under `.careflow/cases/<case_id>/learnings/`.

Policy checks:

```bash
agent-careflow policy check-file --case <case_id> --path src/app.py --operation write
agent-careflow policy check-command --command "git reset --hard HEAD"
```

Hook adapters, prompt guard, and adapter conformance:

```bash
printf '{"prompt":"debug patient MRN: ABC123456"}' | agent-careflow hook codex user-prompt-submit
agent-careflow hook codex pre-tool-use < tests/fixtures/hooks/codex_pre_tool_use_bash_danger.json
agent-careflow conformance record --adapter codex --event pre-tool-use --fixture tests/fixtures/hooks/codex_pre_tool_use_bash_danger.json --output .careflow/conformance/codex.jsonl
agent-careflow conformance validate --input .careflow/conformance/codex.jsonl
agent-careflow conformance status --format markdown
```

Guarded Codex entrypoint for non-interactive runs:

```bash
agent-careflow codex exec -- --json "refactor validator tests"
agent-careflow codex exec --probe-output .careflow/cases/<case_id>/evidence/codex-wrapper-preflight.jsonl -- --json "refactor validator tests"
```

`agent-careflow codex exec` runs the same prompt policy used by the Codex `UserPromptSubmit` hook before invoking `codex exec`. This is a wrapper mitigation for runtimes where native `UserPromptSubmit` is not observed; it does not prove the native hook fired.

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
- concrete artifact templates and schema validation
- CASE, PLAN, PLAN.lock, ORDER, RESULT, INCIDENT, REVIEW, CONFERENCE, and DISCHARGE validation surface
- `doctor` one-shot repository health check
- case creation, phase status/advance, order issue/prompt/status, evidence collection, result/review validation, incident creation, and close/discharge validation
- YAML-backed policy engine for phase/file/command gates
- prompt guard for likely secrets and PHI-like identifiers before agent context entry
- Codex, Claude, and Cursor hook adapter entrypoints with fixtures, Stop hooks, and opt-in incident creation on deny
- adapter conformance records using `agent-careflow.adapter_conformance.v1` JSONL
- fixture replay that verifies input normalization, shared policy decisions, and runtime-specific renderer output
- target repository bootstrap profiles that record tool intent while writing only `.careflow/` runtime files
- profile validate/render/install support for rendered tool configs
- isolation planning and guarded worktree/clone execution with patch export
- TAKT comparative analysis plus import/export reports
- focused unit and fixture tests

Runtime compatibility evidence is optional for v0.1. Fixture replay and adapter conformance decide core completion; live Codex, Claude, or Cursor CLI runs can be recorded separately as environment observations. PLAN locks support optional OpenSSH signatures; deployments still need an allowed signers/key-management policy.
