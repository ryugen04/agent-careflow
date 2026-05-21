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
        return dumps(
            {
                "systemMessage": decision.reason,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": decision.reason,
                },
            }
        )
    return "{}"


def render_permission_request(decision: Decision) -> str:
    behavior = "deny" if decision.status == DecisionStatus.DENY else "allow"
    output = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": behavior}}}
    if decision.status == DecisionStatus.DENY:
        output["hookSpecificOutput"]["decision"]["message"] = decision.reason
    return dumps(output)


def render_post_tool_use(decision: Decision) -> str:
    if decision.status == DecisionStatus.DENY:
        return dumps({"decision": "block", "reason": decision.reason})
    if decision.status == DecisionStatus.WARN:
        return dumps(
            {
                "systemMessage": decision.reason,
                "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": decision.reason},
            }
        )
    return "{}"



def render_user_prompt_submit(decision: Decision) -> str:
    if decision.status == DecisionStatus.DENY:
        return dumps({"continue": False, "stopReason": decision.reason, "systemMessage": decision.reason})
    if decision.status == DecisionStatus.WARN:
        return dumps({"systemMessage": decision.reason})
    return "{}"
