---
name: dispatching-parallel-agents
description: Use when two or more independent investigation, implementation, verification, or review tasks can run without shared mutable state.
---

# Dispatching Parallel Careflow Agents

Parallelism is allowed only with explicit boundaries.


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

1. Split independent domains into separate ORDERs.
2. Give each agent one ORDER and one expected RESULT path.
3. Do not let agents share a vague parent chat summary.
4. Merge by reading result artifacts, then run integration verification.
5. Create incidents for conflicting changes or scope drift.

## Superpowers Source

Adapted from `third_party/superpowers/skills/dispatching-parallel-agents/SKILL.md`.
