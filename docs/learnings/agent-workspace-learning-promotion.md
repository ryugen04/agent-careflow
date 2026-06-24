# Agent workspace learning promotion

source_learning: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/learnings/LRN-001-agent-workspace-learning-promotion.md
case_id: ACF-RELIABILITY-SUPERPOWERS

## Summary

This document was promoted from an agent-careflow learning artifact. Edit this docs page for readers, but keep the source learning linked for traceability.

## Source Learning

```markdown
# LEARNING: LRN-001-agent-workspace-learning-promotion

learning_id: LRN-001-agent-workspace-learning-promotion
case_id: ACF-RELIABILITY-SUPERPOWERS
title: Agent workspace learning promotion
source_incident: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/incidents/INC-001-codex-exec-user-prompt-submit-not-observed.md
status: promoted
created_at: 2026-06-14T23:29:06+09:00
promoted_to: docs/learnings/agent-workspace-learning-promotion.md

## Observation

Manual learning files are easy to forget. A later Claude or Codex session needs a deterministic command to capture lessons and a safe promotion path into reader-facing docs.

## Implication

Use `agent-careflow learning new` for capture and `agent-careflow learning promote` when the lesson should become docs. Keep `.careflow` as canonical state and treat docs as derived outputs.

## Follow-up

Regenerate `.careflow/INDEX.md` and `.agent/` after creating or promoting learnings so future sessions see the new artifact.
```
