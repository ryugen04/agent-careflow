---
name: writing-skills
description: Use when creating, editing, testing, or promoting agent-careflow skills, rules, hooks, or reusable workflow guidance.
---

# Writing Careflow Skills

Skills are tested workflow code.

## Required Flow

1. Define the failure mode the skill should prevent.
2. Add or update trigger-focused frontmatter.
3. Keep SKILL.md procedural and concise.
4. Put long references in `references/` or vendor source.
5. Add acceptance tests that prove the skill is rendered or triggered.
6. Record the failure mode and verification as `.careflow` EVIDENCE or INCIDENT when the skill repairs workflow drift.
7. Prefer automation/hooks over prose for mechanical constraints.

## Superpowers Source

Adapted from `third_party/superpowers/skills/writing-skills/SKILL.md`.
