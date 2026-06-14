---
name: executing-plans
description: Use when a careflow PLAN must be executed inline or in a separate session without full subagent support.
---

# Executing Careflow Plans

Use this when subagents are unavailable or the user explicitly wants inline execution.

## Required Flow

1. Read active PLAN and ORDER before any mutation.
2. Execute only the current ORDER scope.
3. Run the ORDER verification commands.
4. Write the expected RESULT file with changes, verification, blockers, and evidence paths.
5. Stop and ask when the ORDER is ambiguous or verification fails repeatedly.
6. Use `verification-before-completion` before claiming success.

## Superpowers Source

Adapted from `third_party/superpowers/skills/executing-plans/SKILL.md`.
