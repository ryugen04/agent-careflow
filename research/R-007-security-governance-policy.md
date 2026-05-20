# R-007: Security Governance Policy

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

Sandboxing, approvals, secrets, network access, package installation, destructive commands, symlink risk, MCP allowlists, central policy tampering, and target bootstrap safety.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| Codex sandboxing docs | official docs | 2026-05-20 | A | sandbox and approval model |
| Claude Code hooks docs | official docs | 2026-05-20 | A | hook execution model |
| Cursor hooks docs | official docs | 2026-05-20 | A | hook surface |
| OWASP secure coding guidance | official standard body | 2026-05-20 | A | general security reference |

## Verified facts

Draft. Threat model and hook runtime behavior require deeper review.

## Implementation implications

Policy decisions should be centralized, auditable, and testable.

## Risks / caveats

Hooks often execute with local user permissions; hook input must be validated.

## Open questions

Whether plan locks need signatures or hashes are sufficient for v0.x.

## Decisions proposed

Implement hashes first; defer signatures until threat model is accepted.

## References to add to PLAN

R-007 should inform policy engine and hook adapter design.
