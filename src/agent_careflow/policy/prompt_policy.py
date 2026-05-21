from __future__ import annotations

import re
from typing import Any

from .decisions import Decision, allow, deny

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "possible API key in prompt"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "possible AWS access key in prompt"),
    (re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"), "possible secret assignment in prompt"),
]

PHI_SIGNAL_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "possible SSN-like identifier in prompt"),
    (re.compile(r"(?i)\b(MRN|medical record number)\s*[:#]?\s*[A-Z0-9-]{6,}\b"), "possible medical record identifier in prompt"),
]


def extract_prompt_text(payload: dict[str, Any]) -> str:
    for key in ("prompt", "user_prompt", "message", "text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    nested = payload.get("tool_input")
    if isinstance(nested, dict):
        return extract_prompt_text(nested)
    return ""


def check_prompt_text(text: str) -> Decision:
    for pattern, reason in [*SECRET_PATTERNS, *PHI_SIGNAL_PATTERNS]:
        if pattern.search(text):
            return deny(reason)
    return allow("prompt allowed")
