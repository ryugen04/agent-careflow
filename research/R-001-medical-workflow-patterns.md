# R-001: Medical Workflow Patterns

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

Structured handoff, closed-loop communication, discharge planning, incident reporting, RCA, and multidisciplinary signoff patterns that can inform AI coding-agent workflow control.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| AHRQ TeamSTEPPS SBAR | official docs | 2026-05-20 | A | structured communication |
| AHRQ PSNet Handoffs | official primer | 2026-05-20 | A | transition risk |
| AHRQ IDEAL Discharge Planning | official toolkit | 2026-05-20 | A | discharge checklist framing |
| WHO Incident Reporting and Learning Systems | official publication | 2026-05-20 | A | learning system structure |
| Joint Commission Sentinel Event Policy | official policy | 2026-05-20 | A | serious incident framing |

## Verified facts

Draft. Sources are registered; detailed extraction remains open.

## Implementation implications

Use SBAR-like sections in ORDER/RESULT templates and require discharge evidence before completion.

## Risks / caveats

The project is not a medical system. Medical terms must not imply clinical safety certification.

## Open questions

Should CLI output expose technical aliases for discharge and incident?

## Decisions proposed

Use `case`, `order`, `incident`, and `discharge` in CLI commands with a README disclaimer.

## References to add to PLAN

R-001 should inform ORDER, RESULT, INCIDENT, and DISCHARGE templates.

## Concept boundary

agent-careflow is not about deploying AI agents inside clinical operations. It uses healthcare workflow knowledge as a mature control pattern for software engineers who operate AI coding agents. The transferable elements are structured planning, bounded orders, handoff discipline, incident reporting, evidence requirements, multidisciplinary review, and explicit closure. Clinical diagnosis, patient care, and medical decision support are outside scope.
