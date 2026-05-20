# R-005: Cursor Composer and Agent Surface 2026

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

Cursor Composer, Plan Mode, Worktrees, Subagents, Agent Skills, Rules, AGENTS.md, hooks, CLI, and Cloud Agents.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| Cursor Plan Mode docs | official docs | 2026-05-20 | A | planning flow |
| Cursor Worktrees docs | official docs | 2026-05-20 | A | isolation surface |
| Cursor Subagents docs | official docs | 2026-05-20 | A | subagent surface |
| Cursor Agent Skills docs | official docs | 2026-05-20 | A | reusable instructions |
| Cursor Hooks docs | official docs | 2026-05-20 | A | hooks surface |
| Cursor Composer 2.5 blog | official blog | 2026-05-20 | A | current product signal |

## Verified facts

Draft. Cursor policy enforcement assumptions must be verified before adapter work.

## Implementation implications

Use the CLI as the enforcement authority even when Cursor is the orchestrator.

## Risks / caveats

Community reports may reveal behavior gaps but cannot justify policy alone.

## Open questions

Whether Cursor hooks can block with the same confidence as Codex or Claude hooks.

## Decisions proposed

Treat Cursor as a useful orchestrator but not the sole policy authority.

## References to add to PLAN

R-005 should inform Cursor adapter design.
