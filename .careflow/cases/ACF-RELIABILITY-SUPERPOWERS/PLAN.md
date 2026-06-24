# PLAN: Reliable Claude and Codex careflow orchestration

case_id: ACF-RELIABILITY-SUPERPOWERS
status: active
risk: C3
owner: codex

## Objective

Make agent-careflow reliably activate and persist across Claude and Codex sessions for the user's operating model: business PCs use Claude for research/planning and Codex for implementation, private PCs may use Codex only, business applications may be multi-repository roots with centralized `.codex`/`.claude`/`.agents` configuration, and worktrees may live under `root-xxxx/.worktrees/{branch-name}/{repo}`. The system must force durable case, plan, order, result, evidence, review, incident, and learning artifacts instead of relying on agents remembering prose instructions.

## User Requirements Captured

- Unified Claude and Codex careflow settings, skills, hooks, and artifact locations.
- Plans must be deliberate, visible, and durable under a predictable case directory.
- Intermediate outputs must go under `.agent`/`.agents` or `.careflow`-style agent artifact directories rather than chat-only summaries.
- Troubles and lessons must be persisted so another session can convert them into improvements or docs.
- Claude-to-Codex, Codex-to-Claude, and subagent handoffs must always begin with an explicit plan/order/subplan/result header.
- The order itself is the executable subplan; the assigned agent must read it before action and write the expected result path before claiming completion.
- Superpowers-style enforcement should be implemented substantially, not by adding a few optional rules.
- The target is practical 100 percent improvement for the known failure mode: low activation, missed recognition, and forgetting the workflow mid-session.

## Non-goals

- Do not promise impossible model-internal memory guarantees beyond installed runtime enforcement and transcript-evidenced behavior.
- Do not require Claude subscription/auth to pass on a machine that cannot authenticate; pre-auth hook and skill bootstrap must still be verifiable.
- Do not treat Claude authentication, Claude subscription, or Claude CLI remediation as in-scope unless the user explicitly reopens that scope; use export/import for business Claude review evidence instead.
- Do not replace every upstream Superpowers file verbatim when a native careflow wrapper plus vendored upstream source preserves the behavior and traceability.
- Do not mutate unrelated dotfiles changes that pre-existed this work.

## Acceptance criteria

- `third_party/superpowers` is vendored so upstream philosophy and skill bodies are locally inspectable.
- Native careflow skills exist for intake, brainstorming, plan writing, execution, subagent development, review request/receipt, debugging, TDD, worktrees, parallel dispatch, branch finishing, skill writing, and completion verification.
- Codex SessionStart bootstrap injects `using-agent-careflow` content and the fixed handoff labels.
- Claude and Codex hook configs include SessionStart and enforcement hooks.
- Mutating tools are blocked when no active case/order exists; Stop denies completion when an active case lacks the expected result path.
- Non-mutating conversation and read-only actions can proceed in hybrid mode with warnings rather than deadlocking exploration.
- Root/worktree resolution finds `.careflow` state from nested repositories and `.worktrees/{branch}/{repo}` layouts.
- Profile rendering installs skills for both Codex and Claude, including `.agents/skills`, `.codex`-reachable skills, and `.claude/skills` where relevant.
- Dotfiles install path configures real user Codex with `hooks = true`, hook symlink, and careflow skill symlinks; Claude install/config includes careflow skills and hooks.
- Handoff prompts and ORDER artifacts use the exact fixed labels: `PLAN_FILE`, `ORDER_FILE`, `SUBPLAN_FILE`, `EXPECTED_RESULT_PATH`, `CASE_ID`, `ORDER_ID`, `ASSIGNED_ROLE`, `TARGET_TOOL`.
- A durable `.careflow/INDEX.md` dashboard can be generated and names the active PLAN, ORDER, SUBPLAN, expected RESULT, evidence, incidents, reviews, learnings, and next step.
- A durable `.agent/` operator workspace can be generated as a human-facing alias to the canonical `.careflow` artifacts, including current work, incidents, learnings, and handoff entrypoints.
- Learnings can be created as structured `.careflow/cases/<case_id>/learnings/*.md` artifacts and promoted into docs with traceable source links.
- Business/C3 review workflow can require both Codex and Claude review artifacts before close, while private/Codex-only workflows can require Codex review only.
- An objective audit command can verify the original requirement end-to-end and fail when residual limitations or open incidents remain.
- Acceptance commands verify profile installation, fixed handoff contract, install audit, live Codex transcript behavior, and live Claude pre-auth bootstrap behavior.
- Runtime probe logs are written in `codex.runtime_probe.v1` JSONL and validate with the local validator.
- Tests pass for agent-careflow after these changes.
- The result file for this ORDER records exact evidence paths, verification commands, and residual runtime limitations.

