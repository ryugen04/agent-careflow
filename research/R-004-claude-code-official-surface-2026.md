# R-004: Claude Code Official Surface 2026

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

Claude Code settings, hooks, subagents, skills, CLAUDE.md, plugins, MCP, and non-interactive usage.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| Claude Code overview | official docs | 2026-05-20 | A | product surface |
| Claude Code hooks guide | official docs | 2026-05-20 | A | hooks behavior |
| Claude Code hooks reference | official docs | 2026-05-20 | A | event schemas |
| Claude Code subagents | official docs | 2026-05-20 | A | subagent model |
| Claude Code settings | official docs | 2026-05-20 | A | settings scopes |

## Verified facts

Draft. Claude must remain optional for v0.1.

## Implementation implications

Profiles must support operation without Claude artifacts.

## Risks / caveats

Tool availability and settings behavior may differ across environments.

## Open questions

Whether project-level settings should be copied or rendered from central templates.

## Decisions proposed

Keep Claude as an optional adapter outside v0.1 core validation.

## References to add to PLAN

R-004 should inform business and private profiles.
