from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_careflow.artifacts import ValidationError, parse_front_matter_lines


@dataclass(frozen=True)
class Profile:
    name: str
    codex: bool
    claude: bool
    cursor: bool


def load_profile(control_repo: Path, name: str) -> Profile:
    path = control_repo / "profiles" / f"{name}.yaml"
    if not path.exists():
        raise ValidationError(f"profile not found: {name}")
    data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
    tools = {"codex": False, "claude": False, "cursor": False}
    lines = path.read_text(encoding="utf-8").splitlines()
    in_tools = False
    for line in lines:
        if line.strip() == "tools:":
            in_tools = True
            continue
        if in_tools and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            if key in tools:
                tools[key] = value.strip().lower() == "true"
        elif in_tools and line and not line.startswith("  "):
            in_tools = False
    return Profile(name=str(data.get("name") or name), codex=tools["codex"], claude=tools["claude"], cursor=tools["cursor"])
