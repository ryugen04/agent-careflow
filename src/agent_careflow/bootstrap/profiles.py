from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, replace
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

TOOLS = ("codex", "claude", "cursor")


def _skill_sources(control_repo: Path) -> list[Path]:
    skills_source = control_repo / "skills"
    if not skills_source.exists():
        return []
    return sorted(skills_source.glob("*/SKILL.md"))


def _copy_skill(source: Path, destination_root: Path, rendered: list[Path]) -> None:
    destination = destination_root / source.parent.name / "SKILL.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    rendered.append(destination)


def validate_profile(control_repo: Path, name: str) -> Profile:
    profile = load_profile(control_repo, name)
    if profile.name != name:
        raise ValidationError(f"profile name mismatch: expected {name}, got {profile.name}")
    if not any([profile.codex, profile.claude, profile.cursor]):
        raise ValidationError(f"profile enables no tools: {name}")
    return profile


def apply_tool_overrides(profile: Profile, *, enable: list[str] | None = None, disable: list[str] | None = None) -> Profile:
    values = {"codex": profile.codex, "claude": profile.claude, "cursor": profile.cursor}
    for tool in enable or []:
        if tool not in values:
            raise ValidationError(f"unknown tool: {tool}")
        values[tool] = True
    for tool in disable or []:
        if tool not in values:
            raise ValidationError(f"unknown tool: {tool}")
        values[tool] = False
    if not any(values.values()):
        raise ValidationError("profile enables no tools after overrides")
    return replace(profile, **values)


def render_profile(control_repo: Path, profile: Profile, target: Path) -> list[Path]:
    control_repo = control_repo.resolve()
    target = target.resolve()
    rendered: list[Path] = []
    mappings = [
        (profile.codex, control_repo / "rules" / "codex" / "hooks.json", target / "codex" / "hooks.json"),
        (profile.claude, control_repo / "rules" / "claude" / "settings.json", target / "claude" / "settings.json"),
        (profile.cursor, control_repo / "rules" / "cursor" / "hooks.json", target / "cursor" / "hooks.json"),
    ]
    for enabled, source, destination in mappings:
        if not enabled:
            continue
        if not source.exists():
            raise ValidationError(f"profile source config missing: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        rendered.append(destination)
    skill_roots = [target / "skills"]
    if profile.codex:
        skill_roots.append(target / ".agents" / "skills")
    if profile.claude:
        skill_roots.append(target / ".claude" / "skills")
    for source in _skill_sources(control_repo):
        for skill_root in skill_roots:
            _copy_skill(source, skill_root, rendered)

    manifest = target / "profile.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "profile": profile.name,
                "tools": {"codex": profile.codex, "claude": profile.claude, "cursor": profile.cursor},
                "skill_roots": [
                    "skills",
                    *( [".agents/skills"] if profile.codex else [] ),
                    *( [".claude/skills"] if profile.claude else [] ),
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    rendered.append(manifest)
    return rendered


def install_profile(control_repo: Path, profile_name: str, target: Path, *, enable: list[str] | None = None, disable: list[str] | None = None) -> list[Path]:
    profile = apply_tool_overrides(validate_profile(control_repo, profile_name), enable=enable, disable=disable)
    install_root = target / profile.name
    return render_profile(control_repo, profile, install_root)
