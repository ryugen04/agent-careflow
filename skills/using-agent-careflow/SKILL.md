---
name: using-agent-careflow
description: Use when starting any coding-agent conversation, before any response or action, to enforce agent-careflow case, plan, order, result, evidence, review, incident, and handoff discipline across Claude and Codex.
---

# Using Agent Careflow

<SUBAGENT-STOP>
If you were dispatched as a subagent with a concrete `order_path`, follow that order and do not restart intake.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
You are operating inside agent-careflow.

Before implementation, mutation, review approval, or completion claims, you must know the active Case, PLAN, ORDER, expected RESULT path, and required EVIDENCE. If they are missing, create or request them before continuing.

If there is even a small chance a careflow skill or workflow applies, use it before answering or acting. Instructions and artifacts beat memory.
</EXTREMELY-IMPORTANT>

## Required Artifact Chain

Every non-trivial task moves through:

1. Case: `.careflow/cases/<case_id>/CASE.yaml`
2. Plan: `.careflow/cases/<case_id>/PLAN.md`
3. Order: `.careflow/cases/<case_id>/orders/*.order.md`
4. Result: `.careflow/cases/<case_id>/results/*.result.md`
5. Evidence: `.careflow/cases/<case_id>/evidence/`
6. Review or Incident when required
7. Discharge/close validation

## Handoff Rule

Every Claude-to-Codex, Codex-to-Claude, or subagent handoff must start with this fixed header, before any explanatory prose:

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

The ORDER is the subplan for the assigned agent. Preserve these exact labels when handing work across Claude, Codex, Cursor, or a subagent. Read the PLAN and ORDER before acting. Do not treat an order as complete until the expected RESULT file exists.

## Hybrid Gate

Conversation, clarification, and read-only research may proceed with warnings when context is missing. Implementation writes, scoped file changes, escalation requests, and completion claims must be blocked until careflow context exists, unless the user explicitly instructs a one-turn bypass.

## Red Flags

Stop and repair the workflow if you catch yourself thinking:

- "This is small enough to skip the case."
- "I remember the plan."
- "The other agent probably handled the order."
- "I can claim this is done before writing result/evidence."
- "I can hand this off with just a chat summary."

## Commands

- Create a case: `agent-careflow case new --title "..." --risk C1`
- Lock a plan: `agent-careflow hash plan --case <case_id> --write-lock`
- Issue an order: `agent-careflow order issue --case <case_id> --order ORD-001 --role implementer`
- Render a handoff prompt: `agent-careflow order prompt --case <case_id> --order ORD-001 --tool codex`
- Check order completion: `agent-careflow order status --case <case_id> --order ORD-001`
- Validate close: `agent-careflow close validate --case <case_id>`
