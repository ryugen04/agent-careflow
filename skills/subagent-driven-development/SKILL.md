---
name: subagent-driven-development
description: Use when executing an approved careflow PLAN with one or more ORDER artifacts using Codex, Claude, or subagents in the current session.
---

# Subagent-Driven Careflow Development

Execute one ORDER at a time with isolated worker context.


## Careflow Handoff Header

Any delegated worker prompt must start with this fixed header before role, context, task, ownership, or output sections:

```text
PLAN_FILE: <.careflow/cases/<case_id>/PLAN.md>
ORDER_FILE: <.careflow/cases/<case_id>/orders/<order_id>.order.md>
SUBPLAN_FILE: <same path as ORDER_FILE unless a child order exists>
EXPECTED_RESULT_PATH: <.careflow/cases/<case_id>/results/<order_id>.result.md>
CASE_ID: <case_id>
ORDER_ID: <order_id>
ASSIGNED_ROLE: <researcher|implementer|verifier|reviewer|incident-commander>
TARGET_TOOL: <codex|claude|cursor>
```

Do not use the upstream Superpowers `ROLE`/`CONTEXT`/`TASK`/`OWNERSHIP`/`CONSTRAINTS`/`OUTPUT` header as the primary handoff contract. Those sections may appear only after the careflow header.

## Required Flow

1. Read `.careflow/state.json`, the active PLAN, and the active ORDER once at the start.
2. Render the handoff prompt with `agent-careflow order prompt --case <case_id> --order <order_id> --tool <codex|claude>`.
3. Dispatch a fresh worker with the rendered prompt; do not rely on chat history.
4. Require the worker to write `expected_result_path`.
5. Review result against PLAN/ORDER, then inspect code quality and evidence.
6. If review finds issues, issue a corrective ORDER or re-run the worker with the same ORDER context.
7. Advance state only after result and evidence exist.

## Superpowers Source

Adapted from `third_party/superpowers/skills/subagent-driven-development/SKILL.md`. Agent-careflow changes: ORDER is the execution unit and result/evidence files are mandatory.
