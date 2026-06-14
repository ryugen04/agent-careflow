---
name: receiving-code-review
description: Use when review feedback arrives from a human, Claude, Codex, GitHub, or subagent before implementing requested changes.
---

# Receiving Careflow Review

Evaluate feedback technically before changing code.

## Required Flow

1. Read every review item.
2. Map each actionable item to PLAN/ORDER scope.
3. Verify whether the feedback is correct for this codebase.
4. Create a corrective ORDER for implementation changes.
5. Record rejected or deferred feedback with technical rationale in review or incident artifacts.
6. Verify after each correction.

## Superpowers Source

Adapted from `third_party/superpowers/skills/receiving-code-review/SKILL.md`.
