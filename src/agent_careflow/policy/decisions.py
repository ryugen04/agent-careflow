from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DecisionStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    reason: str

    @property
    def allowed(self) -> bool:
        return self.status in {DecisionStatus.ALLOW, DecisionStatus.WARN}


def allow(reason: str) -> Decision:
    return Decision(DecisionStatus.ALLOW, reason)


def deny(reason: str) -> Decision:
    return Decision(DecisionStatus.DENY, reason)


def warn(reason: str) -> Decision:
    return Decision(DecisionStatus.WARN, reason)
