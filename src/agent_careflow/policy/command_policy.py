from __future__ import annotations

import re
import shlex

from .decisions import Decision, allow, deny

FORBIDDEN_PATTERNS = [
    (re.compile(r"(^|&&|;)\s*git\s+push\b.*\s(-f|--force(?:=|\s|$)|--force-with-lease(?:=|\s|$)|--mirror(?:\s|$))"), "force Git push is blocked by policy"),
    (re.compile(r"(^|&&|;)\s*git\s+reset\s+--hard(\s|$)"), "git reset --hard is blocked by policy"),
    (re.compile(r"(^|&&|;)\s*rm\s+(-[^\s]*r[^\s]*f|-rf|-fr)(\s|$)"), "rm -rf is blocked by policy"),
    (re.compile(r"curl\b.*\|\s*(sh|bash)\b"), "curl piped to a shell is blocked by policy"),
    (re.compile(r"(^|&&|;)\s*npm\s+install(\s|$)"), "npm install is blocked by policy"),
    (re.compile(r"(^|&&|;)\s*pnpm\s+add(\s|$)"), "pnpm add is blocked by policy"),
    (re.compile(r"(^|&&|;)\s*pip\s+install(\s|$)"), "pip install is blocked by policy"),
    (re.compile(r"(^|&&|;)\s*chmod\s+-R\s+777(\s|$)"), "chmod -R 777 is blocked by policy"),
]


def normalize_command(command: str) -> str:
    try:
        return " ".join(shlex.split(command))
    except ValueError:
        return " ".join(command.split())


def check_command(command: str, forbidden_commands: list[dict[str, str]] | None = None) -> Decision:
    normalized = normalize_command(command)
    if forbidden_commands is not None:
        for rule in forbidden_commands:
            match = rule.get("match", "")
            reason = rule.get("reason") or f"{match} is blocked by policy"
            if match and match in normalized:
                return deny(reason)
        return allow("command allowed")
    for pattern, reason in FORBIDDEN_PATTERNS:
        if pattern.search(normalized):
            return deny(reason)
    return allow("command allowed")
