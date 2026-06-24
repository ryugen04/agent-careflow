---
name: verification-before-completion
description: Use before claiming work is complete, fixed, implemented, passing, reviewed, or ready to close; requires fresh evidence and careflow result files.
---

# Verification Before Completion

No completion claims without fresh evidence.

## Required Gate

1. Identify the exact claim you are about to make.
2. Identify the command or artifact proving it.
3. Run the command or inspect the artifact now.
4. Write or update `expected_result_path` with evidence paths and command output summary.
5. If evidence is missing or weak, report actual status instead of claiming completion.
6. Close only after `agent-careflow order status` and required validation pass.

## Superpowers Source

Adapted from `third_party/superpowers/skills/verification-before-completion/SKILL.md`. Agent-careflow changes: evidence must be tied to RESULT/EVIDENCE artifacts.
