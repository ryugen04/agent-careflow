from __future__ import annotations

from agent_careflow.policy.decisions import Decision, DecisionStatus

from .common import dumps


def render_pre_tool_use(decision: Decision) -> str:
    if decision.status == DecisionStatus.DENY:
        return dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": decision.reason,
                }
            }
        )
    if decision.status == DecisionStatus.WARN:
        return dumps({"systemMessage": decision.reason})
    return "{}"


def render_post_tool_use(decision: Decision) -> str:
    if decision.status == DecisionStatus.DENY:
        return dumps({"decision": "block", "reason": decision.reason})
    if decision.status == DecisionStatus.WARN:
        return dumps({"systemMessage": decision.reason})
    return "{}"
