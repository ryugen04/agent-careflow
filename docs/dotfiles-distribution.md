# Dotfiles Distribution Design

This design keeps `agent-careflow` as the source of truth and limits dotfiles to install/link behavior.

## Ownership Boundaries

`agent-careflow` owns the actual careflow system:

- lifecycle CLI and validators
- schemas, templates, profiles, and policy YAML
- Codex, Claude, and Cursor adapter configs
- hook entrypoints, adapter renderers, and policy behavior
- documentation for the careflow workflow

Dotfiles owns only user-environment installation:

- installing or linking the `agent-careflow` CLI
- linking global/user-level tool adapter configs to the `agent-careflow` repo
- preserving machine-local config such as trusted project paths outside tracked files
- removing or replacing stale local links when the user asks for deletion

A target repository owns only runtime artifacts under `.careflow/`:

- `.careflow/careflow.yaml`
- `.careflow/state.json`
- `.careflow/cases/<case_id>/...`

Target repositories must not receive `.codex/`, `.claude/`, `.cursor/`, `.agents/`, or `.aidlc/` from careflow bootstrap.

## Distribution Shape

The intended install flow is:

1. Clone or update the `agent-careflow` repository.
2. Install the CLI from that repo, for example editable Python install or a small wrapper on `PATH`.
3. Let dotfiles create user/global links to adapter configs in the `agent-careflow` repo.
4. Bootstrap each target repository with `agent-careflow bootstrap --target <repo> --profile <profile> --careflow-repo <agent-careflow>`.
5. Work inside the target repository using the global adapters, which discover `.careflow/` from the current working tree.

Dotfiles should not copy careflow policy or hook code. If an adapter config needs to change, the change belongs in `agent-careflow/rules/<tool>/...`; dotfiles should only relink the current source.

## Dotfiles Package Migration

Old dotfiles content should be treated as legacy:

- `packages/codex-careflow` should be removed or replaced by a thin installer/link command. It should not contain a doctor, policy, templates, or workflow docs that duplicate `agent-careflow`.
- `packages/codex/.codex/templates/careflow`, `packages/codex/.codex/templates/project-AGENTS.md`, and project bootstrap commands that copy `.codex/` or `.aidlc/` into target repos should be removed.
- `packages/codex/.codex/hooks.json` should not be an independent copy. Dotfiles should link the user's global hook config to `agent-careflow/rules/codex/hooks.json`, or generate a minimal wrapper that delegates to `agent-careflow` without embedding policy.
- `packages/codex/.codex/rules/careflow.rules` should be removed unless it remains a narrow sandbox escalation policy. State-aware careflow decisions belong in hooks and policy YAML, not in `.rules`.
- `packages/agents/.agents/skills` is optional user tooling. It is not required by careflow and should be kept only if it is intentionally maintained as separate Codex authoring help.

## Codex Hook Event Matrix

| Event | Global adapter action | Missing `.careflow/` behavior | Reason |
| --- | --- | --- | --- |
| `UserPromptSubmit` | Run prompt guard through `agent-careflow hook codex user-prompt-submit`. | Still run prompt guard. | Secret and PHI-like prompt checks are useful before repository context is known. |
| `PreToolUse` | Run command/file policy through `agent-careflow hook codex pre-tool-use`. | Warn only. | Read and low-risk work should not be blocked outside bootstrapped repos. |
| `PermissionRequest` | Run escalation policy through `agent-careflow hook codex permission-request`. | Deny by default. | Escalated actions without case context should be explicit and conservative. |
| `PostToolUse` | Capture evidence/checkpoints through `agent-careflow hook codex post-tool-use`. | Warn only. | Post hooks cannot undo tool effects; they should report missing context. |

`SessionStart` stays out of the default Codex adapter until a fixture and adapter contract are defined. `Stop` can be represented by fixture replay and conformance records; live CLI execution is optional runtime compatibility evidence rather than a bootstrap prerequisite.

## Parent Repository and Worktree Model

Careflow treats each working tree as an operational unit. A parent repository and its Git worktrees may share object storage, but they should not share mutable `.careflow` case state by accident.

Recommended model:

- Bootstrap the canonical checkout when it is used directly.
- Bootstrap each Git worktree that will host independent agent work.
- Store `.careflow/` inside the working tree root, not in `.git` or a shared common directory.
- Record worktree metadata in `.careflow/careflow.yaml` when detection is available: repository root, git common dir, whether the checkout is a linked worktree, and optional parent checkout path.
- Keep destructive worktree creation/removal as plan output until cleanup and ownership are explicitly approved.

This model avoids cross-worktree case races while still allowing the case record to describe where the work came from.

## Acceptance Criteria For Dotfiles Adaptation

A completed dotfiles adaptation should satisfy all of these:

- Running the dotfiles install does not copy careflow rules, templates, cases, or policy into target repositories.
- Running target bootstrap writes only `.careflow/` paths.
- User-level Codex hook config delegates to `agent-careflow` and does not contain stale `careflow codex-hook` commands.
- Removing the dotfiles package removes only links or managed blocks it created.
- Machine-specific paths are generated locally, not committed.
- Existing unmanaged `~/.codex/config.toml` content and trust paths are preserved outside managed blocks.
- Worktree use is explicit: each active worktree has its own `.careflow/` if it runs careflow-controlled agent work.

## Adapter Conformance and Runtime Evidence

Dotfiles should install or link adapter configs, but conformance belongs to `agent-careflow`. The expected validation path is `agent-careflow conformance record`, `agent-careflow conformance validate`, and `agent-careflow conformance status`.

Live Codex, Claude, or Cursor runs may be collected as compatibility evidence when credentials and local binaries are available. Those observations should not change the ownership boundary: target repositories still receive only `.careflow/` runtime artifacts, and tool-specific configs remain global/user-level links managed outside the target repo.
