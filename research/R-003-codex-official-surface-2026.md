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
