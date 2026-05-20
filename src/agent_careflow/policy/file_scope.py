from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath

from .decisions import Decision, allow, deny

CODE_PATTERNS = ["src/**", "tests/**"]


def normalize_path(path: str) -> str:
    normalized = PurePosixPath(path).as_posix().lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = normalize_path(path)
    return any(fnmatch(normalized, pattern) or fnmatch(normalized + "/", pattern) for pattern in patterns)


def is_code_path(path: str) -> bool:
    return matches_any(path, CODE_PATTERNS)


def check_allowed_scope(path: str, allowed_scope: list[str]) -> Decision:
    if not allowed_scope:
        return deny("no allowed scope is declared")
    if matches_any(path, allowed_scope):
        return allow("path is inside allowed scope")
    return deny(f"path is outside allowed scope: {normalize_path(path)}")
