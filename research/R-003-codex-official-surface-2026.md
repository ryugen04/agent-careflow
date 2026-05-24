# R-003: Codex Official Surface 2026

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

Codex CLI, hooks, subagents, skills, AGENTS.md, config, sandboxing, MCP, plugins, and custom commands.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| Codex hooks docs | official docs | 2026-05-20 | A | hook lifecycle |
| Codex subagents docs | official docs | 2026-05-20 | A | delegation model |
| Codex skills docs | official docs | 2026-05-20 | A | reusable workflows |
| Codex advanced config docs | official docs | 2026-05-20 | A | configuration surface |
| Codex sandboxing docs | official docs | 2026-05-20 | A | safety model |

## Verified facts

Draft. Adapter correctness is evaluated through careflow protocol fixtures and conformance records; live CLI behavior is recorded separately as compatibility evidence.

## Implementation implications

Do not embed policy in prompts; hook adapters should call the shared CLI.

## Risks / caveats

Hook payload schema and CLI behavior may differ by installed Codex version, so live observations should be treated as compatibility notes unless they contradict fixture-based adapter contracts.

## Open questions

Which live Codex CLI modes dispatch each hook event reliably in local environments?

## Decisions proposed

Implement adapter renderers against fixture-based conformance first; use live runtime runs as optional compatibility evidence.

## References to add to PLAN

R-003 should inform Codex adapter and hook fixtures.

## Milestone 3 notes

Codex hook adapters are implemented as thin wrappers around the shared CLI policy engine. The implementation follows the official Codex hooks shape for JSON stdin, `PreToolUse` tool fields, and `hookSpecificOutput.permissionDecision` deny responses. `PermissionRequest` remains represented as a Codex-specific renderer and should be validated against local runtime fixtures before production use.

## Adapter conformance 2026-05-21

fixture-observed: `codex --version` reported `codex-cli 0.131.0` during earlier local checks. Local Codex adapter renderer fixtures for `PreToolUse` and `PermissionRequest` produce deny JSON for dangerous command fixtures and now validate as `agent-careflow.adapter_conformance.v1` records. This validates careflow normalization, shared policy decisions, and Codex renderer output without requiring a live Codex session.

## Runtime compatibility note 2026-05-21 live hook attempt

runtime-observed: project-local `.codex/hooks.json` did not produce a capture log during `codex exec` in a temporary repo, even with `--dangerously-bypass-hook-trust`; the command itself completed but the requested Bash command failed under this environment's bubblewrap limitation. A second attempt using a temporary `CODEX_HOME` with user-level `hooks.json` failed with 401 because auth was not present in that temporary home. This is retained as a compatibility observation, not an implementation blocker for adapter conformance. The Codex hooks template was corrected to match the official top-level `{ "hooks": { ... } }` config shape documented by OpenAI.
