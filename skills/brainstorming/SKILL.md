---
name: brainstorming
description: Use before creative or behavioral work, including new features, components, config changes, workflow changes, or modifying behavior; creates a careflow design/spec before plan or implementation.
---

# Brainstorming Into Careflow Specs

Use this before plan writing or implementation.

## Required Flow

1. Resolve or create the active careflow case.
2. Read relevant repo docs and current code before asking questions.
3. Ask only the missing intent questions needed to define success.
4. Present 2-3 approaches with tradeoffs and a recommendation.
5. Write the approved design/spec under `.careflow/cases/<case_id>/evidence/spec-<topic>.md` or a project-approved docs path.
6. Record open questions and non-goals in the PLAN.
7. Transition to `writing-plans`; do not implement from brainstorming.

## Superpowers Source

Adapted from `third_party/superpowers/skills/brainstorming/SKILL.md`. Agent-careflow changes: outputs go to case evidence and implementation is gated by PLAN/ORDER artifacts.
