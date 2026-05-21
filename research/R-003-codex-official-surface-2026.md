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

Draft. Local runtime probing is still required before hook adapters are implemented.

## Implementation implications

Do not embed policy in prompts; hook adapters should call the shared CLI.

## Risks / caveats

Hook payload schema and CLI behavior may differ by installed Codex version.

## Open questions

Which hook events can reliably block unsafe commands in the local runtime?

## Decisions proposed

Defer adapter implementation until fixture capture and runtime probing.

## References to add to PLAN

R-003 should inform Codex adapter and hook fixtures.

## Milestone 3 notes

Codex hook adapters are implemented as thin wrappers around the shared CLI policy engine. The implementation follows the official Codex hooks shape for JSON stdin, `PreToolUse` tool fields, and `hookSpecificOutput.permissionDecision` deny responses. `PermissionRequest` remains represented as a Codex-specific renderer and should be validated against local runtime fixtures before production use.

## Runtime probe 2026-05-21

runtime-observed: `codex --version` reports `codex-cli 0.131.0`. `codex --help` and `codex --profile codex-config-edit --help` complete successfully. Local adapter renderer probes for Codex `PreToolUse` and `PermissionRequest` produce deny JSON for dangerous command fixtures, and the probe log validates as `codex.runtime_probe.v1`. This does not yet prove live Codex hook event payload shape from an interactive session; that remains a separate fixture-capture task.

## Runtime probe 2026-05-21 live hook attempt

runtime-observed: project-local `.codex/hooks.json` did not produce a capture log during `codex exec` in a temporary repo, even with `--dangerously-bypass-hook-trust`; the command itself completed but the requested Bash command failed under this environment's bubblewrap limitation. A second attempt using a temporary `CODEX_HOME` with user-level `hooks.json` failed with 401 because auth was not present in that temporary home. The live payload capture remains inconclusive. The Codex hooks template was corrected to match the official top-level `{ "hooks": { ... } }` config shape documented by OpenAI.
