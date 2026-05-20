from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_at_indent: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if text.startswith("- "):
            item = text[2:].strip()
            if not isinstance(parent, list):
                raise ValueError(f"list item without list parent in {path}: {raw}")
            if ":" in item and not item.startswith('"'):
                key, value = item.split(":", 1)
                obj = {key.strip(): parse_scalar(value)}
                parent.append(obj)
                stack.append((indent, obj))
            else:
                parent.append(parse_scalar(item))
            continue
        key, value = text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"mapping item without mapping parent in {path}: {raw}")
        if value:
            parent[key] = parse_scalar(value)
            continue
        # Look ahead by syntax convention: keys ending in allow_write/forbidden_commands use lists.
        container: Any = [] if key in {"allow_write", "forbidden_commands"} else {}
        parent[key] = container
        last_key_at_indent[indent] = key
        stack.append((indent, container))
    return root


def load_policy_config(root: Path) -> dict[str, Any]:
    config: dict[str, Any] = {}
    global_dir = root / "rules" / "global"
    for filename in ("command-policy.yaml", "phase-policy.yaml"):
        path = global_dir / filename
        if path.exists():
            config.update(parse_simple_yaml(path))
    return config
