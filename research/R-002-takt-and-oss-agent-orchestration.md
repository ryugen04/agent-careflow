# R-002: TAKT and OSS Agent Orchestration

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

TAKT, related SDD/workflow approaches, worktree isolation patterns, PR automation, and audit trail designs.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| nrslib/takt README | official repository | 2026-05-20 | B | workflow comparison |
| TAKT Japanese docs | official repository docs | 2026-05-20 | B | concepts and operation |
| TAKT configuration docs | official repository docs | 2026-05-20 | B | config structure |
| TAKT export-codex issue | maintainer issue | 2026-05-20 | B | interop signal |
| Zenn TAKT introduction | practitioner blog | 2026-05-20 | C | usage signal |

## Verified facts

Draft. Source list is initialized; detailed comparison remains open.

## Implementation implications

Keep v0.x independent from TAKT and focus on artifact protocol plus validation.

## Risks / caveats

Duplicating workflow-engine features too early may increase scope.

## Open questions

Whether TAKT import/export should exist before v1.0.

## Decisions proposed

Treat TAKT as a comparison and future interop target, not as a v0.x dependency.

## References to add to PLAN

R-002 should inform adapter and isolation design.

## Milestone 7 notes

The v0.x default isolation strategy is `git worktree`. `git clone --shared` and temporary clone strategies are represented as plans but are not executed by the CLI in this milestone. Shared/temp clone cleanup is explicitly marked destructive and must be approved before execution.
