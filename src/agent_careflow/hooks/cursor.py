from __future__ import annotations

from agent_careflow.policy.decisions import Decision, DecisionStatus

from .common import dumps


def render_pre_tool_use(decision: Decision) -> str:
    if decision.status == DecisionStatus.DENY:
        return dumps({"decision": "block", "reason": decision.reason})
    if decision.status == DecisionStatus.WARN:
        return dumps({"decision": "warn", "reason": decision.reason})
    return dumps({"decision": "allow", "reason": decision.reason})


def render_post_tool_use(decision: Decision) -> str:
    return render_pre_tool_use(decision)