## Risk class

C3. This changes shared agent workflow infrastructure, hook enforcement, user-home installation, and cross-tool handoff behavior. It can affect future Claude and Codex sessions, but does not modify production application code.

## Allowed scope

- `/home/glaucus03/dev/projects/agent-careflow/.careflow/**`
- `/home/glaucus03/dev/projects/agent-careflow/.agent/**`
- `/home/glaucus03/dev/projects/agent-careflow/README.md`
- `/home/glaucus03/dev/projects/agent-careflow/docs/**`
- `/home/glaucus03/dev/projects/agent-careflow/rules/**`
- `/home/glaucus03/dev/projects/agent-careflow/skills/**`
- `/home/glaucus03/dev/projects/agent-careflow/src/**`
- `/home/glaucus03/dev/projects/agent-careflow/tests/**`
- `/home/glaucus03/dev/projects/agent-careflow/third_party/superpowers/**`
- `/home/glaucus03/dev/projects/dotfiles/.gitignore`
- `/home/glaucus03/dev/projects/dotfiles/install.sh`
- `/home/glaucus03/dev/projects/dotfiles/packages/agents/.agents/skills/codex-config-authoring/**`
- `/home/glaucus03/dev/projects/dotfiles/packages/agents/.agents/skills/codex-hooks-authoring/**`
- `/home/glaucus03/dev/projects/dotfiles/packages/claude/.claude/settings.json`
- `/home/glaucus03/dev/projects/dotfiles/packages/codex/.codex/config.toml.template`
- `/home/glaucus03/dev/projects/dotfiles/.codex/artifacts/**`
- `/home/glaucus03/dev/projects/dotfiles/.codex/probes/**`
- User-home install targets only through `install.sh codex` / `install.sh claude` audit or installation commands.

## Phase plan

1. Requirements and source intake: capture user requirements, inspect existing careflow/dotfiles structure, and vendor/analyze Superpowers.
2. Runtime architecture: implement root/worktree context resolution, SessionStart bootstrap, hook behavior, and shared Claude/Codex rendering.
3. Skill and handoff migration: create native careflow skill wrappers, fixed ORDER header rendering, result skeletons, and handoff prompt contract.
4. Distribution integration: update profile rendering and dotfiles install/config paths for Codex and Claude.
5. Acceptance harness: add install, profile, handoff, and live transcript acceptance commands with runtime probe logs.
6. Verification: run tests, install audit, transcript probes, and probe-log validation.
7. Result and close: update RESULT with evidence, residual limitations, and next action if any acceptance remains weak.

## Evidence requirements

- `PYTHONPATH=src pytest -q` output from agent-careflow.
- `agent-careflow acceptance install-audit --target-home "$HOME" --tool codex --tool claude` output.
- `agent-careflow acceptance transcript --live-codex ...` output proving fixed labels were read/emitted.
- `agent-careflow acceptance transcript --live-claude ...` output proving pre-auth SessionStart bootstrap and skill inventory when auth is unavailable.
- Runtime probe JSONL validation output for install audit and live transcript probes.
- `bash -n install.sh` output from dotfiles.
- `agent-careflow dashboard --write` output proving `.careflow/INDEX.md` is generated.
- `agent-careflow workspace --write` output proving `.agent/` is generated.
- `agent-careflow learning new` and `agent-careflow learning promote` outputs proving learning capture and docs promotion.
- `agent-careflow review new` and `agent-careflow review require` outputs proving Codex/Claude review gating.
- `agent-careflow acceptance objective-audit` output proving full-goal audit coverage.
- Result file summarizing changed files and residual limitations.

## Rollback plan

- Revert agent-careflow changes in `skills`, `third_party`, `src`, `rules`, `docs`, `README`, `tests`, and this case if the approach is rejected.
- Revert dotfiles changes in `install.sh`, Codex/Claude config templates, skill authoring docs, and `.gitignore`.
- Re-run `install.sh codex` / `install.sh claude` from the accepted previous state if user-home symlinks must be restored.

## Decisions

- 2026-06-15: The user directed that Claude fixes should be skipped. Business-mode strict Claude review remains required, but local Claude auth/CLI repair is no longer a careflow implementation task. Future sessions should use the fixed export/import review path or run `review claude-run` only from an already authenticated Claude environment.

## Unresolved questions

- Whether Codex `UserPromptSubmit` is expected to fire in every `codex exec` mode. Current runtime evidence shows SessionStart and skill activation can be proven; prompt blocking needs either a different surface probe or an explicit runtime limitation record.
- A real strict Claude review artifact is still missing for business-mode completion; it must be imported from an authenticated Claude environment or produced on a machine where Claude is already authenticated.
