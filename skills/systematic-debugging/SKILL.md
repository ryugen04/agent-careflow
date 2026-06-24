---
name: systematic-debugging
description: Use when encountering bugs, test failures, hook failures, unexpected behavior, flaky tests, or workflow drift before proposing fixes.
---

# Systematic Careflow Debugging

Do not patch symptoms before understanding cause.

## Required Flow

1. Capture the symptom as evidence.
2. Reproduce or isolate the failing condition.
3. Trace from symptom to root cause with the smallest focused checks.
4. Record failed hypotheses when useful.
5. Fix the root cause inside an ORDER scope.
6. Add regression evidence.
7. If the failure indicates workflow drift, create an INCIDENT and learning artifact.

## Superpowers Source

Adapted from `third_party/superpowers/skills/systematic-debugging/SKILL.md`.
